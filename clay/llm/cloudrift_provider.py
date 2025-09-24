"""Cloudrift AI LLM provider implementation."""

import os
import json
from typing import Optional, List, Dict, Any
import aiohttp

from .base import LLMProvider, LLMResponse
from ..trace import trace_operation, trace_llm_call, trace_error


class CloudriftProvider(LLMProvider):
    """Cloudrift AI API provider (OpenAI-compatible)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-ai/DeepSeek-V3"):
        api_key = api_key or os.getenv("CLOUDRIFT_API_KEY")
        if not api_key:
            raise ValueError("Cloudrift API key required")
        super().__init__(api_key, model)
        self.base_url = "https://inference.cloudrift.ai/v1"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Get completion from Cloudrift."""
        with trace_operation("LLM", "api_call",
                           provider="cloudrift",
                           model=self.model,
                           prompt_length=len(system_prompt) + len(user_prompt),
                           temperature=temperature or self.default_temperature):

            trace_llm_call("cloudrift", self.model, len(system_prompt) + len(user_prompt),
                          temperature=temperature or self.default_temperature,
                          max_tokens=max_tokens or self.default_max_tokens)

            messages = self.build_messages(system_prompt, user_prompt, kwargs.get("history"))

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature or self.default_temperature,
                "max_tokens": max_tokens or self.default_max_tokens
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=data
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            error = Exception(f"Cloudrift API error: {error_text}")
                            trace_error("LLM", "api_call_failed", error,
                                       provider="cloudrift",
                                       status_code=response.status)
                            raise error

                        result = await response.json()
                        response_obj = LLMResponse(
                            content=result["choices"][0]["message"]["content"],
                            model=result["model"],
                            usage=result.get("usage"),
                            metadata={"finish_reason": result["choices"][0].get("finish_reason")}
                        )

                        # Log successful completion
                        trace_llm_call("cloudrift", self.model, len(system_prompt) + len(user_prompt),
                                      response_length=len(response_obj.content),
                                      usage=result.get("usage"),
                                      finish_reason=result["choices"][0].get("finish_reason"))

                        return response_obj

            except Exception as e:
                trace_error("LLM", "api_call_exception", e, provider="cloudrift")
                raise

    async def stream_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """Stream completion from Cloudrift."""
        messages = self.build_messages(system_prompt, user_prompt, kwargs.get("history"))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
            "stream": True
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Cloudrift API error: {error_text}")

                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except json.JSONDecodeError:
                            continue