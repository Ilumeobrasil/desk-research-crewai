# tools.py
from __future__ import annotations

import os
import datetime as dt
from typing import Any, Dict, List, Optional, Union

import requests
from crewai.tools import BaseTool
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from desk_research.utils.makelog.makeLog import make_log


load_dotenv()


def _log(msg: str) -> None:
    print(f"[SocialNetworkXSearchTool] {msg}")


class TwitterSearchToolInput(BaseModel):
    """Input schema for SocialNetworkXSearchTool."""

    query: str = Field(..., description="A query de busca (tema ou keywords)")
    max_results: Optional[Union[int, str]] = Field(
        None, description="Número máximo de tweets"
    )
    days_window: Optional[Union[int, str]] = Field(
        None, description="Janela de dias para busca (ex: 7)"
    )
    min_engagement: Optional[Union[int, str]] = Field(
        None, description="Mínimo de engajamento (likes+retweets)"
    )


class SocialNetworkXSearchTool(BaseTool):
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
                if max_results is not None:
                    max_results = int(max_results)
                if days_window is not None:
                    days_window = int(days_window)
                if min_engagement is not None:
                    min_engagement = int(min_engagement)
            except ValueError:
                _log("Warning: Invalid number format in arguments. Using defaults.")
                max_results = None
                days_window = None
                min_engagement = None

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
                min_engagement=0,
                language=language,
            )
        except Exception as e:
            _log(f"CRITICAL ERROR in _run: {e}")
            return [{"error": str(e)}]

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

        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        end_time = now - dt.timedelta(seconds=15)
        start_time = now - dt.timedelta(days=days_window) + dt.timedelta(seconds=5)
        # start_time = now - dt.timedelta(days=max_days) + dt.timedelta(seconds=5)

        print(f"start_time: {start_time}")
        print(f"end_time: {end_time}")

        # A API nova do X usa api.x.com; a antiga, api.twitter.com.
        # Para PoC, qualquer um dos dois domínios pode ser ajustado pelos devs.
        url = "https://api.twitter.com/2/tweets/search/all"
        # url = "https://api.twitter.com/2/tweets/search/recent"

        headers = {
            "Authorization": f"Bearer {bearer}",
        }

        # Construção simples de query (você pode enriquecer depois)
        # full_query = f"{query} lang:{language}"
        full_query = f"""{query} has:links -is:retweet lang:pt"""

        start_time_str = (
            start_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
        end_time_str = (
            end_time.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )

        params = {
            "query": full_query,
            "max_results": 10,#max_results,
            "tweet.fields": "created_at,public_metrics,lang",
        }

        resp = requests.get(url, headers=headers, params=params, timeout=30)

        make_log(
            {
                "logName": query,
                "content": {
                    "start_time": start_time_str,
                    "end_time": end_time_str,
                    "full_query": full_query,
                    "max_results": max_results,
                    "resp": resp.json(),
                },
            }
        )
        if resp.status_code == 429:
            reset = resp.headers.get("x-rate-limit-reset")
            print(f"reset: {reset}")
            _log("Rate limit atingido.")
            return []

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
twitter_search_tool = SocialNetworkXSearchTool()
