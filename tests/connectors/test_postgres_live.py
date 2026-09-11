"""Opt-in integration tests against a dedicated disposable PostgreSQL database.

BASEERA_TEST_POSTGRES_URL must identify a database ending in ``_source_test``.
The suite creates and removes only its own unique tables in that database.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from baseera.errors import AppError
from baseera.source_adapters import SourceLimits, SourcePolicy, fetch_source
from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine
from sqlalchemy.engine import make_url


@pytest.fixture
def postgres_source():
    dsn = os.getenv("BASEERA_TEST_POSTGRES_URL")
    if not dsn:
        pytest.skip("A dedicated BASEERA_TEST_POSTGRES_URL is required")
    url = make_url(dsn)
    if not (url.database or "").endswith("_source_test"):
        pytest.fail("Refusing integration DDL outside a dedicated _source_test database")
    engine = create_engine(url)
    metadata = MetaData()
    table = Table(
        f"baseera_adapter_{uuid.uuid4().hex}",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("updated_at", DateTime(timezone=True), nullable=True),
        Column("name", String(80)),
        Column("amount", Numeric(12, 2)),
    )
    metadata.create_all(engine)
    instant = datetime(2026, 9, 5, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            table.insert(),
            [
                {
                    "id": value,
                    "updated_at": instant,
                    "name": f"شركة {value}",
                    "amount": Decimal("123.45") + value,
                }
                for value in [1, 2, 10]
            ],
        )
    host, port = url.host or "127.0.0.1", url.port or 5432
    configuration = {
        "host": host,
        "port": port,
        "database": url.database,
        "table": table.name,
        "columns": ["id", "updated_at", "name", "amount"],
    }
    credentials = {"username": url.username, "password": url.password}
    policy = SourcePolicy(
        allowed_hosts=(f"{host}:{port}",),
        private_hosts=(f"{host}:{port}",),
        postgres_sslmode="disable",
    )
    try:
        yield engine, table, configuration, credentials, policy
    finally:
        metadata.drop_all(engine)
        engine.dispose()


def test_postgres_real_keyset_resume_preserves_ties_and_decimal_precision(postgres_source):
    _, _, configuration, credentials, policy = postgres_source
    first = fetch_source(
        "postgresql", configuration, credentials, policy=policy, limits=SourceLimits(max_rows=2)
    )
    assert first.complete is False
    assert [record["id"] for record in first.records] == [1, 2]
    assert first.records[0]["name"] == "شركة 1"
    assert first.records[0]["amount"] == "124.45"
    second = fetch_source(
        "postgresql", configuration, credentials, policy=policy, checkpoint=first.checkpoint
    )
    assert second.complete is True
    assert [record["id"] for record in second.records] == [10]
    assert second.schema == first.schema
    empty = fetch_source(
        "postgresql", configuration, credentials, policy=policy, checkpoint=second.checkpoint
    )
    assert empty.complete is True
    assert empty.records == []
    assert empty.schema == first.schema
    assert empty.checkpoint == second.checkpoint


def test_postgres_rejects_null_watermark_before_advancing_checkpoint(postgres_source):
    engine, table, configuration, credentials, policy = postgres_source
    with engine.begin() as connection:
        connection.execute(table.insert().values(id=20, updated_at=None, name="missing"))
    with pytest.raises(AppError) as caught:
        fetch_source(
            "postgresql", configuration, credentials, policy=policy, limits=SourceLimits(max_rows=1)
        )
    assert caught.value.code == "connector_null_checkpoint"


def test_postgres_driver_transaction_is_read_only(postgres_source, monkeypatch):
    import baseera.source_adapters as adapters
    from sqlalchemy import event

    _, _, configuration, credentials, policy = postgres_source
    observed = []

    def monitored_engine(*args, **kwargs):
        engine = create_engine(*args, **kwargs)

        @event.listens_for(engine, "before_cursor_execute")
        def inspect_transaction(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("SELECT"):
                raw = connection.connection.cursor()
                raw.execute("SHOW transaction_read_only")
                observed.append(raw.fetchone()[0])
                raw.close()

        return engine

    monkeypatch.setattr(adapters, "create_engine", monitored_engine)
    batch = fetch_source("postgresql", configuration, credentials, policy=policy)
    assert len(batch.records) == 3
    assert observed and set(observed) == {"on"}
