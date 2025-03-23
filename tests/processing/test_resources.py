"""Module to test the processing of sitemaps"""

import pytest
from datetime import datetime
from typing import Optional
from kcrw_feed.processing.resources import SitemapProcessor, ROBOTS_FILE, MUSIC_FILTER_RE, SITEMAP_RE
from kcrw_feed import source_manager


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
        # This sitemap contains two <url> entries:
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


class DummySource:
    """Dummy source implementation for tests"""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def get_resource(self, path: str) -> Optional[bytes]:
        return fake_get_file(self.reference(path))

    def relative_path(self, url: str) -> str:
        return url

    def reference(self, path: str) -> str:
        # If the path isn't an absolute URL, prepend the base URL.
        if not path.startswith("http"):
            path = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        return path


@pytest.fixture
def dummy_source():
    return DummySource("https://www.testsite.com/")


@pytest.fixture(autouse=True)
def patch_get_file(monkeypatch):
    """Patch the _get_file method in BaseSource to use fake_get_file."""
    monkeypatch.setattr(source_manager.BaseSource, "_get_file", fake_get_file)


def test_sitemaps_from_robots(dummy_source):
    """
    Test that _sitemaps_from_robots() correctly reads robots.txt.
    """
    processor = SitemapProcessor(dummy_source)
    sitemap_urls = processor._sitemaps_from_robots()
    expected = {"https://www.testsite.com/sitemap1.xml",
                "https://www.testsite.com/sitemap2.xml"}
    assert set(sitemap_urls) == expected


def test_read_sitemap_for_entries(dummy_source):
    """
    Test that _read_sitemap_for_entries() parses a sitemap XML file and stores
    only music show entries in _sitemap_entities.
    """
    processor = SitemapProcessor(dummy_source)
    processor._read_sitemap_for_entries(
        "https://www.testsite.com/sitemap1.xml")
    # From sitemap1.xml, only the URL containing "/music/shows/" should be stored.
    assert "https://www.testsite.com/music/shows/show1" in processor._resources
    assert "https://www.testsite.com/other/url" not in processor._resources


def test_read_sitemap_for_child_sitemaps(dummy_source):
    """
    Test that _read_sitemap_for_child_sitemaps() extracts child sitemap URLs from a sitemap index.
    For this test, we simulate an index by having fake_get_file return a crafted XML.
    """
    # Create a fake sitemap index XML.
    sitemap_index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://www.testsite.com/music/shows/sitemap-child1.xml</loc>
  </sitemap>
  <sitemap>
    <loc>https://www.testsite.com/music/shows/sitemap-child2.xml</loc>
  </sitemap>
</sitemapindex>"""

    def fake_get_resource(path: str) -> Optional[bytes]:
        if path == "https://www.testsite.com/sitemap-index.xml":
            return sitemap_index_xml.encode("utf-8")
        return None
    # Override get_resource for this test.
    dummy_source.get_resource = fake_get_resource
    processor = SitemapProcessor(dummy_source)
    child_sitemaps = processor._read_sitemap_for_child_sitemaps(
        "https://www.testsite.com/sitemap-index.xml")
    # Additionally, the processor filters child sitemaps with MUSIC_FILTER_RE.
    # For testing, if MUSIC_FILTER_RE does not match these URLs, child_sitemaps might be empty.
    # Let's assume that for the test, MUSIC_FILTER_RE is not filtering these.
    expected = {"https://www.testsite.com/music/shows/sitemap-child1.xml",
                "https://www.testsite.com/music/shows/sitemap-child2.xml"}
    # We compare as sets.
    assert set(child_sitemaps) == expected


def test_gather_entries(dummy_source, monkeypatch):
    """Test that gather_entries() returns all music show URLs by processing
    sitemaps recursively. In this test we simulate extra sitemaps by monkeypatching
    _sitemaps_from_robots() to return an extra sitemap URL."""
    processor = SitemapProcessor(dummy_source)
    # For this test, override _sitemaps_from_robots to include an extra sitemap.

    def fake_sitemaps_from_robots():
        return [
            "https://www.testsite.com/sitemap1.xml",
            "https://www.testsite.com/sitemap2.xml",
            "https://www.testsite.com/extra-sitemap.xml",
        ]
    monkeypatch.setattr(processor, "_sitemaps_from_robots",
                        fake_sitemaps_from_robots)
    urls = processor.gather_entries()
    expected = {
        "https://www.testsite.com/music/shows/show1",
        "https://www.testsite.com/music/shows/show2",
        "https://www.testsite.com/music/shows/show3",
    }
    assert set(urls) == expected


# def test_get_all_entries(dummy_source):
#     """Test that get_all_entries() returns all stored sitemap entry
#     dictionaries."""
#     processor = SitemapProcessor(dummy_source)
#     # Preload fake entries.
#     processor._source_entities = {
#         "https://www.testsite.com/music/shows/show1": {
#             "loc": "https://www.testsite.com/music/shows/show1",
#             "lastmod": "2025-01-01T00:00:00"
#         },
#         "https://www.testsite.com/music/shows/show2": {
#             "loc": "https://www.testsite.com/music/shows/show2",
#             "lastmod": "2025-02-01T00:00:00"
#         }
#     }
#     entries = processor.get_all_entries()
#     expected = [
#         {"loc": "https://www.testsite.com/music/shows/show1",
#             "lastmod": "2025-01-01T00:00:00"},
#         {"loc": "https://www.testsite.com/music/shows/show2",
#             "lastmod": "2025-02-01T00:00:00"},
#     ]
#     # Use frozenset for unordered comparison.
#     assert {frozenset(entry.items()) for entry in entries} == {
#         frozenset(entry.items()) for entry in expected}


# def test_get_entries_after(dummy_source):
#     """Test that get_entries_after() returns only entries with a lastmod date
#     after a given threshold."""
#     processor = SitemapProcessor(dummy_source)
#     processor._source_entities = {
#         "https://www.testsite.com/music/shows/show1": {
#             "loc": "https://www.testsite.com/music/shows/show1",
#             "lastmod": "2025-01-01T00:00:00"
#         },
#         "https://www.testsite.com/music/shows/show2": {
#             "loc": "https://www.testsite.com/music/shows/show2",
#             "lastmod": "2025-02-01T00:00:00"
#         },
#         "https://www.testsite.com/music/shows/show3": {
#             "loc": "https://www.testsite.com/music/shows/show3",
#             "lastmod": "2025-03-01T00:00:00"
#         }
#     }
#     threshold = datetime.fromisoformat("2025-01-15T00:00:00")
#     entries = processor.get_entries_after(threshold)
#     result_locs = {entry["loc"] for entry in entries}
#     expected_locs = {
#         "https://www.testsite.com/music/shows/show2",
#         "https://www.testsite.com/music/shows/show3",
#     }
#     assert result_locs == expected_locs


# def test_get_entries_between(dummy_source):
#     """Test that get_entries_between() returns only entries with a lastmod
#     date between start and end."""
#     processor = SitemapProcessor(dummy_source)
#     processor._source_entities = {
#         "https://www.testsite.com/music/shows/show1": {
#             "loc": "https://www.testsite.com/music/shows/show1",
#             "lastmod": "2025-01-01T00:00:00"
#         },
#         "https://www.testsite.com/music/shows/show2": {
#             "loc": "https://www.testsite.com/music/shows/show2",
#             "lastmod": "2025-02-01T00:00:00"
#         },
#         "https://www.testsite.com/music/shows/show3": {
#             "loc": "https://www.testsite.com/music/shows/show3",
#             "lastmod": "2025-03-01T00:00:00"
#         }
#     }
#     start = datetime.fromisoformat("2025-01-15T00:00:00")
#     end = datetime.fromisoformat("2025-02-15T00:00:00")
#     entries = processor.get_entries_between(start, end)
#     result_locs = {entry["loc"] for entry in entries}
#     expected_locs = {"https://www.testsite.com/music/shows/show2"}
#     assert result_locs == expected_locs
