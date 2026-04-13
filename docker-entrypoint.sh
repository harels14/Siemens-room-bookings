#!/bin/sh
set -e

DB_FILE="/app/data/bookings.db"

# Seed the database if it doesn't exist yet, or if SEED_DB=1 is set.
if [ ! -f "$DB_FILE" ] || [ "${SEED_DB}" = "1" ]; then
    echo "Seeding database..." >&2
    python scripts/seed_db.py
fi

# Run the MCP server (stdio transport — stdout is JSON-RPC, logs go to stderr).
exec python -m mcp_server.server
