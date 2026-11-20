from askboard.runtime import new_selector_event_loop


def pytest_asyncio_loop_factories(config, item):
    # psycopg async needs a SelectorEventLoop; Windows defaults to Proactor.
    return {"selector": new_selector_event_loop}
