from pathlib import Path

import uvicorn
from dotenv import load_dotenv

from askboard.logging_config import configure_logging
from askboard.runtime import UVICORN_LOOP

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
configure_logging()

from askboard.server import create_app  # noqa: E402  (after env + logging setup)

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "askboard.main:app",
        host="127.0.0.1",
        port=8000,
        loop=UVICORN_LOOP,
    )
