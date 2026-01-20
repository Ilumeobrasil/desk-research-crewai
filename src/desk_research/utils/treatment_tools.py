from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from desk_research.tools.rag_tools import get_rag_from_env


def _load_env() -> None:
    load_dotenv(override=False)
    load_dotenv(".env.asimov", override=False)


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


RAG_SYSTEM_PROMPT = (
    "Você é um assistente especializado em pesquisa qualitativa e Consumer Insights. "
    "Você deve retornar APENAS JSON válido, sem markdown, sem texto extra."
)

RAG_QUERY_TEMPLATE = """A partir do TEXTO-ALVO abaixo, retorne APENAS um JSON válido (sem markdown) com os campos:
- language: código (ex.: "pt")
- brand_mentions: lista de marcas (normalizadas)
- themes: lista de temas (curtos)
- sentiments: lista curta (ex.: "positivo", "neutro", "negativo", "ambivalente")
- moments: lista de momentos/ocasiões (curtos)
- evidence: lista de 2 a 5 evidências (objetos) com:
  - text: trecho literal curto do TEXTO-ALVO
  - source: null OU string curta descrevendo o “porquê” (ex.: "menção direta", "emoção", "ocasião")

TEXTO-ALVO:
\"\"\"{target}\"\"\"
"""


def _fallback_semantics(cleaned_text: str) -> dict[str, Any]:
    """
    Fallback determinístico (sem LLM), para não bloquear pipeline quando o RAG falhar.
    Não inventa marca/tema — só dá estrutura e evidências mínimas.
    """
    ev = []
    if cleaned_text:
        ev.append({"text": cleaned_text[:300], "source": "fallback_excerpt"})
    return {
        "language": "pt" if cleaned_text else None,
        "brand_mentions": [],
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
    dataset = (os.getenv("ASIMOV_DATASET") or "").strip()

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

        original_text = str(payload.get("text") or "")
        cleaned_text = _clean_text(original_text)

        out_item: dict[str, Any] = {
            "source_file": payload.get("source_file"),
            "file": payload.get("file") or payload.get("filename") or fp.name,
            "text": original_text,
            "cleaned_text": cleaned_text,
            "semantics": {
                "language": None,
                "brand_mentions": [],
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

        # texto vazio -> semântica fallback e grava
        if not cleaned_text:
            out_item["semantics"] = _fallback_semantics(cleaned_text)
            (output_dir / fp.name).write_text(json.dumps(out_item, ensure_ascii=False, indent=2), encoding="utf-8")
            processed_ok += 1
            continue

        if enable_rag:
            model = (os.getenv("MODEL") or "").strip()
            if not model:
                resp = {"ok": False, "reason": "missing_MODEL_env", "error": "MODEL environment variable not set"}
            else:
                resp = rag.completion_with_context(
                    messages=[
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user", "content": RAG_QUERY_TEMPLATE.format(target=cleaned_text[:6000])},
                    ],
                    dataset=dataset,
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
                    sem["brand_mentions"] = [str(x) for x in (parsed.get("brand_mentions") or []) if x]
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
                else:
                    # LLM respondeu mas não veio JSON parseável -> fallback
                    out_item["semantics"] = _fallback_semantics(cleaned_text)
                    top_errors["rag_unparseable_json"] = top_errors.get("rag_unparseable_json", 0) + 1
            else:
                # erro de RAG (inclui model_not_authorized) -> fallback + auditoria
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

        # grava sempre
        (output_dir / fp.name).write_text(json.dumps(out_item, ensure_ascii=False, indent=2), encoding="utf-8")

        # critério de OK: arquivo produzido com schema tratado
        # (mesmo que rag falhe, pipeline segue; erro fica em rag.ok/error)
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
        "chat_model": os.getenv("MODEL"),
        "top_errors": top_errors_list,
        "error_samples": error_samples,
    }


class TreatmentToolInput(BaseModel):
    input_dir: str = Field(..., description="Diretório com JSONs do output do Agente 1 (ingestor).")
    output_dir: str = Field(..., description="Diretório para escrever os JSONs tratados do Agente 2.")
    enable_rag: bool = Field(True, description="Se True, consulta RAG. Se False, apenas normaliza.")
    poll_attempts: int = Field(12, description="Compat: não usado no endpoint /chat/completions.")
    poll_sleep_s: float = Field(2.0, description="Compat: não usado no endpoint /chat/completions.")
    temperature: float = Field(0.2, description="Temperatura do modelo.")
    max_tokens: int = Field(1200, description="Máximo de tokens na resposta.")


class TreatmentFolderTool(BaseTool):
    name: str = "treat_folder"
    description: str = (
        "Agente 2 (Treatment): lê JSONs do Agente 1, limpa/normaliza texto e extrai semântica via RAG. "
        "Sempre grava saída tratada por arquivo, com auditoria de falhas do RAG."
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
