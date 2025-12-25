"""Abstract LLM interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Response from an LLM."""

    content: str
    model: str
    tokens_used: int = 0
    finish_reason: str = ""
    raw_response: Any = None

    def __str__(self) -> str:
        return self.content


@dataclass
class LLMMessage:
    """Message for LLM conversation."""

    role: str  # "system", "user", "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    def __init__(
        self,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key

    @abstractmethod
    def complete(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Complete a single prompt.

        Args:
            prompt: The prompt to complete
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with the completion
        """
        pass

    @abstractmethod
    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> LLMResponse:
        """Chat with a list of messages.

        Args:
            messages: List of conversation messages
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with the assistant's reply
        """
        pass

    def complete_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]:
        """Complete a prompt and parse JSON response.

        Args:
            prompt: The prompt to complete
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON dict
        """
        import json

        response = self.complete(prompt, **kwargs)

        # Try to extract JSON from response
        content = response.content.strip()

        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            # Try to find JSON in the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    pass

            raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Rough approximation: ~4 characters per token.
        """
        return len(text) // 4
