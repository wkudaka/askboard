FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY askboard ./askboard
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 app
USER app

EXPOSE 8000
CMD ["uvicorn", "askboard.main:app", "--host", "0.0.0.0", "--port", "8000", "--loop", "askboard.runtime:new_selector_event_loop"]
