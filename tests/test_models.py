"""Module to hold tests for core dataclass objects"""

from typing import Any, Dict

from datetime import datetime, timedelta
from kcrw_feed.models import Host, Show, Episode


def test_show_add_host():
    """Test that a host can be added to a show."""
    # Create a Host instance
    host = Host(name="Test Host")

    # Create a Show instance and add the host
    show = Show(title="Test Show", url="http://example.com/show")
    show.hosts.append(host)

    # Verify that the host is added correctly.
    assert len(show.hosts) == 1
    assert show.hosts[0].name == "Test Host"


def test_show_add_episode():
    """Test that an episode can be added to a show."""
    # Create a Show instance.
    show = Show(title="Test Show", url="http://example.com/show")

    # Create an Episode instance.
    airdate = datetime(2023, 1, 1, 12, 0, 0)
    episode = Episode(
        title="Episode 1",
        airdate=airdate,
        url="http://example.com/episode1",
        media_url="http://example.com/episode1.mp3",
        description="Episode description"
    )

    # Add the episode to the show.
    show.episodes.append(episode)

    # Verify the episode is added correctly.
    assert len(show.episodes) == 1
    assert show.episodes[0].title == "Episode 1"


def test_episode_creation():
    """Test that an Episode is created correctly."""
    airdate = datetime(2023, 1, 1, 12, 0, 0)
    episode = Episode(
        title="Episode 1",
        airdate=airdate,
        url="http://example.com/episode1",
        media_url="http://example.com/episode1.mp3",
        description="Test episode"
    )
    assert episode.title == "Episode 1"
    assert episode.airdate == airdate
    assert episode.media_url == "http://example.com/episode1.mp3"
    assert episode.description == "Test episode"
