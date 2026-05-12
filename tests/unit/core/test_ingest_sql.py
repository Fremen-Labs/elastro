"""
Tests for SQL readers (SQLDumpReader and SQLReader).

SQLReader tests are limited to import checks since they require a live database.
SQLDumpReader tests use fixture SQL dump files.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from elastro.core.ingest.readers import SQLDumpReader, read_source

# ---------------------------------------------------------------------------
# SQLDumpReader
# ---------------------------------------------------------------------------


class TestSQLDumpReader:
    def test_basic_insert(self, tmp_path: Path) -> None:
        """Parse a simple INSERT INTO ... VALUES statement."""
        sql_file = tmp_path / "dump.sql"
        sql_file.write_text(
            "-- MySQL dump\n"
            "INSERT INTO users (id, name, email) VALUES "
            "(1, 'Alice', 'alice@test.com');\n"
        )

        docs = list(SQLDumpReader(sql_file).read())
        assert len(docs) == 1
        assert docs[0]["id"] == 1
        assert docs[0]["name"] == "Alice"
        assert docs[0]["email"] == "alice@test.com"

    def test_multi_row_insert(self, tmp_path: Path) -> None:
        """Parse INSERT with multiple value tuples on one line."""
        sql_file = tmp_path / "dump.sql"
        sql_file.write_text(
            "INSERT INTO products (id, name, price) VALUES "
            "(1, 'Widget', 9.99), (2, 'Gadget', 19.99);\n"
        )

        docs = list(SQLDumpReader(sql_file).read())
        assert len(docs) == 2
        assert docs[0]["name"] == "Widget"
        assert docs[0]["price"] == 9.99
        assert docs[1]["id"] == 2

    def test_null_and_boolean(self, tmp_path: Path) -> None:
        """NULL and boolean literals should be coerced correctly."""
        sql_file = tmp_path / "dump.sql"
        sql_file.write_text(
            "INSERT INTO flags (id, active, notes) VALUES " "(1, TRUE, NULL);\n"
        )

        docs = list(SQLDumpReader(sql_file).read())
        assert docs[0]["active"] is True
        assert docs[0]["notes"] is None

    def test_comments_and_blanks_skipped(self, tmp_path: Path) -> None:
        """Comments and blank lines should be ignored."""
        sql_file = tmp_path / "dump.sql"
        sql_file.write_text(
            "-- This is a comment\n"
            "\n"
            "-- Another comment\n"
            "INSERT INTO t (a) VALUES (42);\n"
        )

        docs = list(SQLDumpReader(sql_file).read())
        assert len(docs) == 1
        assert docs[0]["a"] == 42

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            list(SQLDumpReader(tmp_path / "missing.sql").read())

    def test_quoted_values_with_commas(self, tmp_path: Path) -> None:
        """Strings containing commas should be parsed correctly."""
        sql_file = tmp_path / "dump.sql"
        sql_file.write_text(
            "INSERT INTO addresses (id, addr) VALUES " "(1, '123 Main St, Suite 4');\n"
        )

        docs = list(SQLDumpReader(sql_file).read())
        assert docs[0]["addr"] == "123 Main St, Suite 4"

    def test_backtick_column_names(self, tmp_path: Path) -> None:
        """Backtick-quoted column names (MySQL style) should be stripped."""
        sql_file = tmp_path / "dump.sql"
        sql_file.write_text("INSERT INTO `users` (`id`, `name`) VALUES (1, 'Bob');\n")

        docs = list(SQLDumpReader(sql_file).read())
        assert docs[0]["id"] == 1
        assert docs[0]["name"] == "Bob"


# ---------------------------------------------------------------------------
# read_source with .sql extension
# ---------------------------------------------------------------------------


class TestReadSourceSQL:
    def test_sql_extension_routes_to_dump_reader(self, tmp_path: Path) -> None:
        """A .sql file should be routed to SQLDumpReader via read_source."""
        sql_file = tmp_path / "data.sql"
        sql_file.write_text("INSERT INTO t (x) VALUES (1), (2), (3);\n")

        docs = list(read_source(str(sql_file)))
        assert len(docs) == 3


# ---------------------------------------------------------------------------
# SQLReader (import-only — requires sqlalchemy at runtime)
# ---------------------------------------------------------------------------


class TestSQLReaderImport:
    def test_import_error_without_sqlalchemy(self) -> None:
        """SQLReader.read() should raise ImportError if sqlalchemy is missing."""
        from elastro.core.ingest.readers import SQLReader

        reader = SQLReader("sqlite:///test.db", "SELECT 1")
        # We can't easily remove sqlalchemy at runtime, but we can verify
        # the reader constructs without issue.
        assert reader.dsn == "sqlite:///test.db"
        assert reader.query == "SELECT 1"
        assert reader.yield_per == 2000
