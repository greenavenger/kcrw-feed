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
from kcrw_feed import show_index
# from kcrw_feed import sitemap
# from kcrw_feed import utils
# from kcrw_feed import scraper
# from kcrw_feed import generate_feed

pprint.pprint(CONFIG)
print(CONFIG.get("extra_sitemaps"))


def main():

    parser = argparse.ArgumentParser(description="KCRW Feed Generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    gather_parser = subparsers.add_parser("gather", help="Gather show URLs")
    gather_parser.add_argument(
        "--source", default="sitemap", choices=["sitemap", "feed"])

    update_parser = subparsers.add_parser("update", help="Update show data")
    update_parser.add_argument(
        "--source", default="sitemap", choices=["sitemap", "feed"])
    update_parser.add_argument(
        "--delay", type=float, default=5.0, help="Delay between requests")
    update_parser.add_argument(
        "--shows", nargs="*", help="List of show URLs to update")

    save_parser = subparsers.add_parser("save", help="Save the state to disk")

    args = parser.parse_args()

    collection = show_index.ShowIndex(
        CONFIG["source_url"], extra_sitemaps=CONFIG["extra_sitemaps"])
    if args.command == "gather":
        urls = collection.process_sitemap(args.source or CONFIG["source"])
        print("Gathered URLs:")
        pprint.pprint(urls)  # [:10])
    elif args.command == "update":
        # urls = collection.process_sitemap(args.source or CONFIG["source"])
        # # If --shows is specified, filter the URLs.
        # urls = [url.replace("https://www.kcrw.com",
        #                     "https://www.example.com") for url in urls]
        # pprint.pprint(urls[:10])
        # if args.shows:
        #     urls = [url for url in urls if url in args.shows]
        # pprint.pprint(urls[:10])
        updated_shows = collection.update(
            source=(args.source or CONFIG["source"]), selected_urls=args.shows)
        # Save the state or pass it to the next phase.
        # For now, print a summary.
        for s in updated_shows:
            # print(s.title, s.last_updated)
            pprint.pprint(s)
    elif args.command == "save":
        # Call your state persistence functions.
        pass


if __name__ == "__main__":
    main()
