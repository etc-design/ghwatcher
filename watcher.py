#!/usr/bin/env python3
"""
GAFSHUB Keyword Watcher
------------------------
Checks gafshub.com's search API for new posts matching your keywords,
and emails you a summary when something new shows up.

Designed to be run repeatedly on a schedule (e.g. every 2-5 minutes via
Windows Task Scheduler or cron). Each run is independent and fast - it
remembers what it already told you about in state.json, so you'll never
get duplicate alerts for the same post.

Usage:
    python watcher.py

Requires:
    pip install cloudscraper
"""

import json
import os
import smtplib
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from email.mime.text import MIMEText

import cloudscraper

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
STATE_PATH = os.path.join(SCRIPT_DIR, "state.json")
LOG_PATH = os.path.join(SCRIPT_DIR, "watcher.log")

MAX_SEEN_IDS_KEPT = 5000  # trim state file so it doesn't grow forever
REQUEST_TIMEOUT = 15
USER_AGENT = "gafshub-keyword-watcher/1.0 (personal use)"


_scraper = None


def get_scraper():
    """Returns a shared cloudscraper session (created once, reused across calls)."""
    global _scraper
    if _scraper is None:
        _scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
    return _scraper


def log(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        log(f"ERROR: config.json not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    keywords = config.get("keywords", [])
    if not keywords:
        log("ERROR: No keywords configured in config.json")
        sys.exit(1)

    placeholder_keywords = {"example keyword 1", "example keyword 2", "example keyword 3"}
    if set(keywords) <= placeholder_keywords:
        log("WARNING: config.json still has placeholder keywords. Edit config.json "
            "and replace them with what you actually want to track.")

    if config.get("auth_cookie", "paste-your-full-cookie-header-here") == "paste-your-full-cookie-header-here":
        log("WARNING: config.json still has a placeholder auth_cookie. If GAFSHUB "
            "requires login to see deals, requests will fail or return empty results "
            "until you paste in your real cookie header.")

    email_cfg = config.get("email", {})
    if email_cfg.get("smtp_app_password") == "your-16-char-app-password":
        log("WARNING: config.json still has placeholder email credentials. "
            "The script will run but email sending will fail until you fill these in.")

    return config


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            log("WARNING: state.json was unreadable, starting fresh.")
    return {"seen_post_ids": []}


def save_state(state: dict) -> None:
    # Trim to the most recent MAX_SEEN_IDS_KEPT ids to keep the file small.
    seen = state.get("seen_post_ids", [])
    if len(seen) > MAX_SEEN_IDS_KEPT:
        state["seen_post_ids"] = seen[-MAX_SEEN_IDS_KEPT:]
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def sanitize_keyword_for_search(keyword: str) -> str:
    """
    Some characters (notably '/') get URL-encoded in a way that certain
    server-side security layers (e.g. Cloudflare WAF) flag as suspicious,
    causing an outright 403 rather than a normal search response. Since
    Discourse search tokenizes on non-letters anyway, swapping these for
    spaces preserves the intent of the search without tripping that.
    """
    for char in ["/", "\\"]:
        keyword = keyword.replace(char, " ")
    return " ".join(keyword.split())  # collapse repeated whitespace


def search_keyword(base_url: str, keyword: str, auth_cookie: str = "") -> list:
    """
    Query Discourse's search API for a keyword, ordered by newest first.
    Returns a list of match dicts: {post_id, topic_id, title, excerpt, url, created_at}
    """
    safe_keyword = sanitize_keyword_for_search(keyword)
    query = f"{safe_keyword} order:latest"
    url = f"{base_url}/search.json?{urllib.parse.urlencode({'q': query})}"

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": base_url + "/",
    }
    if auth_cookie and auth_cookie != "paste-your-full-cookie-header-here":
        # Strip any stray newlines/carriage returns/whitespace - these can sneak in
        # from copy-pasting (browser dev tools, GitHub secrets, etc.) and HTTP
        # headers cannot contain raw newline characters.
        clean_cookie = auth_cookie.replace("\n", "").replace("\r", "").strip()
        headers["Cookie"] = clean_cookie

    try:
        resp = get_scraper().get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log(f"ERROR: request failed for keyword '{keyword}': {e}")
        return []
    except ValueError as e:
        log(f"ERROR: bad JSON response for keyword '{keyword}': {e}")
        return []

    if auth_cookie and data.get("posts") is None:
        log("WARNING: got a response with no 'posts' field — your auth_cookie "
            "may be missing, expired, or invalid. Check config.json.")

    posts = data.get("posts", [])
    topics = {t["id"]: t for t in data.get("topics", [])}

    results = []
    for post in posts:
        post_id = post.get("id")
        topic_id = post.get("topic_id")
        topic = topics.get(topic_id, {})
        title = topic.get("title", "(unknown topic)")
        excerpt = (post.get("blurb") or "").replace("\n", " ").strip()
        # /p/<post_id> is a stable Discourse permalink that redirects correctly.
        post_url = f"{base_url}/p/{post_id}"
        results.append({
            "post_id": post_id,
            "topic_id": topic_id,
            "title": title,
            "excerpt": excerpt,
            "url": post_url,
            "created_at": post.get("created_at"),
        })
    return results


def send_email(email_cfg: dict, subject: str, body: str) -> bool:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email_cfg["from_address"]
    msg["To"] = email_cfg["to_address"]

    try:
        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"], timeout=REQUEST_TIMEOUT) as server:
            server.starttls()
            server.login(email_cfg["smtp_username"], email_cfg["smtp_app_password"])
            server.sendmail(email_cfg["from_address"], [email_cfg["to_address"]], msg.as_string())
        return True
    except Exception as e:
        log(f"ERROR: failed to send email: {e}")
        return False


def main():
    config = load_config()
    state = load_state()
    seen_ids = set(state.get("seen_post_ids", []))

    base_url = config.get("site_base_url", "https://gafshub.com").rstrip("/")
    max_per_run = config.get("max_notified_posts_per_run", 20)
    auth_cookie = config.get("auth_cookie", "")

    new_matches = []  # list of (keyword, match_dict)

    for keyword in config["keywords"]:
        matches = search_keyword(base_url, keyword, auth_cookie)
        for match in matches:
            if match["post_id"] not in seen_ids:
                new_matches.append((keyword, match))
                seen_ids.add(match["post_id"])
        time.sleep(0.5)  # be polite to the server between keyword queries

    if not new_matches:
        log("No new matches this run.")
    else:
        new_matches = new_matches[:max_per_run]
        log(f"Found {len(new_matches)} new match(es). Sending email...")

        lines = [f"GAFSHUB keyword watcher found {len(new_matches)} new post(s):\n"]
        for keyword, match in new_matches:
            lines.append(f"Keyword: {keyword}")
            lines.append(f"Topic:   {match['title']}")
            if match["excerpt"]:
                lines.append(f"Excerpt: {match['excerpt']}")
            lines.append(f"Link:    {match['url']}")
            lines.append("-" * 40)

        body = "\n".join(lines)
        subject = f"GAFSHUB: {len(new_matches)} new match(es) for your keywords"

        sent = send_email(config["email"], subject, body)
        if sent:
            log("Email sent successfully.")
        else:
            log("Email NOT sent (see error above). New matches were still recorded as seen.")

    state["seen_post_ids"] = list(seen_ids)
    save_state(state)


if __name__ == "__main__":
    main()
