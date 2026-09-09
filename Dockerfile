# Multi-stage Dockerfile for Atlas
# Builds Rust core, Go services, and bundles everything into one image.

# Stage 1: Build Rust core
FROM rust:slim AS rust-builder
WORKDIR /build
COPY core/ core/
COPY store/ store/
COPY apps/ apps/
COPY Cargo.toml Cargo.lock ./
RUN apt-get update && apt-get install -y pkg-config libssl-dev && rm -rf /var/lib/apt/lists/* \
    && cargo build --release --workspace 2>&1

# Stage 2: Build Go services
FROM golang:1.26-alpine AS go-builder
WORKDIR /build/line
COPY line/ .
RUN go build -o /atlas-mcp ./cmd/atlas-mcp \
    && go build -o /atlas-town ./cmd/atlas-town \
    && go build -o /atlas-door ./cmd/atlas-door

# Stage 3: Final image
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy binaries
COPY --from=rust-builder /build/target/release/atlas /usr/local/bin/
COPY --from=go-builder /atlas-mcp /usr/local/bin/
COPY --from=go-builder /atlas-town /usr/local/bin/
COPY --from=go-builder /atlas-door /usr/local/bin/

# Copy runtime files (VERSION, agents, specs — no live data/)
COPY VERSION /etc/atlas/VERSION
COPY agents/ /etc/atlas/agents/
COPY specs/ /etc/atlas/specs/

# Create empty data directory (operator populates at runtime)
RUN mkdir -p /etc/atlas/data

# Set working directory
WORKDIR /etc/atlas

# Verify binaries
RUN atlas --version && atlas-mcp --version && atlas-town --version && atlas-door --version

# Labels
LABEL org.opencontainers.image.title="Atlas" \
      org.opencontainers.image.description="Sovereign agent harnessing - make agents that won't wreck your stuff." \
      org.opencontainers.image.version="0.1.0+f1" \
      org.opencontainers.image.licenses="MIT"

# Expose door port
EXPOSE 8080

# Default: run the door
CMD ["atlas-door", "--port", "8080"]
