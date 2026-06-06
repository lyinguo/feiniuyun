"""LangChain LLM factory for script graph agents."""

from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.services.llm_output_parser import parse_json_object

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)
logger = logging.getLogger(__name__)


class GraphLLMConfigurationError(RuntimeError):
    """Raised when the LangGraph agent LLM cannot be created."""


class GraphLLMResponseError(RuntimeError):
    """Raised when a graph LLM call cannot be parsed into the requested schema."""


def create_chat_llm(*, temperature: float | None = None, max_tokens: int | None = None):
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
        max_tokens=max_tokens or settings.llm_max_tokens,
    )


def create_structured_llm(
    schema: type[StructuredModel],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    """Create an LLM bound to a Pydantic structured-output schema."""

    method = _structured_output_method()
    return create_chat_llm(temperature=temperature, max_tokens=max_tokens).with_structured_output(
        schema,
        method=method,
    )


async def invoke_structured(
    prompt: ChatPromptTemplate,
    schema: type[StructuredModel],
    values: dict[str, Any],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> StructuredModel:
    """Invoke a prompt and return a validated Pydantic object.

    Some OpenAI-compatible providers reject provider-native ``response_format``
    modes, and LangChain can return ``None`` when a tool/function response is
    present but not parseable. This helper keeps the preferred structured
    output path, then falls back to plain chat + JSON parsing without sending
    ``response_format``.
    """

    try:
        output = await _invoke_structured_with_raw(
            prompt,
            schema,
            values,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return output
    except Exception as exc:
        if _should_retry_as_plain_json(exc):
            logger.warning(
                "Structured output failed for %s, retrying as plain JSON: %s",
                schema.__name__,
                exc,
            )
            return await _invoke_plain_json(
                prompt,
                schema,
                values,
                temperature=temperature,
                max_tokens=max_tokens,
                original_error=exc,
            )
        raise


async def _invoke_structured_with_raw(
    prompt: ChatPromptTemplate,
    schema: type[StructuredModel],
    values: dict[str, Any],
    *,
    temperature: float | None,
    max_tokens: int | None,
) -> StructuredModel:
    llm = create_chat_llm(temperature=temperature, max_tokens=max_tokens).with_structured_output(
        schema,
        method=_structured_output_method(),
        include_raw=True,
    )
    result = await (prompt | llm).ainvoke(values)

    if not isinstance(result, dict) or "parsed" not in result:
        if result is None:
            raise GraphLLMResponseError(
                f"{schema.__name__} structured output parser returned None."
            )
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)

    parsed = result.get("parsed")
    if parsed is not None:
        if isinstance(parsed, schema):
            return parsed
        return schema.model_validate(parsed)

    raw_payload = _extract_raw_payload(result.get("raw"))
    if raw_payload is not None:
        try:
            return schema.model_validate(raw_payload)
        except ValidationError as exc:
            raise GraphLLMResponseError(
                f"{schema.__name__} raw structured arguments failed validation: {exc}"
            ) from exc

    parsing_error = result.get("parsing_error")
    raise GraphLLMResponseError(
        f"{schema.__name__} structured output parser returned None. "
        f"Parsing error: {parsing_error}"
    )


async def _invoke_plain_json(
    prompt: ChatPromptTemplate,
    schema: type[StructuredModel],
    values: dict[str, Any],
    *,
    temperature: float | None,
    max_tokens: int | None,
    original_error: Exception,
) -> StructuredModel:
    messages = prompt.format_messages(**values)
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    messages.append(
        HumanMessage(
            content=(
                "请重新输出，且只能输出一个 JSON object。不要使用 Markdown，不要解释。\n"
                f"JSON 必须满足这个 Pydantic schema：\n{schema_json}"
            )
        )
    )

    response = await create_chat_llm(
        temperature=temperature,
        max_tokens=max_tokens,
    ).ainvoke(messages)
    content = _message_content_to_text(getattr(response, "content", ""))
    try:
        data = parse_json_object(content)
        return schema.model_validate(data)
    except Exception as exc:
        raise GraphLLMResponseError(
            f"{schema.__name__} output could not be parsed. "
            f"Original structured error: {original_error}. "
            f"Fallback parse error: {exc}. First 500 chars: {content[:500]}"
        ) from exc


def _structured_output_method() -> str:
    method = (settings.llm_structured_output_method or "function_calling").strip().lower()
    if method in {"json_schema", "json_object", "response_format", "json_mode"}:
        logger.warning(
            "LLM_STRUCTURED_OUTPUT_METHOD=%s may use provider response_format; "
            "using function_calling for OpenAI-compatible compatibility.",
            method,
        )
        return "function_calling"
    if method not in {"function_calling"}:
        logger.warning(
            "Unknown LLM_STRUCTURED_OUTPUT_METHOD=%s; using function_calling.",
            method,
        )
        return "function_calling"
    return method


def _extract_raw_payload(raw: Any) -> dict[str, Any] | None:
    """Extract JSON arguments from an AIMessage returned with include_raw=True."""

    for call in getattr(raw, "tool_calls", None) or []:
        payload = _extract_tool_call_args(call)
        if payload is not None:
            return payload

    additional_kwargs = getattr(raw, "additional_kwargs", {}) or {}
    for call in additional_kwargs.get("tool_calls") or []:
        payload = _extract_tool_call_args(call)
        if payload is not None:
            return payload

    content = _message_content_to_text(getattr(raw, "content", ""))
    if content.strip():
        try:
            return parse_json_object(content)
        except Exception:
            return None
    return None


def _extract_tool_call_args(call: Any) -> dict[str, Any] | None:
    if not isinstance(call, dict):
        return None

    args = call.get("args")
    if args is None:
        args = (call.get("function") or {}).get("arguments")

    if isinstance(args, dict):
        return args
    if isinstance(args, str) and args.strip():
        try:
            data = parse_json_object(args)
            return data
        except Exception:
            return None
    return None


def _should_retry_as_plain_json(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        isinstance(exc, GraphLLMResponseError)
        or "response_format" in text
        or "structured output" in text
        or "tool" in text
        or "function" in text
        or "parse" in text
        or "validation" in text
    )


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")
