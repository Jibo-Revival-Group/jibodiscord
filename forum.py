"""New discussions and replies on the Jibo Revival forum (Flarum), read from its public JSON API as a guest, so only
posts everyone can see are announced."""

import html
import re
from datetime import datetime, timedelta, timezone

FORUM_URL = "https://forum.jiborevival.com"
API_URL = FORUM_URL + "/api/posts?sort=-createdAt&page[limit]=20&filter[type]=comment&include=user,discussion"
# Cloudflare refuses Python's default User-Agent.
HEADERS = {"User-Agent": "JiboDisc (+https://github.com/Jibo-Revival-Group/jibodiscord)", "Accept": "application/vnd.api+json"}
SUMMARY_LENGTH = 300
# Only the newest 20 posts are read, so a post edited or approved later could look new; older ones are never posted.
MAX_AGE = timedelta(days=1)


def to_posts(doc: dict) -> list[dict]:
    """API document -> posts oldest first as {id, number, title, author, avatar, url, summary, created}."""
    included = {(i["type"], i["id"]): i.get("attributes", {}) for i in doc.get("included", [])}
    posts = []
    for p in doc.get("data", []):
        a, rel = p.get("attributes", {}), p.get("relationships", {})
        if a.get("contentType") != "comment":
            continue
        discussion_id = ((rel.get("discussion") or {}).get("data") or {}).get("id")
        if not discussion_id:
            continue
        user = included.get(("users", ((rel.get("user") or {}).get("data") or {}).get("id")), {})
        posts.append({
            "id": p["id"],
            "number": a.get("number") or 0,
            "title": included.get(("discussions", discussion_id), {}).get("title") or "",
            "author": user.get("displayName") or user.get("username") or "[deleted]",
            "avatar": user.get("avatarUrl") or "",
            "url": f"{FORUM_URL}/d/{discussion_id}/{a.get('number') or 1}",
            "summary": summary(a.get("contentHtml") or ""),
            **media(a.get("contentHtml") or ""),
            "created": a.get("createdAt") or "",
        })
    return list(reversed(posts))


_UPLOADED_IMAGE = re.compile(r'<a href="([^"]+)"[^>]*class="FoFUpload--Upl-Image-Preview-Link"')
_IMAGE = re.compile(r'<img(?![^>]*class="emoji")[^>]*\ssrc="(https?://[^"]+)"')
_UPLOADED_FILE = re.compile(r'data-fof-upload-download-uuid="([\w-]+)"')


def media(content_html: str) -> dict[str, str]:
    """The post's first picture (an upload at full size, else any image) and its first uploaded file, which on this
    forum can only be a video (uploads are limited to images and videos). Links are made absolute."""
    content_html = html.unescape(content_html)
    image = _UPLOADED_IMAGE.search(content_html) or _IMAGE.search(content_html)
    video = _UPLOADED_FILE.search(content_html)
    return {"image": image.group(1) if image else "", "video": f"{FORUM_URL}/api/fof/download/{video.group(1)}" if video else ""}


def summary(content_html: str) -> str:
    """The post's text without HTML, squeezed to one short paragraph for the embed."""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", content_html)).split())
    return text if len(text) <= SUMMARY_LENGTH else text[:SUMMARY_LENGTH].rsplit(" ", 1)[0] + "…"


def is_recent(post: dict, now: datetime | None = None) -> bool:
    """Posted within MAX_AGE. A missing or unreadable timestamp counts as old, so it is never announced."""
    try:
        created = datetime.fromisoformat(post["created"])
    except (KeyError, ValueError):
        return False
    return (now or datetime.now(timezone.utc)) - created <= MAX_AGE
