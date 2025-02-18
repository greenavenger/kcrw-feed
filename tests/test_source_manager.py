"""Tests for the module for managing the source of show URLs."""

from pathlib import Path
import fsspec
import gzip
import io
import os
import pytest

from kcrw_feed import source_manager


def test_get_file_local(tmp_path: Path):
    """Test 1: Read a local (plain) file."""
    # Create a temporary file with known bytes.
    test_content = b"Hello, world!"
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(test_content)

    # Call get_file with the local file path.
    result = source_manager.get_file(str(test_file))
    assert result == test_content


def test_get_file_gzip(tmp_path: Path):
    """Test 2: Read a gzipped file (automatic decompression)."""
    test_content = b"Hello, Gzip!"
    test_file = tmp_path / "test.txt.gz"
    # Write compressed content.
    with gzip.open(test_file, "wb") as f:
        f.write(test_content)

    # Call get_file, which should automatically decompress the file.
    result = source_manager.get_file(str(test_file))
    assert result == test_content


def test_get_file_https(monkeypatch):
    """Test 3: Simulate an HTTPS file using monkeypatch."""
    # Define a fake open function that returns a BytesIO.
    def fake_open(path, mode="rb", timeout=10, compression="infer"):
        # Check that the path starts with https
        assert path.startswith("https")
        return io.BytesIO(b"Fake HTTPS content")

    # Monkeypatch fsspec.open with our fake_open.
    monkeypatch.setattr(fsspec, "open", fake_open)

    result = source_manager.get_file("https://example.com/file")
    assert result == b"Fake HTTPS content"


def test_get_file_nonexistent(tmp_path: Path):
    """Test 4: Nonexistent file should return None."""
    non_existent = tmp_path / "nonexistent.txt"
    result = source_manager.get_file(str(non_existent))
    # Our function catches exceptions and returns None.
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
    # With urljoin, "https://www.testsite.com" and "extra-sitemap.xml" combine correctly.
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
    # urljoin resets the path because loc starts with a slash.
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_local_path_relative():
    base = "/home/user"
    loc = "documents/report.txt"
    # Expect the joined path to be "/home/user/documents/report.txt"
    expected = os.path.normpath("/home/user/documents/report.txt")
    result = source_manager.normalize_location(base, loc)
    assert result == expected


def test_normalize_local_path_with_leading_slash_in_loc():
    base = "/home/user"
    loc = "/documents/report.txt"
    # Our function strips the leading slash from loc, so the expected path is:
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
    # The fragment should remain intact
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
