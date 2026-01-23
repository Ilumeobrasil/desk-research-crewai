from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from desk_research.tools.asimov_client import AsimovClient
from desk_research.tools.rag_tools import get_rag_from_env


def _load_env() -> None:
    # Regra: não existe .env.asimov. Tudo vem do .env padrão / variáveis de ambiente.
    load_dotenv(override=False)


_WS_RE = re.compile(r"\s+")
_MULTI_PUNCT_RE = re.compile(r"([!?.,;:])\1{2,}")


def _clean_text(text: str) -> str:
    t = (text or "").strip()
    t = _WS_RE.sub(" ", t)
    t = _MULTI_PUNCT_RE.sub(r"\1\1", t)
    return t.strip()


def _parse_llm_json(s: Any) -> Any:
    if not s:
        return None
    if isinstance(s, dict):
        return s
    if not isinstance(s, str):
        return None
    raw = s.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    try:
        return json.loads(raw)
    except Exception:
        return None


def _env_csv(key: str) -> list[str]:
    raw = (os.getenv(key) or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _env_json_dict(key: str) -> dict[str, str]:
    raw = (os.getenv(key) or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            out: dict[str, str] = {}
            for k, v in obj.items():
                if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                    out[k.strip()] = v.strip()
            return out
    except Exception:
        return {}
    return {}


def _normalize_brand_token(s: str) -> str:
    s = (s or "").strip()
    s = _WS_RE.sub(" ", s)
    return s


def _looks_like_brand_token(s: str) -> bool:
    s = _normalize_brand_token(s)
    if not s:
        return False
    if len(s) < 2 or len(s) > 40:
        return False
    if "\n" in s or "\t" in s:
        return False
    if s.count(" ") > 2:
        return False
    bad_chars = sum(1 for ch in s if not (ch.isalnum() or ch in " .-&'/"))
    if bad_chars > 2:
        return False
    return True


def _dedupe_keep_order(seq: list[str]) -> list[str]:
    seen = set()
    out = []
    for x in seq:
        k = (x or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def _extract_window(text: str, start: int, end: int, pad: int = 80) -> str:
    if not text:
        return ""
    s = max(0, start - pad)
    e = min(len(text), end + pad)
    return text[s:e].strip()


def _find_first_occurrence(text: str, needle: str) -> tuple[int | None, int | None]:
    if not text or not needle:
        return None, None
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return None, None
    return idx, idx + len(needle)


def _build_snippet_index_from_ingestor(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Índice chunk_key -> metadados do chunk (do Agente 1), sem carregar texto.
    """
    out: dict[str, dict[str, Any]] = {}
    snippets = payload.get("snippets")
    if not isinstance(snippets, list):
        return out

    for sn in snippets:
        if not isinstance(sn, dict):
            continue
        md = sn.get("metadata")
        if not isinstance(md, dict):
            continue
        key = md.get("chunk_key")
        if not isinstance(key, str) or not key:
            continue

        out[key] = {
            "chunk_index": md.get("chunk_index"),
            "chunks_total": md.get("chunks_total"),
            "chunk_start_char": md.get("chunk_start_char"),
            "chunk_end_char": md.get("chunk_end_char"),
            "chunk_hash_sha256": md.get("chunk_hash_sha256"),
            "source_relpath": md.get("source_relpath"),
            "file_uuid": md.get("file_uuid"),
        }

    return out


def _locate_evidence_in_chunks(evidence_text: str, items_sorted: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Tenta encontrar evidence_text literalmente em algum chunk recuperado do Asimov.
    Retorna um pacote com chunk_key e offsets dentro do chunk, quando encontrado.
    """
    ev = (evidence_text or "").strip()
    if not ev or not items_sorted:
        return None

    ev_low = ev.lower()

    for idx, item in enumerate(items_sorted):
        key = str(item.get("key") or "")
        content = str(item.get("content") or "")
        if not key or not content:
            continue

        pos = content.lower().find(ev_low)
        if pos >= 0:
            return {
                "chunk_key": key,
                "chunk_index_from_retrieval": idx,
                "chunk_offset_start": pos,
                "chunk_offset_end": pos + len(ev),
            }

    return None


def _brand_evidence_from_llm_or_fallback(
    *,
    parsed: dict[str, Any] | None,
    cleaned_text: str,
) -> list[dict[str, Any]]:
    """
    Fonte primária: parsed["brand_evidence"] do LLM.
    Fallback: se vier apenas brand_mentions/brand_mentions_uncertain, tenta gerar evidência
    determinística buscando ocorrência no cleaned_text.
    """
    out: list[dict[str, Any]] = []

    if isinstance(parsed, dict):
        be = parsed.get("brand_evidence")
        if isinstance(be, list):
            for item in be:
                if not isinstance(item, dict):
                    continue
                brand = _normalize_brand_token(str(item.get("brand") or "")).strip()
                txt = str(item.get("text") or "").strip()
                conf = str(item.get("confidence") or "").strip().lower() or "low"
                if conf not in ("high", "low"):
                    conf = "low"
                if not brand or not txt:
                    continue
                out.append(
                    {
                        "brand": brand,
                        "confidence": conf,
                        "text": txt[:600],
                        "source": (str(item.get("source") or "").strip() or None),
                        "mentioned_as": (str(item.get("mentioned_as") or "").strip() or None),
                    }
                )
            if out:
                return out

        # fallback: monta a partir das listas, mas só se conseguir evidência no texto
        raw_confirmed = parsed.get("brand_mentions") or []
        raw_uncertain = parsed.get("brand_mentions_uncertain") or []

        candidates: list[tuple[str, str]] = []
        if isinstance(raw_confirmed, list):
            for x in raw_confirmed:
                if x:
                    candidates.append((str(x), "high"))
        if isinstance(raw_uncertain, list):
            for x in raw_uncertain:
                if x:
                    candidates.append((str(x), "low"))

        for name, conf in candidates:
            b = _normalize_brand_token(name)
            if not _looks_like_brand_token(b):
                continue
            s, e = _find_first_occurrence(cleaned_text, b)
            if s is None or e is None:
                continue
            out.append(
                {
                    "brand": b,
                    "confidence": conf,
                    "text": _extract_window(cleaned_text, s, e, pad=90)[:600],
                    "source": "auto_excerpt",
                    "mentioned_as": b,
                }
            )

    return out


def _postprocess_brand_evidence(
    *,
    brand_evidence: list[dict[str, Any]],
    cleaned_text: str,
    asimov_items_sorted: list[dict[str, Any]],
    ingestor_chunk_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Aplica:
      - aliases via env BRAND_ALIASES_JSON
      - whitelist via env BRAND_WHITELIST_CSV (se existir, só confirma itens presentes)
      - garante evidência: remove qualquer item sem text
      - tenta ligar evidência a chunk_key (Asimov) e anexar chunk_metadata (Agente 1)
    Retorna:
      - brand_mentions
      - brand_mentions_uncertain
      - brand_evidence (enriquecida)
    """
    aliases = _env_json_dict("BRAND_ALIASES_JSON")
    whitelist = set(_env_csv("BRAND_WHITELIST_CSV"))

    enriched: list[dict[str, Any]] = []
    confirmed: list[str] = []
    uncertain: list[str] = []

    for item in brand_evidence:
        if not isinstance(item, dict):
            continue

        brand_raw = _normalize_brand_token(str(item.get("brand") or "")).strip()
        ev_text = str(item.get("text") or "").strip()
        conf = str(item.get("confidence") or "low").strip().lower()
        if conf not in ("high", "low"):
            conf = "low"

        if not brand_raw or not ev_text:
            continue
        if not _looks_like_brand_token(brand_raw):
            continue

        # Garantia mínima: evidência precisa existir no texto analisado (pelo menos como substring)
        if cleaned_text and ev_text.lower() not in cleaned_text.lower():
            # não descarta imediatamente; tenta evidência por janela do próprio brand
            s, e = _find_first_occurrence(cleaned_text, brand_raw)
            if s is None or e is None:
                continue
            ev_text = _extract_window(cleaned_text, s, e, pad=90)[:600]

        mapped = aliases.get(brand_raw, brand_raw)
        mentioned_as = item.get("mentioned_as") or brand_raw

        ev_pack: dict[str, Any] = {
            "brand": mapped,
            "mentioned_as": mentioned_as,
            "confidence": conf,
            "text": ev_text[:600],
            "source": item.get("source"),
        }

        # tenta ligar a chunk do Asimov
        loc = _locate_evidence_in_chunks(ev_pack["text"], asimov_items_sorted) if asimov_items_sorted else None
        if loc:
            ev_pack.update(loc)
            ck = loc.get("chunk_key")
            if isinstance(ck, str) and ck in ingestor_chunk_index:
                ev_pack["chunk_metadata"] = ingestor_chunk_index[ck]

        # Whitelist (se existir): só confirma se estiver nela
        if whitelist:
            if mapped in whitelist and conf == "high":
                confirmed.append(mapped)
            else:
                uncertain.append(mapped)
        else:
            if conf == "high":
                confirmed.append(mapped)
            else:
                uncertain.append(mapped)

        enriched.append(ev_pack)

    confirmed = _dedupe_keep_order(confirmed)
    uncertain = _dedupe_keep_order([x for x in uncertain if x not in set([c.lower() for c in confirmed])])

    # Garante a regra: toda marca nas listas tem evidência associada
    allowed = set([b.lower() for b in confirmed + uncertain])
    enriched = [e for e in enriched if str(e.get("brand") or "").strip().lower() in allowed]

    return {
        "brand_mentions": confirmed,
        "brand_mentions_uncertain": uncertain,
        "brand_evidence": enriched,
    }


RAG_SYSTEM_PROMPT = (
    "Você é um assistente especializado em pesquisa qualitativa e Consumer Insights. "
    "Você deve retornar APENAS JSON válido, sem markdown, sem texto extra."
)

RAG_QUERY_TEMPLATE = """A partir do TEXTO-ALVO abaixo, retorne APENAS um JSON válido (sem markdown) com os campos:
- language: código (ex.: "pt")
- brand_evidence: lista de objetos, onde CADA ITEM tem evidência literal. Campos:
  - brand: nome do termo/marca
  - confidence: "high" se você tem confiança de que é marca/empresa/produto, senão "low"
  - text: TRECHO LITERAL curto do TEXTO-ALVO que mostra a menção (obrigatório)
  - mentioned_as: como apareceu no texto (opcional; útil quando você normaliza)
  - source: null ou string curta (ex.: "menção direta", "contexto de compra")
- themes: lista de temas (curtos)
- sentiments: lista curta (ex.: "positivo", "neutro", "negativo", "ambivalente")
- moments: lista de momentos/ocasiões (curtos)
- evidence: lista de 2 a 5 evidências gerais (objetos) com:
  - text: trecho literal curto do TEXTO-ALVO
  - source: null OU string curta

REGRAS OBRIGATÓRIAS:
- NÃO invente marcas.
- NENHUM item pode aparecer como marca/candidato sem um trecho literal em brand_evidence.text.
- Se estiver em dúvida se é marca, use confidence="low" (isso virará brand_mentions_uncertain).
- Evidências devem ser literais e curtas.

TEXTO-ALVO:
\"\"\"{target}\"\"\"
"""


def _fallback_semantics(cleaned_text: str) -> dict[str, Any]:
    ev = []
    if cleaned_text:
        ev.append({"text": cleaned_text[:300], "source": "fallback_excerpt"})
    return {
        "language": "pt" if cleaned_text else None,
        "brand_mentions": [],
        "brand_mentions_uncertain": [],
        "brand_evidence": [],
        "themes": [],
        "sentiments": [],
        "moments": [],
        "evidence": ev,
    }


def run_treatment_folder(
    *,
    input_dir: Path,
    output_dir: Path,
    enable_rag: bool,
    poll_attempts: int,
    poll_sleep_s: float,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    _load_env()

    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rag = get_rag_from_env()
    asimov = AsimovClient.from_env()

    files = sorted(input_dir.glob("*.json"))

    processed_ok = 0
    processed_error = 0
    skipped = 0
    valid_inputs = 0

    top_errors: dict[str, int] = {}
    error_samples: list[dict[str, Any]] = []

    for fp in files:
        try:
            payload = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            skipped += 1
            top_errors["invalid_json"] = top_errors.get("invalid_json", 0) + 1
            continue

        if not isinstance(payload, dict) or "text" not in payload:
            skipped += 1
            top_errors["skip_non_ingestor_schema"] = top_errors.get("skip_non_ingestor_schema", 0) + 1
            continue

        valid_inputs += 1

        file_uuid = payload.get("uuid") or str(uuid.uuid4())
        original_text = str(payload.get("text") or "")

        # dataset preferencial: payload.run.dataset > env ASIMOV_DATASET
        dataset = None
        run_info = payload.get("run")
        if isinstance(run_info, dict):
            ds = run_info.get("dataset")
            if isinstance(ds, str) and ds.strip():
                dataset = ds.strip()
        if not dataset:
            dataset = (os.getenv("ASIMOV_DATASET") or "").strip() or None

        # Índice do Agente 1 (para anexar metadados ao chunk_key)
        ingestor_chunk_index = _build_snippet_index_from_ingestor(payload)

        asimov_chunks_count = 0
        asimov_items_sorted: list[dict[str, Any]] = []
        asimov_chunks_text = ""
        retrieval_keys: list[str] = []

        if asimov.enabled and asimov.is_configured() and dataset:
            try:
                chunks_result = asimov.find_snippets(
                    dataset=dataset,
                    key_prefix=file_uuid,
                    max_items=1000,
                    page_size=30,
                    max_pages=100,
                )
                if chunks_result.get("ok"):
                    items = chunks_result.get("items", [])
                    if isinstance(items, list) and items:
                        asimov_chunks_count = len(items)
                        asimov_items_sorted = sorted(items, key=lambda x: str(x.get("key", "")))
                        contents: list[str] = []
                        for item in asimov_items_sorted:
                            key = str(item.get("key") or "")
                            if key:
                                retrieval_keys.append(key)
                            content = item.get("content") or ""
                            if content:
                                contents.append(str(content).strip())
                        asimov_chunks_text = "\n\n".join([c for c in contents if c])
            except Exception as e:
                error_key = f"asimov_fetch_chunks_error:{file_uuid}"
                top_errors[error_key] = top_errors.get(error_key, 0) + 1
                if len(error_samples) < 5:
                    error_samples.append({"file": fp.name, "uuid": file_uuid, "error": str(e)[:300]})

        used_asimov = bool(asimov_chunks_text)
        text_to_use = asimov_chunks_text if used_asimov else original_text
        cleaned_text = _clean_text(text_to_use)

        upstream: dict[str, Any] = {
            "mode": payload.get("mode"),
            "stage": payload.get("stage"),
            "run": payload.get("run"),
            "file_metadata": payload.get("file_metadata"),
            "interview_metadata": payload.get("interview_metadata"),
        }

        out_item: dict[str, Any] = {
            "uuid": file_uuid,
            "source_file": payload.get("source_file"),
            "file": payload.get("file") or payload.get("filename") or payload.get("file_name") or fp.name,
            "text": original_text,
            "cleaned_text": cleaned_text,
            "upstream": upstream,
            "asimov_chunks": {
                "used": bool(used_asimov),
                "count": asimov_chunks_count,
                "text_length": len(asimov_chunks_text),
                "retrieval_keys": retrieval_keys,
            },
            "semantics": {
                "language": None,
                "brand_mentions": [],
                "brand_mentions_uncertain": [],
                "brand_evidence": [],
                "themes": [],
                "sentiments": [],
                "moments": [],
                "evidence": [],
            },
            "rag": {
                "enabled": bool(enable_rag),
                "ok": False,
                "status": None,
                "url": None,
                "status_payload": None,
                "error": None,
                "detail": None,
            },
        }

        if not cleaned_text:
            out_item["semantics"] = _fallback_semantics(cleaned_text)
            (output_dir / f"{file_uuid}.json").write_text(json.dumps(out_item, ensure_ascii=False, indent=2), encoding="utf-8")
            processed_ok += 1
            continue

        if enable_rag:
            model = (os.getenv("ASIMOV_DATASET_MODEL") or "").strip()
            if not model:
                resp = {"ok": False, "reason": "missing_MODEL_env", "error": "MODEL environment variable not set"}
            else:
                resp = rag.completion_with_context(
                    messages=[
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user", "content": RAG_QUERY_TEMPLATE.format(target=cleaned_text[:6000])},
                    ],
                    dataset=dataset or "",
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    poll_attempts=poll_attempts,
                    poll_sleep_s=poll_sleep_s,
                )

            out_item["rag"]["ok"] = bool(resp.get("ok"))
            out_item["rag"]["status"] = resp.get("status")
            out_item["rag"]["url"] = resp.get("url")
            out_item["rag"]["status_payload"] = resp.get("status_payload")
            out_item["rag"]["error"] = resp.get("error")
            out_item["rag"]["detail"] = resp.get("detail")

            if resp.get("ok"):
                parsed = _parse_llm_json(resp.get("content"))
                if isinstance(parsed, dict):
                    sem = out_item["semantics"]
                    sem["language"] = parsed.get("language") or None
                    sem["themes"] = [str(x) for x in (parsed.get("themes") or []) if x]
                    sem["sentiments"] = [str(x) for x in (parsed.get("sentiments") or []) if x]
                    sem["moments"] = [str(x) for x in (parsed.get("moments") or []) if x]

                    ev = parsed.get("evidence") or []
                    keep: list[dict[str, Any]] = []
                    if isinstance(ev, list):
                        for e in ev[:7]:
                            if not isinstance(e, dict):
                                continue
                            txt = str(e.get("text") or "").strip()
                            if not txt:
                                continue
                            keep.append(
                                {
                                    "text": txt[:500],
                                    "source": (e.get("source") if isinstance(e.get("source"), str) else None),
                                }
                            )
                    sem["evidence"] = keep

                    # marcas com evidência obrigatória
                    be_raw = _brand_evidence_from_llm_or_fallback(parsed=parsed, cleaned_text=cleaned_text)
                    be_pack = _postprocess_brand_evidence(
                        brand_evidence=be_raw,
                        cleaned_text=cleaned_text,
                        asimov_items_sorted=asimov_items_sorted,
                        ingestor_chunk_index=ingestor_chunk_index,
                    )

                    sem["brand_mentions"] = be_pack["brand_mentions"]
                    sem["brand_mentions_uncertain"] = be_pack["brand_mentions_uncertain"]
                    sem["brand_evidence"] = be_pack["brand_evidence"]
                else:
                    out_item["semantics"] = _fallback_semantics(cleaned_text)
                    top_errors["rag_unparseable_json"] = top_errors.get("rag_unparseable_json", 0) + 1
            else:
                out_item["semantics"] = _fallback_semantics(cleaned_text)
                err_key = out_item["rag"]["error"] or f"rag_error:{out_item['rag']['status'] or 'unknown'}"
                top_errors[err_key] = top_errors.get(err_key, 0) + 1
                if len(error_samples) < 5:
                    error_samples.append(
                        {
                            "file": fp.name,
                            "status": out_item["rag"]["status"],
                            "url": out_item["rag"]["url"],
                            "detail": (out_item["rag"]["detail"] or "")[:300],
                        }
                    )

        (output_dir / f"{file_uuid}.json").write_text(json.dumps(out_item, ensure_ascii=False, indent=2), encoding="utf-8")

        if enable_rag and not out_item["rag"]["ok"]:
            processed_error += 1
        else:
            processed_ok += 1

    top_errors_list = [{"error": k, "count": v} for k, v in sorted(top_errors.items(), key=lambda x: x[1], reverse=True)]

    return {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "files": len(files),
        "valid_inputs": valid_inputs,
        "skipped": skipped,
        "processed_ok": processed_ok,
        "processed_error": processed_error,
        "rag_enabled": bool(enable_rag),
        "rag_dataset": dataset,
        "chat_model": os.getenv("ASIMOV_DATASET_MODEL"),
        "top_errors": top_errors_list,
        "error_samples": error_samples,
    }


class TreatmentToolInput(BaseModel):
    input_dir: str = Field(..., description="Diretório com JSONs do output do Agente 1 (ingestor).")
    output_dir: str = Field(..., description="Diretório para escrever os JSONs tratados do Agente 2.")
    enable_rag: bool = Field(True, description="Se True, consulta RAG. Se False, apenas normaliza.")
    poll_attempts: int = Field(12, description="Polling do endpoint atual.")
    poll_sleep_s: float = Field(2.0, description="Sleep entre polls.")
    temperature: float = Field(0.2, description="Temperatura do modelo.")
    max_tokens: int = Field(1200, description="Máximo de tokens na resposta.")


class TreatmentFolderTool(BaseTool):
    name: str = "treat_folder"
    description: str = (
        "Agente 2 (Treatment): lê JSONs do Agente 1, normaliza texto e extrai semântica via RAG. "
        "Marcas só aparecem com evidência literal (brand_evidence)."
    )
    args_schema: Type[BaseModel] = TreatmentToolInput

    def _run(
        self,
        input_dir: str,
        output_dir: str,
        enable_rag: bool = True,
        poll_attempts: int = 12,
        poll_sleep_s: float = 2.0,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> str:
        result = run_treatment_folder(
            input_dir=Path(input_dir),
            output_dir=Path(output_dir),
            enable_rag=enable_rag,
            poll_attempts=poll_attempts,
            poll_sleep_s=poll_sleep_s,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return json.dumps(result, ensure_ascii=False)


treat_folder_tool = TreatmentFolderTool()
