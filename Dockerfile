FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install .

EXPOSE 8000

ENV MCP_TOOLKIT_HTTP_HOST=0.0.0.0 \
    MCP_TOOLKIT_HTTP_PORT=8000 \
    MCP_TOOLKIT_DATA_DIR=/data

VOLUME ["/data"]

CMD ["mcp-server-toolkit", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
