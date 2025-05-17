"""Main entry point for the KCRW Feed Generator."""

import argparse
from dataclasses import asdict
import logging.config
import os.path
import pprint
import time
import sys

from kcrw_feed import config
from kcrw_feed.persistence.logger import LOGGING_LEVEL_MAP
from kcrw_feed import station_catalog
from kcrw_feed import updater
from kcrw_feed.source_manager import BaseSource, HttpsSource, CacheSource
from kcrw_feed.persistence.feeds import FeedPersister


def main():
    t0 = time.time()
    parser = argparse.ArgumentParser(description="KCRW Feed Generator")
    # Global options
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Increase verbosity of returned entities")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help='Do not perform any destructive actions. (ex. "update -n" provides a diff)')
    parser.add_argument("-m", "--match", type=str,
                        help='A regex or substring to filter resource URLs (ex. "valida", "shows/valida", "valida.*-2023")')
    parser.add_argument("-s", "--since", type=str,
                        help='Reprocess since provided ISO 8601 timestamp ("YYYY-MM-DDTHH:MM:SS")')
    parser.add_argument("-u", "--until", type=str,
                        help='Reprocess until provided ISO 8601 timestamp ("YYYY-MM-DDTHH:MM:SS")')
    parser.add_argument("--loglevel", type=str,
                        choices=["trace", "debug", "info",
                                 "warning", "error", "critical"],
                        help="Override log level for stdout debug logging")
    parser.add_argument("-o", "--storage_root", type=str,
                        help="Specify the root data directory for state and feed files")
    parser.add_argument("-r", "--source_root", type=str,
                        help='Specify the source root (ex. "https://www.kcrw.com/", "./tests/data/")')
    parser.add_argument("-c", "--config", type=str,
                        help="Path to a custom config file")
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True,
                                       help="Sub-commands: list, diff, update")

    list_parser = subparsers.add_parser(
        "list", help="List resources, shows, episodes, or hosts in feeds (local state)")
    list_parser.add_argument(
        "mode",
        nargs="?",
        choices=["resources", "shows", "episodes", "hosts"],  # "debug"],
        default="resources",
        help="Specify type of entity to list. Default lists resources."
    )

    diff_parser = subparsers.add_parser(
        "diff", help="Show differences between local state and live site (kcrw.com) resources")
    diff_parser.add_argument(
        "mode", nargs="?", choices=["resources", "shows", "episodes", "hosts"],
        default=None, help="Specify type of entity to diff. Default lists all."
    )

    subparsers.add_parser("update",
                          help="Update local show data from live site (kcrw.com)")

    args = parser.parse_args()

    # Load configuration
    CONFIG = config.read_config(args.config)
    logger = logging.getLogger("kcrw_feed")

    # Determine storage root
    storage_root = args.storage_root or CONFIG["storage_root"]
    # Use an absolute path for the storage_root so it's unambiguous.
    storage_root = os.path.abspath(storage_root)

    # Check if state file exists for commands that require it
    state_file = CONFIG["state_file"]
    state_file_path = os.path.join(storage_root, state_file)
    if args.command in ["list", "diff"] and not os.path.exists(state_file_path):
        print(
            f"Error: State file not found at {state_file_path}", file=sys.stderr)
        print("Please run this command from a directory containing the state file, or specify the correct path with --storage_root", file=sys.stderr)
        return 1

    logger.info("Storage root: %s", storage_root)

    # Update cache filename to be relative to storage_root
    if "http_cache" in CONFIG:
        CONFIG["http_cache"]["directory"] = os.path.join(
            storage_root, CONFIG["http_cache"]["directory"])

    # Adjust logging configuration to use storage_root
    if "file" in CONFIG["logging"]["handlers"]:
        log_file = CONFIG["logging"]["handlers"]["file"]["filename"]
        # Make log file path relative to storage_root
        CONFIG["logging"]["handlers"]["file"]["filename"] = os.path.join(
            storage_root, log_file)
        # Ensure log directory exists
        os.makedirs(os.path.dirname(
            CONFIG["logging"]["handlers"]["file"]["filename"]), exist_ok=True)

    # If --loglevel is provided, update the stdout handler level. Leave the
    # file handler log level unchanged.
    if args.loglevel:
        stdout_override = LOGGING_LEVEL_MAP[args.loglevel.lower()]
        # Override stdout handler's level.
        CONFIG["logging"]["handlers"]["stdout"]["level"] = args.loglevel.upper()
        # The file file handler remains unchanged.
        file_level = LOGGING_LEVEL_MAP[CONFIG["logging"]
                                       ["handlers"]["file"]["level"].lower()]
        # The root logger level must be at the lowest (most detailed) of the two.
        new_root_numeric = min(stdout_override, file_level)
        new_root_str = logging.getLevelName(new_root_numeric)
        CONFIG["logging"]["loggers"]["root"]["level"] = new_root_str

    # Configure logging using the YAML-derived configuration.
    logging.config.dictConfig(CONFIG["logging"])
    logger.debug("CONFIG: %s", pprint.pformat(CONFIG))
    logger.debug("Log handler levels: %s", [(name, handler["level"])
                 for name, handler in CONFIG["logging"]["handlers"].items()])

    logger.info("Command: %s", args.command, extra={"parsers": vars(args)})

    filter_opts = config.get_filter_options(args)
    logger.debug("filter_opts: %s", pprint.pformat(filter_opts))

    live_source: BaseSource
    source_root = args.source_root or CONFIG["source_root"]
    if source_root.startswith("http"):
        live_source = HttpsSource(source_root, CONFIG)
        logger.debug("URLs in cache: %s", pprint.pformat(
            live_source._session.cache.urls()))
    else:
        # Use an absolute path for the source_root so it's unambiguous.
        source_root = os.path.abspath(source_root)
        live_source = CacheSource(source_root, CONFIG)
    logger.info("Source root: %s", source_root)

    storage_root = args.storage_root or CONFIG["storage_root"]
    # Use an absolute path for the storage_root so it's unambiguous.
    storage_root = os.path.abspath(storage_root)
    logger.info("Storage root: %s", storage_root)
    state_file = CONFIG["state_file"]
    # Set us up to write out feeds
    feed_directory = CONFIG["feed_directory"]
    feed_persister = feed_persister = FeedPersister(
        storage_root=storage_root, feed_directory=feed_directory)

    # Create a CacheSource for local storage
    local_source = CacheSource(storage_root, CONFIG)

    # Pull in local state from the state file (always needed)
    local_catalog = station_catalog.LocalStationCatalog(
        catalog_source=local_source, state_file=state_file, feed_persister=feed_persister)

    # Pull in live state from kcrw.com only if necessary
    if args.command in ["diff", "update"]:
        live_catalog = station_catalog.LiveStationCatalog(
            catalog_source=live_source)
        catalog_updater = updater.CatalogUpdater(
            local_catalog, live_catalog, filter_opts)

    if args.command == "list":
        if args.mode == "resources":
            resources = local_catalog.list_resources(filter_opts=filter_opts)
            if args.verbose:
                pprint.pprint(list(resources))
            else:
                for resource in sorted([e.url for e in resources]):
                    print(resource)
            logger.info("%s resources", len(resources))
        elif args.mode == "shows":
            shows = local_catalog.list_shows(filter_opts=filter_opts)
            shows = sorted(shows, key=lambda s: s.url)
            if args.verbose:
                print(pprint.pformat(shows))
            else:
                for show in shows:
                    print(show.url)
            logger.info("%s shows", len(shows))
        elif args.mode == "episodes":
            episodes = local_catalog.list_episodes(filter_opts=filter_opts)
            # Sort by airdate for now
            episodes = sorted(episodes)  # , key=lambda s: s.url)
            if args.verbose:
                print(pprint.pformat(episodes))
            else:
                for episode in episodes:
                    print(episode.url)
            logger.info("%s episodes", len(episodes))
        elif args.mode == "hosts":
            hosts = local_catalog.list_hosts(filter_opts=filter_opts)
            hosts = sorted(hosts, key=lambda h: h.name)
            if args.verbose:
                print(pprint.pformat(hosts))
            else:
                for host in hosts:
                    print(host.name)
            logger.info("%s hosts", len(hosts))
    elif args.command == "diff":
        diff = catalog_updater.diff()
        if args.verbose:
            pprint.pprint(diff)
        counts = {k: len(v) for k, v in asdict(diff).items()}
        logger.info("Stats: %s", counts)
    elif args.command == "update":
        enriched_resources = catalog_updater.update()
        if args.verbose:
            pprint.pprint(enriched_resources)
        applied = 0
        if not filter_opts.dry_run:
            applied += len(enriched_resources)
        logger.info("Updates applied: %d", applied)
    else:
        logger.error("Unknown command")

    if source_root.startswith("http"):
        logger.debug("Cache URLs: %s", pprint.pformat(
            live_source._session.cache.urls()))
        # Report cache stats if we access a live source.
        if args.command == "diff" or args.command == "update":
            total_requests = live_source.cache_stats["hits"] + \
                live_source.cache_stats["misses"]
            live_source.cache_stats["hit_rate"] = live_source.cache_stats["hits"] / \
                total_requests if total_requests > 0 else 0.0
            logger.info("Cache stats: %s", live_source.cache_stats)

    logger.info("Elapsed time: %fs", time.time() - t0)


if __name__ == "__main__":
    main()
