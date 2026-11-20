import asyncio

import uvicorn

from askboard.runtime import UVICORN_LOOP, new_selector_event_loop


def test_new_selector_event_loop_builds_a_selector_loop():
    """psycopg's async mode does not work on Windows' default ProactorEventLoop."""
    loop = new_selector_event_loop()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()


def test_uvicorn_resolves_our_loop_setting_to_a_selector_loop():
    # Exercises uvicorn's own resolution path for a custom `loop=` import string.
    config = uvicorn.Config("askboard.main:app", loop=UVICORN_LOOP)

    factory = config.get_loop_factory()
    assert factory is not None
    loop = factory()
    try:
        assert isinstance(loop, asyncio.SelectorEventLoop)
    finally:
        loop.close()
