"""New-post detection for the followed subreddits through Reddit's official API (public feeds no longer work)."""

import time

import aiohttp

SUBREDDITS = ["Jibo", "JiboRevival"]
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
NEW_URL = "https://oauth.reddit.com/r/{}/new?limit=25&raw_json=1".format("+".join(SUBREDDITS))
USER_AGENT = "linux:jibodisc:1.0 (Jibo Revival Group Discord bot)"

_token = {"value": None, "expires": 0.0}


async def token(http, client_id: str, secret: str) -> str:
    """An app-only OAuth token, reused until shortly before it expires."""
    if _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    async with http.post(TOKEN_URL, data={"grant_type": "client_credentials"},
                         auth=aiohttp.BasicAuth(client_id, secret), headers={"User-Agent": USER_AGENT}) as response:
        response.raise_for_status()
        body = await response.json()
    _token.update(value=body["access_token"], expires=time.time() + float(body.get("expires_in", 3600)))
    return _token["value"]


def parse_listing(listing: dict) -> list[dict[str, str]]:
    """A /new listing -> posts oldest first as {id, title, author, subreddit, url, image}."""
    posts = []
    for child in listing.get("data", {}).get("children", []):
        d = child.get("data", {})
        if not d.get("id"):
            continue
        preview = (d.get("preview") or {}).get("images") or [{}]
        image = (preview[0].get("source") or {}).get("url", "")
        posts.append({
            "id": d["id"],
            "title": (d.get("title") or "").strip(),
            "author": d.get("author") or "[deleted]",
            "subreddit": d.get("subreddit") or "",
            "url": "https://www.reddit.com" + (d.get("permalink") or "/"),
            "image": image,
        })
    return list(reversed(posts))
