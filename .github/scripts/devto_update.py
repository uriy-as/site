#!/usr/bin/env python3
"""Update an already published Dev.to article from its devto-*.md source.

Dev.to has no update endpoint for the bulk publish flow, so POST created the
article and left it frozen. This does PUT /api/articles/{id}.

Usage: python devto_update.py <article_id> <source-file.md>
"""
import json
import os
import re
import sys

import requests

API_KEY = os.environ.get("DEVTO_API_KEY", "")
BASE = "https://dev.to/api/articles"
MAX_TAGS = 4


def strip_frontmatter(text):
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip().strip('"')
        text = text[m.end():]
    return meta, text.strip()


def clean_tags(raw):
    tags = []
    for t in raw.split(','):
        t = t.strip().lower().replace(' ', '-')
        if t and t not in tags:
            tags.append(t)
    return tags[:MAX_TAGS]


def main():
    if not API_KEY:
        print("ERROR: DEVTO_API_KEY not set")
        return 1
    if len(sys.argv) != 3:
        print("Usage: devto_update.py <article_id> <source-file.md>")
        return 2

    article_id = sys.argv[1].strip()
    path = sys.argv[2].strip()

    with open(path, encoding="utf-8") as f:
        meta, body = strip_frontmatter(f.read())

    payload = {"article": {
        "title": meta.get("title", ""),
        "body_markdown": body,
        "description": meta.get("description", ""),
        "canonical_url": meta.get("canonical_url", ""),
    }}
    tags = clean_tags(meta.get("tags", ""))
    if tags:
        payload["article"]["tags"] = tags

    print(f"Updating article {article_id}")
    print(f"  source : {path}")
    print(f"  title  : {payload['article']['title']}")
    print(f"  tags   : {tags}")
    print(f"  body   : {len(body)} chars")

    r = requests.put(f"{BASE}/{article_id}",
                     headers={"api-key": API_KEY, "Content-Type": "application/json"},
                     json=payload, timeout=30)

    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text[:300]}")
        return 1

    d = r.json()
    print(f"  OK  id={d.get('id')} url={d.get('url')}")
    print(f"  title now: {d.get('title')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
