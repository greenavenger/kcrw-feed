# Plan: Fix KCRW Feed Scraper After Website Redesign

## Problem Summary

KCRW.com underwent a major redesign. Key breaking changes:

| Component | Old Site | New Site |
|-----------|----------|----------|
| Show URLs | `/music/shows/{show}` | `/shows/{show}` |
| Episode URLs | `/music/shows/{show}/{episode}` | `/shows/{show}/stories/{episode}` |
| Sitemap | `sitemap.xml.gz` | `sitemap-index.xml` → `/shows/sitemap.xml` |
| Show data | Schema.org microdata (`RadioSeries`) | Next.js RSC payload |
| Episode data | `player.json` endpoint | **404** - data embedded in HTML |

## Implementation Strategy

**Approach**: Outside-in TDD - start with highest-level acceptance tests, capture test data first to minimize live site traffic, then implement to make tests pass. Plan for variability in site data.

---

## Phase 0: Capture Test Data (Do First)

**Goal**: Capture HTML/sitemap data from live site once, use locally for all development.

### What to Capture
- `robots.txt`
- `sitemap-index.xml`
- `shows/sitemap.xml` (filtered for 2 music shows)
- `stories/sitemap/0.xml` (partial, for our test shows)
- Show pages: **Henry Rollins** and **Morning Becomes Eclectic**
- Episode pages: ~5 episodes per show

### File Structure
```
tests/data/
  robots.txt
  sitemap-index.xml
  shows/
    sitemap.xml
    henry-rollins/
      index.html
      stories/
        kcrw-broadcast-877/index.html
        kcrw-broadcast-876/index.html
        ... (3-5 more)
    morning-becomes-eclectic/
      index.html
      stories/
        morning-becomes-eclectic-playlist-january-24-2026/index.html
        ... (3-5 more)
  stories/
    sitemap/
      0.xml
```

### Clean Up
- Remove old `tests/data/music/` structure
- Remove old `tests/data/sitemap-shows/` structure
- Update `tests/data/config.yaml` if needed

---

## Phase 1: High-Level Acceptance Tests (TDD Outside-In)

**Goal**: Define what "working" looks like before any implementation.

### Test 1: End-to-End Update (Highest Level)
```python
# tests/test_e2e.py

def test_update_discovers_shows_and_episodes():
    """Update command discovers shows and creates episodes."""
    result = subprocess.run([
        "poetry", "run", "kcrw-feed",
        "--storage_root", str(tmp_path),
        "--source_root", str(test_data_path),
        "update"
    ], capture_output=True, text=True)

    assert result.returncode == 0
    assert "shows" in result.stdout.lower() or "Updates applied" in result.stdout

    # Verify state file was created with shows
    state_file = tmp_path / "kcrw_catalog.json"
    assert state_file.exists()

    state = json.loads(state_file.read_text())
    assert len(state.get("shows", {})) >= 2
```

### Test 2: List Shows Works
```python
def test_list_shows_returns_discovered_shows():
    """List command returns shows from local state."""
    result = subprocess.run([
        "poetry", "run", "kcrw-feed",
        "--storage_root", str(test_data_path),
        "list", "shows"
    ], capture_output=True, text=True)

    assert "henry-rollins" in result.stdout
    assert "morning-becomes-eclectic" in result.stdout
```

### Test 3: RSS Feeds Generated
```python
def test_update_generates_rss_feeds():
    """Update creates valid RSS feed files."""
    # ... run update ...

    feed_file = tmp_path / "feeds" / "henry-rollins.xml"
    assert feed_file.exists()

    # Parse and validate basic RSS structure
    tree = ET.parse(feed_file)
    assert tree.find(".//channel/title") is not None
    assert len(tree.findall(".//item")) >= 1
```

---

## Phase 2: Integration Tests (Show/Episode Processing)

**Goal**: Test the processing layer with captured data.

### Test: Process Show from HTML
```python
# tests/processing/test_station.py

def test_process_show_extracts_required_fields():
    """Processing a show page produces a Show with required fields."""
    html = (test_data_path / "shows/henry-rollins/index.html").read_bytes()
    # ... setup processor with mock source returning this HTML ...

    show = processor._process_show(resource)

    assert show is not None
    assert show.title is not None
    assert show.uuid is not None
    assert isinstance(show.hosts, list)
```

### Test: Process Episode from HTML
```python
def test_process_episode_extracts_required_fields():
    """Processing an episode page produces an Episode with required fields."""
    html = (test_data_path / "shows/henry-rollins/stories/kcrw-broadcast-877/index.html").read_bytes()
    # ...

    episode = processor._process_episode(resource)

    assert episode is not None
    assert episode.title is not None
    assert episode.media_url is not None
    assert episode.airdate is not None
```

### Handling Variability
- Tests assert presence of required fields, not exact values
- Allow optional fields (description, image) to be None
- Log warnings for missing optional data, don't fail

---

## Phase 3: Parser Implementation

**Goal**: Build the page parser to make integration tests pass.

### Test: Parser Extracts Key Fields
```python
# tests/processing/test_page_parser.py

def test_extract_show_title():
    """Parser extracts show title from page."""
    html = (test_data_path / "shows/henry-rollins/index.html").read_text()
    parser = PageDataParser(html)

    data = parser.get_show_data()
    assert data.get("title") is not None

def test_handles_missing_fields_gracefully():
    """Parser returns None for missing optional fields, not errors."""
    html = "<html>minimal page</html>"
    parser = PageDataParser(html)

    data = parser.get_show_data()
    assert data == {} or data.get("title") is None  # Graceful failure
```

### Implementation
Create `kcrw_feed/processing/page_parser.py`:
- Extract structured data from HTML pages
- Return None for missing optional fields
- Log warnings for unexpected structures

---

## Phase 4: URL Patterns & Sitemap Discovery

**Goal**: Connect discovery to processing.

### Tests
```python
def test_sitemap_discovers_show_urls():
    """Sitemap parsing finds show URLs."""
    # ...
    resources = processor.fetch_resources()
    assert any("/shows/henry-rollins" in r.url for r in resources.values())

def test_show_url_recognized():
    """Show URLs are correctly identified."""
    resource = Resource(url="https://www.kcrw.com/shows/henry-rollins", ...)
    assert processor.is_show_resource(resource)

def test_episode_url_recognized():
    """Episode URLs are correctly identified."""
    resource = Resource(url="https://www.kcrw.com/shows/henry-rollins/stories/kcrw-broadcast-877", ...)
    assert processor.is_episode_resource(resource)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| [tests/data/](tests/data/) | Replace test data structure |
| [processing/station.py](kcrw_feed/processing/station.py) | URL regexes, use page parser |
| [processing/resources.py](kcrw_feed/processing/resources.py) | MUSIC_FILTER_RE pattern |
| [processing/page_parser.py](kcrw_feed/processing/page_parser.py) | **NEW** - HTML page data extraction |
| [tests/test_e2e.py](tests/test_e2e.py) | E2E acceptance tests |
| [tests/processing/test_station.py](tests/processing/test_station.py) | Show/episode processing tests |
| [tests/processing/test_page_parser.py](tests/processing/test_page_parser.py) | **NEW** - Parser unit tests |

---

## Verification

### During Development (Local Only)
```bash
# Run tests against captured data
poetry run pytest

# Manual verification with local data
poetry run kcrw-feed --storage_root ./tests/data list shows
```

### After Implementation Complete
```bash
# Verify against live site (once, at the end)
poetry run kcrw-feed -m "henry-rollins" -n update
```

---

## Handling Variability

The KCRW site has ongoing human changes. Our approach:

1. **Required vs Optional fields**: Only fail on truly required fields (title, uuid, media_url, airdate). Treat others as optional.

2. **Graceful degradation**: Log warnings for missing optional data, don't error.

3. **Flexible parsing**: Don't assume exact payload structure. Search for known field names.

4. **Test assertions**: Assert presence, not exact values. E.g., `assert show.title is not None` not `assert show.title == "Henry Rollins"`
