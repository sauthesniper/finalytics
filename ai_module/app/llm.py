"""
Thin LLM client wrapper around the OpenAI Chat Completions API.

Designed so the rest of the app never crashes if the API key is
missing or the call fails: callers receive (text, used_llm) and can
fall back to deterministic templates when used_llm is False.
"""
import os
from typing import Tuple, Optional

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY")
LLM_TIMEOUT = int(os.getenv("OPENAI_TIMEOUT", "40"))

_client = None


def _get_client():
    """Lazily build the OpenAI client; returns None if unavailable."""
    global _client
    if _client is not None:
        return _client
    if not API_KEY:
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(api_key=API_KEY, timeout=LLM_TIMEOUT)
        return _client
    except Exception:
        return None


def llm_available() -> bool:
    return _get_client() is not None


def chat(system_prompt: str, user_prompt: str,
         temperature: float = 0.3, max_tokens: int = 600) -> Tuple[Optional[str], bool]:
    """
    Run a chat completion.

    Returns (content, used_llm). On any failure returns (None, False) so
    the caller can use a deterministic fallback.
    """
    client = _get_client()
    if client is None:
        return None, False
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        if not content:
            return None, False
        return content.strip(), True
    except Exception:
        return None, False


def stream_chat(system_prompt: str, user_prompt: str,
                temperature: float = 0.3, max_tokens: int = 600):
    """
    Stream a chat completion, yielding text deltas as they arrive.

    Yields nothing if the client is unavailable or the call fails, so the
    caller can detect "no tokens produced" and fall back.
    """
    client = _get_client()
    if client is None:
        return
    try:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception:
        return


def chat_with_tools(messages: list, tools: list,
                    temperature: float = 0.2, max_tokens: int = 700):
    """
    Run a tool-enabled chat completion (OpenAI function calling).

    Returns (message, used_llm) where ``message`` is the assistant message
    object (it may carry ``tool_calls``). On any failure returns (None, False)
    so the caller can fall back to the deterministic path.
    """
    client = _get_client()
    if client is None:
        return None, False
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message, True
    except Exception:
        return None, False
