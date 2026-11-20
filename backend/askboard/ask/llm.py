"""LLM access: one method, `generate(system, user, schema) -> schema instance`.

Ported from sales-analytics-agent-wk's LLMService. Structured output (tool calling) is
tried first; models without it get the JSON schema in the prompt and we parse the reply.
"""

import asyncio
import json
import re
from typing import Protocol, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from askboard.config import Settings

T = TypeVar("T", bound=BaseModel)

_FENCED_JSON = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```")
_BARE_JSON = re.compile(r"(\{[\s\S]*\})")


class LLMError(Exception):
    """The model failed to produce a valid structured answer."""


class LLMNotConfiguredError(LLMError):
    """No usable LLM provider/credentials are configured."""


class StructuredLLM(Protocol):
    async def generate(self, system_prompt: str, user_prompt: str, schema: type[T]) -> T: ...


def _extract_json(text: str) -> str:
    for pattern in (_FENCED_JSON, _BARE_JSON):
        if match := pattern.search(text):
            return match.group(1)
    return text


class LangChainLLM:
    def __init__(self, chat_model: BaseChatModel, *, timeout_seconds: float):
        self._model = chat_model
        self._timeout = timeout_seconds

    async def generate(self, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        try:
            structured = self._model.with_structured_output(schema)
            return await asyncio.wait_for(structured.ainvoke(messages), timeout=self._timeout)
        except Exception as first_error:
            schema_json = json.dumps(schema.model_json_schema(), indent=2)
            fallback = [
                SystemMessage(
                    content=f"{system_prompt}\n\nRespond ONLY with a JSON object matching this schema:\n{schema_json}"
                ),
                HumanMessage(content=user_prompt),
            ]
            try:
                raw = await asyncio.wait_for(self._model.ainvoke(fallback), timeout=self._timeout)
                return schema.model_validate_json(_extract_json(str(raw.content)))
            except Exception:
                reason = str(first_error) or type(first_error).__name__
                raise LLMError(f"LLM call failed: {reason}") from first_error


def make_chat_model(settings: Settings) -> BaseChatModel:
    if settings.llm_provider == "bedrock":
        try:
            from langchain_aws import ChatBedrockConverse
        except ImportError as exc:
            raise LLMNotConfiguredError(
                "LLM_PROVIDER=bedrock needs langchain-aws: pip install -e .[bedrock]"
            ) from exc
        return ChatBedrockConverse(model=settings.bedrock_model_id, region_name=settings.aws_region, temperature=0)

    if not settings.openrouter_api_key:
        raise LLMNotConfiguredError("OPENROUTER_API_KEY is not set (see backend/.env.example)")
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        model=settings.llm_model,
        temperature=0,
        default_headers={"X-Title": "Askboard"},
    )


def make_llm(settings: Settings) -> StructuredLLM:
    return LangChainLLM(make_chat_model(settings), timeout_seconds=settings.llm_timeout_seconds)
