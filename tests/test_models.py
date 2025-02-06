from datetime import datetime, timedelta
from kcrw_feed.models import Host, Show, Episode


def test_dj_add_show():
    """Test Host method"""
    # Create a Host instance
    dj = Host(name="Test DJ")

    # Create a Show instance and add it to the host
    show = Show(title="Test Show", url="http://example.com/show")
    dj.add_show(show)

    # Verify that the show is added correctly.
    assert len(dj.shows) == 1
    assert dj.shows[0].title == "Test Show"
    # The get_active_shows() method currently returns all shows.
    assert dj.get_active_shows() == dj.shows


def test_show_update_info():
    """Test Show method"""
    # Create a Show instance with an initial description and empty metadata.
    show = Show(title="Test Show", url="http://example.com/show",
                description="Old description", metadata={})

    # Prepare new data for updating
    new_data = {"description": "New description",
                "metadata": {"genre": "rock"}}

    # Capture the time before updating
    # before_update = datetime.now()
    show.update_info(new_data)

    # Verify that the description and metadata are updated.
    assert show.description == "New description"
    assert show.metadata.get("genre") == "rock"

    # Verify that last_updated is set and is a datetime close to now.
    assert show.last_updated is not None
    assert (datetime.now() - show.last_updated) < timedelta(seconds=1)


def test_show_add_episode():
    """Test Show method"""
    # Create a Show instance.
    show = Show(title="Test Show", url="http://example.com/show")

    # Create an Episode instance.
    pub_date = datetime(2023, 1, 1, 12, 0, 0)
    episode = Episode(
        title="Episode 1",
        pub_date=pub_date,
        audio_url="http://example.com/episode1.mp3",
        description="Episode description"
    )

    # Add the episode to the show.
    show.add_episode(episode)

    # Verify the episode is added.
    assert len(show.episodes) == 1
    assert show.episodes[0].title == "Episode 1"


def test_show_needs_update():
    """Test Show method"""
    # Create a Show with no last_updated, so it should need an update.
    show = Show(title="Test Show", url="http://example.com/show")
    assert show.needs_update() is True

    # Update the show info (which sets last_updated).
    show.update_info({"description": "Updated description"})

    # Now, needs_update should return False.
    assert show.needs_update() is False


def test_episode_creation():
    """Test Episode method"""
    # Create an Episode and verify its attributes.
    pub_date = datetime(2023, 1, 1, 12, 0, 0)
    episode = Episode(
        title="Episode 1",
        pub_date=pub_date,
        audio_url="http://example.com/episode1.mp3",
        description="Test episode"
    )
    assert episode.title == "Episode 1"
    assert episode.pub_date == pub_date
    assert episode.audio_url == "http://example.com/episode1.mp3"
    assert episode.description == "Test episode"
