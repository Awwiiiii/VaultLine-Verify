"""Verify migration round trip in an isolated transactional PostgreSQL schema."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

from vaultline_api.db.base import Base
from vaultline_api.db.session import get_engine


def test_verification_migration_round_trip():
    directory = Path(__file__).parents[1] / "migrations" / "versions"
    names = [
        "0001_database_foundation",
        "0002_cases_evidence",
        "0003_financial_extraction",
        "0004_verification_runs",
        "0005_financing_claims",
        "0006_investigations",
    ]
    modules = []
    for name in names:
        spec = spec_from_file_location(name, directory / f"{name}.py")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        modules.append(module)
    with get_engine().connect() as connection:
        transaction = connection.begin()
        try:
            # Generated identifier contains only ASCII letters and UUID hex.
            schema = "synthetic_migration_" + uuid4().hex
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            with Operations.context(MigrationContext.configure(connection)):
                for module in modules:
                    module.upgrade()
                assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
                assert "verification_findings" in inspect(connection).get_table_names(schema=schema)
                modules[-1].downgrade()
                assert "investigations" not in inspect(connection).get_table_names(schema=schema)
                assert "evidence_documents" in inspect(connection).get_table_names(schema=schema)
                modules[-1].upgrade()
                assert "verification_runs" in inspect(connection).get_table_names(schema=schema)
        finally:
            transaction.rollback()
