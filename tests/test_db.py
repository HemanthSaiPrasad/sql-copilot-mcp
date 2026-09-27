"""Integration tests: these need the database running (docker compose up -d)."""

import psycopg
import pytest

from sql_copilot_mcp import db


def test_list_tables_includes_core_tables():
    tables = db.list_tables()
    assert "customer" in tables
    assert "payment" in tables


def test_list_tables_hides_partitions():
    assert not any(t.startswith("payment_p") for t in db.list_tables())


def test_describe_table_returns_columns():
    columns = [c["column"] for c in db.describe_table("customer")]
    assert "first_name" in columns
    assert "email" in columns


def test_run_query_returns_rows():
    result = db.run_query("SELECT first_name FROM customer ORDER BY customer_id LIMIT 3")
    assert result["columns"] == ["first_name"]
    assert result["row_count"] == 3
    assert result["truncated"] is False


def test_run_query_caps_rows():
    result = db.run_query("SELECT * FROM customer")
    assert result["row_count"] == db.MAX_ROWS
    assert result["truncated"] is True


def test_run_query_blocks_writes():
    with pytest.raises(psycopg.Error):
        db.run_query("DELETE FROM customer WHERE customer_id = 1")
