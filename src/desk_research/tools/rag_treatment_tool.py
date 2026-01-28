from __future__ import annotations

import json
import re
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from desk_research.utils.makelog.makeLog import make_log


def _parse_rag_result(rag_result_text: str) -> dict[str, Any]:
    """Extrai informações estruturadas do resultado do RAG."""
    snippets = []
    interview_uuids = set()
    
    # Extrai resposta do RAG
    answer_match = re.search(r"RESPOSTA DO RAG:\s*(.*?)(?=SNIPPETS|USO DE TOKENS|$)", rag_result_text, re.DOTALL)
    answer = answer_match.group(1).strip() if answer_match else ""
    
    # Extrai snippets do formato retornado pelo rag_search_tool
    snippet_pattern = r"--- Snippet \d+.*?\(similaridade: ([\d.]+)\) ---\n(.*?)(?=\n--- Snippet|\nUSO DE TOKENS|$)"
    matches = re.finditer(snippet_pattern, rag_result_text, re.DOTALL)
    
    for match in matches:
        similarity = float(match.group(1)) if match.group(1) else 0.0
        snippet_content = match.group(2).strip()
        
        # Tenta extrair key do snippet se disponível
        key_match = re.search(r"key[:\s]+([^\s]+)", snippet_content, re.IGNORECASE)
        key = key_match.group(1) if key_match else ""
        
        if key and "#" in key:
            uuid = key.split("#")[0]
            interview_uuids.add(uuid)
        
        snippets.append({
            "content": snippet_content,
            "similarity": similarity,
            "key": key,
        })
    
    # Se não encontrou snippets no formato padrão, tenta extrair de outra forma
    if not snippets:
        # Procura por blocos de texto que parecem snippets
        snippet_blocks = re.split(r"--- Snippet \d+", rag_result_text, flags=re.IGNORECASE)
        for block in snippet_blocks[1:]:  # Pula o primeiro (antes do primeiro snippet)
            content = block.split("---", 1)[0].strip() if "---" in block else block.strip()
            if content and len(content) > 50:  # Snippet deve ter pelo menos 50 caracteres
                snippets.append({
                    "content": content,
                    "similarity": 0.0,
                    "key": "",
                })
    
    return {
        "answer": answer,
        "snippets": snippets,
        "total_snippets": len(snippets),
        "total_interviews": len(interview_uuids),
        "interview_uuids": list(interview_uuids),
    }


class RAGTreatmentArgs(BaseModel):
    rag_search_result: str = Field(..., description="Resultado completo da busca RAG do rag_searcher.")
    topic: str = Field(..., description="Tema do relatório para contextualizar o tratamento.")


class RAGTreatmentTool(BaseTool):
    name: str = "rag_treatment_tool"
    description: str = (
        "Trata e estrutura os dados retornados pelo rag_searcher, consolidando informações, "
        "organizando por temas, marcas, sentimentos e evidências para preparar "
        "o contexto estruturado necessário para o relatório executivo."
    )
    args_schema: Type[BaseModel] = RAGTreatmentArgs

    def _run(
        self,
        rag_search_result: str,
        topic: str,
    ) -> str:
        """
        Trata os dados do RAG, estruturando e consolidando para o writer.
        """
        try:
            parsed = _parse_rag_result(rag_search_result)
                        
            # Estrutura dados tratados
            treated_data = {
                "topic": topic,
                "rag_answer": parsed.get("answer", ""),
                "total_snippets": parsed.get("total_snippets", 0),
                "total_interviews": parsed.get("total_interviews", 0),
                "interview_uuids": parsed.get("interview_uuids", []),
                "snippets": parsed.get("snippets", []),
            }
            
            return json.dumps(treated_data, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "ok": False,
                "error": f"Erro ao tratar dados do RAG: {str(e)}"
            }, ensure_ascii=False)


rag_treatment_tool = RAGTreatmentTool()

