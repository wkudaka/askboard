"""Event-loop setup.

psycopg's async mode cannot run on Windows' default ``ProactorEventLoop``, so every
entrypoint (uvicorn, tests) must use a ``SelectorEventLoop``. On Linux this is what
asyncio uses anyway, so forcing it is harmless.

Uvicorn treats a custom ``--loop module:attr`` value as the loop factory itself
(a zero-argument callable returning a new loop), unlike its built-in names.
"""

import asyncio

UVICORN_LOOP = "askboard.runtime:new_selector_event_loop"


def new_selector_event_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
