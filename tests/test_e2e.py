"""Test the program end-to-end with test data"""

import os
import pytest
import subprocess
import tempfile
import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime


STATE_FILE = "kcrw_catalog.json"


@pytest.fixture
def source_root(request) -> str:
    return os.path.abspath(request.config.getoption("source_root"))


@pytest.fixture(scope="session")
def storage_root(tmp_path_factory, request) -> str:
    """Shared storage root that runs update once for all tests that need state."""
    opt = request.config.getoption("storage_root")
    if opt:
        return os.path.abspath(opt)

    source_root = os.path.abspath(request.config.getoption("source_root"))
    tmp_dir = str(tmp_path_factory.mktemp("state"))

    # Run update once to populate state for list/filter tests
    project_root = os.path.abspath(".")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}",
           f"--storage_root={tmp_dir}",
           "update"]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    if result.returncode != 0:
        pytest.skip(f"Update failed, cannot populate state: {result.stderr}")

    return tmp_dir


# Expected shows in the test data
# Note: MBE's og:url uses the legacy /music/ prefix even on the redesigned site
SHOWS = [
    "https://www.kcrw.com/shows/henry-rollins",
    "https://www.kcrw.com/music/morning-becomes-eclectic"
]

# Expected episodes in the test data
EPISODES_HENRY_ROLLINS = [
    "https://www.kcrw.com/shows/henry-rollins/stories/henry-rollins-kcrw-broadcast-877",
    "https://www.kcrw.com/shows/henry-rollins/stories/henry-rollins-kcrw-broadcast-876",
    "https://www.kcrw.com/shows/henry-rollins/stories/henry-rollins-kcrw-broadcast-875",
    "https://www.kcrw.com/shows/henry-rollins/stories/henry-rollins-kcrw-broadcast-874",
    "https://www.kcrw.com/shows/henry-rollins/stories/henry-rollins-kcrw-broadcast-872",
]

# Note: MBE episode slugs include descriptive suffixes from og:url
EPISODES_MBE = [
    "https://www.kcrw.com/shows/morning-becomes-eclectic/stories/morning-becomes-eclectic-playlist-january-23-2026-new-james-blake-joshua",
    "https://www.kcrw.com/shows/morning-becomes-eclectic/stories/morning-becomes-eclectic-playlist-january-22-2026-stereolab-and-silvana",
    "https://www.kcrw.com/shows/morning-becomes-eclectic/stories/morning-becomes-eclectic-playlist-january-21-2026-a-persian-pop-song",
    "https://www.kcrw.com/shows/morning-becomes-eclectic/stories/morning-becomes-eclectic-playlist-january-20-2026",
    "https://www.kcrw.com/shows/morning-becomes-eclectic/stories/morning-becomes-eclectic-playlist-january-19-2026-with-guest-host-chris",
]

EPISODES = EPISODES_HENRY_ROLLINS + EPISODES_MBE

# Expected hosts
# TODO: Host extraction not yet implemented for redesigned site
HOSTS = [
    "Henry Rollins",
]


def test_update_discovers_shows_and_episodes(source_root: str):
    """Update command discovers shows and creates episodes."""
    project_root = os.path.abspath(".")

    with tempfile.TemporaryDirectory() as tmpdirname:
        cmd = ["poetry", "run", "kcrw-feed",
               f"--source_root={source_root}",
               f"--storage_root={tmpdirname}",
               "update"
               ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=project_root
        )

        # Check command succeeded
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check state file was created
        state_file = os.path.join(tmpdirname, STATE_FILE)
        assert os.path.exists(state_file), f"State file not found at {state_file}"

        # Load and verify state
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)

        # Verify shows were discovered
        assert "shows" in state, "No 'shows' key in state"
        assert len(state["shows"]) >= 2, f"Expected at least 2 shows, got {len(state['shows'])}"


def test_update_generates_rss_feeds(source_root: str):
    """Update creates valid RSS feed files."""
    project_root = os.path.abspath(".")

    with tempfile.TemporaryDirectory() as tmpdirname:
        cmd = ["poetry", "run", "kcrw-feed",
               f"--source_root={source_root}",
               f"--storage_root={tmpdirname}",
               "update"
               ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=project_root
        )
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Check feeds directory was created
        feeds_dir = os.path.join(tmpdirname, "feeds")
        assert os.path.isdir(feeds_dir), f"Feeds directory not found at {feeds_dir}"

        # Check feed files were created
        feed_files = os.listdir(feeds_dir)
        assert len(feed_files) >= 2, f"Expected at least 2 feed files, got {len(feed_files)}"

        # Verify feed filenames are URL slugs (no spaces or special characters)
        for feed_file in feed_files:
            assert " " not in feed_file, f"Feed filename contains spaces: {feed_file}"
            assert "|" not in feed_file, f"Feed filename contains pipe: {feed_file}"
            # Should be lowercase slug with .xml extension
            name = feed_file.removesuffix(".xml")
            assert name.replace("-", "").replace("_", "").isalnum(), \
                f"Feed filename is not a valid slug: {feed_file}"

        # Validate RSS structure of first feed
        feed_file = os.path.join(feeds_dir, feed_files[0])
        tree = ET.parse(feed_file)
        root = tree.getroot()

        assert root.tag == "rss", f"Feed root element is not <rss>: {root.tag}"
        channel = root.find("channel")
        assert channel is not None, "No <channel> element found in feed"

        # Check required elements
        title = channel.find("title")
        assert title is not None and title.text, "Channel title missing or empty"

        items = channel.findall("item")
        assert len(items) >= 1, "No <item> elements found in feed"


def test_list_shows_returns_discovered_shows(source_root: str, storage_root: str):
    """List command returns shows from local state."""
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}",
           f"--storage_root={storage_root}",
           "list", "shows"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    for show in SHOWS:
        assert show in result.stdout, f"Show {show} not found in output"


def test_list_episodes_returns_discovered_episodes(source_root: str, storage_root: str):
    """List command returns episodes from local state."""
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}",
           f"--storage_root={storage_root}",
           "list", "episodes"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    for episode in EPISODES:
        assert episode in result.stdout, f"Episode {episode} not found in output"


@pytest.mark.xfail(reason="TODO: Host extraction not yet implemented for redesigned site")
def test_list_hosts_returns_discovered_hosts(source_root: str, storage_root: str):
    """List command returns hosts from local state."""
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}",
           f"--storage_root={storage_root}",
           "list", "hosts"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    for host in HOSTS:
        assert host in result.stdout, f"Host {host} not found in output"


def test_list_shows_match_filter(source_root: str, storage_root: str):
    """List command with --match filters shows."""
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}",
           f"--storage_root={storage_root}",
           "--match", "henry",
           "list", "shows"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, f"Command failed: {result.stderr}"

    assert "henry-rollins" in result.stdout
    assert "morning-becomes-eclectic" not in result.stdout


def test_feed_items_in_chronological_order(source_root: str):
    """Feed episodes are sorted with most recent first."""
    project_root = os.path.abspath(".")

    with tempfile.TemporaryDirectory() as tmpdirname:
        cmd = ["poetry", "run", "kcrw-feed",
               f"--source_root={source_root}",
               f"--storage_root={tmpdirname}",
               "update"
               ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=project_root
        )
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        feeds_dir = os.path.join(tmpdirname, "feeds")
        feed_files = [f for f in os.listdir(feeds_dir) if f.endswith('.xml')]

        for feed_file in feed_files:
            tree = ET.parse(os.path.join(feeds_dir, feed_file))
            items = tree.findall(".//item")

            pub_dates = []
            for item in items:
                pub_date_elem = item.find("pubDate")
                if pub_date_elem is not None and pub_date_elem.text:
                    pub_dates.append(parsedate_to_datetime(pub_date_elem.text))

            if len(pub_dates) > 1:
                # Dates should be sorted from most recent to oldest
                assert pub_dates == sorted(pub_dates, reverse=True), \
                    f"Episode pubDates in {feed_file} are not in descending order"
