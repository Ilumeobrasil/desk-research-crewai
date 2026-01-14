from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type

from crewai.tools import BaseTool
from docx import Document
from pydantic import BaseModel, Field

from desk_research.tools.asimov_client import AsimovClient


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


def _safe_stem(name: str) -> str:
    """Normaliza nome de arquivo para ser seguro em Windows e consistente no output."""
    keep = []
    for ch in name:
        if ch.isalnum() or ch in ("-", "_", " "):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip().replace(" ", "_")


def _rel_source_key(input_root: Path, fp: Path, chunk_idx: int | None = None, chunks_total: int | None = None) -> str:
    """
    Gera uma key estável para o Asimov Snippet:
      <pasta_relativa>/<nome_arquivo>.docx#chunk_XXofYY

    Se não houver chunk, retorna apenas o caminho relativo do arquivo.
    """
    try:
        rel = fp.relative_to(input_root).as_posix()
    except Exception:
        rel = fp.name

    if chunk_idx is None or chunks_total is None:
        return rel

    return f"{rel}#chunk_{chunk_idx:02d}of{chunks_total:02d}"


def _chunk_text(text: str, max_chars: int) -> list[str]:
    """Chunking simples por tamanho, tentando respeitar quebras de linha."""
    text = (text or "").strip()
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    lines = text.splitlines()

    buf: list[str] = []
    size = 0

    for line in lines:
        line = line.rstrip()
        add = line + "\n"
        if size + len(add) > max_chars and buf:
            chunks.append("".join(buf).strip())
            buf = []
            size = 0
        buf.append(add)
        size += len(add)

    if buf:
        chunks.append("".join(buf).strip())

    # fallback extremo (linha gigante sem \n)
    final: list[str] = []
    for ch in chunks:
        if len(ch) <= max_chars:
            final.append(ch)
        else:
            start = 0
            while start < len(ch):
                end = min(start + max_chars, len(ch))
                final.append(ch[start:end].strip())
                start = end

    return [c for c in final if c]


class IngestFolderArgs(BaseModel):
    input_dir: str = Field(..., description="Diretório de entrada contendo arquivos .docx (recursivo)")
    output_dir: str = Field(..., description="Diretório de saída para gravar arquivos .json")

    upload_to_asimov: bool = Field(
        default=True,
        description="Se true, envia o conteúdo extraído para o Asimov via SNIPPETS (content_list + dataset).",
    )

    snippet_chunk_chars: int = Field(
        default=3500,
        description="Tamanho máximo (chars) por snippet. Útil para documentos grandes.",
    )

    max_snippets_per_request: int = Field(
        default=30,
        description="Tamanho do batch por request no endpoint /snippets. No Asimov atual o limite é 30.",
    )


class IngestFolderTool(BaseTool):
    name: str = "ingest_folder_tool"
    description: str = (
        "Lê arquivos .docx em um diretório (recursivo), extrai texto e escreve arquivos .json no diretório de saída. "
        "Opcionalmente envia o texto extraído para o Asimov via SNIPPETS (content_list + dataset)."
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

        warnings: list[str] = []
        outputs: list[str] = []

        uploaded_snippets = 0

        if not in_path.exists():
            return {
                "ok": False,
                "reason": f"input_dir_not_found:{in_path}",
                "input_dir": str(in_path),
                "output_dir": str(out_path),
            }

        _ensure_dir(out_path)
        docx_files = sorted(in_path.rglob("*.docx"))

        asimov = AsimovClient.from_env()

        # clamp defensivo (se alguém passar 200 de novo, não estoura)
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

        # 1) Garante dataset (se for subir pro Asimov)
        if upload_to_asimov and asimov.enabled and asimov.is_configured():
            ensured = asimov.ensure_dataset()
            if not ensured.get("ok"):
                warnings.append(f"asimov_ensure_dataset_failed:{ensured}")
            else:
                if ensured.get("created"):
                    warnings.append(
                        f"asimov_dataset_created:name={ensured.get('dataset_name')} uuid={ensured.get('dataset_uuid')}"
                    )

        def _flush(batch: list[dict[str, str]]) -> None:
            nonlocal uploaded_snippets, warnings
            if not batch:
                return

            up = asimov.upload_snippets(batch)
            if up.get("ok") is True:
                uploaded_snippets += int(up.get("sent_items") or len(batch))
            else:
                warnings.append(
                    f"upload_snippets_failed:status={up.get('status')} body={str(up.get('json') or up.get('text'))[:800]}"
                )

        batch: list[dict[str, str]] = []

        for fp in docx_files:
            try:
                text = _read_docx_text(fp)
                if not text:
                    warnings.append(f"empty_text:{fp.name}")
                    continue

                # JSON local (sempre)
                payload = {"source_file": str(fp), "file_name": fp.name, "text": text}
                out_fp = out_path / (_safe_stem(fp.stem) + ".json")
                out_fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                outputs.append(str(out_fp))

                # 2) Upload para Asimov (via SNIPPETS)
                if upload_to_asimov and asimov.enabled and asimov.is_configured():
                    chunks = _chunk_text(text, max_chars=snippet_chunk_chars)
                    if not chunks:
                        warnings.append(f"no_chunks:{fp.name}")
                        continue

                    total = len(chunks)
                    for idx, chunk in enumerate(chunks, start=1):
                        key = _rel_source_key(in_path, fp, idx, total) if total > 1 else _rel_source_key(in_path, fp)
                        batch.append({"key": key, "content": chunk})

                        if len(batch) >= max_snippets_per_request:
                            _flush(batch)
                            batch = []

            except Exception as e:
                warnings.append(f"failed:{fp.name}:{e}")

        # flush final
        if upload_to_asimov and asimov.enabled and asimov.is_configured():
            _flush(batch)

        # warning útil (sem “falso positivo”)
        if upload_to_asimov and asimov.enabled and asimov.is_configured():
            if uploaded_snippets == 0:
                warnings.append("asimov_upload_warning:0_snippets_uploaded (verifique ASIMOV_* e endpoint /api/application/snippets)")
        else:
            warnings.append("asimov_skipped:disabled_or_not_configured")

        return {
            "ok": True,
            "input_dir": str(in_path),
            "output_dir": str(out_path),
            "input_files": len(docx_files),
            "output_files": len(outputs),
            "outputs": outputs,
            "uploaded_snippets": uploaded_snippets,
            "warnings": warnings,
        }


ingest_folder_tool = IngestFolderTool()
