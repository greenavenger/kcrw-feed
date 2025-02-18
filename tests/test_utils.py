"""Tests for utility functions."""

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
