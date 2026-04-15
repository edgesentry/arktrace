# syntax=docker/dockerfile:1
#
# Multi-stage build:
#   builder      — installs Python deps (compiles Rust/lance-graph)
#   llama-server — copies the pre-built llama-server binary from the official image
#   runtime      — lean final image: Python app + llama-server binary

# ── builder: Python deps (Rust/maturin for lance-graph) ───────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    pkg-config \
    libssl-dev \
    protobuf-compiler \
    libprotobuf-dev \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"
ENV CARGO_BUILD_JOBS=2

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cargo/registry \
    --mount=type=cache,target=/root/.cargo/git \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen

# ── llama-server: copy pre-built binary from official llama.cpp image ─────────
# The official server image is multi-arch (linux/amd64 + linux/arm64).
# Binary is at /llama-server inside that image.
FROM ghcr.io/ggml-org/llama.cpp:server AS llama-server-src

# ── runtime: lean final image ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime libs: libgomp (OpenMP, required by llama-server), curl (health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Python virtualenv from builder
COPY --from=builder /app/.venv /app/.venv

# llama-server binary from the official llama.cpp image
COPY --from=llama-server-src /llama-server /usr/local/bin/llama-server

# Application source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh /usr/local/bin/llama-server

ENV PATH="/app/.venv/bin:${PATH}"

# Data dir inside the container — override with ARKTRACE_DATA_DIR
ENV ARKTRACE_DATA_DIR=/root/.arktrace/data

# Model volume mount point — mount a GGUF model here to enable analyst briefs
VOLUME ["/models"]

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
