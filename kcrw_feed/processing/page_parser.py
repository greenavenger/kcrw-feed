"""Module for parsing HTML pages to extract structured data."""

import logging
import re
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urlparse

logger = logging.getLogger("kcrw_feed")

# Pattern to match audio file URLs
AUDIO_URL_PATTERN = re.compile(r'https://[^"\']*\.(mp3|m4a|ogg|aac)', re.IGNORECASE)


class PageDataParser:
    """Extracts structured data from HTML pages.

    Uses meta tags (Open Graph, Twitter Card) and page content to extract
    show and episode information.
    """

    def __init__(self, html: bytes):
        """Initialize parser with HTML content.

        Args:
            html: The raw HTML bytes to parse.
        """
        self.soup = BeautifulSoup(html, "html.parser")
        self._html_str = html.decode("utf-8", errors="replace")

    def get_meta(self, name: str, property_name: Optional[str] = None) -> Optional[str]:
        """Get content from a meta tag by name or property.

        Args:
            name: The meta tag name attribute.
            property_name: Optional property attribute to check.

        Returns:
            The meta tag content, or None if not found.
        """
        # Try name attribute first
        tag = self.soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"]

        # Try property attribute
        if property_name:
            tag = self.soup.find("meta", attrs={"property": property_name})
            if tag and tag.get("content"):
                return tag["content"]

        return None

    def get_og(self, property_suffix: str) -> Optional[str]:
        """Get Open Graph meta tag content.

        Args:
            property_suffix: The part after 'og:' (e.g., 'title', 'description').

        Returns:
            The meta tag content, or None if not found.
        """
        tag = self.soup.find("meta", attrs={"property": f"og:{property_suffix}"})
        if tag and tag.get("content"):
            return tag["content"]
        return None

    def get_title(self) -> Optional[str]:
        """Extract page title.

        Returns:
            The page title, cleaned of site suffix.
        """
        # Try og:title first
        title = self.get_og("title")
        if title:
            # Remove common suffixes like " | KCRW"
            if " | " in title:
                title = title.rsplit(" | ", 1)[0]
            return title

        # Fall back to <title> tag
        title_tag = self.soup.find("title")
        if title_tag and title_tag.text:
            title = title_tag.text.strip()
            if " | " in title:
                title = title.rsplit(" | ", 1)[0]
            return title

        return None

    def get_description(self) -> Optional[str]:
        """Extract page description."""
        return self.get_og("description") or self.get_meta("description")

    def get_url(self) -> Optional[str]:
        """Extract canonical URL."""
        # Try og:url
        url = self.get_og("url")
        if url:
            return url

        # Try canonical link
        canonical = self.soup.find("link", attrs={"rel": "canonical"})
        if canonical and canonical.get("href"):
            return canonical["href"]

        return None

    def get_image(self) -> Optional[str]:
        """Extract image URL."""
        return self.get_og("image")

    def get_author(self) -> Optional[str]:
        """Extract author name."""
        return self.get_meta("author")

    def get_published_time(self) -> Optional[str]:
        """Extract published time from article:published_time."""
        tag = self.soup.find("meta", attrs={"property": "article:published_time"})
        if tag and tag.get("content"):
            return tag["content"]
        return None

    def get_audio_url(self) -> Optional[str]:
        """Extract audio file URL from page content.

        Returns:
            The first audio URL found, or None.
        """
        match = AUDIO_URL_PATTERN.search(self._html_str)
        if match:
            # Clean up any trailing backslash
            url = match.group(0).rstrip("\\")
            return url
        return None

    def get_show_data(self) -> Dict[str, Any]:
        """Extract show data from the page.

        Returns:
            Dictionary with show fields.
        """
        return {
            "title": self.get_title(),
            "description": self.get_description(),
            "url": self.get_url(),
            "image": self.get_image(),
        }

    def get_episode_data(self) -> Dict[str, Any]:
        """Extract episode data from the page.

        Returns:
            Dictionary with episode fields.
        """
        return {
            "title": self.get_title(),
            "description": self.get_description(),
            "url": self.get_url(),
            "image": self.get_image(),
            "airdate": self.get_published_time(),
            "media_url": self.get_audio_url(),
            "author": self.get_author(),
        }

    def get_music_show_slugs(self) -> list[str]:
        """Extract music show slugs from a shows-and-djs listing page.

        Parses links to /shows/{slug} and returns the unique slugs.

        Returns:
            List of show slugs (e.g., ['henry-rollins', 'morning-becomes-eclectic']).
        """
        slugs = set()
        for link in self.soup.find_all("a", href=True):
            href = link["href"]
            # Match /shows/{slug} pattern (not /shows/{slug}/something)
            match = re.match(r"^/shows/([a-z0-9-]+)/?$", href)
            if match:
                slugs.add(match.group(1))
        return sorted(slugs)
