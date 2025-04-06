"""Test the program end-to-end with golden data"""

import os
import pprint
import subprocess
import tempfile
import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

# Run test_update_command() first to ensure that kcrw_feed.json exists for list commands.
# TODO: move list commands into a tempdir too!


def test_update_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "update"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    assert "Updates applied: 14" in result.stdout
    pprint.pprint(result.stdout)


RESOURCES_PRE_2025 = ["/music/shows/henry-rollins/kcrw-broadcast-820",
                      "/music/shows/henry-rollins/kcrw-broadcast-819",
                      "/music/shows/henry-rollins/kcrw-broadcast-818",
                      "/music/shows/henry-rollins/kcrw-broadcast-817",
                      "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-december-18-2024"]
RESOURCES_POST_2025 = ["/music/shows/henry-rollins/kcrw-broadcast-825",
                       "/music/shows/henry-rollins/kcrw-broadcast-824",
                       "/music/shows/henry-rollins/kcrw-broadcast-822",
                       "/music/shows/henry-rollins/kcrw-broadcast-821",
                       "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-25-2025",
                       "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-22-2025",
                       "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-15-2025"]
RESOURCES = RESOURCES_PRE_2025 + RESOURCES_POST_2025


def test_list_resources_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for resource in RESOURCES:
        assert resource in result.stdout
    pprint.pprint(result.stdout)


def test_list_resources_until_date_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "--until", "2025-01-01", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for resource in RESOURCES_PRE_2025:
        assert resource in result.stdout
    pprint.pprint(result.stdout)


def test_list_resources_since_date_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "--since", "2025-01-01", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for resource in RESOURCES_POST_2025:
        assert resource in result.stdout
    pprint.pprint(result.stdout)


SHOWS = ["https://www.kcrw.com/music/shows/henry-rollins",
         "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras"]


def test_list_shows_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "list", "shows"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for show in SHOWS:
        assert show in result.stdout
    pprint.pprint(result.stdout)


def test_list_shows_match_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "--match", "wylde", "list", "shows"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    assert SHOWS[1] in result.stdout
    pprint.pprint(result.stdout)


EPISODES_PRE_2025 = ["https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-817",
                     "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-818",
                     "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-819",
                     "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-820",
                     "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-821",
                     "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-december-18-2024",
                     ]
EPISODES_POST_2025 = ["https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-822",
                      "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-824",
                      "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-825",
                      "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-15-2025",
                      "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-22-2025",
                      "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-25-2025"]
EPISODES = EPISODES_PRE_2025 + EPISODES_POST_2025


def test_list_episodes_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "list", "episodes"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for episode in EPISODES:
        assert episode in result.stdout
    pprint.pprint(result.stdout)


def test_list_episodes_filter_until_date_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "--until", "2025-01-01", "list", "episodes"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for episode in EPISODES_PRE_2025:
        assert episode in result.stdout
    pprint.pprint(result.stdout)


def test_list_episodes_filter_since_date_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "--since", "2025-01-01", "list", "episodes"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for episode in EPISODES_POST_2025:
        assert episode in result.stdout
    pprint.pprint(result.stdout)


HOSTS = [
    'Henry Rollins',
    'Ro "Wyldeflower" Contreras'
]


def test_list_hosts_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "list", "hosts"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for host in HOSTS:
        assert host in result.stdout
    pprint.pprint(result.stdout)


def test_save_functionality():
    # Use an absolute path for source_root.
    source_root = os.path.abspath("./tests/data/")
    # Use the project root as cwd so Poetry finds pyproject.toml.
    project_root = os.path.abspath(".")

    # Run the CLI in a temporary working directory so output files are isolated.
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Construct the command. This assumes your CLI picks up the output location
        # as the current working directory.
        cmd = [
            "poetry", "run", "kcrw-feed",
            f"--source_root={source_root}",
            f"--storage_root={tmpdirname}",
            "update"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=project_root, check=True
        )
        # Check that the command exited successfully.
        assert result.returncode == 0
        # Check that expected log messages are present.
        assert "Saving state" in result.stdout
        assert "Writing feeds" in result.stdout

        # Check that the JSON file was written.
        json_file = os.path.join(tmpdirname, "kcrw_feed.json")
        assert os.path.exists(json_file), f"JSON file not found at {json_file}"
        with open(json_file, "r", encoding="utf-8") as f:
            state = json.load(f)
        # Verify that the state contains shows.
        assert "shows" in state, "No 'shows' key in JSON state"
        assert len(state["shows"]) > 0, "No shows persisted in JSON file"

        # Check that RSS feed files were written in a subdirectory (e.g., 'feeds').
        feeds_dir = os.path.join(tmpdirname, "feeds")
        assert os.path.isdir(
            feeds_dir), f"Feeds directory not found at {feeds_dir}"
        feed_files = os.listdir(feeds_dir)
        assert len(feed_files) > 0, "No feed files found in feeds directory"

        # Pick one feed file and parse its XML.
        feed_file = os.path.join(feeds_dir, feed_files[0])
        tree = ET.parse(feed_file)
        root = tree.getroot()
        # Verify that the root element is <rss> and it contains a <channel>.
        assert root.tag == "rss", f"Feed root element is not <rss>: {root.tag}"
        channel = root.find("channel")
        assert channel is not None, "No <channel> element found in feed"

        # Check that the channel has a title and at least one <item>.
        title = channel.find("title")
        assert title is not None and title.text, "Channel title missing or empty"
        items = channel.findall("item")
        assert len(items) > 0, "No <item> elements (episodes) found in feed"

        # Verify that the pubDate values of the items are in descending order.
        pub_dates = [item.find("pubDate").text for item in items if item.find(
            "pubDate") is not None]
        dates = [parsedate_to_datetime(d) for d in pub_dates]
        # Dates should be sorted from most recent to oldest.
        assert dates == sorted(
            dates, reverse=True), "Episode pubDates are not in descending order"

        # TODO: Why is this no longer working?
        # pprint.pprint("JSON state:", json.dumps(state, indent=2))
        # pprint.pprint("RSS feed file:", feed_file)
