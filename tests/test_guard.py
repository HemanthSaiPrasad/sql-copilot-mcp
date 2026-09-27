"""Unit tests for the query guard. No database needed: pure logic."""

import pytest

from sql_copilot_mcp.guard import UnsafeQueryError, check_and_prepare


def prepare(sql: str) -> str:
    return check_and_prepare(sql, max_rows=100)


# --- Queries that should be ALLOWED ---

def test_allows_simple_select_and_adds_limit():
    assert prepare("SELECT first_name FROM customer") == "SELECT first_name FROM customer LIMIT 100"


def test_keeps_a_smaller_limit():
    assert prepare("SELECT * FROM film LIMIT 5").endswith("LIMIT 5")


def test_caps_a_larger_limit():
    assert prepare("SELECT * FROM film LIMIT 5000").endswith("LIMIT 100")


def test_allows_joins_and_aggregates():
    sql = "SELECT c.customer_id, SUM(p.amount) FROM customer c JOIN payment p USING (customer_id) GROUP BY 1"
    assert "SUM" in prepare(sql)


def test_allows_union():
    assert "UNION" in prepare("SELECT 1 UNION SELECT 2")


# --- Queries that should be BLOCKED ---

@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customer",
        "UPDATE customer SET email = 'x'",
        "INSERT INTO customer (first_name) VALUES ('x')",
        "DROP TABLE customer",
        "TRUNCATE customer",
        "SET statement_timeout = 0",
        "COPY customer TO '/tmp/out.csv'",
    ],
)
def test_blocks_non_select_statements(sql):
    with pytest.raises(UnsafeQueryError):
        prepare(sql)


def test_blocks_multiple_statements():
    with pytest.raises(UnsafeQueryError, match="exactly one"):
        prepare("SELECT 1; DROP TABLE customer")


def test_blocks_delete_hidden_inside_with():
    # Looks like a SELECT at the top, but deletes data inside the WITH clause
    with pytest.raises(UnsafeQueryError, match="DELETE"):
        prepare("WITH gone AS (DELETE FROM customer RETURNING *) SELECT * FROM gone")


def test_blocks_select_into():
    with pytest.raises(UnsafeQueryError, match="INTO"):
        prepare("SELECT * INTO customer_copy FROM customer")


def test_blocks_row_locks():
    with pytest.raises(UnsafeQueryError, match="lock"):
        prepare("SELECT * FROM customer FOR UPDATE")


def test_blocks_dangerous_functions():
    with pytest.raises(UnsafeQueryError, match="pg_sleep"):
        prepare("SELECT pg_sleep(60)")


def test_blocks_unparseable_sql():
    with pytest.raises(UnsafeQueryError, match="parse"):
        prepare("SELEC nonsense ((")
