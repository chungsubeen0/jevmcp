# Jev MCP — local MCP server. Do not bake TYPESAFE_API_KEY or JEV_MCP_HTTP_TOKEN.
# stdio (default):
#   docker run --rm -i -e TYPESAFE_API_KEY jev-mcp --profile interactive --shadow
# Streamable HTTP (publish loopback only; token required):
#   docker run --rm -e TYPESAFE_API_KEY -e JEV_MCP_HTTP_TOKEN -e JEV_MCP_HTTP_BIND_ALL=1 \
#     -e JEV_MCP_HTTP_HOST=0.0.0.0 -p 127.0.0.1:8765:8765 \
#     jev-mcp --transport streamable-http --profile interactive --shadow
# Do not pass a whole ~/.env file; it may contain unrelated secrets.

FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}" \
    JEV_MCP_DATA_DIR=/var/lib/jev-mcp \
    JEV_MCP_LOG_LEVEL=INFO

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin jev \
    && mkdir -p /var/lib/jev-mcp \
    && chown -R jev:jev /var/lib/jev-mcp

COPY --from=build /install /usr/local

USER jev
WORKDIR /home/jev
VOLUME ["/var/lib/jev-mcp"]

# MCP speaks JSON-RPC on stdin/stdout, or Streamable HTTP when --transport is set.
EXPOSE 8765
ENTRYPOINT ["jev-mcp"]
CMD ["--profile", "interactive", "--shadow"]
