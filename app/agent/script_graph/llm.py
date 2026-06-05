"""LangChain LLM factory for script graph agents."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.config import settings

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


class GraphLLMConfigurationError(RuntimeError):
    """Raised when the LangGraph agent LLM cannot be created."""


def create_chat_llm(*, temperature: float | None = None):
    """Create a LangChain chat model for the graph agents.

    The project uses OpenAI-compatible providers, so DashScope, SiliconFlow,
    OpenAI, and private gateways can share the same configuration shape.
    """

    if not settings.llm_configured:
        raise GraphLLMConfigurationError(
            "No model API key configured. Set LLM_API_KEY, OPENAI_API_KEY, "
            "or DASHSCOPE_API_KEY in .env."
        )

    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - environment guard
        raise GraphLLMConfigurationError(
            "langchain_openai is not installed. Install the LangChain dependencies first."
        ) from exc

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature if temperature is None else temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )


def create_structured_llm(schema: type[StructuredModel], *, temperature: float | None = None):
    """Create an LLM bound to a Pydantic structured-output schema."""

    return create_chat_llm(temperature=temperature).with_structured_output(schema)

