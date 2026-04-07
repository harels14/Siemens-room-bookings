"""
Tool: reset_database

Spec: specs/mcp_tools.md → reset_database
"""

import os

from mcp_server import database as db


def reset_database(admin_password: str) -> dict:
    """
    Deletes the database file entirely.

    Requires the correct admin password (set via MCP_ADMIN_PASSWORD environment variable).
    Use this to fully reset between demo sessions.

    Args:
        admin_password: The secret admin password configured on the server.
    """
    expected = os.environ.get("MCP_ADMIN_PASSWORD")

    if not expected:
        return {"error": "Admin password not configured on the server"}

    if admin_password != expected:
        return {"error": "Unauthorized: invalid admin password"}

    db_path = db.DB_PATH
    if db_path.exists():
        db_path.unlink()
        return {"success": True, "message": "Database file deleted"}
    return {"success": True, "message": "Database file did not exist"}
