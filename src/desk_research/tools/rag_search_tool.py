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
        "que foram usados como contexto para gerar a resposta, incluindo informações estruturadas "
        "como citações, perguntas, informações demográficas, marcas mencionadas e insights."
    )
    args_schema: Type[BaseModel] = RAGSearchArgs

    def _parse_snippet_content(self, content: str) -> dict:
        """Tenta fazer parse do conteúdo do snippet (JSON estruturado)."""
        try:
            return json.loads(content)
        except:
            return {"raw_content": content}

    def _format_snippet_info(self, snippet: dict, idx: int) -> str:
        """Formata informações estruturadas de um snippet."""
        similarity = snippet.get("similarity", 0)
        content = snippet.get("content", "")
        
        # Tentar fazer parse do conteúdo (pode ser JSON estruturado)
        parsed = self._parse_snippet_content(content)
        
        # Se for chunk de metadados
        if "uuid" in parsed and "total_citacoes" in parsed:
            return (
                f"\n--- Snippet {idx} (METADADOS - similaridade: {similarity:.3f}) ---\n"
                f"Arquivo: {parsed.get('file_name', 'N/A')}\n"
                f"UUID: {parsed.get('uuid', 'N/A')}\n"
                f"Total de citações: {parsed.get('total_citacoes', 0)}\n"
                f"Data de extração: {parsed.get('data_extracao', 'N/A')}\n"
            )
        
        # Se for chunk de citação
        if "citacao" in parsed:
            quota = parsed.get("quota", {})
            marcas = parsed.get("marcaMencionada", [])
            
            info = (
                f"\n--- Snippet {idx} (CITAÇÃO - similaridade: {similarity:.3f}) ---\n"
            )
            
            # Informações demográficas
            if quota:
                nome = quota.get("nome", "Não informado")
                idade = quota.get("idade", "Não informado")
                regiao = quota.get("regiao", "Não informado")
                classe = quota.get("classeSocial", "Não informado")
                info += f"Participante: {nome} ({idade}) - {regiao} - Classe {classe}\n"
            
            # Data da entrevista
            if parsed.get("dataEntrevista"):
                info += f"Data da entrevista: {parsed.get('dataEntrevista')}\n"
            
            # Marcas mencionadas
            if marcas:
                info += f"Marcas mencionadas: {', '.join(marcas)}\n"
            
            # Pergunta
            pergunta = parsed.get("pergunta", "")
            if pergunta and pergunta != "Não identificada":
                info += f"Pergunta: {pergunta}\n"
            
            # Citação
            info += f"Citação: {parsed.get('citacao', '')}\n"
            
            # Insight
            insight = parsed.get("insight", "")
            if insight:
                info += f"Insight: {insight}\n"
            
            return info
        
        # Fallback: conteúdo raw
        return (
            f"\n--- Snippet {idx} (similaridade: {similarity:.3f}) ---\n"
            f"{content}\n"
        )

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

            # Prompt melhorado para aproveitar a estrutura dos snippets
            prompt_template = (
                "Você é um analista especializado em entrevistas qualitativas do Consumer Hours. "
                "Baseado nas informações estruturadas abaixo (citações de entrevistas com metadados), "
                "responda a pergunta de forma precisa e detalhada.\n\n"
                "Cada snippet pode conter:\n"
                "- Citações literais dos participantes\n"
                "- Informações demográficas (nome, idade, região, classe social)\n"
                "- Marcas mencionadas\n"
                "- Perguntas que geraram as respostas\n"
                "- Insights extraídos\n"
                "- Datas das entrevistas\n\n"
                "Use essas informações estruturadas para dar uma resposta completa e fundamentada. "
                "Sempre cite as informações demográficas e marcas quando relevante. "
                "Se não souber, diga que não tem informação suficiente.\n\n"
                "Informações estruturadas: {context}\n\n"
                "Pergunta: {query}\n\n"
                "Resposta detalhada:"
            )

            messages = [
                {
                    "role": "system",
                    "content": (
                        "Você é um analista especializado em entrevistas qualitativas de Consumer Hours. "
                        "Você analisa citações estruturadas com informações demográficas, marcas mencionadas, "
                        "perguntas e insights para responder perguntas sobre comportamento do consumidor, "
                        "percepções de marcas, preferências e tendências."
                    )
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
                
                response_text = (
                    f"RESPOSTA DO RAG:\n{content}\n\n"
                    f"SNIPPETS USADOS COMO CONTEXTO ({len(snippets)} snippets encontrados):"
                )
                
                for idx, snippet in enumerate(snippets, 1):
                    response_text += self._format_snippet_info(snippet, idx)
                
                if usage:
                    response_text += (
                        f"\n\nUSO DE TOKENS: "
                        f"{usage.get('total_tokens', 'N/A')} tokens totais "
                        f"({usage.get('prompt_tokens', 'N/A')} prompt + "
                        f"{usage.get('completion_tokens', 'N/A')} completion)"
                    )
                
                return response_text
            else:
                error_msg = result.get("error") or result.get("reason", "Erro desconhecido")
                return f"Erro na busca RAG: {error_msg}"

        except Exception as e:
            return f"Erro ao executar busca RAG: {str(e)}"


rag_search_tool = RAGSearchTool()

