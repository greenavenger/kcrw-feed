# import requests
# from bs4 import BeautifulSoup
# import feedgenerator
# import json
# from datetime import datetime
import argparse
# import re
# import io
# from typing import List, Dict, Optional
# from urllib.parse import urlparse
# import urllib.robotparser as urobot
# import sys
import pprint

from kcrw_feed.config import CONFIG
# from kcrw_feed.models import Host, Show, Episode
# from kcrw_feed import state_manager
from kcrw_feed import show_gatherer
# from kcrw_feed import sitemap
# from kcrw_feed import utils
# from kcrw_feed import scraper
# from kcrw_feed import generate_feed

pprint.pprint(CONFIG)
print(CONFIG.get("extra_sitemaps"))


def main():

    parser = argparse.ArgumentParser(description="KCRW Feed Updater")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gather_parser = subparsers.add_parser("gather", help="Gather show URLs")
    gather_parser.add_argument(
        "--gather_source", default="sitemap", choices=["sitemap", "feed"])

    update_parser = subparsers.add_parser("update", help="Update show data")
    update_parser.add_argument(
        "--delay", type=float, default=5.0, help="Delay between requests")
    update_parser.add_argument(
        "--shows", nargs="*", help="List of show URLs to update")

    save_parser = subparsers.add_parser("save", help="Save the state to disk")

    args = parser.parse_args()

    show_index = show_gatherer.ShowIndex(CONFIG.get(
        "source_url"), extra_sitemaps=CONFIG.get("extra_sitemaps"))
    if args.command == "gather":
        gather_source = args.gather_source or CONFIG.get("gather_source")
        urls = show_index.gather_shows(
            source=gather_source)
        print("Gathered URLs:")
        pprint.pprint(urls)
    elif args.command == "update":
        urls = show_index.gather_shows(source="sitemap")
        # If --shows is specified, filter the URLs.
        if args.shows:
            urls = [url for url in urls if url in args.shows]
        pass
        # updated_shows = scrape_shows(urls, delay=args.delay, only=args.shows)
        # # Save the state or pass it to the next phase.
        # # For now, print a summary.
        # for s in updated_shows:
        #     print(s.title, s.last_updated)
    elif args.command == "save":
        # Call your state persistence functions.
        pass


if __name__ == "__main__":
    main()
