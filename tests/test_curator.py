"""
test_curator.py
---------------
Unit tests for the Curator module.
Uses mocks so no real LLM calls are made.
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.curator import Curator


@pytest.fixture()
def mock_curator(tmp_path):
    c = Curator(run_id="test-run")
    # Replace LLM with a mock
    c.llm = MagicMock()
    c.llm.logger = MagicMock()
    c.llm.complete = MagicMock(
        return_value=json.dumps({
            "source_type": "test",
            "summary": "Test summary.",
            "key_data_points": ["Point A", "Point B"],
            "verbatim_quotes": ["Quote 1"],
            "metadata": {},
        })
    )
    return c, tmp_path


def test_curate_text_file(mock_curator):
    curator, tmp_path = mock_curator
    sample = tmp_path / "transcript.txt"
    sample.write_text("Customer said: I want a comparison tool.", encoding="utf-8")

    result = curator.curate(str(sample))

    assert result["source_type"] == "test"
    assert "summary" in result
    assert isinstance(result["verbatim_quotes"], list)


def test_curate_csv_file(mock_curator):
    curator, tmp_path = mock_curator

    # Create minimal CSV
    csv_file = tmp_path / "survey.csv"
    csv_file.write_text("question,response\nCompare prices?,Yes\n", encoding="utf-8")

    result = curator.curate(str(csv_file))
    assert "key_data_points" in result


def test_curate_unsupported_extension(mock_curator):
    curator, tmp_path = mock_curator
    bad_file = tmp_path / "file.docx"
    bad_file.write_text("content", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file type"):
        curator.curate(str(bad_file))


def test_curate_missing_file(mock_curator):
    curator, _ = mock_curator
    with pytest.raises(FileNotFoundError):
        curator.curate("nonexistent/path/file.txt")


def test_curate_url(mock_curator):
    curator, _ = mock_curator
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "<html><body>Article content here.</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = curator.curate("https://example.com/article")
        assert result["source_type"] == "test"
