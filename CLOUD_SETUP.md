# Running GAFSHUB Watcher for free on GitHub Actions

This runs the same watcher script in the cloud, on a schedule, at **zero
cost** — GitHub Actions is unlimited and free on public repositories. Your
computer no longer needs to stay on.

Your keywords, cookie, and email password are never stored in the repo
itself — they live only in GitHub's encrypted "Secrets" vault, which even
repo collaborators/viewers can't read back out. The repo being public only
exposes the *code*, not your credentials.

## 1. Create the repo

1. Go to https://github.com/new
2. Name it whatever you like (e.g. `gafshub-watcher`), set visibility to
   **Public**, click **Create repository**.

## 2. Upload these files

Upload the whole folder's contents to the repo (via the GitHub web
"Add file → Upload files" button, or `git push` if you're comfortable with
git):

```
watcher.py
generate_config.py
requirements.txt
state.json
.gitignore
.github/workflows/watch.yml
```

**Do NOT upload `config.json`** — it's not needed on GitHub (it gets
generated fresh from Secrets on every run) and if it has real credentials
in it, you don't want it in the repo. `.gitignore` already excludes it if
you're using git directly.

## 3. Add your secrets

In the repo: **Settings → Secrets and variables → Actions → New repository
secret**. Add each of these one at a time:

| Secret name | Value |
|---|---|
| `GAFSHUB_KEYWORDS` | your keywords, comma-separated, e.g. `ramjet,widget,5 8` |
| `GAFSHUB_AUTH_COOKIE` | the full cookie header string you copied from DevTools |
| `SMTP_HOST` | `smtp.gmail.com` (or your provider's) |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | your email address |
| `SMTP_APP_PASSWORD` | your Gmail app password |
| `FROM_ADDRESS` | your email address |
| `TO_ADDRESS` | where you want alerts sent |

## 4. Turn it on

1. Go to the **Actions** tab of your repo → you should see "GAFSHUB
   Watcher" listed → click it → **Enable workflow** if prompted.
2. Click **Run workflow** (top right) to trigger a test run manually right
   now, instead of waiting for the schedule.
3. Click into the run to watch the logs live and confirm it worked.

From then on, it runs automatically every 10 minutes, forever, for free —
no computer required.

## Notes

- **Schedule timing:** GitHub says scheduled runs may be delayed a few
  minutes during high-traffic periods. This is normal; treat "every 10
  minutes" as approximate, not exact.
- **Changing keywords/frequency later:** edit the `GAFSHUB_KEYWORDS`
  secret to change keywords (no code edits needed), or edit the `cron:`
  line in `.github/workflows/watch.yml` to change frequency (e.g.
  `*/5 * * * *` for every 5 minutes — GitHub Actions won't go faster than
  5-minute intervals).
- **If your cookie expires:** get a fresh one the same way as before
  (DevTools → Network → Cookie header) and update the
  `GAFSHUB_AUTH_COOKIE` secret — no need to touch code or redeploy
  anything else.
- **Staying active:** each successful run commits `state.json` back to the
  repo, which counts as activity — so GitHub won't auto-disable the
  schedule for inactivity.
- You can turn this off any time from the Actions tab (Disable workflow),
  and go back to running it locally on your computer if you prefer — both
  use the exact same `watcher.py`.
