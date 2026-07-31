# Handoff — Material Witness, end of 30 July

**Everything is committed and pushed. `main` is at `fd3ac16`. The working tree is clean.**
Read [`HANDOFF.md`](HANDOFF.md) for the original traps, then this for what changed today.

---

## Get running

```bash
cd ~/Downloads/source/hack-video
set -a; . ./.env; set +a
make up && make serve          # neo4j, then the app on :8000
```

Then `http://127.0.0.1:8000/story.html`. If the graph looks empty, `make up` — the container
is `hackgraph` and it was **OOM-killed once today**: Docker has only 1.9 GB and there are
five other containers running. `docker stop enid-demo` buys real headroom if you need it.

**Live:** https://hack-video-v6kg.onrender.com — deploys from `main` automatically.
**Aura** holds the graph the live app reads. Credentials are on Render, not in `.env`.

---

## What this is now

Five pages, one masthead, black on every one.

| Page | Route | What it does |
|---|---|---|
| **So what** | `/story.html` | The argument at projector scale. Three numbers, the ledger, the counter-example |
| **News analysis** | `/` | Corpus manifest, search, click-a-hit-to-seek |
| **Reasoning** | `/graph.html` | Four steps, flippable one at a time with ← → or 1–4 |
| **Research** | `/research.html` | You.com → both lanes: documents to the graph, video to the corpus |
| **Architecture** | `/explainers/architecture.html` | Two lanes, and where one stops |

---

## The graph, as it stands

**289 nodes · 902 relationships.** Nine broadcasters, 160 video→concept links.

Three things arrived today and all three are load-bearing:

**The risk bridge.** `(:Observation)-[:SUGGESTS_RISK]->(:Risk)<-[:EXPOSED_TO]-(:Covenant)`.
Risk is a **sink** — both arrows point in, so there is no forward path from a clip to a
covenant. Getting there means traversing `EXPOSED_TO` backwards, visible in the query text.
Safety by type, not policy. The model may only ever write `proposed` on `SUGGESTS_RISK`,
same as `MAY_AFFECT`.

**The counter-example.** `:RatioTest` nodes carrying the real covenant history from Gatwick's
own compliance certificate, plus a `:Waiver` that hangs off the tests it covers **without
deleting the breach**. This is what makes the zero mean something — see below.

**Entities and topics.** 27 entities canonicalised across broadcasters. "Gatwick Airport" is
**one** node reached from 19 segments through surface forms as mangled as *"get work"*.

---

## The argument, in the order it should be told

1. **106 → 160 links across nine broadcasters. Zero reach a covenant.** The corpus grew by
   half today and the zero did not move — which is a much better test than this morning's.
2. **Video reaches the *risk*, never the number.** That is what footage is worth: it tells a
   credit analyst which test to open, months before the filing that settles it.
3. **A model may only ever propose.** On 29 July it claimed an 11-hour water outage could hit
   interest cover. You rejected it, signed and timestamped, and the rejection is kept.
4. **The counter-example.** Feed the same graph an admissible document and it reaches the
   covenant at once:

| Tested | Senior ICR | Senior RAR | |
|---|---|---|---|
| 31 Mar 2019 — **the drone year** | 2.93 | 0.59 | both clear |
| 31 Dec 2020 | **−1.29** | **0.94** | both past event of default |
| 31 Dec 2021 | **−1.49** | 0.81 | ICR default · RAR lock-up only |

> The drone shut Britain's second airport and led every bulletin on earth; the covenants
> did not move. A pandemic nobody filmed there inverted the ratio. **The system is not
> incapable. It is discriminating.**

---

## Numbers that are now correct — do not regress these

| | |
|---|---|
| **The £2bn loss was Heathrow's** | Gatwick's Security Group: **£525.9m** (2020), **£368.7m** (2021). This was in the repo from the first commit |
| **Two waivers, not one** | The Amendment and Waiver Agreement is dated **8 September 2021**. August is when discussions began. An earlier "22 September 2020 Amendments" covers the worse breach |
| **Covenant tiers** | ICR: trigger **1.50**, default **1.10**. RAR: trigger **0.70**, default **0.85**. All from the Common Terms Agreement of 15 February 2011 |
| **The headline ratio is dated** | 0.61 against 0.70 = 12.9% is the **31 March 2018** vintage. There is fresher data: 30 June 2024 interims show ICR 3.74/3.48, RAR 0.47/0.45 |

Full evidence in [`docs/07-the-counter-example.md`](docs/07-the-counter-example.md), sourced
to primary filings.

---

## Open, in the order I would do them

1. **`DELETE /api/indexes/{id}` is live, unauthenticated, on a public URL.** One curl destroys
   the TwelveLabs index. Guard it or remove it. This is the only thing here I would call urgent.
2. **`ingest_video index` has no duplicate guard.** `fetch` refuses to re-download but `index`
   will happily upload the same clip twice — it did, tonight. Whoever clicks twice pays twice.
3. **Aura is behind again.** It has the 247/661 state; local is 289/902. Re-sync with
   `-m graph.migrate wipe` then `-m graph.export load`, with `/tmp/aura_env` sourced. The
   wipe needs a human — the classifier blocks it, correctly.
4. **The demo page (`/demo.html`) is stale.** It was built before the risk layer, the
   counter-example and the black theme. Either update it or drop it; the four real pages have
   overtaken it.
5. **Threshold nodes.** The graph still flattens thresholds onto `:Covenant`. The tiered
   `:Threshold` design with validity windows is written up in
   [`docs/07-the-counter-example-design.md`](docs/07-the-counter-example-design.md) and never
   implemented.

---

## Traps added today

- **A restarted server is not a reloaded server.** Three times today a new endpoint 404'd or
  405'd because uvicorn predated it. If a call fails with 405, `make serve` before debugging.
- **The browser caches this app hard.** Verify with `?v=N` or `Cmd+Shift+R`. I twice checked
  a stale page and drew the wrong conclusion from it.
- **A search for "material breach" returns a canal breach in Shropshire.** Filmed by a wedding
  photographer, 85MB, indexed before anyone looked. This is why the human-picks step in the
  ingest loop is real and not ceremonial.
- **Portrait video breaks a naive yt-dlp format selector** — `height` is the long edge, so a
  height filter picks a too-small rendition and TwelveLabs rejects it *after* the upload is
  paid for. Fixed with an ffprobe pre-check.
- **`sys.exit()` in library code dies silently on a worker thread.** `SystemExit` is a
  `BaseException`, so `except Exception` never sees it — the stream just stops and it reads
  as a hang. Raise a normal exception.
- **Every page is forced dark now.** The `prefers-color-scheme` blocks are deleted, not
  overridden. The old pre-flight advice to "set macOS Appearance to Light" is obsolete.

---

## What is not claimed

The containment barrier has had **one live test** — the water outage refusal — and it held.
A scan of all transcripts for 21 finance and regulation terms returns zero hits: the corpus
is financially mute, so the barrier is mostly holding back material that was never going to
reach a covenant. Say "one test", not "proven".

"Gatwick Airport" and "Gatwick Airport Limited" are still two entity nodes.
`graph/entities.py status` reports it rather than hiding it.
