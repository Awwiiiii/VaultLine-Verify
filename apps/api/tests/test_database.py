"""Database session lifecycle tests without requiring PostgreSQL."""

from unittest.mock import MagicMock, patch

from vaultline_api.db.session import get_db_session


@patch("vaultline_api.db.session.get_session_factory")
def test_session_is_closed_and_unfinished_transaction_rolled_back(factory_mock: MagicMock) -> None:
    session = MagicMock()
    session.in_transaction.return_value = True
    factory_mock.return_value.return_value = session

    yielded = next(get_db_session())

    assert yielded is session
    session.rollback.assert_called_once()
    session.close.assert_called_once()
