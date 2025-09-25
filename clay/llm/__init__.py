"""Simple completion function for Clay LLM integration."""

import os
import json
import aiohttp
import asyncio
from typing import AsyncIterator, Iterator, Dict, Any, List, Optional
from ..config import get_config


async def completion(
    messages: List[Dict[str, str]],
    stream: bool = False,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **kwargs
) -> AsyncIterator[Dict[str, Any]] | Dict[str, Any]:
    """Simple completion function using global config."""

    config = get_config()
    provider = config.get_default_provider()

    if provider != "cloudrift":
        raise ValueError(f"Unsupported provider: {provider}")

    api_key, model = config.get_provider_credentials(provider)
    if not api_key:
        raise ValueError("No API key found in configuration")

    if not model:
        model = "deepseek-ai/DeepSeek-V3"  # Default model

    url = "https://inference.cloudrift.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": stream
    }

    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    # Add any additional kwargs
    payload.update(kwargs)

    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as response:
            response.raise_for_status()

            if stream:
                return _stream_response(response)
            else:
                return await response.json()


def _stream_response(response) -> Iterator[Dict[str, Any]]:
    """Parse streaming response from Cloudrift API."""
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = line[6:]  # Remove 'data: ' prefix
                if data == '[DONE]':
                    break
                try:
                    chunk = json.loads(data)
                    yield chunk
                except json.JSONDecodeError:
                    continue


class Delta:
    """Simple delta class to mimic LiteLLM structure."""
    def __init__(self, content: str = None):
        self.content = content


class Choice:
    """Simple choice class to mimic LiteLLM structure."""
    def __init__(self, delta: Delta):
        self.delta = delta


class StreamChunk:
    """Simple chunk class to mimic LiteLLM structure."""
    def __init__(self, choices: List[Choice]):
        self.choices = choices


def format_stream_chunk(chunk: Dict[str, Any]) -> StreamChunk:
    """Convert raw API chunk to LiteLLM-like structure."""
    choices = []
    if 'choices' in chunk:
        for choice in chunk['choices']:
            delta_content = None
            if 'delta' in choice and 'content' in choice['delta']:
                delta_content = choice['delta']['content']
            choices.append(Choice(Delta(delta_content)))
    return StreamChunk(choices)