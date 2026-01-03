# syntax=docker/dockerfile:1

FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --no-dev --no-editable

# Copy source code
COPY src/ ./src/

# Create data directory
RUN mkdir -p /app/data

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["uv", "run", "checkin-bot"]
