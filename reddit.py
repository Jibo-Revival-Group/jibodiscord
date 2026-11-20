"""New-post detection for the followed subreddits. Reddit blocks plain HTTP clients (no feeds, no JSON, and its
API needs approval), so a headless Chromium loads each subreddit's /new page and reads the posts it shows."""

import asyncio
import re
from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

SUBREDDITS = ["Jibo", "JiboRevival"]
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
# Each <shreddit-post> carries the post's data as attributes.
# The text post's body and the media preview (video poster, image) are inside it.
_READ = """els => els.map(e => ({
    id: e.id, title: e.getAttribute('post-title'), author: e.getAttribute('author'),
    permalink: e.getAttribute('permalink'), type: e.getAttribute('post-type'), href: e.getAttribute('content-href'),
    created: e.getAttribute('created-timestamp'),
    body: (e.querySelector('[slot="text-body"]') || {}).innerText || '',
    media: ([...e.querySelectorAll('img')].map(i => i.src).find(s => /(preview|i)\\.redd\\.it\\//.test(s)) || '')}))"""
SUMMARY_LENGTH = 300
# /new only lists a few posts at first, so an old post can show up as "unseen" later; only newer ones get posted.
MAX_AGE = timedelta(days=1)
_YOUTUBE = re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})")


def to_posts(subreddit: str, raw: list[dict]) -> list[dict[str, str]]:
    """Scraped <shreddit-post> data -> posts oldest first as {id, title, author, subreddit, url, summary, image, video}."""
    posts = []
    for r in raw:
        if not (r.get("id") or "").startswith("t3_") or not r.get("permalink"):
            continue  # ads and placeholders
        posts.append({
            "id": r["id"][3:],
            "title": (r.get("title") or "").strip(),
            "author": r.get("author") or "[deleted]",
            "subreddit": subreddit,
            "url": "https://www.reddit.com" + r["permalink"],
            "summary": summary(r.get("body") or ""),
            "created": r.get("created") or "",
            "image": image(r),
            "video": (r.get("href") or "") if (r.get("href") or "").startswith("https://v.redd.it/") else "",
        })
    return list(reversed(posts))


def is_recent(post: dict, now: datetime | None = None) -> bool:
    """Posted within MAX_AGE. A missing or unreadable timestamp counts as old, so it is never announced."""
    try:
        created = datetime.strptime(post["created"], "%Y-%m-%dT%H:%M:%S.%f%z")
    except (KeyError, ValueError):
        return False
    return (now or datetime.now(timezone.utc)) - created <= MAX_AGE


def summary(body: str) -> str:
    """The post's text squeezed to one short paragraph for the embed."""
    text = " ".join(body.split())
    return text if len(text) <= SUMMARY_LENGTH else text[:SUMMARY_LENGTH].rsplit(" ", 1)[0] + "…"


def image(r: dict) -> str:
    """A picture for the post: Reddit's media preview, the image itself, or a linked YouTube video's thumbnail."""
    href = r.get("href") or ""
    if href.startswith("https://v.redd.it/"):
        return ""  # Reddit's video poster is the (usually black) first frame; the bot grabs a later one instead
    if r.get("media"):
        return r["media"]
    if r.get("type") == "image":
        return href
    m = _YOUTUBE.search(href)
    return f"https://i.ytimg.com/vi/{m.group(1)}/hqdefault.jpg" if m else ""


async def video_frame(video: str) -> bytes | None:
    """A JPEG of a Reddit video one second in (best quality via its HLS playlist), or None if ffmpeg fails."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-v", "error", "-ss", "1", "-i", video.rstrip("/") + "/HLSPlaylist.m3u8", "-frames:v", "1",
        "-q:v", "3", "-f", "image2", "-c:v", "mjpeg", "pipe:1",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), 60)
    except asyncio.TimeoutError:
        proc.kill()
        return None
    return out if proc.returncode == 0 and out else None


async def fetch_new() -> list[dict[str, str]]:
    """The newest posts of every followed subreddit. Raises if a page shows no posts (blocked or changed layout)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page(user_agent=USER_AGENT, locale="en-US")
            posts = []
            for sub in SUBREDDITS:
                await page.goto(f"https://www.reddit.com/r/{sub}/new/", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_selector("shreddit-post", timeout=30000)
                posts += to_posts(sub, await page.eval_on_selector_all("shreddit-post", _READ))
            return posts
        finally:
            await browser.close()
