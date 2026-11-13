"""New-video detection from YouTube's public channel feeds (no API key needed)."""

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
_NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def parse_feed(xml_text: str) -> list[str]:
    """Video IDs in a channel feed, oldest first."""
    entries = ET.fromstring(xml_text).findall("a:entry", _NS)
    ids = [e.findtext("yt:videoId", namespaces=_NS) for e in entries]
    return [i for i in reversed(ids) if i]


def new_videos(seen: dict[str, list[str]], channel: str, ids: list[str]) -> list[str]:
    """IDs not seen before for this channel, and remember them. A channel's first check posts nothing,
    so adding a channel (or losing the state file) never floods the server with old videos."""
    first = channel not in seen
    known = set(seen.setdefault(channel, []))
    fresh = [i for i in ids if i not in known]
    seen[channel] += fresh
    return [] if first else fresh
