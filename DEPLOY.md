# Deploying to Render

Researched against Render docs, July 2026. The repo is public, so Blueprint deploy
works with no GitHub permissions dance.

## What is already true

- Python 3.14 is supported and is Render's *default* (3.14.3, for services created
  on or after 11 Feb 2026). `.python-version` pins `3.14`. Nothing in
  `requirements.txt` needs to move.
- `render.yaml` is a Blueprint. Committing it is what makes the dashboard offer a
  one-click deploy.
- `video/` (171 MB) is gitignored and will not exist on Render. See
  [The video problem](#the-video-problem) — this needs a code change before the
  player works in the deployed app.

## Before the first deploy

Three changes live in files this doc does not own. They are listed in the handoff
report; the deploy-blocking one is `/api/hls/{video_id}` in `server.py` plus the
`hls.js` swap in `static/index.html`. Without them the deployed page loads, lists
videos, searches, and analyzes — but every click on a video 404s the player.

Provision Neo4j Aura Free first if the graph pages are part of the demo. Five of
the seven `/api/graph/*` endpoints have no try/except around `cy()`, so an
unreachable database returns a 500 with a driver traceback rather than an empty
panel.

## Deploy: dashboard

1. Push `render.yaml`, `.python-version`, and `.env.example` to `main`.
2. <https://dashboard.render.com> → **New** → **Blueprint**.
3. Pick `jymiller/hack-video`, branch `main`. Render finds `render.yaml` at the root.
4. Render lists one service, `hack-video`, and prompts for every `sync: false`
   variable in one form:
   - `TWELVELABS_API_KEY`
   - `OPENAI_API_KEY`
   - `YDC_API_KEY`
   - `NEO4J_URI` — `neo4j+s://<id>.databases.neo4j.io`
   - `NEO4J_PASSWORD`

   `NEO4J_USER` is set to `neo4j` by the Blueprint and is not prompted.
   Fill all five now. A blank `TWELVELABS_API_KEY` crash-loops the service:
   `server.py:11` reads it with `os.environ[...]` at import.
5. **Apply**. First build runs `pip install -r requirements.txt` (2–4 min cold).
6. Live at `https://hack-video.onrender.com` (or `hack-video-<hash>` if the name
   is taken — check the service page for the real URL).

## Deploy: CLI

```bash
brew install render
render login                       # opens browser, writes a local token
render workspace set               # pick the workspace, if you have several
```

The CLI cannot create a Blueprint — do the first deploy in the dashboard, then:

```bash
render services -o json | jq -r '.[] | "\(.service.id)  \(.service.name)"'
export SVC=srv-xxxxxxxxxxxxxxxxxxxx

render deploys create $SVC --wait          # redeploy current branch tip
render deploys create $SVC --commit <sha>  # redeploy a specific commit
render deploys list $SVC
render logs $SVC                           # live tail
```

For CI or a non-interactive shell, skip `render login` and set `RENDER_API_KEY`
instead (`.env` already carries one locally).

## Changing a secret later

Dashboard → service → **Environment** → edit → **Save changes**. Saving triggers a
restart, not a rebuild — roughly 30 seconds.

Do not put secrets in `render.yaml`. `sync: false` exists precisely so the key
lives in the dashboard while the variable's *existence* stays in version control.

## Rollback

Dashboard → service → **Events** → find a green deploy → **Rollback** →
**Rollback to this deploy**. Render reuses the stored build artifact, so this is
much faster than a fresh build.

One thing to know: rolling back **automatically disables autodeploy** on that
service, as a guard against the next push re-landing the bad commit. Re-enable it
under Settings when you have pushed the fix, or the service will look stuck.

Rollback only reaches deploys whose build artifacts Render still retains; how many
depends on the workspace plan. If the artifact is gone, use
`render deploys create $SVC --commit <good-sha>` instead.

## Free tier, and what it costs you during a demo

- Free web services **spin down after 15 minutes with no inbound HTTP request or
  WebSocket message**.
- Waking one takes **about a minute**, during which the visitor sits on a Render
  loading page.
- 750 instance-hours per workspace per month. Bandwidth and build minutes draw on
  the workspace's included amounts.

A cold start in front of an audience is a minute of dead air. Options, cheapest
effort first:

1. **Hit the URL 5–10 minutes before you present** and keep the tab open. The
   simplest thing that works.
2. **Poll it.** Any external cron (a GitHub Action on a 10-minute schedule, or an
   uptime pinger) hitting `/` keeps it warm. This burns instance-hours 24/7 —
   730 hours/month against a 750 budget, so it fits exactly one service and
   nothing else.
3. **Upgrade to Starter for the day.** No spin-down at all. Downgrade after.

Also note the free instance is 512 MB / 0.1 CPU and the filesystem is **ephemeral**
— anything written at runtime is gone on the next restart or deploy. The in-memory
`JOBS` dict in `server.py` disappears with it, which is fine, and `/api/upload`
writes into `video/`, which is not (see the handoff report).

## The video problem

`static/index.html` plays via `player.src = '/media/' + filename`, and `/media/`
reads from `video/`, which is gitignored. On Render every one of those is a 404.

**Recommended fix: stream the HLS renditions TwelveLabs already generated.** No
media in git, no S3 bucket, no CDN to configure. Verified against the live
account:

- `GET /v1.3/assets/{id}` returns `hls.manifest_url` on CloudFront, `status: ready`
  for all six Gatwick videos.
- **The asset `_id` is the same id as the index video `_id`** — no filename
  matching needed, the id the UI already holds is the right key.
- CloudFront serves both the `.m3u8` and the `.ts` segments with
  `access-control-allow-origin: *`, so the browser fetches them directly. The
  server never proxies video bytes.
- Both are served as `Content-Type: application/octet-stream`, **not**
  `application/vnd.apple.mpegurl`. This is why the fix leads with hls.js: hls.js
  ignores Content-Type, Safari's native HLS does not and will likely refuse.
  hls.js covers Chrome, Firefox, Edge, and desktop Safari (all have MSE). iOS
  Safari falls through to the native path and may not play — not a desktop-demo
  concern, but do not promise it on a phone.

The exact edits are in the handoff report. Vendoring hls.js with no build step and
no runtime CDN is a one-time download, committed:

```bash
mkdir -p static/vendor
curl -L -o static/vendor/hls.min.js \
  https://cdn.jsdelivr.net/npm/hls.js@1.6.16/dist/hls.min.js
```

jsdelivr is used once here, at authoring time. The deployed page loads
`/vendor/hls.min.js` from the app's own static mount, so there is no third-party
request at runtime and nothing to break if a CDN is blocked on the venue wifi.

Pin 1.6.16 — 1.7.0 was still a release candidate as of this writing.

## Troubleshooting

**Service builds, then immediately crashes.** Almost always a missing
`TWELVELABS_API_KEY`. `render logs $SVC` shows `KeyError: 'TWELVELABS_API_KEY'`.

**502 on every request.** The start command is not binding `0.0.0.0:$PORT`. The
one in `render.yaml` is correct; check nobody edited it to `127.0.0.1` or a
hardcoded `8000`.

**Graph panels return 500.** `NEO4J_URI` still points at localhost, or Aura is
paused. Aura Free instances pause themselves after a few days idle — resume it in
the Aura console before the demo, not during.

**`/api/you/*` says unconfigured.** `YDC_API_KEY` is not set. `server.py:10` loads
it from a sibling project's `.env` on a local machine; that path does not exist on
Render, so the variable has to be set in the dashboard.
