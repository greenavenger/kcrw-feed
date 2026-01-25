# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

KCRW Feed Generator scrapes KCRW.com music show data and generates RSS/Atom feeds for podcast players. It does not host audio files - only points to KCRW's servers.

## Commands

```bash
# Install dependencies
poetry install

# Run the CLI
poetry run kcrw-feed <command>

# Run all tests
poetry run pytest

# Run a single test file
poetry run pytest tests/test_models.py

# Run a specific test
poetry run pytest tests/test_models.py::test_function_name -v

# Run tests with coverage
poetry run pytest --cov=kcrw_feed

# Lint
poetry run pylint kcrw_feed
```

### CLI Usage

```bash
# List local resources/shows/episodes/hosts
poetry run kcrw-feed list [resources|shows|episodes|hosts]

# Show diff between local state and live site
poetry run kcrw-feed diff

# Update local state from kcrw.com
poetry run kcrw-feed update

# Common flags
-v, --verbose       # Detailed output
-n, --dry-run       # Preview changes without applying
-m, --match REGEX   # Filter by URL pattern (e.g., "henry-rollins", "dan-wilcox")
-s, --since DATE    # Filter by date (ISO 8601)
-u, --until DATE    # Filter by date (ISO 8601)
-o, --storage_root  # Data directory for state/feeds
-r, --source_root   # Source URL or local path
```

## Architecture

### Data Flow

1. **ResourceProcessor** (`processing/resources.py`) - Parses robots.txt → sitemaps → extracts music show URLs as `Resource` objects
2. **StationProcessor** (`processing/station.py`) - Enriches Resources by fetching HTML/JSON, populating `Show` and `Episode` models
3. **StationCatalog** (`station_catalog.py`) - Central repository holding all entities; `LocalStationCatalog` for persisted state, `LiveStationCatalog` for live kcrw.com data
4. **CatalogUpdater** (`updater.py`) - Compares local vs live catalogs, merges changes, triggers persistence
5. **Persisters** (`persistence/`) - Write state to JSON and generate RSS feeds

### Key Classes

- **Models** (`models.py`): `Resource`, `Show`, `Episode`, `Host`, `Catalog`, `FilterOptions`
- **Sources** (`source_manager.py`): `HttpsSource` (live HTTP with caching), `CacheSource` (local files)
- **Config** (`config.py`): YAML-based configuration with defaults in `kcrw_feed/data/default_config.yaml`

### State Management

- State persisted to JSON file (default: `kcrw_feed.json`)
- HTTP responses cached via `requests_cache` (SQLite backend)
- Feeds written to `feeds/` directory

## Testing

Test data in `tests/data/` simulates KCRW site structure. For integration tests:

```bash
# Start local nginx to serve test data
cd tests/data && docker compose up -d

# Run against local test server
poetry run kcrw-feed --storage_root ./tests/data list
```

## Configuration

Default config at `kcrw_feed/data/default_config.yaml`. Override with `-c path/to/config.yaml`.
