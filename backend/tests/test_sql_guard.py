"""Phase 2d — SQL read-only guard. The old check only asserted the query STARTS
with SELECT/WITH, which a data-modifying CTE or a stacked query walks straight
through. These lock the hardened `_is_readonly_sql` down."""
import pytest

from backend.main import _is_readonly_sql


@pytest.mark.parametrize("q", [
    "SELECT * FROM sales",
    "  select id, name from users where active = true  ",
    "SELECT * FROM t;",                                   # a single trailing ; is fine
    "WITH r AS (SELECT * FROM orders) SELECT * FROM r",   # read-only CTE
    "SELECT COUNT(*), REPLACE(name,'x','y') FROM t",      # REPLACE() the string fn is fine
    "select updated_at, created_at from events",          # write words as column substrings
    "SELECT * FROM t OFFSET 10",                           # 'offset' contains 'set' — must pass
])
def test_allows_readonly_selects(q):
    assert _is_readonly_sql(q) is True


@pytest.mark.parametrize("q", [
    "DROP TABLE users",
    "SELECT 1; DROP TABLE users",                          # stacked
    "SELECT 1; DELETE FROM t",                             # stacked
    "INSERT INTO t VALUES (1)",
    "WITH x AS (INSERT INTO t VALUES (1) RETURNING *) SELECT * FROM x",  # write CTE bypass
    "SELECT * INTO newtable FROM t",                       # SELECT … INTO
    "UPDATE t SET a = 1",
    "TRUNCATE t",
    "GRANT ALL ON t TO public",
    "SELECT pg_sleep(10)",                                 # DoS function
    "SELECT pg_read_file('/etc/passwd')",                  # file read
    "SELECT load_file('/etc/passwd')",                     # MySQL file read
    "SELECT benchmark(1000000, md5('x'))",                 # MySQL DoS
    "COPY t TO '/tmp/x'",                                  # file write
    "select * from t; select * from u",                   # stacked selects
    "DELETE FROM t WHERE 1=1",
    "",                                                    # empty
    "   ",                                                 # whitespace
    "not sql at all",
])
def test_rejects_writes_and_stacked(q):
    assert _is_readonly_sql(q) is False


def test_rejects_non_string():
    assert _is_readonly_sql(None) is False
    assert _is_readonly_sql(123) is False


def test_connect_endpoint_rejects_write_cte(client):
    # End-to-end: the connector endpoint refuses a write-CTE with a 400, before
    # ever touching the database.
    r = client.post("/api/connect", json={
        "type": "database",
        "connection_string": "postgresql://u:p@db.example.com/x",
        "query": "WITH x AS (INSERT INTO t VALUES (1) RETURNING *) SELECT * FROM x",
    })
    assert r.status_code == 400
    assert "read-only" in r.json()["detail"].lower()
