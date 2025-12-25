"""OpenAI API integration."""

import os
from typing import Any

from openai import OpenAI

from globallm.llm.base import BaseLLM, LLMResponse, LLMMessage
from globallm.logging_config import get_logger

logger = get_logger(__name__)


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider."""

    DEFAULT_MODELS = {
        "gpt-4o": "gpt-4o",
        "gpt-4o-mini": "gpt-4o-mini",
        "gpt-4-turbo": "gpt-4-turbo",
        "gpt-4": "gpt-4",
        "gpt-3.5-turbo": "gpt-3.5-turbo",
    }

    def __init__(
        self,
        model: str = "gpt-4o",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        api_key: str | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens, api_key)
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        if not self.client.api_key:
            logger.warning("openai_no_api_key")

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Complete a single prompt using OpenAI.

        Args:
            prompt: The prompt to complete
            **kwargs: Additional parameters

        Returns:
            LLMResponse with the completion
        """
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)

        logger.debug("openai_complete", model=self.model, prompt_len=len(prompt))

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )

        except Exception as e:
            logger.error("openai_complete_failed", error=str(e))
            raise

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Chat with OpenAI using message history.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with the assistant's reply
        """
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)

        api_messages = [m.to_dict() for m in messages]

        logger.debug("openai_chat", model=self.model, messages_count=len(api_messages))

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=response.choices[0].finish_reason,
                raw_response=response,
            )

        except Exception as e:
            logger.error("openai_chat_failed", error=str(e))
            raise


def create_openai(
    model: str = "gpt-4o",
    temperature: float = 0.0,
    max_tokens: int = 8192,
    api_key: str | None = None,
) -> OpenAILLM:
    """Factory function to create an OpenAI LLM instance.

    Args:
        model: Model name (gpt-4o, gpt-4o-mini, etc.)
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)

    Returns:
        Configured OpenAILLM instance
    """
    return OpenAILLM(
        model=model, temperature=temperature, max_tokens=max_tokens, api_key=api_key
    )
