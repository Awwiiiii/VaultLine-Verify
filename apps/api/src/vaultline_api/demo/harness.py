"""Rollback-only PostgreSQL schema and private temporary files for local demonstrations."""

from contextlib import contextmanager
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.orm import Session

from vaultline_api.core.config import get_settings
from vaultline_api.db.session import get_db_session, get_engine
from vaultline_api.investigations.providers import MetaAIProvider, get_provider
from vaultline_api.main import create_app


@contextmanager
def isolated_demo():
    """Never commit, delete user records, edit secrets or change the default app provider."""
    settings = get_settings()
    names = (
        "evidence_storage_dir",
        "cors_allowed_origins",
        "verification_amount_tolerance",
        "verification_quantity_tolerance",
        "verification_price_tolerance",
    )
    previous = {name: getattr(settings, name) for name in names}
    with (
        TemporaryDirectory(prefix="vaultline-synthetic-") as storage,
        get_engine().connect() as conn,
    ):
        transaction = conn.begin()
        try:
            schema = "synthetic_demo_" + uuid4().hex
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            migrations = Path(__file__).resolve().parents[3] / "migrations" / "versions"
            with Operations.context(MigrationContext.configure(conn)):
                for path in sorted(migrations.glob("*.py")):
                    spec = spec_from_file_location(path.stem, path)
                    module = module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.upgrade()
            settings.evidence_storage_dir = Path(storage)
            settings.cors_allowed_origins = [
                "http://127.0.0.1:3100",
                "http://localhost:3100",
                "http://127.0.0.1:3101",
            ]
            for name in names[2:]:
                setattr(settings, name, Decimal("0"))
            app = create_app()
            lock = Lock()

            def sessions():
                # Generator setup/teardown may run on different threads; Lock supports that.
                with (
                    lock,
                    Session(
                        conn, join_transaction_mode="create_savepoint", expire_on_commit=False
                    ) as session,
                ):
                    yield session

            app.dependency_overrides[get_db_session] = sessions
            app.dependency_overrides[get_provider] = lambda: MetaAIProvider(allow_requests=False)
            yield app
        finally:
            transaction.rollback()
            for name, value in previous.items():
                setattr(settings, name, value)
