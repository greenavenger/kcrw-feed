"""Test the program end-to-end with golden data"""

import os
import pprint
import subprocess
import tempfile
import json
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

RESOURCES = ["/music/shows/henry-rollins/kcrw-broadcast-825",
             "/music/shows/henry-rollins/kcrw-broadcast-824",
             "/music/shows/henry-rollins/kcrw-broadcast-822",
             "/music/shows/henry-rollins/kcrw-broadcast-821",
             "/music/shows/henry-rollins/kcrw-broadcast-820",
             "/music/shows/henry-rollins/kcrw-broadcast-819",
             "/music/shows/henry-rollins/kcrw-broadcast-818",
             "/music/shows/henry-rollins/kcrw-broadcast-817",
             "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-25-2025",
             "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-22-2025",
             "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-15-2025",
             "/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-december-18-2024"]


def test_gather_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "gather"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for resource in RESOURCES:
        assert resource in result.stdout
    pprint.pprint(result.stdout)


def test_update_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "update"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    assert "Updated 15" in result.stdout
    pprint.pprint(result.stdout)


SHOWS = ["https://www.kcrw.com/music/shows/henry-rollins",
         "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras"]


def test_list_shows_command():
    # Use an absolute path for the source_root so it's unambiguous.
    source_root = os.path.abspath("./tests/data/")
    cmd = ["poetry", "run", "kcrw-feed",
           f"--source_root={source_root}", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert result.returncode == 0
    for show in SHOWS:
        assert show in result.stdout
    pprint.pprint(result.stdout)


# TODO: Fix so filtering properly applies to list commands
# def test_list_shows_match_command():
#     # Use an absolute path for the source_root so it's unambiguous.
#     source_root = os.path.abspath("./tests/data/")
#     cmd = ["poetry", "run", "kcrw-feed",
#            f"--source_root={source_root}", "list",
#            f"--shows={SHOWS[0]}"]
#     result = subprocess.run(cmd, capture_output=True, text=True, check=True)
#     assert result.returncode == 0
#     assert SHOWS[0] in result.stdout
#     pprint.pprint(result.stdout)


EPISODES = ["https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-817",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-818",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-819",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-820",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-821",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-822",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-824",
            "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-825",
            "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-december-18-2024",
            "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-15-2025",
            "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-22-2025",
            "https://www.kcrw.com/music/shows/ro-wyldeflower-contreras/ro-wyldeflower-contreras-playlist-january-25-2025"]


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


def test_save_command():
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
            f"--data_root={tmpdirname}",
            "save"
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=project_root, check=True
        )
        # Check that the command exited successfully.
        assert result.returncode == 0
        # Check that expected log messages are present.
        assert "Saving entities" in result.stdout
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
