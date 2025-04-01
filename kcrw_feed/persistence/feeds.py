"""Module to handle feeds persistence"""

import logging
import os

from django.utils.feedgenerator import Rss201rev2Feed

from kcrw_feed.persistence.base import BasePersister
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import ShowDirectory


logger = logging.getLogger("kcrw_feed")

FEED_DIRECTORY = "feeds/"


class FeedPersister(BasePersister):
    """Concrete implementation for storing feeds."""

    def __init__(self, storage_root: str, feed_dir: str = FEED_DIRECTORY) -> None:
        self.feed_dir = os.path.join(storage_root, feed_dir)
        logger.debug("RSS output directory: %s", self.feed_dir)

    def save(self, show_directory: ShowDirectory, feed_dir: str | None = None) -> None:
        """Generate an individual RSS feed XML file for each show in the state.
        Episodes are sorted in reverse chronological order (most recent first).

        Parameters:
          state: A ShowDirectory instance containing a list of shows.
          output_dir: The output directory where feed files will be written."""
        feed_dir = feed_dir or self.feed_dir
        os.makedirs(feed_dir, exist_ok=True)
        for show in show_directory.shows:
            # Create an RSS feed using Django's feed generator.
            feed = Rss201rev2Feed(
                title=show.title,
                link=show.url,
                description=show.description or "",
                language="en"
            )
            # Sort episodes: most recent first.
            episodes = sorted(
                [ep for ep in show.episodes if ep.airdate is not None], reverse=True)
            for ep in episodes:
                feed.add_item(
                    title=ep.title,
                    link=ep.media_url,
                    description=ep.description or "",
                    pubdate=ep.airdate
                )
            # Generate the XML as a string.
            feed_xml = feed.writeString("utf-8")
            # Use the show's UUID as the filename (or fallback to title).
            file_name = f"{show.title}.xml" if show.title else f"{show.uuid}.xml"
            output_path = os.path.join(feed_dir, file_name)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(feed_xml)

    def load(self, filename: str) -> ShowDirectory:
        raise NotImplementedError("RSS load not implemented")
