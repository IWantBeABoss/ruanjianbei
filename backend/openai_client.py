import os
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load .env from backend directory
load_dotenv(Path(__file__).parent / ".env")

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set — create backend/.env with OPENAI_API_KEY=your-key")
        base_url = os.getenv("OPENAI_BASE_URL")
        _client = AsyncOpenAI(api_key=api_key, base_url=base_url) if base_url else AsyncOpenAI(api_key=api_key)
    return _client


async def chat_complete(messages: list[dict]) -> str:
    """Non-streaming chat for agents that need full response."""
    client = _get_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
    )
    return response.choices[0].message.content or ""


async def stream_chat(messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> AsyncGenerator[
    str, None]:
    """Stream chat completion with configurable parameters."""
    client = _get_client()
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    print(f"[stream_chat] Using model: {model}, temperature: {temperature}, max_tokens: {max_tokens}", flush=True)

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,  # 重要！设置最大输出长度
        stream=True,
    )

    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
