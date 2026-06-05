"""Test suite for LinkedIn profile data extraction layer.

Tests cover:
- Individual extraction functions (name, headline, workplace, jobs, schools)
- Multi-strategy fallback behavior (JSON-LD → semantic → meta tags)
- Fail-safe error handling with try/except closures
- Edge cases (missing sections, malformed JSON-LD, minimal HTML)
- Integration with BeautifulSoup4 + lxml parser
"""

import pytest
from pathlib import Path
from bs4 import BeautifulSoup
from scraper import (
    extract_full_name,
    extract_headline,
    extract_current_workplace,
    extract_jobs_array,
    extract_schools_array,
    extract_profile_with_beautifulsoup,
)


@pytest.fixture
def sample_html_complete():
    """Load complete sample profile HTML."""
    path = Path(__file__).parent / "fixtures" / "sample_profile.html"
    with open(path, "r") as f:
        return f.read()


@pytest.fixture
def sample_html_minimal():
    """Load minimal sample profile HTML."""
    path = Path(__file__).parent / "fixtures" / "sample_profile_minimal.html"
    with open(path, "r") as f:
        return f.read()


@pytest.fixture
def soup_complete(sample_html_complete):
    """Parse complete HTML with BeautifulSoup lxml."""
    return BeautifulSoup(sample_html_complete, "lxml")


@pytest.fixture
def soup_minimal(sample_html_minimal):
    """Parse minimal HTML with BeautifulSoup lxml."""
    return BeautifulSoup(sample_html_minimal, "lxml")


class TestExtractFullName:
    """Test extract_full_name() function with multiple strategies."""

    def test_extract_from_h1_tag(self, soup_complete):
        """Extract name from h1 tag (primary semantic header)."""
        result = extract_full_name(soup_complete)
        assert result == "John Smith"

    def test_extract_from_jsonld_when_h1_missing(self):
        """Fallback to JSON-LD when h1 not present."""
        html = '''
        <html>
        <head>
          <script type="application/ld+json">
          {"name": "Alice Johnson"}
          </script>
        </head>
        <body></body>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_full_name(soup)
        assert result == "Alice Johnson"

    def test_extract_from_og_title_fallback(self):
        """Fallback to og:title when h1 and JSON-LD missing."""
        html = '''
        <html>
        <head>
          <meta property="og:title" content="Bob Wilson">
        </head>
        <body></body>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_full_name(soup)
        assert result == "Bob Wilson"

    def test_return_default_when_all_missing(self, soup_minimal):
        """Return default value when no extraction strategy succeeds."""
        result = extract_full_name(soup_minimal)
        # Jane Doe should be in h1
        assert result in ["Jane Doe", ""]

    def test_strip_whitespace(self):
        """Extracted name is stripped of whitespace."""
        html = '<h1>  John Doe  </h1>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_full_name(soup)
        assert result == "John Doe"
        assert result == result.strip()

    def test_ignore_short_strings(self):
        """Ignore names shorter than 2 characters."""
        html = '<h1>A</h1>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_full_name(soup)
        assert result == ""  # Falls through to default


class TestExtractHeadline:
    """Test extract_headline() function with multiple strategies."""

    def test_extract_from_semantic_headline_div(self, soup_complete):
        """Extract from div[id*='headline']."""
        result = extract_headline(soup_complete)
        assert "Senior Software Engineer" in result

    def test_extract_from_jsonld_jobTitle(self):
        """Fallback to JSON-LD jobTitle."""
        html = '''
        <html>
        <head>
          <script type="application/ld+json">
          {"jobTitle": "Staff Engineer at Meta"}
          </script>
        </head>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_headline(soup)
        assert result == "Staff Engineer at Meta"

    def test_extract_from_meta_description(self):
        """Fallback to meta description first part."""
        html = '''
        <html>
        <head>
          <meta name="description" content="Senior Developer | Tech Company Inc">
        </head>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_headline(soup)
        assert "Senior Developer" in result

    def test_return_default_when_missing(self):
        """Return empty string when headline not found."""
        html = '<html><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_headline(soup)
        assert result == ""

    def test_ignore_very_short_headlines(self):
        """Ignore headlines shorter than 3 characters."""
        html = '<div id="headline">AB</div>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_headline(soup)
        assert result == ""


class TestExtractCurrentWorkplace:
    """Test extract_current_workplace() function."""

    def test_extract_from_jsonld_worksFor(self, soup_complete):
        """Extract from JSON-LD worksFor field."""
        result = extract_current_workplace(soup_complete)
        assert result == "Acme Corporation"

    def test_extract_from_experience_section(self):
        """Fallback to experience section current marker."""
        html = '''
        <section id="experience-section">
          <div class="current">Acme Corp</div>
        </section>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_current_workplace(soup)
        assert result == "Acme Corp"

    def test_extract_from_strong_tag_in_experience(self):
        """Fallback to strong tag in experience section."""
        html = '''
        <section id="experience-section">
          <strong>TechCorp Inc</strong>
        </section>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_current_workplace(soup)
        assert result == "TechCorp Inc"

    def test_return_default_when_missing(self):
        """Return empty string when workplace not found."""
        html = '<html><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_current_workplace(soup)
        assert result == ""

    def test_handle_worksFor_as_list(self):
        """Handle JSON-LD worksFor as list (multiple current jobs)."""
        html = '''
        <html>
        <head>
          <script type="application/ld+json">
          {
            "worksFor": [
              {"name": "Company A"},
              {"name": "Company B"}
            ]
          }
          </script>
        </head>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_current_workplace(soup)
        assert result == "Company A"  # Takes first


class TestExtractJobsArray:
    """Test extract_jobs_array() function."""

    def test_extract_from_jsonld_workHistory(self, soup_complete):
        """Extract jobs from JSON-LD workHistory."""
        result = extract_jobs_array(soup_complete)
        assert isinstance(result, list)
        assert len(result) >= 1

        # Check structure
        if result:
            job = result[0]
            assert "title" in job
            assert "company" in job
            assert "duration" in job
            assert "description" in job

    def test_extract_jobs_structure(self, soup_complete):
        """Verify extracted jobs have required fields."""
        result = extract_jobs_array(soup_complete)
        assert len(result) == 2  # Sample has 2 jobs

        assert result[0]["title"] == "Senior Software Engineer"
        assert result[0]["company"] == "Acme Corp"

    def test_extract_from_experience_list_items(self):
        """Fallback to experience section li elements."""
        html = '''
        <section id="experience">
          <li>
            <h3>Product Manager</h3>
            <span class="company">StartupXYZ</span>
            <span class="date">2020 - 2021</span>
          </li>
        </section>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_jobs_array(soup)
        assert len(result) >= 1
        assert result[0]["title"] == "Product Manager"

    def test_return_empty_array_when_no_jobs(self):
        """Return empty list when no jobs found."""
        html = '<html><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_jobs_array(soup)
        assert result == []
        assert isinstance(result, list)

    def test_skip_empty_job_items(self):
        """Skip job items with no title or company."""
        html = '''
        <section id="experience">
          <li><span class="date">2020</span></li>
          <li>
            <h3>Engineer</h3>
            <span class="company">Company</span>
          </li>
        </section>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_jobs_array(soup)
        # Should only include items with title or company
        assert len(result) == 1


class TestExtractSchoolsArray:
    """Test extract_schools_array() function."""

    def test_extract_from_jsonld_alumniOf(self, soup_complete):
        """Extract schools from JSON-LD alumniOf."""
        result = extract_schools_array(soup_complete)
        assert isinstance(result, list)
        assert len(result) >= 1

        if result:
            school = result[0]
            assert "school" in school
            assert "degree" in school
            assert "field" in school
            assert "year" in school

    def test_extract_schools_structure(self, soup_complete):
        """Verify extracted schools have required fields."""
        result = extract_schools_array(soup_complete)
        assert len(result) == 1

        assert result[0]["school"] == "University of California, Berkeley"
        assert result[0]["degree"] == "BS"
        assert result[0]["field"] == "Computer Science"
        assert result[0]["year"] == "2019"

    def test_extract_from_education_list_items(self):
        """Fallback to education section li elements."""
        html = '''
        <section id="education">
          <li>
            <h3>Stanford University</h3>
            <span class="degree">BS</span>
            <span class="field">Computer Engineering</span>
            <span class="year">2018</span>
          </li>
        </section>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_schools_array(soup)
        assert len(result) == 1
        assert result[0]["school"] == "Stanford University"

    def test_return_empty_array_when_no_schools(self):
        """Return empty list when no schools found."""
        html = '<html><body></body></html>'
        soup = BeautifulSoup(html, "lxml")
        result = extract_schools_array(soup)
        assert result == []
        assert isinstance(result, list)

    def test_skip_schools_without_name(self):
        """Skip school entries without school name."""
        html = '''
        <section id="education">
          <li>
            <span class="degree">BA</span>
            <span class="year">2020</span>
          </li>
          <li>
            <h3>MIT</h3>
            <span class="degree">MS</span>
          </li>
        </section>
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_schools_array(soup)
        assert len(result) == 1
        assert result[0]["school"] == "MIT"


class TestExtractionIntegration:
    """Integration tests across multiple extraction functions."""

    def test_complete_profile_extraction(self, soup_complete):
        """Full profile data extraction with all fields."""
        name = extract_full_name(soup_complete)
        headline = extract_headline(soup_complete)
        workplace = extract_current_workplace(soup_complete)
        jobs = extract_jobs_array(soup_complete)
        schools = extract_schools_array(soup_complete)

        assert name == "John Smith"
        assert "Software Engineer" in headline
        assert workplace == "Acme Corporation"
        assert len(jobs) >= 1
        assert len(schools) >= 1

    def test_minimal_profile_extraction(self, soup_minimal):
        """Profile extraction with minimal HTML structure."""
        name = extract_full_name(soup_minimal)
        headline = extract_headline(soup_minimal)

        assert name == "Jane Doe"
        # headline may be empty with minimal HTML

    def test_malformed_jsonld_ignored(self):
        """Malformed JSON-LD is safely skipped."""
        html = '''
        <html>
        <head>
          <script type="application/ld+json">
          {invalid json
          </script>
        </head>
        <body>
          <h1>Alice</h1>
        </body>
        </html>
        '''
        soup = BeautifulSoup(html, "lxml")
        # Should fall back to h1
        result = extract_full_name(soup)
        assert result == "Alice"

    def test_lxml_handles_malformed_html(self):
        """lxml parser gracefully handles broken HTML."""
        html = '''
        <h1>Name</h1>
        <div id="headline">Senior Developer
        <!-- Missing closing div -->
        <p>Missing closing p
        '''
        soup = BeautifulSoup(html, "lxml")
        result = extract_full_name(soup)
        assert result == "Name"  # lxml auto-closes tags

    def test_special_characters_preserved(self):
        """Unicode and special characters are preserved."""
        html = '''
        <h1>José María García-López</h1>
        <div id="headline">CTO at Société Générale</div>
        '''
        soup = BeautifulSoup(html, "lxml")
        name = extract_full_name(soup)
        headline = extract_headline(soup)

        assert "José" in name
        assert "Générale" in headline


class TestExtractProfileWithBeautifulSoup:
    """Test async wrapper function extract_profile_with_beautifulsoup()."""

    def test_returns_dict_with_all_keys(self, sample_html_complete):
        """Returned dict contains all required keys."""
        import asyncio
        from unittest.mock import AsyncMock

        async def run_test():
            page = AsyncMock()
            page.content = AsyncMock(return_value=sample_html_complete)
            return await extract_profile_with_beautifulsoup(page, "https://linkedin.com/in/test")

        result = asyncio.run(run_test())

        required_keys = [
            "linkedin_url",
            "full_name",
            "headline",
            "current_workplace",
            "location",
            "about_text",
            "jobs",
            "schools",
        ]
        for key in required_keys:
            assert key in result

    def test_isolated_extraction_errors(self, sample_html_minimal):
        """Single extraction failure doesn't crash entire function."""
        import asyncio
        from unittest.mock import AsyncMock

        async def run_test():
            page = AsyncMock()
            page.content = AsyncMock(return_value=sample_html_minimal)
            return await extract_profile_with_beautifulsoup(page, "https://linkedin.com/in/test")

        result = asyncio.run(run_test())

        # Should return dict with defaults, not raise
        assert isinstance(result, dict)
        assert result["full_name"] == "Jane Doe"
        assert result["jobs"] == []
        assert result["schools"] == []

    def test_page_parsing_failure_returns_defaults(self):
        """Page content parsing error returns profile dict with empty values."""
        import asyncio
        from unittest.mock import AsyncMock

        async def run_test():
            page = AsyncMock()
            page.content = AsyncMock(side_effect=Exception("Page fetch failed"))
            return await extract_profile_with_beautifulsoup(page, "https://linkedin.com/in/test")

        result = asyncio.run(run_test())

        # Should return dict with defaults
        assert result["linkedin_url"] == "https://linkedin.com/in/test"
        assert result["full_name"] == ""
        assert result["jobs"] == []
