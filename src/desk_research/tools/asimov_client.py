from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

import requests
from dotenv import load_dotenv


def _load_env() -> None:
    # Carrega variáveis padrão e depois .env.asimov (sem sobrescrever o que já está no ambiente)
    load_dotenv(override=False)
    load_dotenv(".env.asimov", override=False)


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _clip_text(s: str | None, max_len: int = 2000) -> str | None:
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= max_len else s[:max_len] + "..."


_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


def _is_uuid(x: str) -> bool:
    return bool(_UUID_RE.match((x or "").strip()))


def _as_bool(x: str | None, default: bool = False) -> bool:
    if x is None:
        return default
    return str(x).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _clamp_int(v: Any, *, lo: int, hi: int) -> int:
    try:
        i = int(v)
    except Exception:
        i = lo
    if i < lo:
        return lo
    if i > hi:
        return hi
    return i


@dataclass(frozen=True)
class AsimovEnv:
    api_base: str
    api_key: str
    dataset: str  # preferencialmente NOME
    dataset_model: str
    enabled: bool


class AsimovClient:
    """
    Compatível com ASIMOV_API_BASE em dois formatos:

    A) base = https://.../asimov_stg_saz
       endpoints: /api/application/...

    B) base = https://.../asimov_stg_saz/api
       endpoints: /application/...

    Regras importantes:
      - Datasets:
          GET  {base}/(api/)application/datasets
          GET  {base}/(api/)application/datasets/{uuid}  -> exige UUID (nome dá 422)
          POST {base}/(api/)application/datasets

      - Snippets:
          POST {base}/(api/)application/snippets
            payload: {"dataset": "<DATASET_NAME>", "content_list": [{"key": "...", "content": "..."}]}
            Observação: para /snippets, "dataset" precisa ser NOME (string). UUID costuma falhar com 400.

          GET  {base}/(api/)application/snippets?limit=&offset=
            Observação: alguns ambientes retornam lista GLOBAL (sem filtrar dataset).
            Este client suporta filtro opcional client-side e tenta filtro server-side por query param.

          GET    {base}/(api/)application/snippets/{uuid}
          DELETE {base}/(api/)application/snippets/{uuid}

    Limites conhecidos:
      - listagem de snippets: limit <= 30 (backend retorna 422 se exceder)
    """

    MAX_SNIPPETS_LIMIT = 30

    def __init__(self, env: AsimovEnv) -> None:
        raw = (env.api_base or "").strip()
        self.base_url = raw.rstrip("/")
        self.api_key = (env.api_key or "").strip()
        self.dataset = (env.dataset or "").strip()
        self.dataset_model = (env.dataset_model or "").strip()
        self.enabled = env.enabled

        # Se base termina com /api, NÃO prefixa "api" nos paths; caso contrário prefixa.
        self._api_prefix = "" if self.base_url.endswith("/api") else "api"

        # caches
        self._dataset_uuid_cache: dict[str, str] = {}  # name -> uuid
        self._dataset_name_cache: dict[str, str] = {}  # uuid -> name

    @classmethod
    def from_env(cls) -> "AsimovClient":
        _load_env()
        api_base = (os.getenv("ASIMOV_API_BASE") or "").strip()
        api_key = (os.getenv("ASIMOV_API_KEY") or "").strip()
        dataset = (os.getenv("ASIMOV_DATASET") or "").strip()
        dataset_model = (os.getenv("ASIMOV_DATASET_MODEL") or "openai/text-embedding-ada-002").strip()
        enabled = _as_bool(os.getenv("ASIMOV_ENABLED"), default=False)
        return cls(AsimovEnv(api_base, api_key, dataset, dataset_model, enabled))

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    # -------- headers --------
    def _headers_json(self) -> dict[str, str]:
        k = self.api_key
        return {
            "Authorization": f"Bearer {k}",
            "Ocp-Apim-Subscription-Key": k,
            "x-api-key": k,
            "Content-Type": "application/json",
        }

    # -------- url / request --------
    def _path(self, suffix: str) -> str:
        suffix = suffix.lstrip("/")
        if self._api_prefix:
            return f"{self._api_prefix}/{suffix}"
        return suffix

    def _url(self, suffix: str) -> str:
        return f"{self.base_url}/{self._path(suffix)}"

    def _request(
        self,
        method: str,
        suffix: str,
        *,
        headers: dict[str, str],
        timeout: int,
        json: Any = None,
        params: Any = None,
    ) -> dict[str, Any]:
        url = self._url(suffix)
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json,
            params=params,
            timeout=timeout,
        )
        return {
            "ok": resp.status_code in (200, 201),
            "status": resp.status_code,
            "url": url,
            "text": _clip_text(resp.text),
            "json": _safe_json(resp),
        }

    # -------------------- Datasets --------------------
    def list_datasets(self) -> dict[str, Any]:
        return self._request("GET", "application/datasets", headers=self._headers_json(), timeout=60)

    def create_dataset(self, name: str, model: Optional[str] = None) -> dict[str, Any]:
        payload = {"name": name, "model": model or self.dataset_model}
        return self._request("POST", "application/datasets", headers=self._headers_json(), timeout=60, json=payload)

    def check_dataset(self, dataset: Optional[str] = None) -> dict[str, Any]:
        ident = self._resolve_dataset_ident(dataset)
        if not ident.get("ok"):
            return ident

        uuid = ident["dataset_uuid"]
        out = self._request("GET", f"application/datasets/{uuid}", headers=self._headers_json(), timeout=60)
        out["dataset_uuid"] = uuid
        out["dataset_name"] = ident.get("dataset_name")
        return out

    def ensure_dataset(self, dataset: Optional[str] = None) -> dict[str, Any]:
        ds = (dataset or self.dataset or "").strip()
        if not ds:
            return {"ok": False, "reason": "ASIMOV_DATASET_missing"}

        # UUID -> apenas valida
        if _is_uuid(ds):
            chk = self.check_dataset(ds)
            if chk.get("ok"):
                return {
                    "ok": True,
                    "created": False,
                    "dataset_uuid": ds,
                    "dataset_name": (chk.get("json") or {}).get("name"),
                }
            return {"ok": False, "reason": "ensure_dataset_uuid_check_failed", "detail": chk}

        # name -> resolve; se não existir, cria
        ident = self._resolve_dataset_ident(ds)
        if ident.get("ok"):
            return {"ok": True, "created": False, **ident}

        if ident.get("reason") != "dataset_name_not_found":
            return {"ok": False, "reason": "ensure_dataset_failed_precheck", "detail": ident}

        created = self.create_dataset(ds, model=self.dataset_model)
        if not created.get("ok"):
            return {"ok": False, "reason": "create_dataset_failed", "detail": created}

        ident2 = self._resolve_dataset_ident(ds)
        if ident2.get("ok"):
            return {"ok": True, "created": True, "create_response": created, **ident2}

        return {"ok": True, "created": True, "create_response": created, "warning": "created_but_not_resolved"}

    def _resolve_dataset_ident(self, dataset: Optional[str] = None) -> dict[str, Any]:
        ds = (dataset or self.dataset or "").strip()
        if not ds:
            return {"ok": False, "reason": "ASIMOV_DATASET_missing"}

        # UUID -> resolve nome via GET
        if _is_uuid(ds):
            if ds in self._dataset_name_cache:
                return {"ok": True, "dataset_uuid": ds, "dataset_name": self._dataset_name_cache[ds]}

            out = self._request("GET", f"application/datasets/{ds}", headers=self._headers_json(), timeout=60)
            if not out.get("ok"):
                return {"ok": False, "reason": "dataset_uuid_not_found", "detail": out}

            name = ((out.get("json") or {}).get("name") or "").strip() or None
            if name:
                self._dataset_name_cache[ds] = name
                self._dataset_uuid_cache[name] = ds
            return {"ok": True, "dataset_uuid": ds, "dataset_name": name}

        # NAME -> uuid via list
        if ds in self._dataset_uuid_cache:
            return {"ok": True, "dataset_uuid": self._dataset_uuid_cache[ds], "dataset_name": ds}

        listed = self.list_datasets()
        if not listed.get("ok"):
            return {"ok": False, "reason": "list_datasets_failed", "detail": listed}

        items = (listed.get("json") or {}).get("items") or []
        for it in items:
            if (it.get("name") or "").strip() == ds:
                uuid = (it.get("uuid") or "").strip()
                if uuid:
                    self._dataset_uuid_cache[ds] = uuid
                    self._dataset_name_cache[uuid] = ds
                    return {"ok": True, "dataset_uuid": uuid, "dataset_name": ds}

        return {"ok": False, "reason": "dataset_name_not_found", "dataset_name": ds}

    # -------------------- Snippets --------------------
    def upload_snippets(self, snippets: list[dict[str, Any]], dataset: Optional[str] = None) -> dict[str, Any]:
        """
        Envia snippets para o Asimov.
        Nota: o campo "dataset" do payload precisa ser o NOME do dataset.
        """
        if not self.enabled:
            return {"ok": False, "skipped": True, "reason": "ASIMOV_ENABLED=false"}
        if not self.is_configured():
            return {"ok": False, "skipped": True, "reason": "asimov_not_configured"}

        ds_raw = (dataset or self.dataset or "").strip()
        if not ds_raw:
            return {"ok": False, "reason": "ASIMOV_DATASET_missing"}

        ident = self._resolve_dataset_ident(ds_raw)
        if not ident.get("ok"):
            return {"ok": False, "reason": "dataset_resolve_failed", "detail": ident}

        dataset_name = (ident.get("dataset_name") or "").strip()
        if not dataset_name:
            return {"ok": False, "reason": "dataset_name_required_for_snippets", "detail": ident}

        payload = {"dataset": dataset_name, "content_list": snippets}
        out = self._request("POST", "application/snippets", headers=self._headers_json(), timeout=300, json=payload)
        out["dataset_name"] = dataset_name
        out["dataset_uuid"] = ident.get("dataset_uuid")
        out["sent_items"] = len(snippets)
        return out

    def list_snippets(
        self,
        *,
        limit: int = 30,
        offset: int = 0,
        dataset: Optional[str] = None,
        key_prefix: Optional[str] = None,
        client_side_filter: bool = True,
    ) -> dict[str, Any]:
        """
        Lista snippets.

        - Backend impõe limit<=30. Este método faz clamp automático.
        - Tenta passar dataset (nome) como query param se fornecido.
        - Se a API não filtrar, aplica filtro client-side (dataset/key_prefix) com base no JSON retornado.
        """
        if not self.enabled:
            return {"ok": False, "skipped": True, "reason": "ASIMOV_ENABLED=false"}
        if not self.is_configured():
            return {"ok": False, "skipped": True, "reason": "asimov_not_configured"}

        limit_i = _clamp_int(limit, lo=1, hi=self.MAX_SNIPPETS_LIMIT)
        offset_i = _clamp_int(offset, lo=0, hi=10_000_000)

        ds_name: Optional[str] = None
        if dataset:
            ident = self._resolve_dataset_ident(dataset)
            if ident.get("ok"):
                ds_name = (ident.get("dataset_name") or "").strip() or None
            else:
                ds_name = None

        params: dict[str, Any] = {"limit": limit_i, "offset": offset_i}
        if ds_name:
            # se o backend suportar, ele filtra; se não suportar, ele ignora
            params["dataset"] = ds_name

        out = self._request("GET", "application/snippets", headers=self._headers_json(), timeout=60, params=params)

        if not out.get("ok") or not client_side_filter:
            out["requested_dataset"] = ds_name
            out["requested_key_prefix"] = key_prefix
            out["limit_used"] = limit_i
            out["offset_used"] = offset_i
            return out

        j = out.get("json") or {}
        items = j.get("items") or []

        # filtro client-side por dataset / key_prefix
        filtered = items
        if ds_name:

            def _ds_of(it: dict[str, Any]) -> str:
                ds = it.get("dataset") or {}
                return (ds.get("name") or "").strip()

            filtered = [it for it in filtered if _ds_of(it) == ds_name]

        if key_prefix:
            kp = str(key_prefix)
            filtered = [it for it in filtered if str(it.get("key") or "").startswith(kp)]

        # substitui JSON retornado por versão filtrada (mantendo count original em campos auxiliares)
        out["requested_dataset"] = ds_name
        out["requested_key_prefix"] = key_prefix
        out["limit_used"] = limit_i
        out["offset_used"] = offset_i
        out["json_unfiltered_count"] = j.get("count")
        out["json_unfiltered_items_returned"] = len(items)
        out["json"] = {"count": len(filtered), "items": filtered}
        out["text"] = None  # evita log gigante; o JSON filtrado já é suficiente
        return out

    def find_snippets(
        self,
        *,
        dataset: Optional[str] = None,
        key_prefix: Optional[str] = None,
        max_items: int = 50,
        page_size: int = 30,
        max_pages: int = 50,
    ) -> dict[str, Any]:
        """
        Pagina no endpoint de snippets para encontrar itens do seu dataset/key_prefix.
        Útil quando o endpoint lista geral.

        page_size é clampado para <=30 automaticamente para evitar 422.
        """
        max_items_i = _clamp_int(max_items, lo=1, hi=10_000)
        page_size_i = _clamp_int(page_size, lo=1, hi=self.MAX_SNIPPETS_LIMIT)
        max_pages_i = _clamp_int(max_pages, lo=1, hi=10_000)

        found: list[dict[str, Any]] = []
        offset = 0
        scanned = 0
        last_resp: dict[str, Any] | None = None

        while scanned < max_pages_i and len(found) < max_items_i:
            resp = self.list_snippets(
                limit=page_size_i,
                offset=int(offset),
                dataset=dataset,
                key_prefix=key_prefix,
                client_side_filter=True,
            )
            last_resp = resp
            if not resp.get("ok"):
                return {"ok": False, "reason": "find_snippets_failed", "detail": resp}

            items = (resp.get("json") or {}).get("items") or []
            if not items:
                break

            found.extend(items)
            if len(found) >= max_items_i:
                found = found[:max_items_i]
                scanned += 1
                offset += page_size_i
                break

            scanned += 1
            offset += page_size_i

        return {
            "ok": True,
            "items": found,
            "count": len(found),
            "scanned_pages": scanned,
            "next_offset": offset,
            "page_size_used": page_size_i,
            "requested_dataset": (last_resp or {}).get("requested_dataset"),
            "requested_key_prefix": key_prefix,
        }

    def get_snippet(self, snippet_uuid: str) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "skipped": True, "reason": "ASIMOV_ENABLED=false"}
        if not self.is_configured():
            return {"ok": False, "skipped": True, "reason": "asimov_not_configured"}
        if not (snippet_uuid or "").strip():
            return {"ok": False, "reason": "missing_snippet_uuid"}

        return self._request("GET", f"application/snippets/{snippet_uuid}", headers=self._headers_json(), timeout=60)

    def delete_snippet(self, snippet_uuid: str) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "skipped": True, "reason": "ASIMOV_ENABLED=false"}
        if not self.is_configured():
            return {"ok": False, "skipped": True, "reason": "asimov_not_configured"}
        if not (snippet_uuid or "").strip():
            return {"ok": False, "reason": "missing_snippet_uuid"}

        return self._request("DELETE", f"application/snippets/{snippet_uuid}", headers=self._headers_json(), timeout=60)
