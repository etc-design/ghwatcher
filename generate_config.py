#!/usr/bin/env python3
"""
Builds config.json from environment variables at runtime.

Used in the GitHub Actions workflow so that your keywords, cookie, and
email credentials live only in GitHub's encrypted Secrets - never in the
repo itself, even though the repo is public.
"""

import json
import os

keywords_raw = os.environ.get("GAFSHUB_KEYWORDS", "")
keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

config = {
    "keywords": keywords,
    "site_base_url": os.environ.get("GAFSHUB_BASE_URL", "https://gafshub.com"),
    "auth_cookie": os.environ.get("GAFSHUB_AUTH_COOKIE", "").replace("\n", "").replace("\r", "").strip(),
    "email": {
        "smtp_host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        "smtp_username": os.environ.get("SMTP_USERNAME", ""),
        "smtp_app_password": os.environ.get("SMTP_APP_PASSWORD", ""),
        "from_address": os.environ.get("FROM_ADDRESS", ""),
        "to_address": os.environ.get("TO_ADDRESS", ""),
    },
    "max_notified_posts_per_run": int(os.environ.get("MAX_NOTIFIED_POSTS_PER_RUN", "20")),
}

if not keywords:
    raise SystemExit("ERROR: GAFSHUB_KEYWORDS secret is empty or missing.")
if not config["auth_cookie"]:
    raise SystemExit("ERROR: GAFSHUB_AUTH_COOKIE secret is empty or missing.")

with open("config.json", "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)

print("config.json generated from environment variables.")
