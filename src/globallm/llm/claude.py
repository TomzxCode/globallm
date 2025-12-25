"""Claude API integration."""

import os
from typing import Any

from anthropic import Anthropic

from globallm.llm.base import BaseLLM, LLMResponse, LLMMessage
from globallm.logging_config import get_logger

logger = get_logger(__name__)


class ClaudeLLM(BaseLLM):
    """Claude (Anthropic) LLM provider."""

    DEFAULT_MODELS = {
        "haiku": "claude-3-5-haiku-20241022",
        "sonnet": "claude-3-5-sonnet-20241022",
        "opus": "claude-3-opus-20240229",
    }

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.0,
        max_tokens: int = 8192,
        api_key: str | None = None,
    ) -> None:
        super().__init__(model, temperature, max_tokens, api_key)
        self.client = Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        if not self.client.api_key:
            logger.warning("claude_no_api_key")

    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Complete a single prompt using Claude.

        Args:
            prompt: The prompt to complete
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            LLMResponse with the completion
        """
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)

        logger.debug("claude_complete", model=self.model, prompt_len=len(prompt))

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=response.stop_reason,
                raw_response=response,
            )

        except Exception as e:
            logger.error("claude_complete_failed", error=str(e))
            raise

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Chat with Claude using message history.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with the assistant's reply
        """
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        temperature = kwargs.get("temperature", self.temperature)

        api_messages = [m.to_dict() for m in messages]

        logger.debug("claude_chat", model=self.model, messages_count=len(api_messages))

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=api_messages,
            )

            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return LLMResponse(
                content=content,
                model=self.model,
                tokens_used=tokens_used,
                finish_reason=response.stop_reason,
                raw_response=response,
            )

        except Exception as e:
            logger.error("claude_chat_failed", error=str(e))
            raise


def create_claude(
    model_size: str = "sonnet",
    temperature: float = 0.0,
    max_tokens: int = 8192,
    api_key: str | None = None,
) -> ClaudeLLM:
    """Factory function to create a Claude LLM instance.

    Args:
        model_size: Size of model ("haiku", "sonnet", "opus")
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

    Returns:
        Configured ClaudeLLM instance
    """
    model = ClaudeLLM.DEFAULT_MODELS.get(model_size, model_size)
    return ClaudeLLM(
        model=model, temperature=temperature, max_tokens=max_tokens, api_key=api_key
    )
