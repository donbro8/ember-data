"""Tests for WatchStore CRUD operations with a mocked BigQuery client."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from ember_data.bigquery.watch_schema import WatchConfig
from ember_data.bigquery.watch_store import WatchStore

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
_DATASET = "ember_test"
_TABLE = f"{_DATASET}.watch_configs"


def _make_store(rows: list[dict] | None = None) -> tuple[WatchStore, MagicMock]:
    """Create a WatchStore with a mocked client.

    Args:
        rows: Default return value for query_with_params.
    """
    client = MagicMock()
    client.query_with_params.return_value = rows or []
    store = WatchStore(client, _DATASET)
    return store, client


def _sample_row(**overrides: object) -> dict:
    base = {
        "watch_id": "test-uuid-1234",
        "name": "Test Watch",
        "query": "adalimumab biosimilars",
        "schedule": "weekly",
        "schedule_day": 1,
        "enabled": True,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
        "last_run_id": None,
        "last_run_at": None,
        "notify_on_change": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestWatchStoreCreate:
    def test_create_returns_watch_config(self):
        store, client = _make_store()
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            config = store.create(name="Test", query="q", schedule="weekly")
        assert isinstance(config, WatchConfig)
        assert config.name == "Test"
        assert config.query == "q"
        assert config.schedule == "weekly"

    def test_create_generates_uuid(self):
        store, _ = _make_store()
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            c1 = store.create(name="A", query="q", schedule="weekly")
            c2 = store.create(name="B", query="q", schedule="weekly")
        assert c1.watch_id != c2.watch_id
        assert len(c1.watch_id) == 36  # UUID format

    def test_create_sets_timestamps_to_now(self):
        store, _ = _make_store()
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            config = store.create(name="T", query="q", schedule="weekly")
        assert config.created_at == _NOW
        assert config.updated_at == _NOW

    def test_create_calls_insert_rows(self):
        store, client = _make_store()
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            store.create(name="T", query="q", schedule="monthly", schedule_day=5)
        client.insert_rows.assert_called_once()
        table_arg, rows_arg = client.insert_rows.call_args.args
        assert table_arg == _TABLE
        assert len(rows_arg) == 1
        row = rows_arg[0]
        assert row["name"] == "T"
        assert row["query"] == "q"
        assert row["schedule"] == "monthly"
        assert row["schedule_day"] == 5

    def test_create_defaults_enabled_true(self):
        store, _ = _make_store()
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            config = store.create(name="T", query="q", schedule="weekly")
        assert config.enabled is True

    def test_create_sets_notify_on_change(self):
        store, _ = _make_store()
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            config = store.create(name="T", query="q", schedule="weekly", notify_on_change=True)
        assert config.notify_on_change is True


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestWatchStoreGet:
    def test_get_returns_watch_config(self):
        store, client = _make_store(rows=[_sample_row()])
        result = store.get("test-uuid-1234")
        assert isinstance(result, WatchConfig)
        assert result.watch_id == "test-uuid-1234"

    def test_get_returns_none_for_missing_watch(self):
        store, client = _make_store(rows=[])
        result = store.get("nonexistent-id")
        assert result is None

    def test_get_uses_parameterized_query(self):
        store, client = _make_store(rows=[_sample_row()])
        store.get("test-uuid-1234")
        client.query_with_params.assert_called_once()
        _, params = client.query_with_params.call_args.args
        assert params.get("watch_id") == "test-uuid-1234"

    def test_get_does_not_use_string_interpolation(self):
        store, client = _make_store(rows=[_sample_row()])
        store.get("test-uuid-1234")
        sql_arg = client.query_with_params.call_args.args[0]
        assert "test-uuid-1234" not in sql_arg


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestWatchStoreList:
    def test_list_returns_all_configs(self):
        rows = [_sample_row(watch_id="id-1"), _sample_row(watch_id="id-2")]
        store, client = _make_store(rows=rows)
        result = store.list()
        assert len(result) == 2
        assert all(isinstance(r, WatchConfig) for r in result)

    def test_list_enabled_only_includes_where_clause(self):
        store, client = _make_store(rows=[])
        store.list(enabled_only=True)
        sql_arg = client.query_with_params.call_args.args[0]
        assert "enabled" in sql_arg.lower()

    def test_list_without_enabled_only_omits_where_enabled(self):
        store, client = _make_store(rows=[])
        store.list(enabled_only=False)
        sql_arg = client.query_with_params.call_args.args[0]
        # Should not filter by enabled when enabled_only=False
        assert "WHERE enabled = TRUE" not in sql_arg

    def test_list_returns_empty_list_when_no_rows(self):
        store, _ = _make_store(rows=[])
        result = store.list()
        assert result == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


class TestWatchStoreUpdate:
    def test_update_returns_updated_config(self):
        updated_row = _sample_row(name="Updated Name")
        store, client = _make_store()
        # query_with_params: first call for UPDATE (DML returns []), second for get()
        client.query_with_params.side_effect = [[], [updated_row]]
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            result = store.update("test-uuid-1234", name="Updated Name")
        assert result.name == "Updated Name"

    def test_update_includes_updated_at(self):
        store, client = _make_store()
        updated_row = _sample_row()
        client.query_with_params.side_effect = [[], [updated_row]]
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            store.update("test-uuid-1234", enabled=False)
        # First call is the UPDATE DML
        first_call_sql = client.query_with_params.call_args_list[0].args[0]
        assert "updated_at" in first_call_sql

    def test_update_only_specified_fields_in_set_clause(self):
        store, client = _make_store()
        updated_row = _sample_row()
        client.query_with_params.side_effect = [[], [updated_row]]
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            store.update("test-uuid-1234", name="New Name")
        first_call_sql = client.query_with_params.call_args_list[0].args[0]
        # "name" should be in SET, but "query" should not be
        assert "name" in first_call_sql
        # "query" is not being updated so should not appear in SET
        assert "query = @query" not in first_call_sql

    def test_update_raises_if_not_found_after_update(self):
        store, client = _make_store()
        # UPDATE returns [], then get() returns []
        client.query_with_params.side_effect = [[], []]
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            with pytest.raises(ValueError, match="not found"):
                store.update("nonexistent", name="X")


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestWatchStoreDelete:
    def test_delete_returns_true_when_exists(self):
        store, client = _make_store()
        # get() returns a row, then DELETE query
        client.query_with_params.side_effect = [[_sample_row()], []]
        result = store.delete("test-uuid-1234")
        assert result is True

    def test_delete_returns_false_for_nonexistent_watch(self):
        store, client = _make_store(rows=[])
        result = store.delete("nonexistent-id")
        assert result is False

    def test_delete_calls_delete_sql_when_found(self):
        store, client = _make_store()
        client.query_with_params.side_effect = [[_sample_row()], []]
        store.delete("test-uuid-1234")
        # Two calls: get() and DELETE
        assert client.query_with_params.call_count == 2
        delete_sql = client.query_with_params.call_args_list[1].args[0]
        assert "DELETE" in delete_sql.upper()

    def test_delete_does_not_call_delete_sql_when_not_found(self):
        store, client = _make_store(rows=[])
        store.delete("nonexistent-id")
        # Only one call: get() that returns empty
        assert client.query_with_params.call_count == 1


# ---------------------------------------------------------------------------
# record_run
# ---------------------------------------------------------------------------


class TestWatchStoreRecordRun:
    def test_record_run_calls_query_with_correct_params(self):
        store, client = _make_store(rows=[])
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            store.record_run("test-uuid-1234", "run-abc")
        client.query_with_params.assert_called_once()
        sql, params = client.query_with_params.call_args.args
        assert params["watch_id"] == "test-uuid-1234"
        assert params["run_id"] == "run-abc"
        assert "last_run_at" in params
        assert "updated_at" in params

    def test_record_run_updates_both_fields_in_sql(self):
        store, client = _make_store(rows=[])
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            store.record_run("test-uuid-1234", "run-abc")
        sql = client.query_with_params.call_args.args[0]
        assert "last_run_id" in sql
        assert "last_run_at" in sql

    def test_record_run_uses_parameterized_query(self):
        store, client = _make_store(rows=[])
        with patch("ember_data.bigquery.watch_store._now_utc", return_value=_NOW):
            store.record_run("test-uuid-1234", "run-abc")
        sql = client.query_with_params.call_args.args[0]
        assert "run-abc" not in sql
        assert "test-uuid-1234" not in sql
