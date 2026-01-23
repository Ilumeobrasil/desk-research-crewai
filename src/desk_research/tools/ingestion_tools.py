from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from docx import Document
from pydantic import BaseModel, Field

from desk_research.tools.asimov_client import AsimovClient


PIPELINE_STAGE = "ingested"
STAGE_VERSION = "ingestor_v1"


_MONTHS: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "fev": 2,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "abr": 4,
    "apr": 4,
    "april": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "ago": 8,
    "aug": 8,
    "august": 8,
    "set": 9,
    "sep": 9,
    "september": 9,
    "out": 10,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dez": 12,
    "dec": 12,
    "december": 12,
}

_DT_EN_RE = re.compile(
    r"\(\s*(?P<month>[A-Za-z]{3,9})\s+(?P<day>\d{1,2}),\s*(?P<year>\d{4})\s*[-–—]\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)\s*\)",
    re.IGNORECASE,
)
_DT_DMY_RE = re.compile(
    r"\(\s*(?P<day>\d{1,2})[\/\-.](?P<month>\d{1,2})[\/\-.](?P<year>\d{4})\s*[-–—]\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>am|pm)?\s*\)",
    re.IGNORECASE,
)
_DT_ISO_RE = re.compile(
    r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[ T](?P<hour>\d{2}):(?P<minute>\d{2})(:(?P<second>\d{2}))?\b"
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes((text or "").encode("utf-8", errors="ignore"))


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _read_docx_text(fp: Path) -> str:
    doc = Document(str(fp))
    parts: list[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts).strip()


def _read_text(fp: Path) -> str:
    ext = fp.suffix.lower()

    if ext == ".docx":
        return _read_docx_text(fp)

    if ext in (".txt", ".md"):
        return fp.read_text(encoding="utf-8", errors="ignore").strip()

    if ext == ".pdf":
        # Best-effort sem dependência hard.
        try:
            import pdfplumber  # type: ignore

            parts: list[str] = []
            with pdfplumber.open(str(fp)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        parts.append(page_text.strip())
            return "\n\n".join(parts).strip()
        except Exception:
            try:
                import PyPDF2  # type: ignore

                parts: list[str] = []
                with fp.open("rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            parts.append(page_text.strip())
                return "\n\n".join(parts).strip()
            except Exception:
                return ""

    return fp.read_text(encoding="utf-8", errors="ignore").strip()


def _safe_stem(name: str) -> str:
    keep: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", " "):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip().replace(" ", "_")


def _generate_uuid_key(file_uuid: str, chunk_idx: int | None = None, chunks_total: int | None = None) -> str:
    if chunk_idx is None or chunks_total is None:
        return file_uuid
    return f"{file_uuid}#chunk_{chunk_idx:02d}of{chunks_total:02d}"


def _chunk_text_spans(text: str, max_chars: int) -> list[dict[str, Any]]:
    """
    Chunking por caracteres com offsets (start/end) no texto canônico.
    - Sem overlap.
    - Tenta quebrar em \n (último \n dentro da janela) para preservar legibilidade.
    """
    t = (text or "").strip()
    if not t:
        return []

    if len(t) <= max_chars:
        return [{"text": t, "start": 0, "end": len(t)}]

    spans: list[dict[str, Any]] = []
    n = len(t)
    pos = 0

    while pos < n:
        end = min(pos + max_chars, n)

        if end < n:
            window = t[pos:end]
            cut = window.rfind("\n")
            if cut >= 200:
                end = pos + cut

        chunk_text = t[pos:end].strip()
        if chunk_text:
            spans.append({"text": chunk_text, "start": pos, "end": end})

        pos = end
        while pos < n and t[pos] in "\r\n":
            pos += 1

    return spans


def _file_metadata(fp: Path, *, root_dir: Path) -> dict[str, Any]:
    stat = fp.stat()
    try:
        rel = fp.relative_to(root_dir).as_posix()
    except Exception:
        rel = fp.name

    return {
        "file_hash_sha256": _sha256_bytes(fp.read_bytes()),
        "file_size_bytes": int(stat.st_size),
        "file_mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "source_type": fp.suffix.lstrip(".").lower() or None,
        "source_relpath": rel,
        "safe_stem": _safe_stem(fp.stem),
    }


def _infer_language_from_filename(name: str) -> str | None:
    n = (name or "").lower()
    if "portuguese" in n or "português" in n:
        return "pt"
    if "english" in n or "ingl" in n:
        return "en"
    if "spanish" in n or "espanhol" in n:
        return "es"
    return None


def _try_parse_interview_datetime(text: str) -> tuple[str | None, str | None, str | None]:
    """
    Extrai datetime quando explicitamente presente no texto.
    Regra: se não houver metadado parseável, retorna (None, None, None).
    """
    head = (text or "")[:2000]

    m = _DT_EN_RE.search(head)
    if m:
        month = _MONTHS.get(m.group("month").strip().lower())
        if month:
            day = int(m.group("day"))
            year = int(m.group("year"))
            hour = int(m.group("hour"))
            minute = int(m.group("minute"))
            ampm = m.group("ampm").lower()
            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
            dt = datetime(year, month, day, hour, minute)
            return dt.isoformat(), None, None

    m = _DT_DMY_RE.search(head)
    if m:
        day = int(m.group("day"))
        month = int(m.group("month"))
        year = int(m.group("year"))
        hour = int(m.group("hour"))
        minute = int(m.group("minute"))
        ampm = (m.group("ampm") or "").strip().lower() or None
        if ampm:
            if ampm == "pm" and hour != 12:
                hour += 12
            if ampm == "am" and hour == 12:
                hour = 0
        dt = datetime(year, month, day, hour, minute)
        return dt.isoformat(), None, None

    m = _DT_ISO_RE.search(head)
    if m:
        year = int(m.group("year"))
        month = int(m.group("month"))
        day = int(m.group("day"))
        hour = int(m.group("hour"))
        minute = int(m.group("minute"))
        second = int(m.group("second") or 0)
        dt = datetime(year, month, day, hour, minute, second)
        return dt.isoformat(), None, None

    return None, None, None


def _extract_simple_fields(text: str) -> dict[str, str | None]:
    """
    Extrai metadados textuais simples a partir do cabeçalho (sem inventar).
    Observação: title aqui é a primeira linha não vazia (heurística leve).
    """
    head_lines = [(ln or "").strip() for ln in (text or "").splitlines()[:80]]
    head = "\n".join([ln for ln in head_lines if ln])

    def _find(patterns: list[str]) -> str | None:
        for p in patterns:
            m = re.search(p, head, flags=re.IGNORECASE)
            if m:
                val = (m.group(1) or "").strip()
                return val or None
        return None

    title = None
    for ln in head_lines:
        if ln:
            title = ln
            break

    interviewer = _find([r"\binterviewer\s*:\s*(.+)", r"\bmoderador\s*:\s*(.+)", r"\bentrevistador\s*:\s*(.+)"])
    respondent = _find([r"\brespondent\s*:\s*(.+)", r"\bparticipant\s*:\s*(.+)", r"\bentrevistado\s*:\s*(.+)"])
    location = _find([r"\blocation\s*:\s*(.+)", r"\blocal\s*:\s*(.+)"])

    return {
        "title": title or None,
        "interviewer": interviewer,
        "respondent": respondent,
        "location": location,
    }


class IngestFolderArgs(BaseModel):
    input_dir: str = Field(..., description="Diretório de entrada contendo entrevistas (recursivo).")
    output_dir: str = Field(..., description="Diretório de saída para gravar JSONs do ingestor.")

    upload_to_asimov: bool = Field(
        default=True,
        description="Se true, envia o conteúdo extraído para o Asimov via /snippets.",
    )

    snippet_chunk_chars: int = Field(
        default=3500,
        description="Tamanho máximo (chars) por snippet.",
    )

    max_snippets_per_request: int = Field(
        default=30,
        description="Batch por request no endpoint /snippets (limite prático 30).",
    )


class IngestFolderTool(BaseTool):
    name: str = "ingest_folder_tool"
    description: str = (
        "Agente 1 (Ingestor): lê entrevistas (docx/txt/md/pdf), extrai texto, gera JSONs com metadados e "
        "opcionalmente envia chunks para o Asimov via /snippets."
    )
    args_schema: Type[BaseModel] = IngestFolderArgs

    def _run(
        self,
        input_dir: str,
        output_dir: str,
        upload_to_asimov: bool = True,
        snippet_chunk_chars: int = 3500,
        max_snippets_per_request: int = 30,
    ) -> dict[str, Any]:
        in_path = Path(input_dir)
        out_path = Path(output_dir)

        if not in_path.exists():
            return {
                "ok": False,
                "reason": f"input_dir_not_found:{in_path}",
                "input_dir": str(in_path),
                "output_dir": str(out_path),
            }

        _ensure_dir(out_path)

        warnings: list[str] = []
        outputs: list[str] = []

        run_id = str(uuid.uuid4())
        ingested_at = _utcnow_iso()

        supported_exts = {".docx", ".txt", ".md", ".pdf"}
        input_files = sorted([p for p in in_path.rglob("*") if p.is_file() and p.suffix.lower() in supported_exts])

        asimov = AsimovClient.from_env()
        dataset_name = asimov.dataset or (os.getenv("ASIMOV_DATASET") or "").strip() or None

        try:
            snippet_chunk_chars = int(snippet_chunk_chars)
        except Exception:
            snippet_chunk_chars = 3500

        try:
            max_snippets_per_request = int(max_snippets_per_request)
        except Exception:
            max_snippets_per_request = 30

        if max_snippets_per_request <= 0:
            max_snippets_per_request = 30
        if max_snippets_per_request > 30:
            max_snippets_per_request = 30

        if upload_to_asimov and asimov.enabled and asimov.is_configured():
            ensured = asimov.ensure_dataset()
            if not ensured.get("ok"):
                warnings.append(f"asimov_ensure_dataset_failed:{ensured}")
            elif ensured.get("created"):
                warnings.append(
                    f"asimov_dataset_created:name={ensured.get('dataset_name')} uuid={ensured.get('dataset_uuid')}"
                )

        def _flush(batch: list[dict[str, str]], *, errors: list[dict[str, Any]], file_name: str) -> int:
            if not batch:
                return 0
            up = asimov.upload_snippets(batch)
            if up.get("ok") is True:
                return int(up.get("sent_items") or len(batch))

            errors.append(
                {
                    "file": file_name,
                    "status": up.get("status"),
                    "url": up.get("url"),
                    "detail": str(up.get("json") or up.get("text"))[:1200],
                    "attempted": len(batch),
                }
            )
            warnings.append(
                f"upload_snippets_failed:file={file_name} status={up.get('status')} body={str(up.get('json') or up.get('text'))[:200]}"
            )
            return 0

        uploaded_snippets = 0

        for fp in input_files:
            try:
                text = _read_text(fp)
                if not text:
                    warnings.append(f"empty_text:{fp.name}")
                    continue

                file_already_processed = False
                for json_file in sorted(out_path.rglob("*.json")):
                    try:
                        json_data = json.loads(json_file.read_text(encoding="utf-8"))
                        
                        if json_data.get("file_name") == str(fp.name):
                            outputs.append(str(json_file))
                            file_already_processed = True
                            break
                    except (json.JSONDecodeError, KeyError, Exception) as exc:
                        continue
            
                if file_already_processed:
                    continue

                file_uuid = str(uuid.uuid4())
                file_meta = _file_metadata(fp, root_dir=in_path)

                dt_start, dt_end, tz_hint = _try_parse_interview_datetime(text)
                simple_fields = _extract_simple_fields(text)
                language = _infer_language_from_filename(fp.name)

                interview_metadata: dict[str, Any] = {
                    "interview_datetime_start": dt_start,
                    "interview_datetime_end": dt_end,
                    "timezone": tz_hint,
                    "title": simple_fields.get("title"),
                    "interviewer": simple_fields.get("interviewer"),
                    "respondent": simple_fields.get("respondent"),
                    "location": simple_fields.get("location"),
                    "language": language,
                }

                spans = _chunk_text_spans(text, max_chars=snippet_chunk_chars)
                if not spans:
                    warnings.append(f"no_chunks:{fp.name}")
                    continue

                total_chunks = len(spans)
                snippets: list[dict[str, Any]] = []
                upload_items: list[dict[str, str]] = []

                for idx0, sp in enumerate(spans):
                    chunk_text = str(sp.get("text") or "")
                    start = int(sp.get("start") or 0)
                    end = int(sp.get("end") or (start + len(chunk_text)))

                    chunk_key = (
                        _generate_uuid_key(file_uuid, idx0 + 1, total_chunks)
                        if total_chunks > 1
                        else _generate_uuid_key(file_uuid)
                    )

                    snippets.append(
                        {
                            "uuid": str(uuid.uuid4()),
                            "text": chunk_text,
                            "metadata": {
                                "file_uuid": file_uuid,
                                "source_file": str(fp),
                                "source_relpath": file_meta.get("source_relpath"),
                                "chunk_index": idx0,
                                "chunks_total": total_chunks,
                                "chunk_key": chunk_key,
                                "chunk_chars": len(chunk_text),
                                "chunk_start_char": start,
                                "chunk_end_char": end,
                                "chunk_hash_sha256": _sha256_text(chunk_text),
                                "pipeline_stage": PIPELINE_STAGE,
                                "stage_version": STAGE_VERSION,
                            },
                        }
                    )

                    upload_items.append({"key": chunk_key, "content": chunk_text})

                asimov_upload: dict[str, Any] = {
                    "status": "skipped",
                    "attempted": total_chunks,
                    "uploaded": 0,
                    "skipped_duplicates": 0,
                    "errors": [],
                }

                payload: dict[str, Any] = {
                    # compat
                    "uuid": file_uuid,
                    "source_file": str(fp),
                    "file_name": fp.name,
                    "text": text,
                    # schema rico
                    "mode": "consumer_hours",
                    "stage": "ingestor",
                    "run": {
                        "run_id": run_id,
                        "dataset": dataset_name,
                        "source_type": file_meta.get("source_type"),
                        "source_file": fp.name,
                        "source_relpath": file_meta.get("source_relpath"),
                        "ingested_at": ingested_at,
                        "chunking": {"strategy": "char_newline_no_overlap", "max_chars": snippet_chunk_chars, "overlap_chars": 0},
                        "pipeline_stage": PIPELINE_STAGE,
                        "stage_version": STAGE_VERSION,
                    },
                    "interview_metadata": interview_metadata,
                    "file_metadata": file_meta,
                    "snippets": snippets,
                    "asimov_upload": asimov_upload,
                }

                out_fp = out_path / f"{file_uuid}.json"
                out_fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                outputs.append(str(out_fp))

                if upload_to_asimov and asimov.enabled and asimov.is_configured():
                    errors: list[dict[str, Any]] = []
                    uploaded_this_file = 0
                    batch: list[dict[str, str]] = []

                    for item in upload_items:
                        batch.append(item)
                        if len(batch) >= max_snippets_per_request:
                            uploaded_this_file += _flush(batch, errors=errors, file_name=fp.name)
                            batch = []

                    if batch:
                        uploaded_this_file += _flush(batch, errors=errors, file_name=fp.name)

                    asimov_upload["uploaded"] = uploaded_this_file
                    asimov_upload["errors"] = errors

                    if errors and uploaded_this_file == 0:
                        asimov_upload["status"] = "error"
                    elif errors and uploaded_this_file < total_chunks:
                        asimov_upload["status"] = "partial"
                    else:
                        asimov_upload["status"] = "ok"

                    uploaded_snippets += uploaded_this_file
                else:
                    warnings.append("asimov_skipped:disabled_or_not_configured")

                out_fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            except Exception as e:
                warnings.append(f"failed:{fp.name}:{e}")

        if upload_to_asimov and asimov.enabled and asimov.is_configured() and uploaded_snippets == 0:
            warnings.append("asimov_upload_warning:0_snippets_uploaded (verifique ASIMOV_* e endpoint /snippets)")

        return {
            "ok": True,
            "input_dir": str(in_path),
            "output_dir": str(out_path),
            "run_id": run_id,
            "ingested_at": ingested_at,
            "dataset": dataset_name,
            "input_files": len(input_files),
            "output_files": len(outputs),
            "outputs": outputs,
            "uploaded_snippets": uploaded_snippets,
            "warnings": warnings,
        }


ingest_folder_tool = IngestFolderTool()
