from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

from desk_research.tools.asimov_client import AsimovClient, _safe_json


def _load_env() -> None:
    load_dotenv(override=False)
    load_dotenv(".env.asimov", override=False)


def _get_chat_base() -> str:
    """
    Base do chat (api/v2), conforme orientação do Coradini.
    Normalmente vem do .env (OPENAI_API_BASE).
    """
    _load_env()
    base = (os.getenv("OPENAI_API_BASE") or os.getenv("BASE_URL") or "").strip()
    return base.rstrip("/")


def _get_chat_key() -> str:
    """
    Chave do chat. Normalmente OPENAI_API_KEY no .env.
    """
    _load_env()
    return (os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY") or os.getenv("ASIMOV_API_KEY") or "").strip()


def _chat_headers() -> dict[str, str]:
    k = _get_chat_key()
    # Mantém compat com APIM: tenta enviar também subscription/x-api-key
    return {
        "Authorization": f"Bearer {k}",
        "Ocp-Apim-Subscription-Key": k,
        "x-api-key": k,
        "Content-Type": "application/json",
    }


@dataclass(frozen=True)
class RAG:
    """
    RAG via endpoints de completions (chat).
    """
    client: AsimovClient  # usado para dataset config (ASIMOV_*), se necessário

    def completion_with_context(
        self,
        *,
        messages: list[dict[str, str]],
        dataset: str,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        prompt_template: str | None = None,
        poll_attempts: int = 10,
        poll_sleep_s: float = 2.0,
    ) -> dict[str, Any]:
        chat_base = _get_chat_base()
        if not chat_base:
            return {"ok": False, "reason": "missing_OPENAI_API_BASE"}
        if not _get_chat_key():
            return {"ok": False, "reason": "missing_OPENAI_API_KEY"}

        payload: dict[str, Any] = {
            "messages": messages,
            "model": model,
            "dataset": dataset,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if prompt_template:
            payload["prompt_template"] = prompt_template

        # Step 1: initiate
        resp = requests.post(
            f"{chat_base}/api/completions/context",
            headers=_chat_headers(),
            json=payload,
            timeout=120,
        )

        if resp.status_code not in (200, 201):
            return {"ok": False, "status": resp.status_code, "text": resp.text, "json": _safe_json(resp)}

        init_json = _safe_json(resp) or {}
        uuid = (init_json.get("location", "") or "").split("/")[-1]
        if not uuid:
            return {"ok": False, "reason": "missing_uuid", "status": resp.status_code, "json": init_json}

        # Step 2: poll status
        done = False
        status_payload: dict[str, Any] | None = None
        for _ in range(poll_attempts):
            sresp = requests.get(
                f"{chat_base}/api/completions/status/{uuid}",
                headers=_chat_headers(),
                timeout=60,
            )
            if sresp.status_code == 200:
                status_payload = _safe_json(sresp) or {}
                status = status_payload.get("status")
                if status in (0, 2):
                    done = True
                    break
            time.sleep(poll_sleep_s)

        # Step 3: fetch result
        rresp = requests.get(
            f"{chat_base}/api/completions/context/{uuid}",
            headers=_chat_headers(),
            timeout=120,
        )

        if rresp.status_code != 200:
            return {
                "ok": False,
                "uuid": uuid,
                "done": done,
                "status_payload": status_payload,
                "status": rresp.status_code,
                "text": rresp.text,
                "json": _safe_json(rresp),
            }

        result_json = _safe_json(rresp) or {}
        content = None
        if isinstance(result_json.get("choices"), list) and result_json["choices"]:
            msg = result_json["choices"][0].get("message") or {}
            content = msg.get("content")

        return {"ok": True, "uuid": uuid, "done": done, "status_payload": status_payload, "result_json": result_json, "content": content}


def get_rag_from_env() -> RAG:
    client = AsimovClient.from_env()
    return RAG(client=client)
