#!/usr/bin/env python3
"""Publish devto-*.md files to Dev.to via API."""
import os, json, glob, re, requests

API_KEY = os.environ.get("DEVTO_API_KEY", "")
STATE_FILE = os.path.join(os.path.dirname(__file__), "devto_state.json")

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"published": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

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

def publish(title, body_markdown, description, tags, canonical_url):
    r = requests.post("https://dev.to/api/articles",
        headers={"api-key": API_KEY, "Content-Type": "application/json"},
        json={"article": {
            "title": title,
            "body_markdown": body_markdown,
            "description": description,
            "tags": tags,
            "canonical_url": canonical_url,
            "published": True
        }},
        timeout=30
    )
    r.raise_for_status()
    return r.json()

def main():
    if not API_KEY:
        print("ERROR: DEVTO_API_KEY not set")
        return

    state = load_state()
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    site_dir = os.path.abspath(os.path.join(scripts_dir, "..", ".."))
    files = sorted(glob.glob(os.path.join(site_dir, "devto-*.md")))

    for fpath in files:
        fname = os.path.basename(fpath)
        if fname in state["published"]:
            print(f"SKIP (already published): {fname}")
            continue

        with open(fpath, encoding="utf-8") as f:
            text = f.read()

        meta, body = strip_frontmatter(text)
        title = meta.get("title", fname)
        description = meta.get("description", "")
        tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
        canonical_url = meta.get("canonical_url", "")

        print(f"Publishing: {title}...")
        try:
            result = publish(title, body, description, tags, canonical_url)
            print(f"  URL: {result.get('url')}")
            state["published"].append(fname)
            save_state(state)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 422:
                print(f"  ALREADY PUBLISHED (422 - skipping): {fname}")
                state["published"].append(fname)
                save_state(state)
            else:
                print(f"  ERROR: {e}")
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    main()
