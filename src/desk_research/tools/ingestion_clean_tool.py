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
STAGE_VERSION = "ingestor_v1_clean"

_MONTHS: dict[str, int] = {
    "jan": 1, "january": 1, "fev": 2, "feb": 2, "february": 2,
    "mar": 3, "march": 3, "abr": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "ago": 8, "aug": 8, "august": 8,
    "set": 9, "sep": 9, "september": 9, "out": 10, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dez": 12, "dec": 12, "december": 12,
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
        try:
            import pdfplumber
            parts: list[str] = []
            with pdfplumber.open(str(fp)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        parts.append(page_text.strip())
            return "\n\n".join(parts).strip()
        except Exception:
            try:
                import PyPDF2
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


def _clean_interview_text(text: str) -> str:
    """Limpa o texto da entrevista removendo artefatos e resquícios desnecessários."""
    if not text:
        return ""
    
    t = text.strip()
    
    t = re.sub(r'\s+', ' ', t)
    
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)
    t = re.sub(r'\*(.*?)\*', r'\1', t)
    t = re.sub(r'`(.*?)`', r'\1', t)
    
    t = t.replace('"', '"').replace('"', '"')
    t = t.replace(''', "'").replace(''', "'")
    
    t = t.replace('—', '-').replace('–', '-')
    
    t = t.replace('�', '')
    t = re.sub(r'\?{2,}', '?', t)
    
    t = re.sub(r'\n{3,}', '\n\n', t)
    
    t = re.sub(r'!{3,}', '!', t)
    t = re.sub(r'\?{3,}', '?', t)
    t = re.sub(r'\.{3,}', '...', t)
    
    t = re.sub(r'\([0-9:]+ - [0-9:]+\)\s*', '', t)
    
    t = t.replace('nao', 'não')
    t = t.replace('voce', 'você')
    t = t.replace('pra', 'para')
    
    t = t.strip()
    t = re.sub(r' {2,}', ' ', t)
    
    return t


def _safe_stem(name: str) -> str:
    keep: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", " "):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip().replace(" ", "_")


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
    head_lines = [(ln or "").strip() for ln in (text or "").splitlines()[:80]]
    head = "\n".join([ln for ln in head_lines if ln])
    
    def _find(patterns: list[str]) -> str | None:
        for p in patterns:
            m = re.search(p, head, flags=re.IGNORECASE)
            if m:
                val = (m.group(1) or "").strip()
                return val or None
        return None
    
    interviewer = _find([r"\binterviewer\s*:\s*(.+)", r"\bmoderador\s*:\s*(.+)", r"\bentrevistador\s*:\s*(.+)"])
    respondent = _find([r"\brespondent\s*:\s*(.+)", r"\bparticipant\s*:\s*(.+)", r"\bentrevistado\s*:\s*(.+)"])
    location = _find([r"\blocation\s*:\s*(.+)", r"\blocal\s*:\s*(.+)"])
    
    return {
        "interviewer": interviewer,
        "respondent": respondent,
        "location": location,
    }


def _generate_chunk_key(file_uuid: str, chunk_number: int, total_chunks: int) -> str:
    """Gera key no formato: uuid#chunk_01of30"""
    return f"{file_uuid}#chunk_{chunk_number:02d}of{total_chunks:02d}"


def _chunk_text_for_asimov(text: str, max_chars: int = 3500) -> list[dict[str, Any]]:
    """Divide texto em chunks para upload no Asimov."""
    chunks = []
    for i in range(0, len(text), max_chars):
        chunk_text = text[i:i + max_chars]
        chunks.append({
            "text": chunk_text,
            "start": i,
            "end": min(i + max_chars, len(text))
        })
    return chunks


class IngestCleanFolderArgs(BaseModel):
    input_dir: str = Field(..., description="Diretório de entrada contendo entrevistas (recursivo).")
    output_dir: str = Field(..., description="Diretório de saída para gravar JSONs do ingestor com texto limpo.")


class IngestCleanFolderTool(BaseTool):
    name: str = "ingest_clean_folder_tool"
    description: str = (
        "Lê entrevistas (docx/txt/md/pdf), extrai texto, aplica limpeza rigorosa "
        "removendo artefatos e resquícios desnecessários, gera JSONs estruturados "
        "e envia o texto limpo para o Asimov em chunks."
    )
    args_schema: Type[BaseModel] = IngestCleanFolderArgs
    
    def _run(
        self,
        input_dir: str,
        output_dir: str,
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
        
        for fp in input_files:
            try:
                raw_text = _read_text(fp)
                if not raw_text:
                    warnings.append(f"empty_text:{fp.name}")
                    continue
                
                cleaned_text = _clean_interview_text(raw_text)
                
                if not cleaned_text:
                    warnings.append(f"empty_after_cleaning:{fp.name}")
                    continue
                
                file_already_processed = False
                for json_file in sorted(out_path.rglob("*.json")):
                    try:
                        json_data = json.loads(json_file.read_text(encoding="utf-8"))
                        if json_data.get("file_name") == str(fp.name):
                            outputs.append(str(json_file))
                            file_already_processed = True
                            break
                    except (json.JSONDecodeError, KeyError, Exception):
                        continue
                
                if file_already_processed:
                    continue
                
                file_uuid = str(uuid.uuid4())
                file_meta = _file_metadata(fp, root_dir=in_path)
                
                dt_start, dt_end, tz_hint = _try_parse_interview_datetime(cleaned_text)
                simple_fields = _extract_simple_fields(cleaned_text)
                language = _infer_language_from_filename(fp.name)
                
                interview_metadata: dict[str, Any] = {
                    "interview_datetime_start": dt_start,
                    "interview_datetime_end": dt_end,
                    "timezone": tz_hint,
                    "interviewer": simple_fields.get("interviewer"),
                    "respondent": simple_fields.get("respondent"),
                    "location": simple_fields.get("location"),
                    "language": language,
                }
                
                # ===== ENVIO PARA ASIMOV =====
                asimov = AsimovClient.from_env()
                dataset_name = asimov.dataset or (os.getenv("ASIMOV_DATASET") or "").strip() or None
                
                asimov_upload: dict[str, Any] = {
                    "status": "skipped",
                    "attempted": 0,
                    "uploaded": 0,
                    "errors": [],
                }
                
                if asimov.enabled and asimov.is_configured() and dataset_name:
                    try:
                        ensured = asimov.ensure_dataset()
                        if not ensured.get("ok"):
                            warnings.append(f"asimov_ensure_dataset_failed:{ensured}")
                        elif ensured.get("created"):
                            warnings.append(
                                f"asimov_dataset_created:name={ensured.get('dataset_name')} uuid={ensured.get('dataset_uuid')}"
                            )
                        
                        text_chunks = _chunk_text_for_asimov(cleaned_text, max_chars=3500)
                        total_chunks = len(text_chunks)
                        
                        if total_chunks > 0:
                            upload_items: list[dict[str, str]] = []
                            for idx, chunk_data in enumerate(text_chunks):
                                chunk_key = _generate_chunk_key(file_uuid, idx + 1, total_chunks)
                                upload_items.append({
                                    "key": chunk_key,
                                    "content": chunk_data["text"]
                                })
                            
                            uploaded_total = 0
                            upload_errors = []
                            max_per_request = 30
                            
                            for batch_start in range(0, len(upload_items), max_per_request):
                                batch = upload_items[batch_start:batch_start + max_per_request]
                                result = asimov.upload_snippets(batch, dataset=dataset_name)
                                
                                if result.get("ok"):
                                    uploaded_total += result.get("sent_items", len(batch))
                                else:
                                    upload_errors.append({
                                        "batch": (batch_start // max_per_request) + 1,
                                        "error": result.get("reason") or result.get("error")
                                    })
                            
                            asimov_upload["attempted"] = total_chunks
                            asimov_upload["uploaded"] = uploaded_total
                            asimov_upload["errors"] = upload_errors
                            
                            if len(upload_errors) == 0:
                                asimov_upload["status"] = "ok"
                            elif uploaded_total > 0:
                                asimov_upload["status"] = "partial"
                            else:
                                asimov_upload["status"] = "error"
                    except Exception as e:
                        warnings.append(f"asimov_upload_error:{fp.name}:{e}")
                        asimov_upload["status"] = "error"
                        asimov_upload["errors"].append({"error": str(e)})
                
                payload: dict[str, Any] = {
                    "uuid": file_uuid,
                    "source_file": str(fp),
                    "file_name": fp.name,
                    "text": cleaned_text,
                    "mode": "consumer_hours",
                    "stage": "ingestor",
                    "run": {
                        "run_id": run_id,
                        "source_type": file_meta.get("source_type"),
                        "source_file": fp.name,
                        "source_relpath": file_meta.get("source_relpath"),
                        "ingested_at": ingested_at,
                        "pipeline_stage": PIPELINE_STAGE,
                        "stage_version": STAGE_VERSION,
                        "text_cleaned": True,
                    },
                    "interview_metadata": interview_metadata,
                    "file_metadata": file_meta,
                    "asimov_upload": asimov_upload,
                }
                
                out_fp = out_path / f"{file_uuid}.json"
                out_fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                outputs.append(str(out_fp))
                
            except Exception as e:
                warnings.append(f"failed:{fp.name}:{e}")
        
        asimov_stats = {
            "total_attempted": 0,
            "total_uploaded": 0,
            "files_with_upload": 0,
            "files_with_errors": 0,
        }
        
        for json_file in outputs:
            try:
                json_data = json.loads(Path(json_file).read_text(encoding="utf-8"))
                upload_info = json_data.get("asimov_upload", {})
                if upload_info.get("status") == "ok":
                    asimov_stats["files_with_upload"] += 1
                    asimov_stats["total_attempted"] += upload_info.get("attempted", 0)
                    asimov_stats["total_uploaded"] += upload_info.get("uploaded", 0)
                elif upload_info.get("status") == "error":
                    asimov_stats["files_with_errors"] += 1
            except Exception:
                pass
        
        return {
            "ok": True,
            "input_dir": str(in_path),
            "output_dir": str(out_path),
            "run_id": run_id,
            "ingested_at": ingested_at,
            "input_files": len(input_files),
            "output_files": len(outputs),
            "outputs": outputs,
            "warnings": warnings,
            "asimov_upload_stats": asimov_stats,
        }


ingest_clean_folder_tool = IngestCleanFolderTool()

