"""Tests for the redesigned multipage UI: pure helpers + page smoke."""
import json

import pandas as pd
import pytest

from ui_helpers import (
    split_url_validation,
    filter_profiles,
    prepare_profiles_table,
    top_companies,
    collection_timeline,
)


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        [
            {
                "linkedin_url": "https://www.linkedin.com/in/alice",
                "full_name": "Alice Smith",
                "headline": "Senior Engineer",
                "location": "London",
                "current_company": "Acme",
                "about_text": "Builder.",
                "experience_json": json.dumps([{"title": "SWE"}, {"title": "Lead"}]),
                "education_json": json.dumps([{"school": "MIT"}]),
                "collected_at": "2026-06-05 10:00:00",
            },
            {
                "linkedin_url": "https://www.linkedin.com/in/bob",
                "full_name": "Bob Jones",
                "headline": "Designer",
                "location": "Berlin",
                "current_company": "Globex",
                "about_text": None,
                "experience_json": json.dumps([{"title": "UX"}]),
                "education_json": None,
                "collected_at": "2026-06-04 09:00:00",
            },
        ]
    )


class TestUrlValidation:
    def test_splits_valid_and_invalid(self):
        text = "https://www.linkedin.com/in/alice\nnot-a-url\nhttps://linkedin.com/in/bob"
        valid, invalid = split_url_validation(text)
        assert valid == ["https://www.linkedin.com/in/alice", "https://linkedin.com/in/bob"]
        assert invalid == ["not-a-url"]

    def test_ignores_blank_lines(self):
        valid, invalid = split_url_validation("\n  \nhttps://linkedin.com/in/x\n")
        assert valid == ["https://linkedin.com/in/x"]
        assert invalid == []

    def test_empty_input(self):
        assert split_url_validation("") == ([], [])
        assert split_url_validation(None) == ([], [])


class TestFilterProfiles:
    def test_company_filter(self, sample_df):
        out = filter_profiles(sample_df, ["Acme"], "")
        assert list(out["full_name"]) == ["Alice Smith"]

    def test_search_matches_name_and_headline(self, sample_df):
        assert list(filter_profiles(sample_df, [], "bob")["full_name"]) == ["Bob Jones"]
        assert list(filter_profiles(sample_df, [], "designer")["full_name"]) == ["Bob Jones"]

    def test_no_filters_returns_all(self, sample_df):
        assert len(filter_profiles(sample_df, [], "")) == 2

    def test_empty_df(self):
        empty = pd.DataFrame()
        assert filter_profiles(empty, ["x"], "y").empty


class TestPrepareTable:
    def test_columns_and_counts(self, sample_df):
        table = prepare_profiles_table(sample_df)
        assert list(table.columns) == [
            "Name", "Headline", "Location", "Company", "Jobs", "Degrees", "Profile", "Collected"
        ]
        alice = table[table["Name"] == "Alice Smith"].iloc[0]
        assert alice["Jobs"] == 2
        assert alice["Degrees"] == 1
        assert alice["Profile"] == "https://www.linkedin.com/in/alice"

    def test_sorted_desc_by_collected(self, sample_df):
        table = prepare_profiles_table(sample_df)
        assert table.iloc[0]["Name"] == "Alice Smith"  # newer first

    def test_empty_df_returns_typed_empty(self):
        table = prepare_profiles_table(pd.DataFrame())
        assert table.empty
        assert "Profile" in table.columns


class TestAggregations:
    def test_top_companies(self, sample_df):
        tc = top_companies(sample_df, 8)
        assert set(tc.index) == {"Acme", "Globex"}
        assert tc.loc["Acme", "Profiles"] == 1

    def test_timeline_groups_by_day(self, sample_df):
        tl = collection_timeline(sample_df)
        assert tl["Profiles"].sum() == 2
        assert len(tl) == 2

    def test_empty_aggregations(self):
        assert top_companies(pd.DataFrame()).empty
        assert collection_timeline(pd.DataFrame()).empty


class TestAppSmoke:
    """AppTest smoke: entry + each page renders without raising."""

    def _run(self, script):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(script, default_timeout=30)
        at.run()
        return at

    def test_entry_runs(self):
        at = self._run("app.py")
        assert not at.exception

    @pytest.mark.parametrize(
        "page",
        [
            "pages/1_dashboard.py",
            "pages/2_collect.py",
            "pages/3_live_monitor.py",
            "pages/4_data.py",
            "pages/5_settings.py",
        ],
    )
    def test_page_runs(self, page):
        at = self._run(page)
        assert not at.exception
