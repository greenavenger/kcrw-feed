import pytest
import io
from typing import Optional
from kcrw_feed.show_gatherer import ShowIndex
from kcrw_feed import utils


def fake_get_file(path: str, timeout: int = 10) -> Optional[bytes]:
    """Define a fake get_file function that returns bytes based on the input path."""
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
  </url>
</urlset>"""
        return content.encode("utf-8")
    elif path == "https://www.testsite.com/extra-sitemap.xml":
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.testsite.com/music/shows/show3</loc>
  </url>
</urlset>"""
        return content.encode("utf-8")
    return None


@pytest.fixture(autouse=True)
def patch_get_file(monkeypatch):
    """Automatically patch utils.get_file in all tests in this module."""
    monkeypatch.setattr(utils, "get_file", fake_get_file)


def test_find_sitemaps():
    """Test that find_sitemaps() correctly reads robots.txt and includes
    both the discovered sitemaps and any extra sitemaps provided.
    """
    # Instantiate ShowIndex with a fake base URL and an extra sitemap.
    index = ShowIndex("https://www.testsite.com/",
                      extra_sitemaps=["extra-sitemap.xml"])
    sitemap_urls = index.find_sitemaps()
    # Expected: sitemap1.xml, sitemap2.xml (from robots.txt) and extra-sitemap.xml.
    expected = {
        "https://www.testsite.com/sitemap1.xml",
        "https://www.testsite.com/sitemap2.xml",
        "https://www.testsite.com/extra-sitemap.xml"
    }
    assert set(sitemap_urls) == expected


# def test_read_sitemap():
#     """
#     Test that read_sitemap() correctly parses a sitemap XML file and extracts
#     all <loc> values.
#     """
#     index = ShowIndex("https://www.testsite.com/")
#     # Use the fake sitemap1.xml content.
#     urls = index.read_sitemap("https://www.testsite.com/sitemap1.xml")
#     # The fake sitemap1.xml contains two <loc> values.
#     expected = {
#         "https://www.testsite.com/music/shows/show1",
#         "https://www.testsite.com/other/url"
#     }
#     assert set(urls) == expected


# def test_gather_shows():
#     """
#     Test that gather_shows() returns only music show URLs by filtering out
#     non-matching URLs.
#     """
#     index = ShowIndex("https://www.testsite.com/",
#                       extra_sitemaps=["extra-sitemap.xml"])
#     # In our fake data:
#     # - sitemap1.xml provides two locs, but only show1 (which contains "/music/shows/") should match.
#     # - sitemap2.xml provides show2 (matching "/music/shows/").
#     # - extra-sitemap.xml provides show3 (matching "/music/shows/").
#     shows = index.gather_shows(source="sitemap")
#     expected = {
#         "https://www.testsite.com/music/shows/show1",
#         "https://www.testsite.com/music/shows/show2",
#         "https://www.testsite.com/music/shows/show3"
#     }
#     assert set(shows) == expected


def test_extract_entries_simple():
    """Test _extract_entries() on a simple dict with only 'loc'."""
    index = ShowIndex("https://www.testsite.com/")
    data = {"loc": "https://www.testsite.com/music/shows/showX"}
    entries = index._extract_entries(data)
    expected = [{"loc": "https://www.testsite.com/music/shows/showX"}]
    assert entries == expected


def test_extract_entries_with_optional_fields():
    """Test _extract_entries() when optional fields are present with mixed key case."""
    index = ShowIndex("https://www.testsite.com/")
    data = {
        "LoC": "https://www.testsite.com/music/shows/showY",
        "LASTMOD": "2025-02-01T00:00:00",
        "ChangeFreq": "weekly",
        "Priority": "0.5"
    }
    entries = index._extract_entries(data)
    expected = [{
        "loc": "https://www.testsite.com/music/shows/showY",
        "lastmod": "2025-02-01T00:00:00",
        "changefreq": "weekly",
        "priority": "0.5"
    }]
    assert entries == expected


def test_extract_entries_nested():
    """Test _extract_entries() on nested data structures."""
    index = ShowIndex("https://www.testsite.com/")
    data = {
        "urlset": {
            "url": [
                {"loc": "https://www.testsite.com/music/shows/showA"},
                {"loc": "https://www.testsite.com/other/url"}
            ]
        }
    }
    entries = index._extract_entries(data)
    expected = [
        {"loc": "https://www.testsite.com/music/shows/showA"},
        {"loc": "https://www.testsite.com/other/url"}
    ]
    # Order may not be guaranteed, so compare sets of loc values.
    result_locs = {entry["loc"] for entry in entries}
    expected_locs = {entry["loc"] for entry in expected}
    assert result_locs == expected_locs
