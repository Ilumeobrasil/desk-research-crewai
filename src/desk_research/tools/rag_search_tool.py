from __future__ import annotations

import json
import os
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from desk_research.tools.rag_tools import get_rag_from_env
from desk_research.tools.asimov_client import AsimovClient
from desk_research.utils.makelog.makeLog import make_log


class RAGSearchArgs(BaseModel):
    query: str = Field(..., description="Pergunta ou query para buscar no RAG.")
    dataset: str = Field(
        default="",
        description="Nome do dataset no Asimov. Se vazio, usa ASIMOV_DATASET do ambiente.",
    )
    model: str = Field(
        default="openai/gpt-4o",
        description="Modelo a ser usado para a busca RAG.",
    )
    temperature: float = Field(
        default=0.3,
        description="Temperatura para a geração (0.0 a 1.0).",
    )
    max_tokens: int = Field(
        default=2000,
        description="Número máximo de tokens na resposta.",
    )


class RAGSearchTool(BaseTool):
    name: str = "rag_search_tool"
    description: str = (
        "Busca informações no RAG do Asimov usando completion_with_context. "
        "Use esta ferramenta para fazer perguntas sobre os dados das entrevistas Consumer Hours "
        "que foram processadas e indexadas no Asimov. "
        "A ferramenta retorna a resposta do modelo e os snippets (trechos das entrevistas) "
        "que foram usados como contexto para gerar a resposta."
    )
    args_schema: Type[BaseModel] = RAGSearchArgs

    def _run(
        self,
        query: str,
        dataset: str = "",
        model: str = "openai/gpt-4o",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> str:
        try:
            rag = get_rag_from_env()
            
            if not dataset:
                asimov_client = AsimovClient.from_env()
                dataset = asimov_client.dataset or ""
            
            if not dataset:
                return json.dumps({
                    "ok": False,
                    "error": "Dataset não fornecido e ASIMOV_DATASET não configurado no ambiente."
                }, ensure_ascii=False)

            prompt_template = (
                "Baseado nas informações abaixo, responda a pergunta. "
                "Traga o trecho real da entrevista que contém a afirmação."
                "Se não souber, diga que não tem informação suficiente.\n\n"
                "Informações: {context}\n\n"
                "Pergunta: {query}\n\n"
                "Resposta:"
            )

            messages = [
                {
                    "role": "system",
                    "content": "Você é um assistente que responde perguntas baseadas nas informações de contexto fornecidas."
                },
                {
                    "role": "user",
                    "content": query
                }
            ]


            result = rag.completion_with_context(
                messages=messages,
                dataset=dataset,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_template=prompt_template,
                poll_attempts=10,
                poll_sleep_s=2.0,
            )

            if result.get("ok"):
                content = result.get("content", "")
                result_json = result.get("result_json", {})
                snippets = result_json.get("snippets", [])
                usage = result_json.get("usage", {})
                
                response_text = f"""RESPOSTA DO RAG: {content} SNIPPETS USADOS COMO CONTEXTO ({len(snippets)} snippets encontrados):"""
                for idx, snippet in enumerate(snippets, 1):
                    similarity = snippet.get("similarity", 0)
                    snippet_content = snippet.get("content", "")
                    response_text += f"\n--- Snippet {idx} (similaridade: {similarity:.3f}) ---\n{snippet_content}\n"
                
                if usage:
                    response_text += f"\nUSO DE TOKENS: {usage.get('total_tokens', 'N/A')} tokens totais"
                
                return response_text
            else:
                error_msg = result.get("error") or result.get("reason", "Erro desconhecido")
                return f"Erro na busca RAG: {error_msg}"

        except Exception as e:
            return f"Erro ao executar busca RAG: {str(e)}"


rag_search_tool = RAGSearchTool()

