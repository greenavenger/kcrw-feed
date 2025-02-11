"""Tests for utility functions."""

import fsspec
import gzip
import io
import os
from pathlib import Path
import pytest
import uuid

from kcrw_feed import utils


def test_extract_uuid_plain():
    text = "a73ec36f655c9452cf88f50e99cba946"
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_extract_uuid_uppercase_plain():
    text = "A73EC36F655C9452CF88F50E99CBA946"
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_extract_uuid_dashed():
    text = "a73ec36f-655c-9452-cf88-f50e99cba946"
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f-655c-9452-cf88-f50e99cba946")
    assert result == expected


def test_extract_uuid_uppercase_dashed():
    text = "A73EC36F-655C-9452-CF88-F50E99CBA946"
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f-655c-9452-cf88-f50e99cba946")
    assert result == expected


def test_extract_uuid_with_noise():
    text = 'itemid="/#a73ec36f655c9452cf88f50e99cba946-episodes">'
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_extract_uuid_uppercase_with_noise():
    text = 'itemid="/#A73EC36F655C9452CF88F50E99CBA946-episodes">'
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_extract_uuid_invalid():
    text = "This string does not contain a valid UUID."
    result = utils.extract_uuid(text)
    assert result is None


def test_extract_uuid_multiple_matches():
    # If multiple UUIDs appear, the function returns the first one.
    text = 'foo a73ec36f655c9452cf88f50e99cba946 bar 5883da63a527de85856a5c05e27331b8'
    result = utils.extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_get_file_local(tmp_path: Path):
    """Test 1: Read a local (plain) file."""
    # Create a temporary file with known bytes.
    test_content = b"Hello, world!"
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(test_content)

    # Call get_file with the local file path.
    result = utils.get_file(str(test_file))
    assert result == test_content


def test_get_file_gzip(tmp_path: Path):
    """Test 2: Read a gzipped file (automatic decompression)."""
    test_content = b"Hello, Gzip!"
    test_file = tmp_path / "test.txt.gz"
    # Write compressed content.
    with gzip.open(test_file, "wb") as f:
        f.write(test_content)

    # Call get_file, which should automatically decompress the file.
    result = utils.get_file(str(test_file))
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

    result = utils.get_file("https://example.com/file")
    assert result == b"Fake HTTPS content"


def test_get_file_nonexistent(tmp_path: Path):
    """Test 4: Nonexistent file should return None."""
    non_existent = tmp_path / "nonexistent.txt"
    result = utils.get_file(str(non_existent))
    # Our function catches exceptions and returns None.
    assert result is None


def test_normalize_url_with_leading_slash():
    base = "https://www.testsite.com/"
    loc = "/extra-sitemap.xml"
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = utils.normalize_location(base, loc)
    assert result == expected


def test_normalize_url_without_leading_slash():
    base = "https://www.testsite.com"
    loc = "extra-sitemap.xml"
    # With urljoin, "https://www.testsite.com" and "extra-sitemap.xml" combine correctly.
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = utils.normalize_location(base, loc)
    assert result == expected


def test_normalize_url_with_directory():
    base = "https://www.testsite.com/dir/"
    loc = "extra-sitemap.xml"
    expected = "https://www.testsite.com/dir/extra-sitemap.xml"
    result = utils.normalize_location(base, loc)
    assert result == expected


def test_normalize_url_with_directory_and_leading_slash():
    base = "https://www.testsite.com/dir/"
    loc = "/extra-sitemap.xml"
    # urljoin resets the path because loc starts with a slash.
    expected = "https://www.testsite.com/extra-sitemap.xml"
    result = utils.normalize_location(base, loc)
    assert result == expected


def test_normalize_local_path_relative():
    base = "/home/user"
    loc = "documents/report.txt"
    # Expect the joined path to be "/home/user/documents/report.txt"
    expected = os.path.normpath("/home/user/documents/report.txt")
    result = utils.normalize_location(base, loc)
    assert result == expected


# TODO: fix
# def test_normalize_local_path_with_leading_slash_in_loc():
#     base = "/home/user"
#     loc = "/documents/report.txt"
#     # Our function strips the leading slash from loc, so the expected path is:
#     expected = os.path.normpath("/home/user/documents/report.txt")
#     result = utils.normalize_location(base, loc)
#     assert result == expected


def test_normalize_local_path_with_trailing_slash_in_base():
    base = "/home/user/"
    loc = "documents/report.txt"
    expected = os.path.normpath("/home/user/documents/report.txt")
    result = utils.normalize_location(base, loc)
    assert result == expected
