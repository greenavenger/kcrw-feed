"""Module to test the processing of shows"""

import pytest
from datetime import datetime
from typing import Optional
from kcrw_feed.sitemap_processor import SitemapProcessor
from kcrw_feed import utils


def fake_get_file(path: str, timeout: int = 10) -> Optional[bytes]:
    """Fake get_file function to simulate file retrieval."""
    if path == "https://www.testsite.com/robots.txt":
        content = (
            "User-agent: *\n"
            "Disallow: /private/\n"
            "Sitemap: https://www.testsite.com/sitemap1.xml\n"
            "Sitemap: https://www.testsite.com/sitemap2.xml\n"
        )
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/sitemap1.xml":
        # This sitemap contains two <loc> values:
        # one for a music show and one for another URL.
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show1</loc>
    <lastmod>2025-01-01T00:00:00</lastmod>
  </url>
  <url>
    <loc>https://www.testsite.com/other/url</loc>
  </url>
</urlset>"""
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/sitemap2.xml":
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show2</loc>
    <changefreq>weekly</changefreq>
  </url>
</urlset>"""
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/extra-sitemap.xml":
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show3</loc>
    <priority>0.8</priority>
  </url>
</urlset>"""
        return content.encode("utf-8")
    return None


@pytest.fixture(autouse=True)
def patch_get_file(monkeypatch):
    """Automatically patch utils.get_file in all tests in this module."""
    monkeypatch.setattr(utils, "get_file", fake_get_file)


def test_find_sitemaps():
    """
    Test that find_sitemaps() correctly reads robots.txt and includes
    both the discovered sitemaps and any extra sitemaps provided.
    """
    processor = SitemapProcessor("https://www.testsite.com/",
                                 extra_sitemaps=["extra-sitemap.xml"])
    sitemap_urls = processor.find_sitemaps()
    expected = {
        "https://www.testsite.com/sitemap1.xml",
        "https://www.testsite.com/sitemap2.xml",
        "https://www.testsite.com/extra-sitemap.xml"
    }
    assert set(sitemap_urls) == expected


def test_read_sitemap():
    """
    Test that read_sitemap() correctly parses a sitemap XML file and populates
    the internal urls dict with entries that match the music filter.
    """
    processor = SitemapProcessor("https://www.testsite.com/")
    # Read fake sitemap1.xml.
    processor.read_sitemap("https://www.testsite.com/sitemap1.xml")
    # Our fake sitemap1.xml has two <url> entries, but only the one matching
    # /music/shows/ should be stored.
    assert "https://www.testsite.com/music/shows/show1" in processor._sitemap_entities
    # The non-music URL should not be present.
    assert "https://www.testsite.com/other/url" not in processor._sitemap_entities


def test_gather_shows():
    """
    Test that gather_shows() returns only music show URLs, combining data from
    robots.txt and extra sitemaps.
    """
    processor = SitemapProcessor("https://www.testsite.com/",
                                 extra_sitemaps=["/extra-sitemap.xml"])
    # When gather_shows is called, it processes all sitemaps and stores entries in self.urls.
    urls = processor.gather_entries(source="sitemap")
    expected = {
        "https://www.testsite.com/music/shows/show1",
        "https://www.testsite.com/music/shows/show2",
        "https://www.testsite.com/music/shows/show3"
    }
    assert set(urls) == expected

# Tests for _extract_entries() remain similar.


def test_extract_entries_simple():
    """Test _extract_entries() on a simple dict with only 'loc'."""
    processor = SitemapProcessor("https://www.testsite.com/")
    data = {"loc": "https://www.testsite.com/music/shows/showX"}
    processor._sitemap_entities = {}  # Reset internal dictionary.
    processor._extract_entries(data)
    expected = {"https://www.testsite.com/music/shows/showX":
                {"loc": "https://www.testsite.com/music/shows/showX"}}
    assert processor._sitemap_entities == expected


def test_extract_entries_with_optional_fields():
    """Test _extract_entries() when optional fields are present with mixed key case."""
    processor = SitemapProcessor("https://www.testsite.com/")
    data = {
        "LoC": "https://www.testsite.com/music/shows/showY",
        "LASTMOD": "2025-02-01T00:00:00",
        "ChangeFreq": "weekly",
        "Priority": "0.5"
    }
    processor._sitemap_entities = {}
    processor._extract_entries(data)
    expected = {
        "https://www.testsite.com/music/shows/showY": {
            "loc": "https://www.testsite.com/music/shows/showY",
            "lastmod": "2025-02-01T00:00:00",
            "changefreq": "weekly",
            "priority": "0.5"
        }
    }
    assert processor._sitemap_entities == expected


def test_extract_entries_nested():
    """Test _extract_entries() on nested data structures."""
    processor = SitemapProcessor("https://www.testsite.com/")
    data = {
        "urlset": {
            "url": [
                {"loc": "https://www.testsite.com/music/shows/showA"},
                {"loc": "https://www.testsite.com/other/url"}
            ]
        }
    }
    processor._sitemap_entities = {}
    processor._extract_entries(data)
    # Only the music show should be stored.
    expected = {
        "https://www.testsite.com/music/shows/showA": {"loc": "https://www.testsite.com/music/shows/showA"}
    }
    assert processor._sitemap_entities == expected


def test_get_all_entries():
    """
    Test that get_all_entries() returns all stored sitemap entries.
    """
    processor = SitemapProcessor("https://www.testsite.com/")
    # Preload fake entries into the internal dict.
    processor._sitemap_entities = {
        "https://www.testsite.com/music/shows/show1": {
            "loc": "https://www.testsite.com/music/shows/show1",
            "lastmod": "2025-01-01T00:00:00"
        },
        "https://www.testsite.com/music/shows/show2": {
            "loc": "https://www.testsite.com/music/shows/show2",
            "lastmod": "2025-02-01T00:00:00"
        }
    }
    entries = processor.get_all_entries()
    expected = [
        {"loc": "https://www.testsite.com/music/shows/show1",
            "lastmod": "2025-01-01T00:00:00"},
        {"loc": "https://www.testsite.com/music/shows/show2",
            "lastmod": "2025-02-01T00:00:00"}
    ]
    # Convert each entry to a frozenset of items for unordered comparison.
    assert {frozenset(entry.items()) for entry in entries} == {
        frozenset(entry.items()) for entry in expected}


def test_get_entries_after():
    """
    Test that get_entries_after() returns only entries with a lastmod date after a given threshold.
    """
    processor = SitemapProcessor("https://www.testsite.com/")
    processor._sitemap_entities = {
        "https://www.testsite.com/music/shows/show1": {
            "loc": "https://www.testsite.com/music/shows/show1",
            "lastmod": "2025-01-01T00:00:00"
        },
        "https://www.testsite.com/music/shows/show2": {
            "loc": "https://www.testsite.com/music/shows/show2",
            "lastmod": "2025-02-01T00:00:00"
        },
        "https://www.testsite.com/music/shows/show3": {
            "loc": "https://www.testsite.com/music/shows/show3",
            "lastmod": "2025-03-01T00:00:00"
        }
    }
    threshold = datetime.fromisoformat("2025-01-15T00:00:00")
    entries = processor.get_entries_after(threshold)
    result_locs = {entry["loc"] for entry in entries}
    expected_locs = {"https://www.testsite.com/music/shows/show2",
                     "https://www.testsite.com/music/shows/show3"}
    assert result_locs == expected_locs


def test_get_entries_between():
    """
    Test that get_entries_between() returns only entries with a lastmod date between start and end.
    """
    processor = SitemapProcessor("https://www.testsite.com/")
    processor._sitemap_entities = {
        "https://www.testsite.com/music/shows/show1": {
            "loc": "https://www.testsite.com/music/shows/show1",
            "lastmod": "2025-01-01T00:00:00"
        },
        "https://www.testsite.com/music/shows/show2": {
            "loc": "https://www.testsite.com/music/shows/show2",
            "lastmod": "2025-02-01T00:00:00"
        },
        "https://www.testsite.com/music/shows/show3": {
            "loc": "https://www.testsite.com/music/shows/show3",
            "lastmod": "2025-03-01T00:00:00"
        }
    }
    start = datetime.fromisoformat("2025-01-15T00:00:00")
    end = datetime.fromisoformat("2025-02-15T00:00:00")
    entries = processor.get_entries_between(start, end)
    result_locs = {entry["loc"] for entry in entries}
    expected_locs = {"https://www.testsite.com/music/shows/show2"}
    assert result_locs == expected_locs
