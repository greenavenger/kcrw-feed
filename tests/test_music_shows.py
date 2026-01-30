"""Tests for music shows page parsing and music_shows module."""

import json
import os
import re

from kcrw_feed.music_shows import (
    build_music_shows_pattern,
    fetch_music_shows,
    sync_music_shows,
)
from kcrw_feed.processing.page_parser import PageDataParser
from kcrw_feed.source_manager import CacheSource


TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SHOWS_AND_DJS_HTML = os.path.join(TEST_DATA_DIR, "music", "shows-and-djs", "index.html")

EXPECTED_SLUGS = [
    "anne-litt",
    "chris-douridas",
    "dan-wilcox",
    "eclectic24",
    "francesca-harding",
    "henry-rollins",
    "john-tejada",
    "leroy-downs",
    "live-from",
    "luxxury",
    "metropolis",
    "morning-becomes-eclectic",
    "peanut-butter-wolf",
    "raul-campos",
    "resident-dj",
    "ro-wyldeflower-contreras",
    "silva",
    "todays-top-tune",
    "tyler-boudreaux",
]

TEST_CONFIG = {
    "source_root": TEST_DATA_DIR,
    "storage_root": ".",
}


class TestGetMusicShowSlugs:
    def test_parses_show_slugs_from_real_html(self):
        with open(SHOWS_AND_DJS_HTML, "rb") as f:
            html = f.read()
        parser = PageDataParser(html)
        slugs = parser.get_music_show_slugs()
        assert slugs == EXPECTED_SLUGS

    def test_returns_empty_for_page_without_show_links(self):
        html = b"<html><body><p>No shows here</p></body></html>"
        parser = PageDataParser(html)
        slugs = parser.get_music_show_slugs()
        assert slugs == []


class TestFetchMusicShows:
    def test_fetches_from_cache_source(self):
        source = CacheSource(TEST_DATA_DIR, TEST_CONFIG)
        slugs = fetch_music_shows(source)
        assert slugs == EXPECTED_SLUGS


class TestSyncMusicShows:
    def test_creates_file_and_returns_slugs(self, tmp_path):
        source = CacheSource(TEST_DATA_DIR, TEST_CONFIG)
        result = sync_music_shows(str(tmp_path), source)
        assert result == EXPECTED_SLUGS

        # Verify file was written
        filepath = tmp_path / "music_shows.json"
        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert data["music_shows"] == EXPECTED_SLUGS

    def test_idempotent_on_second_call(self, tmp_path):
        source = CacheSource(TEST_DATA_DIR, TEST_CONFIG)
        first = sync_music_shows(str(tmp_path), source)
        filepath = tmp_path / "music_shows.json"
        mtime_after_first = filepath.stat().st_mtime

        second = sync_music_shows(str(tmp_path), source)
        assert first == second
        # File should not be rewritten if nothing changed
        assert filepath.stat().st_mtime == mtime_after_first

    def test_merges_with_existing_slugs(self, tmp_path):
        # Pre-populate with an extra slug not on the live page
        filepath = tmp_path / "music_shows.json"
        filepath.write_text(json.dumps({
            "music_shows": ["custom-show", "henry-rollins"]
        }))

        source = CacheSource(TEST_DATA_DIR, TEST_CONFIG)
        result = sync_music_shows(str(tmp_path), source)

        # custom-show should be preserved via merge
        assert "custom-show" in result
        # All live slugs should also be present
        for slug in EXPECTED_SLUGS:
            assert slug in result


class TestBuildMusicShowsPattern:
    def test_returns_none_for_empty_list(self):
        assert build_music_shows_pattern([]) is None

    def test_matches_shows_urls(self):
        pattern = build_music_shows_pattern(["henry-rollins", "anne-litt"])
        compiled = re.compile(pattern)
        assert compiled.search("/shows/henry-rollins")
        assert compiled.search("/shows/anne-litt")
        assert compiled.search("/music/henry-rollins")
        assert compiled.search("/shows/henry-rollins/stories/episode-1")

    def test_does_not_match_unrelated_urls(self):
        pattern = build_music_shows_pattern(["henry-rollins"])
        compiled = re.compile(pattern)
        assert not compiled.search("/shows/anne-litt")
        assert not compiled.search("/news/henry-rollins")
        assert not compiled.search("/henry-rollins")
