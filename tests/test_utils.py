"""Tests for utility functions."""

from datetime import datetime
import pytest
import uuid

from kcrw_feed.models import Episode, Host, Show
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


def test_deduplication():
    """Test that uniq_by_uuid() correctly deduplicates episodes."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    # Duplicate with same UUID.
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]
    deduped = utils.uniq_by_uuid(episodes)
    assert len(deduped) == 2
    # The first occurrence for "uuid1" should be preserved.
    assert deduped[0] == ep1
    assert deduped[1] == ep3


def test_no_duplicates():
    """Test that uniq_by_uuid() returns all episodes when there
    are no duplicates."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid2")
    episodes = [ep1, ep2]
    deduped = utils.uniq_by_uuid(episodes)
    assert len(deduped) == 2


def test_none_uuid():
    """Test that episodes with no UUID are all included."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid=None)
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid=None)
    episodes = [ep1, ep2]
    deduped = utils.uniq_by_uuid(episodes)
    assert len(deduped) == 2


def test_mix_of_none_and_duplicates():
    """Test deduplication on a mix of episodes with None and duplicate UUIDs."""
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid=None)
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid1")
    ep4 = Episode(title="Episode 4", airdate=dt, url="url4",
                  media_url="media4", uuid="uuid2")
    ep5 = Episode(title="Episode 5", airdate=dt, url="url5",
                  media_url="media5", uuid=None)
    episodes = [ep1, ep2, ep3, ep4, ep5]
    deduped = utils.uniq_by_uuid(episodes)
    # Expected: first occurrence of "uuid1", both episodes with None, and "uuid2"
    assert len(deduped) == 4
    assert deduped[0] == ep1
    assert deduped[1] == ep2
    assert deduped[2] == ep4
    assert deduped[3] == ep5


def test_dedup_homogeneous_episodes():
    dt = datetime.now()
    ep1 = Episode(title="Episode 1", airdate=dt, url="url1",
                  media_url="media1", uuid="uuid1")
    ep2 = Episode(title="Episode 2", airdate=dt, url="url2",
                  media_url="media2", uuid="uuid1")
    ep3 = Episode(title="Episode 3", airdate=dt, url="url3",
                  media_url="media3", uuid="uuid2")
    episodes = [ep1, ep2, ep3]
    deduped = utils.uniq_by_uuid(episodes)
    assert len(deduped) == 2
    assert deduped[0] == ep1
    assert deduped[1] == ep3


def test_dedup_homogeneous_hosts():
    # Assuming Host is defined with at least uuid and name.
    h1 = Host(uuid="host1", name="Alice")
    h2 = Host(uuid="host1", name="Alice")
    h3 = Host(uuid="host2", name="Bob")
    hosts = [h1, h2, h3]
    deduped = utils.uniq_by_uuid(hosts)
    assert len(deduped) == 2
    assert deduped[0] == h1
    assert deduped[1] == h3


def test_mixed_types_dedup():
    dt = datetime.now()
    ep = Episode(title="Episode 1", airdate=dt, url="url1",
                 media_url="media1", uuid="uuid1")
    h = Host(uuid="host1", name="Alice")
    with pytest.raises(AssertionError, match="Mixed types provided to uniq_by_uuid"):
        utils.uniq_by_uuid([ep, h])
