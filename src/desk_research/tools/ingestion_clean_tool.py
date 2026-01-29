from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from docx import Document
from pydantic import BaseModel, Field

# Padrões de limpeza combinados
CLEANING_PATTERNS = [
    (r'\s+', ' '),
    (r'\*\*(.*?)\*\*', r'\1'),
    (r'\*(.*?)\*', r'\1'),
    (r'`(.*?)`', r'\1'),
    (r'\?{2,}', '?'),
    (r'\n{3,}', '\n\n'),
    (r'!{3,}', '!'),
    (r'\.{3,}', '...'),
    (r'\([0-9:]+ - [0-9:]+\)\s*', ''),
    (r' {2,}', ' '),
]

CLEANING_REPLACES = {
    '"': '"', '"': '"', ''': "'", ''': "'",
    '—': '-', '–': '-', '': '',
    'nao': 'não', 'voce': 'você', 'pra': 'para',
}


def _read_docx(fp: Path) -> str:
    doc = Document(str(fp))
    return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip()).strip()


def _clean_text(text: str) -> str:
    if not text:
        return ""
    
    t = text.strip()
    for pattern, repl in CLEANING_PATTERNS:
        t = re.sub(pattern, repl, t)
    for old, new in CLEANING_REPLACES.items():
        t = t.replace(old, new)
    
    return t.strip()


def _is_processed(file_name: str, output_dir: Path) -> str | None:
    for json_file in output_dir.rglob("*.json"):
        try:
            if json.loads(json_file.read_text(encoding="utf-8")).get("file_name") == file_name:
                return str(json_file)
        except Exception:
            continue
    return None


def _process_file(fp: Path, output_dir: Path, warnings: list[str]) -> str | None:
    """Processa um arquivo: extrai, limpa e salva JSON."""
    if existing := _is_processed(fp.name, output_dir):
        return existing
    
    text = _read_docx(fp)
    if not text:
        warnings.append(f"empty_text:{fp.name}")
        return None
    
    cleaned = _clean_text(text)
    if not cleaned:
        warnings.append(f"empty_after_cleaning:{fp.name}")
        return None
    
    file_uuid = str(uuid.uuid4())
    
    payload = {
        "uuid": file_uuid,
        "source_file": str(fp),
        "file_name": fp.name,
        "text": cleaned,
    }
    
    out_fp = output_dir / f"{file_uuid}.json"
    out_fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_fp)


class IngestCleanFolderArgs(BaseModel):
    input_dir: str = Field(..., description="Diretório de entrada contendo entrevistas (recursivo).")
    output_dir: str = Field(..., description="Diretório de saída para gravar JSONs do ingestor com texto limpo.")


class IngestCleanFolderTool(BaseTool):
    name: str = "ingest_clean_folder_tool"
    description: str = (
        "Lê entrevistas (docx), extrai texto, aplica limpeza rigorosa "
        "removendo artefatos e resquícios desnecessários e gera JSONs estruturados."
    )
    args_schema: Type[BaseModel] = IngestCleanFolderArgs
    
    def _run(self, input_dir: str, output_dir: str) -> dict[str, Any]:
        in_path = Path(input_dir)
        out_path = Path(output_dir)
        
        if not in_path.exists():
            return {"ok": False, "reason": f"input_dir_not_found:{in_path}"}
        
        out_path.mkdir(parents=True, exist_ok=True)
        
        input_files = sorted([p for p in in_path.rglob("*.docx") if p.is_file()])
        
        warnings: list[str] = []
        outputs: list[str] = []
        
        for fp in input_files:
            try:
                if result := _process_file(fp, out_path, warnings):
                    outputs.append(result)
            except Exception as e:
                warnings.append(f"failed:{fp.name}:{e}")
        
        return {
            "ok": True,
            "input_dir": str(in_path),
            "output_dir": str(out_path),
            "input_files": len(input_files),
            "output_files": len(outputs),
            "outputs": outputs,
            "warnings": warnings,
        }


ingest_clean_folder_tool = IngestCleanFolderTool()
