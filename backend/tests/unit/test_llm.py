import asyncio

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from askboard.ask.llm import LangChainLLM, LLMError, LLMNotConfiguredError, make_chat_model
from askboard.config import load_settings


class Answer(BaseModel):
    text: str
    score: int


class FakeStructured:
    def __init__(self, behaviour):
        self._behaviour = behaviour

    async def ainvoke(self, messages):
        return await self._behaviour(messages)


class FakeChatModel:
    """Duck-types the two BaseChatModel methods LangChainLLM uses."""

    def __init__(self, structured=None, raw=None):
        self._structured = structured
        self._raw = raw
        self.raw_messages = None

    def with_structured_output(self, schema):
        return FakeStructured(self._structured)

    async def ainvoke(self, messages):
        self.raw_messages = messages
        return await self._raw(messages)


async def fail(_):
    raise RuntimeError("tool calling not supported")


async def hang(_):
    await asyncio.sleep(10)


async def test_returns_structured_output():
    async def ok(_):
        return Answer(text="hi", score=3)

    llm = LangChainLLM(FakeChatModel(structured=ok), timeout_seconds=1)

    assert await llm.generate("system", "user", Answer) == Answer(text="hi", score=3)


async def test_falls_back_to_parsing_json_from_plain_text():
    async def raw(_):
        return AIMessage(content='Sure!\n```json\n{"text": "fallback", "score": 7}\n```')

    model = FakeChatModel(structured=fail, raw=raw)
    llm = LangChainLLM(model, timeout_seconds=1)

    assert await llm.generate("system", "user", Answer) == Answer(text="fallback", score=7)
    assert '"score"' in model.raw_messages[0].content  # schema sent in the fallback prompt


async def test_raises_llm_error_when_both_attempts_fail():
    async def raw(_):
        return AIMessage(content="not json")

    llm = LangChainLLM(FakeChatModel(structured=fail, raw=raw), timeout_seconds=1)

    with pytest.raises(LLMError, match="tool calling not supported"):
        await llm.generate("system", "user", Answer)


async def test_times_out():
    llm = LangChainLLM(FakeChatModel(structured=hang, raw=hang), timeout_seconds=0.05)

    with pytest.raises(LLMError):
        await llm.generate("system", "user", Answer)


def test_openrouter_requires_api_key():
    with pytest.raises(LLMNotConfiguredError, match="OPENROUTER_API_KEY"):
        make_chat_model(load_settings({}))


def test_openrouter_chat_model_uses_configured_model():
    model = make_chat_model(load_settings({"OPENROUTER_API_KEY": "sk-test", "LLM_MODEL": "openai/gpt-4o"}))

    assert model.model_name == "openai/gpt-4o"
    assert "openrouter.ai" in str(model.openai_api_base)
