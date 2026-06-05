"""Tests for Streamlit app UI components and state management."""
import pytest
import pandas as pd
import json
from pathlib import Path
import tempfile
from datetime import datetime
import sys
from io import BytesIO

# Import modules to test
from ui_helpers import (
    validate_session_file,
    calculate_profile_metrics,
    prepare_profiles_dataframe,
)
from export_helpers import (
    export_profiles_to_csv,
    export_profiles_to_excel,
    generate_export_filename,
)

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


class TestSessionValidation:
    """Test session.json validation logic."""

    def test_validate_session_file_not_found(self):
        """Missing session file returns invalid."""
        is_valid, status, expiry = validate_session_file("/nonexistent/path.json")
        assert is_valid is False
        assert "not found" in status.lower()

    def test_validate_session_file_empty(self):
        """Empty session file returns invalid."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            is_valid, status, expiry = validate_session_file(temp_path)
            assert is_valid is False
            assert "empty" in status.lower()
        finally:
            Path(temp_path).unlink()

    def test_validate_session_file_invalid_json(self):
        """Malformed JSON returns invalid."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{ invalid json")
            temp_path = f.name

        try:
            is_valid, status, expiry = validate_session_file(temp_path)
            assert is_valid is False
            assert "json" in status.lower()
        finally:
            Path(temp_path).unlink()

    def test_validate_session_file_missing_keys(self):
        """Session missing required keys returns invalid."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"cookies": []}, f)
            temp_path = f.name

        try:
            is_valid, status, expiry = validate_session_file(temp_path)
            assert is_valid is False
            assert "origins" in status or "missing" in status.lower()
        finally:
            Path(temp_path).unlink()

    def test_validate_session_file_no_cookies(self):
        """Session with empty cookies returns invalid."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"cookies": [], "origins": []}, f)
            temp_path = f.name

        try:
            is_valid, status, expiry = validate_session_file(temp_path)
            assert is_valid is False
        finally:
            Path(temp_path).unlink()

    def test_validate_session_file_valid(self):
        """Valid session file returns True."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "cookies": [{"name": "li_at", "value": "token123"}],
                    "origins": [{"origin": "https://linkedin.com"}],
                },
                f,
            )
            temp_path = f.name

        try:
            is_valid, status, expiry = validate_session_file(temp_path)
            assert is_valid is True
            assert "valid" in status.lower()
        finally:
            Path(temp_path).unlink()


class TestMetricsCalculation:
    """Test profile metrics calculation."""

    def test_metrics_empty_dataframe(self):
        """Empty dataframe returns zero metrics."""
        df = pd.DataFrame()
        metrics = calculate_profile_metrics(df)
        assert metrics["total_count"] == 0
        assert metrics["new_today"] == 0
        assert metrics["avg_experience_years"] == 0

    def test_metrics_total_count(self):
        """Total count reflects dataframe length."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice", "Bob"],
                "collected_at": [datetime.now(), datetime.now()],
                "experience_json": ["[]", "[]"],
                "education_json": ["[]", "[]"],
            }
        )
        metrics = calculate_profile_metrics(df)
        assert metrics["total_count"] == 2

    def test_metrics_new_today(self):
        """New today includes only recent profiles."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice", "Bob", "Charlie"],
                "collected_at": [
                    datetime.now(),
                    datetime.now(),
                    datetime(2020, 1, 1),
                ],
                "experience_json": ["[]", "[]", "[]"],
                "education_json": ["[]", "[]", "[]"],
            }
        )
        metrics = calculate_profile_metrics(df)
        assert metrics["new_today"] == 2

    def test_metrics_average_experience(self):
        """Average experience calculated from experience_json."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice", "Bob"],
                "collected_at": [datetime.now(), datetime.now()],
                "experience_json": [
                    json.dumps([{"title": "SWE"}, {"title": "Intern"}]),  # 2 jobs
                    json.dumps([{"title": "PM"}]),  # 1 job
                ],
                "education_json": ["[]", "[]"],
            }
        )
        metrics = calculate_profile_metrics(df)
        assert metrics["avg_experience_years"] == 1.5


class TestDataframePreparation:
    """Test dataframe preparation for display."""

    def test_prepare_empty_dataframe(self):
        """Empty dataframe returns empty."""
        df = pd.DataFrame()
        result = prepare_profiles_dataframe(df)
        assert len(result) == 0

    def test_prepare_columns_present(self):
        """Prepared dataframe has correct columns."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice"],
                "headline": ["SWE"],
                "location": ["SF"],
                "current_company": ["Acme"],
                "experience_json": [json.dumps([{"title": "SWE"}])],
                "education_json": [json.dumps([{"school": "MIT"}])],
                "collected_at": [datetime.now()],
            }
        )
        result = prepare_profiles_dataframe(df)
        expected_cols = [
            "Name",
            "Headline",
            "Location",
            "Company",
            "Jobs",
            "Degrees",
            "Collected",
        ]
        assert list(result.columns) == expected_cols

    def test_prepare_job_count_parsing(self):
        """Job count derived from experience_json."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice"],
                "headline": ["SWE"],
                "location": ["SF"],
                "current_company": ["Acme"],
                "experience_json": [
                    json.dumps([{"title": "SWE"}, {"title": "Intern"}])
                ],
                "education_json": [json.dumps([])],
                "collected_at": [datetime.now()],
            }
        )
        result = prepare_profiles_dataframe(df)
        assert result["Jobs"].iloc[0] == 2

    def test_prepare_degree_count_parsing(self):
        """Degree count derived from education_json."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice"],
                "headline": ["SWE"],
                "location": ["SF"],
                "current_company": ["Acme"],
                "experience_json": [json.dumps([])],
                "education_json": [
                    json.dumps([{"school": "MIT"}, {"school": "Stanford"}])
                ],
                "collected_at": [datetime.now()],
            }
        )
        result = prepare_profiles_dataframe(df)
        assert result["Degrees"].iloc[0] == 2


class TestExportFunctions:
    """Test CSV/Excel export logic."""

    def test_export_csv_empty_dataframe(self):
        """Empty dataframe exports as empty bytes."""
        df = pd.DataFrame()
        result = export_profiles_to_csv(df)
        assert result == b""

    def test_export_csv_has_header(self):
        """CSV export includes column headers."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice"],
                "headline": ["SWE"],
                "location": ["SF"],
                "current_company": ["Acme"],
                "experience_json": [json.dumps([])],
                "education_json": [json.dumps([])],
                "collected_at": [datetime.now()],
            }
        )
        result = export_profiles_to_csv(df)
        csv_text = result.decode("utf-8")
        assert "Name" in csv_text
        assert "Headline" in csv_text

    def test_export_csv_has_data(self):
        """CSV export includes data rows."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice"],
                "headline": ["SWE"],
                "location": ["SF"],
                "current_company": ["Acme"],
                "experience_json": [json.dumps([])],
                "education_json": [json.dumps([])],
                "collected_at": [datetime.now()],
            }
        )
        result = export_profiles_to_csv(df)
        csv_text = result.decode("utf-8")
        assert "Alice" in csv_text

    def test_export_excel_empty_dataframe(self):
        """Empty dataframe exports as empty bytes."""
        df = pd.DataFrame()
        result = export_profiles_to_excel(df)
        assert result == b""

    @pytest.mark.skipif(not HAS_OPENPYXL, reason="openpyxl not installed")
    def test_export_excel_has_content(self):
        """Excel export produces non-empty bytes."""
        df = pd.DataFrame(
            {
                "full_name": ["Alice"],
                "headline": ["SWE"],
                "location": ["SF"],
                "current_company": ["Acme"],
                "experience_json": [json.dumps([])],
                "education_json": [json.dumps([])],
                "collected_at": [datetime.now()],
            }
        )
        result = export_profiles_to_excel(df)
        assert len(result) > 0
        assert result.startswith(b"PK")  # ZIP file signature

    def test_export_filename_generation(self):
        """Generated filename has correct format."""
        filename = generate_export_filename("csv")
        assert filename.startswith("linkedin_profiles_export_")
        assert filename.endswith(".csv")
        assert "_" in filename  # Contains timestamp

    def test_export_filename_excel(self):
        """Generated Excel filename has correct format."""
        filename = generate_export_filename("xlsx")
        assert filename.startswith("linkedin_profiles_export_")
        assert filename.endswith(".xlsx")
