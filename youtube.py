"""New-video detection from YouTube's public channel feeds (no API key needed)."""

import re
import xml.etree.ElementTree as ET

# The channels JiboDisc follows: handle -> channel ID (the feed address needs the ID, not the handle).
CHANNELS = {
    "@miraenda": "UCr4hZX6ZkZ010EqsII85-IA",
    "@MsRobot": "UC-OxiwXEYJ-zYYNuy54aj8Q",
    "@jibomorris": "UCyXAi6UIbXnRfhhBjCrYGgg",
    "@zdiw": "UCgyDua_z2k4rF4WT_XBJjbw",
    "@KevinKorDevs": "UChX-r-a32TaTMvbOBG_SE4w",
    "@JakeDubin": "UCCb_FTJ_aAXHpO5w1GDenYw",
    "@nttdisruption8913": "UC_FJ3fcLPTLbT9Fg5KnW1RA",
}
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
WATCH_URL = "https://www.youtube.com/watch?v={}"
_NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def parse_feed(xml_text: str) -> tuple[str, list[dict[str, str]]]:
    """A channel feed -> (the channel's display name, its videos oldest first as {"id", "title"})."""
    feed = ET.fromstring(xml_text)
    videos = [
        {"id": e.findtext("yt:videoId", namespaces=_NS), "title": (e.findtext("a:title", namespaces=_NS) or "").strip()}
        for e in feed.findall("a:entry", _NS)
    ]
    return (feed.findtext("a:title", namespaces=_NS) or "").strip(), [v for v in reversed(videos) if v["id"]]


def new_videos(seen: dict[str, list[str]], channel: str, ids: list[str]) -> list[str]:
    """IDs not seen before for this channel, and remember them. A channel's first check posts nothing,
    so adding a channel (or losing the state file) never floods the server with old videos."""
    first = channel not in seen
    known = set(seen.setdefault(channel, []))
    fresh = [i for i in ids if i not in known]
    seen[channel] += fresh
    return [] if first else fresh


def stream_state(watch_html: str) -> str | None:
    """From a watch page: "upcoming" for a scheduled live stream that hasn't started (the feed lists it as soon as it
    is announced), "live" while it runs, None for a normal video or a finished stream."""
    if '"isLiveNow":true' in watch_html:
        return "live"
    if '"status":"LIVE_STREAM_OFFLINE"' in watch_html:
        return "upcoming"
    return None


def scheduled_start(watch_html: str) -> int | None:
    """An upcoming stream's start time (Unix seconds) from its watch page, or None."""
    found = re.search(r'"scheduledStartTime":"(\d+)"', watch_html)
    return int(found.group(1)) if found else None
