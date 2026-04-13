# Siemens Room Bookings — MCP Server
# Runs with stdio transport (stdin/stdout JSON-RPC).
# Use:  docker run -i --rm -v room-bookings-data:/app/data siemens-room-bookings

FROM python:3.12-slim

WORKDIR /app

# Install build tools (needed by some transitive deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy only the dependency manifest first (cache-friendly layer)
COPY pyproject.toml ./

# Install the package in editable mode so src/ is on the path
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[dev]"

# Copy the rest of the project
COPY db/      ./db/
COPY scripts/ ./scripts/
COPY docker-entrypoint.sh ./

RUN chmod +x docker-entrypoint.sh

# Persistent volume mount point for the SQLite database
VOLUME ["/app/data"]

# MCP servers communicate over stdio — no port needed.
# Pass SEED_DB=1 to (re-)seed the database on startup.
ENV SEED_DB=0

ENTRYPOINT ["./docker-entrypoint.sh"]
