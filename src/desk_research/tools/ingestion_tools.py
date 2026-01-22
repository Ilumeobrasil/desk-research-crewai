from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from docx import Document
from pydantic import BaseModel, Field

from desk_research.tools.asimov_client import AsimovClient

def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_docx_text(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(
        p.text.strip()
        for p in doc.paragraphs
        if p.text and p.text.strip()
    )

def chunk_text(text: str, max_chars: int) -> list[str]:
    if not text or len(text) <= max_chars:
        return [text] if text else []

    chunks: list[str] = []
    buffer: list[str] = []
    size = 0

    for line in text.splitlines():
        line += "\n"
        if size + len(line) > max_chars and buffer:
            chunks.append("".join(buffer).strip())
            buffer, size = [], 0
        buffer.append(line)
        size += len(line)

    if buffer:
        chunks.append("".join(buffer).strip())

    return chunks


def snippet_key(file_uuid: str, idx: int | None = None, total: int | None = None) -> str:
    if idx is None or total is None:
        return file_uuid
    return f"{file_uuid}#chunk_{idx:02d}of{total:02d}"


class IngestFolderArgs(BaseModel):
    input_dir: str = Field(..., description="Diretório com arquivos .docx (recursivo)")
    output_dir: str = Field(..., description="Diretório para saída dos .json")

    upload_to_asimov: bool = True
    snippet_chunk_chars: int = 3500
    max_snippets_per_request: int = 30


class IngestFolderTool(BaseTool):
    name: str = "ingest_folder_tool"
    description: str = (
        "Extrai texto de arquivos .docx, grava JSON localmente "
        "e opcionalmente envia snippets para o Asimov."
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
            }

        ensure_dir(out_path)

        snippet_chunk_chars = max(int(snippet_chunk_chars), 1)
        max_snippets_per_request = min(max(int(max_snippets_per_request), 1), 30)

        asimov = AsimovClient.from_env()
        can_upload = upload_to_asimov and asimov.enabled and asimov.is_configured()

        warnings: list[str] = []
        outputs: list[str] = []
        uploaded_snippets = 0

        if can_upload:
            ensured = asimov.ensure_dataset()
            if not ensured.get("ok"):
                warnings.append(f"asimov_ensure_dataset_failed:{ensured}")
            elif ensured.get("created"):
                warnings.append(
                    f"asimov_dataset_created:{ensured.get('dataset_name')}"
                )

        batch: list[dict[str, str]] = []

        def flush_batch() -> None:
            nonlocal uploaded_snippets
            if not batch:
                return
            res = asimov.upload_snippets(batch)
            if res.get("ok"):
                uploaded_snippets += res.get("sent_items", len(batch))
            else:
                warnings.append(f"upload_snippets_failed:{res}")
            batch.clear()

        for file in sorted(in_path.rglob("*.docx")):
            try:                
                text = read_docx_text(file)
                if not text:
                    warnings.append(f"empty_text:{file.name}")
                    continue

                file_already_processed = False
                for json_file in sorted(out_path.rglob("*.json")):
                    try:
                        json_data = json.loads(json_file.read_text(encoding="utf-8"))
                        
                        if json_data.get("file_name") == str(file.name):
                            outputs.append(str(json_file))
                            file_already_processed = True
                            break
                    except (json.JSONDecodeError, KeyError, Exception) as exc:
                        continue
            
                if file_already_processed:
                    continue
            
                file_uuid = str(uuid.uuid4())

                payload = {
                    "uuid": file_uuid,
                    "source_file": str(file),
                    "file_name": file.name,
                    "text": text,
                }

                out_file = out_path / f"{file_uuid}.json"
                out_file.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                outputs.append(str(out_file))

                if not can_upload:
                    continue

                chunks = chunk_text(text, snippet_chunk_chars)
                total = len(chunks)

                for idx, chunk in enumerate(chunks, start=1):
                    batch.append({
                        "key": snippet_key(file_uuid, idx, total) if total > 1 else file_uuid,
                        "content": chunk,
                    })

                    if len(batch) >= max_snippets_per_request:
                        flush_batch()

            except Exception as exc:
                warnings.append(f"failed:{file.name}:{exc}")

        if can_upload:
            flush_batch()
            if uploaded_snippets == 0:
                warnings.append("asimov_upload_warning:0_snippets_uploaded")
        else:
            warnings.append("asimov_skipped:disabled_or_not_configured")

        return {
            "ok": True,
            "input_files": len(list(in_path.rglob('*.docx'))),
            "output_files": len(outputs),
            "uploaded_snippets": uploaded_snippets,
            "outputs": outputs,
            "warnings": warnings,
        }


ingest_folder_tool = IngestFolderTool()
