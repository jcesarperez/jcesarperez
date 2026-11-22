"""Rewrite the "Writing & talks" block of README.md with my latest content:
Small Steps newsletter posts + the YouTube playlist of talks and podcasts.

Usage: python3 scripts/build_content.py
Only the standard library. Fails loudly if a feed or the README markers are missing.
"""
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
TALKS = json.loads((ROOT / "scripts/talks.json").read_text())

NEWSLETTER_FEED = "https://jcesarperez.substack.com/feed"
PLAYLIST_ID = "PLc9GIQ4dRLPCl38R9F-MCH3Jt_e5Dy-nl"
PLAYLIST_FEED = f"https://www.youtube.com/feeds/videos.xml?playlist_id={PLAYLIST_ID}"
LIMIT = 5

START, END = "<!-- CONTENT:START -->", "<!-- CONTENT:END -->"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-readme-builder"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def articles():
    for item in fetch(NEWSLETTER_FEED).iter("item"):
        yield {
            "kind": "article",
            "title": item.findtext("title").strip(),
            "url": item.findtext("link").strip(),
            "venue": "Small Steps",
            "date": parsedate_to_datetime(item.findtext("pubDate")),
        }


def talks():
    for e in fetch(PLAYLIST_FEED).findall("a:entry", NS):
        vid = e.findtext("yt:videoId", namespaces=NS)
        o = TALKS.get(vid, {})
        date = o.get("date")
        yield {
            "kind": "talk",
            "title": o.get("title") or e.findtext("a:title", namespaces=NS),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "venue": o.get("venue") or e.findtext("a:author/a:name", namespaces=NS),
            "date": datetime.fromisoformat(date).replace(tzinfo=timezone.utc) if date
            else datetime.fromisoformat(e.findtext("a:published", namespaces=NS)),
        }


def line(c):
    icon = "✍️" if c["kind"] == "article" else "🎙️"
    return f"- {icon} [{c['title']}]({c['url']}) · {c['venue']} · {c['date']:%b %Y}"


def main():
    a, t = list(articles()), list(talks())
    if not a or not t:
        raise SystemExit(f"Empty feed: {len(a)} articles, {len(t)} talks")
    latest = sorted(a + t, key=lambda c: c["date"], reverse=True)[:LIMIT]
    block = "\n".join([START, *map(line, latest), END])

    text = README.read_text()
    new, n = re.subn(re.escape(START) + ".*?" + re.escape(END), block, text, flags=re.S)
    if n != 1:
        raise SystemExit(f"Expected 1 content block in README, found {n}")
    if new != text:
        README.write_text(new)
        print("README updated")
    else:
        print("README unchanged")


if __name__ == "__main__":
    main()
