"""Module to handle feeds persistence"""

from datetime import datetime
import logging
from typing import Optional
import os

from atomicwrites import atomic_write
from feedgen.feed import FeedGenerator

from kcrw_feed.persistence.base import BasePersister
from kcrw_feed.persistence.logger import TRACE_LEVEL_NUM
from kcrw_feed.models import Show, Episode, ShowDirectory


logger = logging.getLogger("kcrw_feed")


class FeedPersister(BasePersister):
    """Concrete implementation for storing feeds."""

    def __init__(self, storage_root: str, feed_directory: str) -> None:
        self.feed_directory = os.path.abspath(
            os.path.join(storage_root, feed_directory))
        logger.debug("RSS output directory: %s", self.feed_directory)

    def save(self, show_directory: ShowDirectory, feed_directory: Optional[str] = None) -> None:
        """Generate an individual RSS feed XML file for each show in the state.
        Episodes are sorted in reverse chronological order (most recent first).

        Parameters:
          state: A ShowDirectory instance containing a list of shows.
          output_dir: The output directory where feed files will be written."""
        feed_directory = feed_directory or self.feed_directory
        os.makedirs(feed_directory, exist_ok=True)
        for show in show_directory.shows:
            # Create an RSS feed using Django's feed generator.
            feed_xml = self.generate_rss_feed(show)
            # Use the show's title as the filename (or fallback to UUID).
            file_name = f"{show.title}.xml" if show.title else f"{show.uuid}.xml"
            output_path = os.path.join(feed_directory, file_name)
            with atomic_write(output_path, mode="w", overwrite=True, encoding="utf-8") as f:
                f.write(feed_xml)

    def generate_rss_feed(self, show: Show) -> str:

        host_name = ""
        if show.hosts:
            host_name = show.hosts[0].name

        title = show.title
        if show.hosts:
            title = f"{host_name} - KCRW"

        fg = FeedGenerator()
        fg.load_extension('podcast')

        # RSS channel info
        # github.com/python-feedgen/feedgen/feed.py
        fg.title(title)
        fg.link(href=show.url, rel='alternate')
        fg.description(show.description)

        fg.author({'name': host_name})
        fg.id(show.uuid.hex)
        fg.image(show.image)
        fg.language('en')
        fg.pubDate(show.last_updated)

        # github.com/python-feedgen/feedgen/ext/podcast.py
        fg.podcast.itunes_author(host_name)
        fg.podcast.itunes_category('Music')  # , 'Podcast')
        fg.podcast.itunes_image(show.image)

        for episode in sorted(show.episodes):
            pub_date: datetime = episode.airdate or episode.last_updated or datetime.now()
            length = int(episode.duration)

            # RSS item info
            # github.com/python-feedgen/feedgen/entry.py
            fe = fg.add_entry()
            fe.author({'name': host_name})
            fe.description(episode.description)
            fe.enclosure(episode.media_url, length, "audio/mpeg")
            fe.id(str(episode.uuid.hex))
            fe.link(href=episode.url)
            fe.pubDate(pub_date)
            fe.title(episode.title)

            # github.com/python-feedgen/feedgen/ext/podcast_entry.py
            # fe.podcast.itunes_author(host_name)
            # fe.podcast.itunes_duration(length)

        return fg.rss_str(pretty=True).decode("utf-8")
        # return fg.rss_str().decode("utf-8")

    def load(self, filename: str) -> ShowDirectory:
        raise NotImplementedError("RSS load not implemented")
