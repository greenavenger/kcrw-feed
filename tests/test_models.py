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
    show.add_host(host)

    # Verify that the host is added correctly.
    assert len(show.hosts) == 1
    assert show.hosts[0].name == "Test Host"


def test_show_update_info():
    """Test the update_info method of the Show."""
    # Create a Show instance with an initial description and empty metadata.
    show = Show(
        title="Test Show",
        url="http://example.com/show",
        description="Old description",
        metadata={}
    )

    # Prepare new data for updating.
    new_data: Dict[str, Any] = {
        "description": "New description",
        "metadata": {"genre": "rock"}
    }

    # Update the show info.
    show.update_info(new_data)

    # Verify that the description and metadata are updated.
    assert show.description == "New description"
    assert show.metadata.get("genre") == "rock"

    # Verify that last_updated is set and is a datetime close to now.
    assert show.last_updated is not None
    assert (datetime.now() - show.last_updated) < timedelta(seconds=1)


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
    show.add_episode(episode)

    # Verify the episode is added correctly.
    assert len(show.episodes) == 1
    assert show.episodes[0].title == "Episode 1"


def test_show_needs_update():
    """Test the needs_update method of the Show."""
    # Create a Show with no last_updated, so it should need an update.
    show = Show(title="Test Show", url="http://example.com/show")
    assert show.needs_update() is True

    # Update the show info (which sets last_updated).
    show.update_info({"description": "Updated description"})

    # Now, needs_update should return False.
    assert show.needs_update() is False


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
