import requests
from bs4 import BeautifulSoup
import feedgenerator
import json
from datetime import datetime
import argparse  # For command-line arguments
import re
import io
from typing import List, Dict, Optional
from urllib.parse import urlparse
import sys
import pprint

from models import DJ, Show, Episode
# from kcrw_feed import sitemap
# from kcrw_feed import scraper
# from kcrw_feed import generate_feed


def scrape_show(show_url: str, episode_count: int = 6) -> Optional[List[Dict]]:
    """Scrapes KCRW show data and returns a list of episode dictionaries."""

    try:
        # response = requests.get(show_url)
        # response.raise_for_status()  # Raise an exception for bad status codes
        # soup = BeautifulSoup(response.content, "html.parser")
        with open("./tests/henry-rollins/henry-rollins", "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        # print(soup.prettify())

        # Find the latest episode number (adapt this selector if needed)
        show_headline = soup.find(text=re.compile("KCRW Broadcast ([0-9]+)"))
        if show_headline is None:
            print("Could not find show headline.")
            return None

        latest_episode = int(
            show_headline.text.replace("KCRW Broadcast ", "")
        )  # leave episode number
        # print(latest_episode)

        episodes = []
        fetched_episode_count = 0

        for i in range(episode_count):
            episode_number = latest_episode - i
            # Example: "https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-822/player.json"
            episode_url = f"https://www.kcrw.com/music/shows/henry-rollins/kcrw-broadcast-{
                episode_number}/player.json"  # f-string formatting
            print(episode_number, ":", episode_url)

            try:
                # episode_response = requests.get(episode_url)
                # episode_response.raise_for_status()
                # episode_data = episode_response.json()
                with open(
                    f"./tests/henry-rollins/kcrw-broadcast-{
                        episode_number}_player.json",
                    "r",
                    encoding="utf-8"
                ) as f:
                    episode_data = json.load(f)
                # print(episode_data)

                if episode_data.get("media") and len(episode_data["media"]) > 0:
                    # print("\nmedia:", episode_data.get("media"), "\n")
                    print("airdate:", episode_data.get("airdate"))
                    episodes.append(episode_data)
            except (requests.exceptions.RequestException, FileNotFoundError) as e:
                print(f"Error fetching episode data: {e}")
                continue  # Continue to the next episode

            fetched_episode_count += 1

        print(len(episodes))
        return episodes

    except requests.exceptions.RequestException as e:
        print(f"Error fetching show page: {e}")
        return None


def generate_feed(show_data, feed_filename="kcrw_feed.rss"):
    """Generates an RSS feed from the scraped show data."""
    if show_data is None:
        return

    print([sd.get("airdate") for sd in show_data])
    show_data.sort(
        key=lambda e: datetime.strptime(e["airdate"], "%Y-%m-%dT%H:%M:%S%z"),
        reverse=True,
    )  # Sort by airdate
    print([sd.get("airdate") for sd in show_data])

    feed = feedgenerator.Rss201rev2Feed(
        title="Henry Rollins - KCRW",
        description="Henry Rollins hosts a great mix of all kinds from all over from all time.",
        link="https://www.kcrw.com/music/shows/henry-rollins",
        author_name="Henry Rollins",
        itunes_image="https://www.kcrw.com/music/shows/henry-rollins/@@images/square_image",
        language="en",
    )

    for episode in show_data:
        media_url = urlparse(episode["media"][0]["url"])  # Enclosure URL
        media_url = media_url._replace(query=None)  # strip query parameters
        # print(media_url.geturl())
        feed.add_item(
            title=episode["title"],
            description=episode["description"],
            link=media_url.geturl(),
            guid=episode["uuid"],
            pubdate=datetime.strptime(
                episode["airdate"], "%Y-%m-%dT%H:%M:%S%z"
            ),  # Parse airdate
            itunes_image=episode["image"],
            itunes_duration=episode["duration"],
        )

    # feed_string = io.StringIO()
    # feed.write(feed_string, "utf-8")
    # print(feed_string.getvalue())
    # rss = BeautifulSoup(feed_string, "html.parser")
    # print(rss.prettify())
    with open(feed_filename, "w") as fp:
        feed.write(fp, "utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate KCRW feed.")
    parser.add_argument("show_url", help="URL of the KCRW show page.")
    parser.add_argument(
        "-n",
        "--episodes",
        type=int,
        default=6,
        help="Number of episodes to include (default: 6).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="kcrw_feed.rss",
        help="Output RSS filename (default: kcrw_feed.rss).",
    )

    args = parser.parse_args()

    show_url = args.show_url
    episode_count = args.episodes
    output_filename = args.output

    # model
    dj = DJ(name="Dan Wilcox")

    # Create a show instance.
    show = Show(
        title="Weekly Music Show",
        url="http://kcrw.com/shows/dan-wilcox",
        description="A weekly round-up of music."
    )
    dj.add_show(show)

    # Create an episode.
    from datetime import datetime
    episode = Episode(
        title="Episode 1",
        pub_date=datetime.now(),
        audio_url="http://kcrw.com/audio/episode1.mp3",
        description="Kickoff episode."
    )
    show.add_episode(episode)

    # Output current state (for debugging)
    pprint.pprint(dj)

    # root_sitemap = "./research/sitemap.xml.gz"
    # sitemaps = sitemap.process_sitemap_index(root_sitemap)

    episodes = scrape_show(show_url, episode_count)

    if episodes:
        generate_feed(episodes, output_filename)
        print(f"RSS feed generated successfully: {output_filename}")
    else:
        print("Failed to scrape show data.")


if __name__ == "__main__":
    main()
