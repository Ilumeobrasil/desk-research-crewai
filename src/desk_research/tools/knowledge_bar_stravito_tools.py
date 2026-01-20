from __future__ import annotations

import os
import time
from typing import Any, ClassVar, Dict, List

import requests
from crewai.tools import BaseTool
from desk_research.utils.makelog.makeLog import make_log
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

def _log(msg: str) -> None:
    print(f"[KnowledgeBarStravitoTool] {msg}")

def format_response(result: Dict[str, Any]) -> str:
    if "error" in result:
        return f"❌ Erro: {result['error']}"
    
    output = []
    output.append("=" * 60)
    output.append("RESPOSTA:")
    output.append("=" * 60)
    output.append(result.get("answer", ""))
    output.append("")
    
    sources = result.get("sources", [])
    if sources:
        output.append("=" * 60)
        output.append("FONTES:")
        output.append("=" * 60)
        for i, source in enumerate(sources, 1):
            title = source.get("title", "Sem título")
            url = source.get("url", "")
            page = source.get("pageNumber")
            output.append(f"{i}. {title}")
            if url:
                output.append(f"   URL: {url}")
            if page:
                output.append(f"   Página: {page}")
            output.append("")
    
    follow_ups = result.get("followUps", [])
    if follow_ups:
        output.append("=" * 60)
        output.append("SUGESTÕES DE ACOMPANHAMENTO:")
        output.append("=" * 60)
        for i, follow_up in enumerate(follow_ups, 1):
            output.append(f"{i}. {follow_up}")
        output.append("")
    
    make_log({
        'content': {
            'resultado': output,
        },
        'logName': 'format_response_knowledge_bar_stravito_tool'
    })
    return "\n".join(output)

class KnowledgeBarStravitoToolInput(BaseModel):
    query: str = Field(..., description="A query de busca (tema ou keywords)")

class KnowledgeBarStravitoTool(BaseTool):
    name: str = "knowledge_bar_stravito_tool"
    description: str = (
        "Busca artigos da Knowledge Bar Stravito sobre um tema ou keywords"
    )
    args_schema: type[BaseModel] = KnowledgeBarStravitoToolInput

    BASE_URL: ClassVar[str] = os.getenv("STRAVITO_BASE_URL").strip()

    if BASE_URL and not BASE_URL.endswith("/assistant"):
        if BASE_URL.endswith("/"):
            BASE_URL = BASE_URL.rstrip("/") + "/assistant"
        else:
            BASE_URL = BASE_URL + "/assistant"

    API_KEY: ClassVar[str] = os.getenv("STRAVITO_API_KEY").strip()
    HEADERS: ClassVar[Dict[str, str]] = {
        "x-api-key": API_KEY,
        "Content-Type": "application/json"
    }

    def _run(
        self,
        query: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        try:
            message_id, conversation_id = self.post(query)
            resultado = self.get(conversation_id, message_id)

            #format_response(resultado)
            
            return resultado
        except Exception as e:
            _log(f"CRITICAL ERROR in _run: {e}")
            return {"error": f"Erro ao executar pesquisa: {str(e)}"}

    def post(self, query: str):
        try:
            url = f"{self.BASE_URL}/conversations"
            payload = {"message": query}

            _log(f"[Info] Enviando pergunta: {query[:50]}..." if len(query) > 50 else f"[Info] Enviando pergunta: {query}")

            post_resp = requests.post(url, headers=self.HEADERS, json=payload)
            post_resp.raise_for_status()

            data_init = post_resp.json()
            conversation_id = data_init.get("conversationId")
            message_id = data_init.get("messageId")

            return message_id, conversation_id
        except requests.exceptions.HTTPError as e:
            error_msg = f"Erro ao criar conversa: {str(e)}"
            if hasattr(e.response, 'text'):
                error_msg += f"\nDetalhes: {e.response.text}"
            raise Exception(error_msg)
        except requests.RequestException as e:
            raise Exception(f"Erro de conexão: {str(e)}")

    def get(self, conversation_id: str, message_id: str, max_retries: int = 30, sleep_sec: int = 2):
        get_url = f"{self.BASE_URL}/conversations/{conversation_id}/messages/{message_id}"

        for attempt in range(max_retries):
            try:
                get_resp = requests.get(get_url, headers=self.HEADERS)
                get_resp.raise_for_status()
                
                data_msg = get_resp.json()
                state = data_msg.get("state")
                
                if state == "COMPLETED":
                    answer = data_msg.get("message", "")
                    sources = data_msg.get("sources", [])
                    follow_ups = data_msg.get("followUps", [])
                    
                    print(f"[Info] Resposta recebida com sucesso!")
                    
                    return {
                        "answer": answer,
                        "sources": sources,
                        "followUps": follow_ups,
                        "conversation_id": conversation_id,
                        "message_id": message_id
                    }
                
                elif state == "ERROR":
                    error_detail = data_msg.get("message", "Erro desconhecido")
                    return {"error": f"Erro no processamento: {error_detail}"}
                
                elif state == "IN_PROGRESS":
                    if attempt % 5 == 0:
                        print(f"[Info] Processando... (tentativa {attempt + 1}/{max_retries})")
                    time.sleep(sleep_sec)
                else:
                    print(f"[Warning] Estado desconhecido: {state}")
                    time.sleep(sleep_sec)
                    
            except requests.exceptions.HTTPError as e:
                return {"error": f"Erro ao buscar resposta: {str(e)}"}
            except requests.RequestException as e:
                return {"error": f"Erro de conexão durante polling: {str(e)}"}
        
        return {"error": f"Timeout: A resposta demorou mais de {max_retries * sleep_sec} segundos para ser gerada."}

knowledge_bar_stravito_tool = KnowledgeBarStravitoTool()
