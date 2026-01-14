# tools.py
from __future__ import annotations

import os
import datetime as dt
from typing import Any, Dict, List, Optional, Union

import requests
from crewai.tools import BaseTool
from dotenv import load_dotenv

load_dotenv()


def _log(msg: str) -> None:
    print(f"[TwitterSearchTool] {msg}")


from pydantic import BaseModel, Field

class TwitterSearchToolInput(BaseModel):
    """Input schema for TwitterSearchTool."""
    query: str = Field(..., description="A query de busca (tema ou keywords)")
    max_results: Optional[Union[int, str]] = Field(None, description="Número máximo de tweets")
    days_window: Optional[Union[int, str]] = Field(None, description="Janela de dias para busca (ex: 7)")
    min_engagement: Optional[Union[int, str]] = Field(None, description="Mínimo de engajamento (likes+retweets)")

class TwitterSearchTool(BaseTool):
    """
    Tool de busca no X (Twitter).

    - Usa TWITTER_BEARER_TOKEN quando TWITTER_STUB_MODE=false.
    - Quando TWITTER_STUB_MODE=true ou não há token, retorna dados de EXEMPLO (stub).
    """

    name: str = "twitter_search_tool"
    description: str = (
        "Busca tweets relevantes sobre um tema no X (Twitter), aplicando filtros de "
        "data (janela em dias), idioma e engajamento mínimo. "
        "Retorna uma lista de tweets em formato JSON padronizado."
    )
    args_schema: type[BaseModel] = TwitterSearchToolInput

    def _run(
        self,
        query: str,
        max_results: Optional[Union[int, str]] = None,
        days_window: Optional[Union[int, str]] = None,
        min_engagement: Optional[Union[int, str]] = None,
        language: str = "pt",
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        try:
            bearer = os.getenv("TWITTER_BEARER_TOKEN")
            stub_mode = os.getenv("TWITTER_STUB_MODE", "true").lower() == "true"

            # Cast arguments safely if they come as strings
            try:
                if max_results is not None: max_results = int(max_results)
                if days_window is not None: days_window = int(days_window)
                if min_engagement is not None: min_engagement = int(min_engagement)
            except ValueError:
                 _log("Warning: Invalid number format in arguments. Using defaults.")
                 max_results = None
                 days_window = None
                 min_engagement = None

            # Defaults alinhados com .env
            if max_results is None:
                max_results = int(os.getenv("TWITTER_MAX_TWEETS", "30"))
            if days_window is None:
                days_window = int(os.getenv("TWITTER_DAYS_WINDOW", "3"))
            if min_engagement is None:
                min_engagement = int(os.getenv("TWITTER_MIN_ENGAGEMENT", "5"))

            # Se não temos token ou stub_mode está ligado, devolve dados de exemplo
            if not bearer or stub_mode:
                _log(
                    f"(STUB) query={query!r}, max_results={max_results}, "
                    f"days_window={days_window}, min_engagement={min_engagement}, "
                    f"language={language}"
                )
                return self._fake_results(query)

            # Caso contrário, chama a API real do X
            _log(
                f"query={query!r}, max_results={max_results}, "
                f"days_window={days_window}, min_engagement={min_engagement}, "
                f"language={language}"
            )
            return self._call_twitter_api(
                bearer=bearer,
                query=query,
                max_results=max_results,
                days_window=days_window,
                min_engagement=min_engagement,
                language=language,
            )
        except Exception as e:
            _log(f"CRITICAL ERROR in _run: {e}")
            return [{"error": str(e)}]

    # ---------------------------
    # Implementação STUB
    # ---------------------------

    def _fake_results(self, query: str) -> List[Dict[str, Any]]:
        """
        Retorna uma lista de tweets fake, no mesmo formato que a API real.
        Útil para desenvolvimento, testes e demonstrações.
        """
        now = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        return [
            {
                "id": "1001",
                "text": f"Gente, parei de beber tanto álcool recentemente e tô me sentindo bem melhor. #saude #{query.split()[0] if query else 'trend'}",
                "author": "@fitness_lover",
                "created_at": now,
                "language": "pt",
                "metrics": {"likes": 120, "retweets": 45, "replies": 12, "quotes": 5},
                "tags": ["lifestyle", "positive"],
            },
            {
                "id": "1002",
                "text": f"Sinceramente, cerveja sem álcool tá cada vez melhor. Provei uma ontem que era idêntica à normal. {query}",
                "author": "@cervejeiro_fake",
                "created_at": now,
                "language": "pt",
                "metrics": {"likes": 89, "retweets": 20, "replies": 30, "quotes": 2},
                "tags": ["product", "positive"],
            },
            {
                "id": "1003",
                "text": f"Saio com os amigos e só vejo gente pedindo drink sem álcool ou refrigerante. O mundo tá chato ou a gente tá velho? {query}",
                "author": "@baladeiro_old",
                "created_at": now,
                "language": "pt",
                "metrics": {"likes": 200, "retweets": 80, "replies": 150, "quotes": 10},
                "tags": ["social", "negative"],
            },
            {
                "id": "1004",
                "text": f"Alguém sabe se a nova {query} tem muito açúcar? Tô evitando álcool mas não quero diabetes.",
                "author": "@health_freak",
                "created_at": now,
                "language": "pt",
                "metrics": {"likes": 15, "retweets": 2, "replies": 5, "quotes": 0},
                "tags": ["question", "neutral"],
            },
            {
                "id": "1005",
                "text": f"A indústria tá forçando essa barra de 'menos álcool'. Eu quero é cerveja de verdade! #volta{query}",
                "author": "@hater_raiz",
                "created_at": now,
                "language": "pt",
                "metrics": {"likes": 50, "retweets": 10, "replies": 40, "quotes": 20},
                "tags": ["complaint", "negative"],
            }
        ]

    # ---------------------------
    # Implementação real (API X)
    # ---------------------------

    def _call_twitter_api(
        self,
        bearer: str,
        query: str,
        max_results: int,
        days_window: int,
        min_engagement: int,
        language: str,
    ) -> List[Dict[str, Any]]:
        """
        Chama a API de busca recente do X.

        Simplificado para PoC: não trata paginação em profundidade, apenas uma página.
        """
        # Ajusta a janela de datas
        end_time = dt.datetime.utcnow()
        start_time = end_time - dt.timedelta(days=days_window)

        # A API nova do X usa api.x.com; a antiga, api.twitter.com.
        # Para PoC, qualquer um dos dois domínios pode ser ajustado pelos devs.
        url = "https://api.x.com/2/tweets/search/recent"

        headers = {
            "Authorization": f"Bearer {bearer}",
        }

        # Construção simples de query (você pode enriquecer depois)
        full_query = f"{query} lang:{language}"

        params = {
            "query": full_query,
            "max_results": max_results,
            "start_time": start_time.replace(microsecond=0).isoformat() + "Z",
            "end_time": end_time.replace(microsecond=0).isoformat() + "Z",
            "tweet.fields": "created_at,public_metrics,lang,author_id",
        }

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            _log(f"ERRO API Twitter: {resp.status_code} - {resp.text}")
            return []

        data = resp.json()
        tweets = data.get("data", [])

        results: List[Dict[str, Any]] = []
        for t in tweets:
            metrics = t.get("public_metrics", {}) or {}
            engagement = (
                metrics.get("like_count", 0)
                + metrics.get("retweet_count", 0)
                + metrics.get("reply_count", 0)
                + metrics.get("quote_count", 0)
            )
            if engagement < min_engagement:
                continue

            results.append(
                {
                    "id": t.get("id"),
                    "text": t.get("text", ""),
                    "author": t.get("author_id", ""),
                    "created_at": t.get("created_at"),
                    "language": t.get("lang", ""),
                    "metrics": {
                        "likes": metrics.get("like_count", 0),
                        "retweets": metrics.get("retweet_count", 0),
                        "replies": metrics.get("reply_count", 0),
                        "quotes": metrics.get("quote_count", 0),
                    },
                    "tags": [],
                }
            )

        return results


# Instância pronta para uso nos agentes
twitter_search_tool = TwitterSearchTool()
