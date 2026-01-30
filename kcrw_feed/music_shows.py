"""Module to manage the list of music shows for feed filtering."""

import json
import logging
import os
import re
from typing import List, Optional

from kcrw_feed.processing.page_parser import PageDataParser
from kcrw_feed.source_manager import BaseSource

logger = logging.getLogger("kcrw_feed")

MUSIC_SHOWS_FILE = "music_shows.json"
MUSIC_SHOWS_PAGE = "music/shows-and-djs"


def load_music_shows(storage_root: str) -> List[str]:
    """Load the music shows list from storage.

    Args:
        storage_root: The root directory for state files.

    Returns:
        List of music show slugs.
    """
    filepath = os.path.join(storage_root, MUSIC_SHOWS_FILE)
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("music_shows", [])
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to load music shows file: %s", e)
        return []


def save_music_shows(storage_root: str, slugs: List[str]) -> None:
    """Save the music shows list to storage.

    Args:
        storage_root: The root directory for state files.
        slugs: List of music show slugs to save.
    """
    filepath = os.path.join(storage_root, MUSIC_SHOWS_FILE)
    os.makedirs(storage_root, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"music_shows": sorted(set(slugs))}, f, indent=2)
    logger.info("Saved %d music shows to %s", len(slugs), filepath)


def fetch_music_shows(source: BaseSource) -> List[str]:
    """Fetch the music shows list from the website.

    Args:
        source: The source to fetch from.

    Returns:
        List of music show slugs.
    """
    html = source.get_reference(MUSIC_SHOWS_PAGE)
    if html is None:
        # Fallback for file-based sources (CacheSource uses index.html)
        html = source.get_reference(MUSIC_SHOWS_PAGE + "/index.html")
    if html is None:
        logger.warning("Failed to fetch music shows page")
        return []
    parser = PageDataParser(html)
    slugs = parser.get_music_show_slugs()
    logger.info("Fetched %d music shows from %s", len(slugs), MUSIC_SHOWS_PAGE)
    return slugs


def sync_music_shows(storage_root: str, source: BaseSource) -> List[str]:
    """Sync the music shows list - fetch from website and merge with existing.

    Args:
        storage_root: The root directory for state files.
        source: The source to fetch from.

    Returns:
        The merged list of music show slugs.
    """
    existing = set(load_music_shows(storage_root))
    fetched = set(fetch_music_shows(source))
    merged = sorted(existing | fetched)
    if merged != sorted(existing):
        save_music_shows(storage_root, merged)
    return merged


def build_music_shows_pattern(slugs: List[str]) -> Optional[str]:
    """Build a regex pattern to match music show URLs.

    Matches both /shows/{slug} and /music/{slug} URL patterns since
    some shows use /music/ in their canonical URL (og:url).

    Args:
        slugs: List of music show slugs.

    Returns:
        Regex pattern string, or None if no slugs.
    """
    if not slugs:
        return None
    # Escape any regex special chars in slugs (shouldn't be any, but safe)
    escaped = [re.escape(s) for s in slugs]
    return f"/(shows|music)/({'|'.join(escaped)})(/|$)"
