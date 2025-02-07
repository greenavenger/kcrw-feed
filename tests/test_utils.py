"""Tests for utility functions."""

import uuid
import pytest

from kcrw_feed.utils import extract_uuid


def test_extract_uuid_plain():
    text = "a73ec36f655c9452cf88f50e99cba946"
    result = extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_extract_uuid_dashed():
    text = "a73ec36f-655c-9452-cf88-f50e99cba946"
    result = extract_uuid(text)
    expected = uuid.UUID("a73ec36f-655c-9452-cf88-f50e99cba946")
    assert result == expected


def test_extract_uuid_with_noise():
    text = 'itemid="/#a73ec36f655c9452cf88f50e99cba946-episodes">'
    result = extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected


def test_extract_uuid_invalid():
    text = "This string does not contain a valid UUID."
    result = extract_uuid(text)
    assert result is None


def test_extract_uuid_multiple_matches():
    # If multiple UUIDs appear, the function returns the first one.
    text = 'foo a73ec36f655c9452cf88f50e99cba946 bar 5883da63a527de85856a5c05e27331b8'
    result = extract_uuid(text)
    expected = uuid.UUID("a73ec36f655c9452cf88f50e99cba946")
    assert result == expected
