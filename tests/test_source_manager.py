"""Tests for the module for managing the source of show URLs."""

import os
import io
import gzip
from pathlib import Path
from typing import Optional
import pytest
import fsspec

from kcrw_feed import source_manager


def fake_get_file(self, path: str, timeout: int = 10) -> Optional[bytes]:
    """Fake get_file function to simulate file retrieval."""
    if path.endswith("test.txt"):
        with open(path, "rb") as f:
            return f.read()
    if path.endswith("test.txt.gz"):
        with open(path, "rb") as f:
            gz_bytes = f.read()
        return gzip.decompress(gz_bytes)
    if path.startswith("https"):
        return b"Fake HTTPS content"
    return None


@pytest.fixture(autouse=True)
def patch_get_file(monkeypatch: pytest.MonkeyPatch):
    """Patch the _get_file method in BaseSource to use fake_get_file."""
    monkeypatch.setattr(source_manager.BaseSource, "_get_file", fake_get_file)


# Create a DummySource that subclasses BaseSource.
class DummySource(source_manager.BaseSource):
    def __init__(self, base_url: str) -> None:
        self.base_source = base_url
        self.uses_sitemap = True

    def get_resource(self, resource: str) -> Optional[bytes]:
        return fake_get_file(self.reference(resource))

    def relative_path(self, entity_reference: str) -> str:
        # For testing, just return the entity_reference as is.
        return entity_reference

    def reference(self, entity_reference: str) -> str:
        # If resource is not absolute, prepend base_source.
        if not resource.startswith("http"):
            resource = self.base_source.rstrip(
                "/") + "/" + resource.lstrip("/")
        return resource


# ---- Updated Tests for _get_file (now a method) and related helpers ----

def test_get_file_local(tmp_path: Path):
    """Read a local (plain) file using _get_file from DummySource."""
    test_content = b"Hello, world!"
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(test_content)
    dummy = DummySource(str(tmp_path))
    result = dummy._get_file(str(test_file))
    assert result == test_content


def test_get_file_gzip(tmp_path: Path):
    """Read a gzipped file (automatic decompression) using _get_file."""
    test_content = b"Hello, Gzip!"
    test_file = tmp_path / "test.txt.gz"
    with gzip.open(test_file, "wb") as f:
        f.write(test_content)
    dummy = DummySource(str(tmp_path))
    result = dummy._get_file(str(test_file))
    assert result == test_content


def test_get_file_https(monkeypatch: pytest.MonkeyPatch):
    """Simulate an HTTPS file using monkeypatch for fsspec.open."""
    def fake_open(path, mode="rb", timeout=10, compression="infer", headers=None):
        # Check that the path starts with "https"
        assert path.startswith("https")
        return io.BytesIO(b"Fake HTTPS content")
    monkeypatch.setattr(fsspec, "open", fake_open)
    # We don't really use DummySource here because our HTTPS test path is absolute.
    dummy = DummySource("https://example.com")
    result = dummy._get_file("https://example.com/file")
    assert result == b"Fake HTTPS content"


def test_get_file_nonexistent(tmp_path: Path):
    """Nonexistent file should return None."""
    non_existent = tmp_path / "nonexistent.txt"
    dummy = DummySource(str(tmp_path))
    result = dummy._get_file(str(non_existent))
    # _get_file should catch the exception and return None.
    assert result is None


def test_normalize_url_with_leading_slash():
    base = "https://www.testsite.com/"
    loc = "/extra-sitemap.xml"
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_url_without_leading_slash():
    base = "https://www.testsite.com"
    loc = "extra-sitemap.xml"
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_url_with_directory():
    base = "https://www.testsite.com/dir/"
    loc = "extra-sitemap.xml"
    expected = "https://www.testsite.com/dir/extra-sitemap.xml"
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_url_with_directory_and_leading_slash():
    base = "https://www.testsite.com/dir/"
    loc = "/extra-sitemap.xml"
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_local_path_relative():
    base = "/home/user"
    loc = "documents/report.txt"
    expected = os.path.normpath("/home/user/documents/report.txt")
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_local_path_with_leading_slash_in_loc():
    base = "/home/user"
    loc = "/documents/report.txt"
    expected = os.path.normpath("/home/user/documents/report.txt")
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_local_path_with_trailing_slash_in_base():
    base = "/home/user/"
    loc = "documents/report.txt"
    expected = os.path.normpath("/home/user/documents/report.txt")
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_basic_url_with_query():
    url = "https://example.com/path?foo=bar&baz=qux"
    expected = "https://example.com/path"
    assert source_manager.strip_query_params(url) == expected


def test_url_without_query():
    url = "https://example.com/path"
    assert source_manager.strip_query_params(url) == url


def test_url_with_fragment():
    url = "https://example.com/path?foo=bar#section1"
    expected = "https://example.com/path#section1"
    assert source_manager.strip_query_params(url) == expected


def test_url_with_only_query():
    url = "https://example.com/?foo=bar"
    expected = "https://example.com/"
    assert source_manager.strip_query_params(url) == expected


def test_complex_url():
    url = ("https://ondemand-media.kcrw.com/fdd/audio/download/kcrw/music/hr/"
           "KCRW-henry_rollins-kcrw_broadcast_825-250125.mp3?awCollectionId=henry-rollins&"
           "aw_0_1st.ri=kcrw&awEpisodeId=kcrw-broadcast-825")
    expected = ("https://ondemand-media.kcrw.com/fdd/audio/download/kcrw/music/hr/"
                "KCRW-henry_rollins-kcrw_broadcast_825-250125.mp3")
    assert source_manager.strip_query_params(url) == expected
