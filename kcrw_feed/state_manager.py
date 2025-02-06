"""Module to handle state persistence"""

import json
from datetime import datetime
from dataclasses import asdict

from kcrw_feed.models import Host, Show, Episode


class Json:

    def __init__(self, filename: str = "kcrw_feed.json") -> None:
        self.filename = filename

    # Serialize
    def default_serializer(self, obj):
        """Helper to convert non-serializable objects like datetime"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")

    def save_state(self, dj: Host, filename: str | None = None) -> None:
        filename = filename or self.filename
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(asdict(dj), f, default=self.default_serializer, indent=2)

    # Deserialize
    def _parse_datetime(self, dt_str: str) -> datetime:  # | None:
        """Assume ISO format dates."""
        return datetime.fromisoformat(dt_str)

    def episode_from_dict(self, data: dict) -> Episode:
        return Episode(
            title=data["title"],
            pub_date=self._parse_datetime(data["pub_date"]) if data.get(
                "pub_date") else None,
            audio_url=data["audio_url"],
            description=data.get("description")
        )

    def show_from_dict(self, data: dict) -> Show:
        episodes = [self.episode_from_dict(ep)
                    for ep in data.get("episodes", [])]
        last_updated = self._parse_datetime(
            data["last_updated"]) if data.get("last_updated") else None
        return Show(
            title=data["title"],
            url=data["url"],
            description=data.get("description"),
            episodes=episodes,
            last_updated=last_updated,
            metadata=data.get("metadata", {})
        )

    def host_from_dict(self, data: dict) -> Host:
        shows = [self.show_from_dict(s) for s in data.get("shows", [])]
        return Host(
            name=data["name"],
            shows=shows
        )

    def load_state(self, filename: str | None = None) -> Host:
        filename = filename or self.filename
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.host_from_dict(data)


# # feed_generator_rss.py
# from feedgen.feed import FeedGenerator
# from models import DJ, Show, Episode
# from datetime import datetime

# def generate_rss_feed(dj: DJ) -> str:
#     fg = FeedGenerator()
#     fg.title(f"{dj.name}'s Shows")
#     fg.link(href='http://example.com')  # A placeholder link
#     fg.description('Aggregated feed of DJ shows.')

#     # For each show, add an item (or you might decide to have multiple feeds)
#     for show in dj.shows:
#         fe = fg.add_entry()
#         fe.title(show.title)
#         fe.link(href=show.url)
#         fe.description(show.description or "")
#         if show.last_updated:
#             fe.pubDate(show.last_updated)
#         # Optionally, add custom elements or embed state information:
#         for ep in show.episodes:
#             # You might include details of episodes as custom XML or as separate items.
#             # Here, we’re just illustrating a simple approach.
#             fe.description(f"{fe.description()} | Episode: {ep.title} published on {ep.pub_date.isoformat()}")

#     # Return the RSS XML as a string.
#     return fg.rss_str(pretty=True).decode("utf-8")

# # rehydrate_rss.py
# def parse_feed_datetime(entry) -> datetime:
#     """Convert feedparser's published_parsed to a datetime object."""
#     if "published_parsed" in entry and entry.published_parsed:
#         return datetime(*entry.published_parsed[:6])
#     return None


# def load_show_from_rss(feed_url: str) -> Show:
#     feed = feedparser.parse(feed_url)

#     # Use feed-level metadata for the Show.
#     show_title = feed.feed.get("title", "Untitled Show")
#     show_url = feed.feed.get("link", "")
#     show_description = feed.feed.get("description", "")

#     episodes = []
#     # Each entry is assumed to represent an Episode.
#     for entry in feed.entries:
#         pub_date = parse_feed_datetime(entry)
#         ep = Episode(
#             title=entry.get("title", "Untitled Episode"),
#             pub_date=pub_date,
#             audio_url=entry.get("link", ""),
#             description=entry.get("summary", "")
#         )
#         episodes.append(ep)

#     # For last_updated, we use the most recent episode date.
#     last_updated = max(
#         (ep.pub_date for ep in episodes if ep.pub_date), default=None)

#     return Show(
#         title=show_title,
#         url=show_url,
#         description=show_description,
#         episodes=episodes,
#         last_updated=last_updated,
#         metadata={}  # You could extract custom metadata if available.
#     )


# def load_dj_from_rss(feed_urls: list[str]) -> DJ:
#     """
#     If you have multiple feeds (each for a different show), combine them under one DJ.
#     """
#     shows = []
#     for url in feed_urls:
#         show = load_show_from_rss(url)
#         shows.append(show)
#     # Here we assign a generic DJ name; you might parse this from the feed if available.
#     return DJ(name="DJ from RSS", shows=shows)


# # Example usage:
# if __name__ == "__main__":
#     # Assume we have a list of feed URLs.
#     feed_urls = [
#         "http://example.com/show1.rss",
#         "http://example.com/show2.rss"
#     ]
#     dj = load_dj_from_rss(feed_urls)
#     print(dj)
