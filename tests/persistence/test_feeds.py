"""Module to test the feed generation component."""

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import os
import tempfile
import uuid
import xml.etree.ElementTree as ET

import pytest

from kcrw_feed.persistence.feeds import FeedPersister
from kcrw_feed.models import Show, Episode, ShowDirectory

UUID_SHOW1 = uuid.uuid4()
UUID_SHOW1_EP1 = uuid.uuid4()
UUID_SHOW1_EP2 = uuid.uuid4()
UUID_SHOW2 = uuid.uuid4()
UUID_SHOW2_EP1 = uuid.uuid4()
UUID_SHOW2_EP2 = uuid.uuid4()


@pytest.fixture
def dummy_directory() -> ShowDirectory:
    now = datetime.now().replace(tzinfo=timezone.utc)
    show1 = Show(
        title="Show One",
        url="https://example.com/show1",
        uuid=UUID_SHOW1,
        description="Description for Show One",
        hosts=[],
        episodes=[
            Episode(
                title="Episode 1",
                airdate=now - timedelta(days=1),
                last_updated=now - timedelta(days=1),
                url="https://example.com/show1/ep1",
                media_url="https://example.com/show1/ep1.mp3",
                duration=0,
                uuid=UUID_SHOW1_EP1,
                description="Episode 1 description"
            ),
            Episode(
                title="Episode 2",
                airdate=now,
                last_updated=now,
                url="https://example.com/show1/ep2",
                media_url="https://example.com/show1/ep2.mp3",
                duration=0,
                uuid=UUID_SHOW1_EP2,
                description="Episode 2 description"
            )
        ],
        last_updated=now
    )
    show2 = Show(
        title="Show Two",
        url="https://example.com/show2",
        uuid=UUID_SHOW2,
        description="Description for Show Two",
        hosts=[],
        episodes=[
            Episode(
                title="Episode A",
                airdate=now - timedelta(days=2),
                last_updated=now - timedelta(days=2),
                url="https://example.com/show2/epa",
                media_url="https://example.com/show2/epa.mp3",
                duration=0,
                uuid=UUID_SHOW2_EP1,
                description="Episode A description"
            ),
            Episode(
                title="Episode B",
                airdate=now - timedelta(days=1),
                last_updated=now - timedelta(days=1),
                url="https://example.com/show2/epb",
                media_url="https://example.com/show2/epb.mp3",
                duration=0,
                uuid=UUID_SHOW2_EP2,
                description="Episode B description"
            )
        ],
        last_updated=now - timedelta(days=1)
    )
    return ShowDirectory(shows=[show1, show2])


def test_rss_save_creates_files(dummy_directory: ShowDirectory):
    rss_persister = FeedPersister(storage_root=".", feed_directory="feeds")
    with tempfile.TemporaryDirectory() as tmpdirname:
        rss_persister.save(dummy_directory, tmpdirname)
        # Expect one file per show (i.e. 2 files).
        files = os.listdir(tmpdirname)
        assert len(files) == 2

        for file in files:
            file_path = os.path.join(tmpdirname, file)
            # Parse the XML feed.
            tree = ET.parse(file_path)
            root = tree.getroot()
            # Check that the root element is <rss> and it has a <channel>.
            assert root.tag == "rss"
            channel = root.find("channel")
            assert channel is not None

            # Verify that the channel title is set.
            title = channel.find("title")
            assert title is not None and title.text

            # Verify that items (episodes) exist and their pubDate values are valid.
            items = channel.findall("item")
            pub_dates = [item.find("pubDate").text for item in items if item.find(
                "pubDate") is not None]
            # Convert pubDate strings to datetime objects.
            dates = [parsedate_to_datetime(d) for d in pub_dates]
            # Check that dates are in descending order.
            assert dates == sorted(dates, reverse=True)
