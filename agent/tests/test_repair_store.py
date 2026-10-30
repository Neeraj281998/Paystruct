"""The repository contract on both implementations. The PostgreSQL one runs only when database settings are in the environment
(the docker-compose variables) and the server answers; otherwise it is skipped. Each run uses its own throw-away schema."""
import json
import uuid

import pytest

from agent.db import connection
from agent.repair.pipeline import REPAIRED
from agent.repair.store import InMemoryRepository, PostgresRepository

from .fakes import GOOD, NEEDS_LLM_LINES, make_pipeline, submit


@pytest.fixture(scope="module")
def pg_conn():
    psycopg = pytest.importorskip("psycopg")
    if connection.dsn() is None:
        pytest.skip("no database settings in the environment")
    schema = "agent_test_" + uuid.uuid4().hex[:8]
    try:
        admin = connection.connect()
    except Exception:
        pytest.skip("the database is not reachable")
    admin.execute(f"CREATE SCHEMA {schema}")
    conn = connection.connect(search_path=schema)
    connection.apply_schema(conn)
    yield conn
    conn.close()
    admin.execute(f"DROP SCHEMA {schema} CASCADE")
    admin.close()


@pytest.fixture(params=["memory", "postgres"])
def repo(request):
    if request.param == "memory":
        return InMemoryRepository()
    conn = request.getfixturevalue("pg_conn")
    conn.execute("TRUNCATE agent_steps, agent_repairs CASCADE")
    return PostgresRepository(conn)


def test_claim_is_idempotent(repo):
    assert repo.claim("a", ["x"]).claimed is True
    second = repo.claim("a", ["x"])
    assert second.claimed is False and second.existing.status == "in_progress"
    assert repo.count() == 1


def test_finish_stores_the_result_and_the_steps(repo):
    from agent.repair.agent import Step
    repo.claim("a", ["x", "y"])
    repo.finish("a", "repaired", "REPAIRED", {"TwnNm": "Cork"}, 0.9, 1, 0.001, [], 0, [Step(1, 1, "llm_call", {"m": 1}, {"ok": True}, 10, 5, 7)])
    row = repo.get("a")
    assert row.status == "repaired" and row.repaired == {"TwnNm": "Cork"} and row.original_lines == ["x", "y"] and row.attempts == 1
    assert float(row.cost_usd) == pytest.approx(0.001) and float(row.confidence) == pytest.approx(0.9)
    assert repo.claim("a", ["x"]).claimed is False


def test_retry_later_can_be_claimed_again_until_the_limit(repo):
    repo.claim("a", ["x"])
    repo.finish("a", "retry_later", None, None, None, 1, 0.0, ["API_UNAVAILABLE"], 1, [])
    again = repo.claim("a", ["x"])
    assert again.claimed is True and again.api_failures == 1
    repo.finish("a", "retry_later", None, None, None, 1, 0.0, ["API_UNAVAILABLE"], 3, [])
    assert repo.claim("a", ["x"]).claimed is False


def test_duplicate_delivery_through_the_pipeline_makes_one_repair(repo):
    p = make_pipeline([submit(GOOD)], repo=repo)
    first = p.process("dup-9", NEEDS_LLM_LINES)
    second = p.process("dup-9", NEEDS_LLM_LINES)
    assert first.route == REPAIRED and second.status == "skipped"
    assert repo.count() == 1 and len(p.client.requests) == 1
    row = repo.get("dup-9")
    assert row.attempts == 1 and row.status == "repaired" and row.repaired["TwnNm"] == "Jaipur"


def test_nothing_secret_is_stored(repo, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-SECRETSECRETSECRET")
    p = make_pipeline([submit(GOOD)], repo=repo)
    p.process("k-1", NEEDS_LLM_LINES)
    row = repo.get("k-1")
    assert "sk-ant" not in json.dumps(vars(row), default=str)


def test_the_schema_is_idempotent_and_leaves_the_java_tables_alone(pg_conn):
    connection.apply_schema(pg_conn)
    connection.apply_schema(pg_conn)
    sql = connection.SCHEMA_FILE.read_text()
    for java_table in ("messages", "addresses", "eval_runs", "review_items", "flyway_schema_history", "message_ingest_reports"):
        assert f"TABLE IF NOT EXISTS {java_table}" not in sql and f"ALTER TABLE {java_table}" not in sql
    assert "DROP" not in sql.upper().replace("DROPPED", "")
