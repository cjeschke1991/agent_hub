from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from agent_hub.agents.music_recommender.spotify import TrackDetails


class PandoraError(RuntimeError):
    pass


def parse_pandora_playlist_id(value: str) -> str:
    value = value.strip()
    if "pandora.app.link/" in value:
        desktop_url = resolve_pandora_desktop_url(value)
        if desktop_url:
            value = desktop_url
    if "pandora.com/playlist/" in value:
        tail = value.split("pandora.com/playlist/", 1)[1]
        return tail.split("?", 1)[0].split("/", 1)[0]
    if value.startswith("PL:"):
        return value
    return value


def resolve_pandora_desktop_url(link: str) -> str | None:
    request = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return None
    match = re.search(r'property="og:url" content="([^"]+)"', page)
    if match:
        return html.unescape(match.group(1))
    return None


_PLAY_BUTTON_RE = re.compile(
    r'^Play (.+?) \1 (.+?) \d+:\d+(?:\s+explicit)?\s+more$'
)


def _tracks_from_play_button_names(text: str) -> list[tuple[str, str]]:
    tracks: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = re.match(r'\s+name: "(.+)"$', line)
        if not match:
            continue
        play_match = _PLAY_BUTTON_RE.match(match.group(1))
        if play_match:
            tracks.append((play_match.group(1), play_match.group(2)))
    return tracks


def parse_tracks_from_accessibility_snapshot(text: str) -> list[tuple[str, str]]:
    """Parse title/artist pairs from a Cursor browser_snapshot log."""
    lines = text.splitlines()
    skip_names = {
        "Now Playing",
        "My Collection",
        "Browse",
        "Pandora - Home",
        "Sign Up",
        "Log In",
        "About",
        "Jobs",
        "Advertising",
        "Businesses",
        "For Artists",
        "Investor",
        "Blog",
        "Gifts",
        "Privacy",
        "Terms",
        "Help",
        "Ad Preferences",
        "Your Privacy Choices",
        "More information about your privacy, opens in a new tab",
    }
    tracks: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "- role: button" and i + 1 < len(lines):
            match = re.match(r'\s+name: Play (.+)$', lines[i + 1])
            if match and "Playlist" not in match.group(1):
                j = i + 2
                link_names: list[str] = []
                while j < len(lines) and len(link_names) < 2:
                    if lines[j].strip() == "- role: link" and j + 1 < len(lines):
                        name_match = re.match(r"\s+name: (.+)$", lines[j + 1])
                        if name_match:
                            val = name_match.group(1).strip('"')
                            if (
                                val not in skip_names
                                and not val.startswith("http")
                                and "@" not in val
                            ):
                                link_names.append(val)
                    j += 1
                if len(link_names) >= 2:
                    tracks.append((link_names[0], link_names[1]))
        i += 1
    for title, artist in _tracks_from_play_button_names(text):
        tracks.append((title, artist))
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for title, artist in tracks:
        key = (title.lower(), artist.lower())
        if key not in seen:
            seen.add(key)
            unique.append((title, artist))
    return unique


def _parse_store_data_tracks(page: str) -> list[tuple[str, str]]:
    match = re.search(r"var storeData = (\{.*?\});\s*\n", page, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    track_rows = data.get("v7/playlists/getTracks", [{}])[0].get("tracks", [])
    annotations = data.get("v4/catalog/annotateObjects", [{}])[0]
    tracks: list[tuple[str, str]] = []
    for row in track_rows:
        track_id = row.get("trackPandoraId")
        info = annotations.get(track_id, {}) if track_id else {}
        title = info.get("name")
        artist = info.get("artistName")
        if title and artist:
            tracks.append((str(title), str(artist)))
    return tracks


def fetch_pandora_playlist_tracks(playlist: str) -> list[tuple[str, str]]:
    playlist_id = parse_pandora_playlist_id(playlist)
    url = f"https://www.pandora.com/playlist/{urllib.parse.quote(playlist_id, safe=':')}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise PandoraError(f"Could not fetch Pandora playlist page: {exc.reason}") from exc

    tracks = _parse_store_data_tracks(page)
    if tracks:
        return tracks
    raise PandoraError(
        "Could not read Pandora playlist tracks from the public page. "
        "Pandora requires a logged-in browser session for full playlist export."
    )


def pandora_track_id(title: str, artist: str) -> str:
    digest = hashlib.sha1(f"{title.lower()}|{artist.lower()}".encode()).hexdigest()[:16]
    return f"pandora-{digest}"


def track_details_from_pandora(title: str, artist: str) -> TrackDetails:
    return TrackDetails(
        spotify_id=pandora_track_id(title, artist),
        title=title,
        artist=artist,
        artist_id="",
        album="",
        year=None,
        genres=[],
        energy=None,
        valence=None,
        danceability=None,
        tempo=None,
        popularity=0,
        duration_ms=None,
        image_url=None,
        preview_url=None,
    )
