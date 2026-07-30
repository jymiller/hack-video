# Handoff — hack-video

**Written 29 July 2026, early morning. The event is Thursday 30 July, 09:30–20:00,
AWS Builder Loft, 525 Market St, San Francisco.**

Read this first, then [`STATUS.md`](STATUS.md), then
[`docs/06-the-run-of-show.md`](docs/06-the-run-of-show.md).

---

## Get running in three commands

```bash
cd <this directory>
source .venv/bin/activate          # or: uv venv && uv pip install -r requirements.txt
set -a; . ./.env; set +a           # symlink to ~/Downloads/source/hack-video/.env
make demo                          # check + serve + graph state + the three URLs
```

If the graph is empty or wrong: **`make restore`**, not `make rebuild`. `rebuild` stops
after the load pass and leaves zero Observations, zero corroboration edges and zero
proposed assertions — it takes 23 seconds and quietly breaks beats 2 and 4. `restore`
runs the extraction and assertion passes too: minutes, and it needs the network.
Neither is a stage fallback. `make check` reports the health of every moving part.

---

## What this is

A four-page local app against the hackathon's vendor stack, plus a Neo4j graph whose
**schema encodes an argument** rather than decorating one.

| Page | URL | What it does |
|---|---|---|
| Video | `/` | TwelveLabs — index, drag-drop, cross-video search, **click a hit and the video seeks to that second**, streaming Pegasus analysis |
| Archive | `/archive.html` | Internet Archive metadata + full-text search, fetch straight into the corpus |
| Research | `/research.html` | You.com quick search and deep research; jobs run server-side and survive navigation |
| Graph | `/graph.html` | Neo4j — concept coverage, the attestation queue, read-only Cypher |
| Explainer | `/explainers/the-graph.html` | The whole schema on one page, reading live from the database |

---

## The thesis, in one paragraph

Credit systems consume a **controlled document supply chain** — things a lender is sent by
somebody accountable. News footage is none of that. So sources are either `controlled` or
`observed`; observed sources produce `Observation`s and **may never produce a `Fact` or reach
a covenant**. The payoff is measured, not asserted: 106 links between video and concept across
six broadcasters, and **zero reach either covenant concept**. The graph declines to bridge a
gap that does not exist, and saying so is the product.

Full model: [`docs/05-the-data-model.md`](docs/05-the-data-model.md).

---

## Measured facts (do not re-derive these)

| Fact | Value |
|---|---|
| TwelveLabs indexing speed | **~0.3× realtime** — 20s for a 69s clip |
| Current models | `marengo3.0`, `pegasus1.2`. `model_options` are **visual / audio only** |
| Free tier used | ~27 min of 600 |
| Pegasus modality | **Unreliable.** It labelled spoken content as on-screen text, then denied anything was spoken. Modality is derived by transcript-matching, never taken from the model |
| Novita | 143 models, **zero do audio**. `json_schema` support varies; some wrap JSON in fences, some return only `reasoning_content` |
| Model choice | `zai-org/glm-5.2` — chosen on schema support and latency (~17s), **not accuracy**: across five models, accuracy differences sat inside run-to-run noise (`graph/bakeoff.py`) |
| Strands | Adoptable. 166s from nothing to a verified tool-calling agent, no AWS creds |
| IA TV News archive | Metadata-searchable, **media blocked** (403 video, 401 captions). Full-text search works and is genuinely useful |
| Voice | macOS `say`, Daniel (en_GB), 42.2s rendered, offline |

---

## Traps already paid for

- **`Agent(model='zai-org/glm-5.2')` does not error.** Strands silently builds a `BedrockModel`
  and dies at first invoke with `NoCredentialsError`. Pass an explicit `OpenAIModel`.
- **`NOVITA_MODEL` in `hack-you/.env` is `deepseek-v4-flash`, not glm-5.2.** Code reading that
  variable runs a different model and looks healthy doing it.
- **`load_dotenv` on `hack-you/.env` injects AWS credentials** into the process, which can mask
  an accidental Bedrock fallback. Use `dotenv_values`.
- **`say -v <voice>` exits 0 for a voice that is not installed** and hands you the default,
  byte-identical. Only hashing catches it. `graph/voice.py` validates first.
- **TwelveLabs API encoding is inconsistent** — `/indexes` and `/analyze` are JSON; `/tasks`
  and `/search` are multipart. All handled in `server.py`.
- **Cypher variables do not survive a statement boundary.** `MERGE (d)-[:X]->(f)` as its own
  statement silently creates two anonymous nodes. Bit us once.
- **`NODE KEY` constraints are Enterprise-only** and abort the whole schema file on Community.

---

## The attestation rule — the core design

A model may **only ever** write `status='proposed'`. No computation reads a proposed edge.
Work is keyed on the **sha256 of the canonical source URL**: seen is seen. A pair a human has
closed is never sent to the model again — a fully settled run makes zero API calls in 0.2s.

`/api/graph/validate` requires a signature, returns 409 on an already-decided pair, and
records `reopen` explicitly. Human decisions survive `make rebuild` via
`graph/attestations.py`.

---

## Where things live

```
server.py              FastAPI proxy — all vendor calls, keys stay server-side
static/                the four pages; no build step, edit and refresh
graph/schema.cypher    constraints           graph/seed.cypher    vocabularies, concepts, deal
graph/load.py          concept-driven retrieval from TwelveLabs
graph/extract.py       segments -> Observations with typed values + corroboration
graph/assert_impact.py the model's covenant assertions (skips settled pairs)
graph/attestations.py  export/restore human decisions
graph/voice.py         narration, offline      graph/bakeoff.py   the model comparison
graph/strands_hello.py verified Strands agent  graph/dump/        full graph export (JSON)
docs/05-the-data-model.md   the model     docs/06-the-run-of-show.md   the three minutes
docs/explainers/*.html      six explainers, house style
video/                 6 clips, 171MB, gitignored
audio/                 rendered narration, gitignored
attestations.json      the human decisions — this file is not rebuildable
```

**Credentials.** `.env` is a symlink to `~/Downloads/source/hack-video/.env`
(`TWELVELABS_API_KEY`). Novita and You.com keys are read from
`~/Downloads/source/hack-you/.env` by `server.py`. **No key is committed anywhere.**

**Running services.** Neo4j in docker container `hackgraph` (bolt 7687, browser 7474,
neo4j/hackvideo2026). The app on `:8000`. Both are disposable —
`graph/dump/graph-export.json` holds all 155 nodes and 375 relationships. The node count
drifts upward by one every time `make assert` runs — it writes an `ExtractionRun` audit node
even when the worklist is empty and no model call is made.

---

## The deployment — a submission artifact, not the demo

The demo runs on the laptop. This exists so the 16:00 submission has a URL, and the
dashboard's `GIT.REMOTE` field has something to point at.

**Two manual steps remain, and neither can be scripted:**

1. **Add `hack-video` to Render's GitHub App.**
   <https://github.com/settings/installations> → Render → Repository access.
   Render already deploys four of your repos including two private ones, so the App
   is installed and working — `hack-video` is simply not in the selected list, and
   the API returns *"repository URL is invalid or unfetchable"* until it is.
2. **Create a Neo4j Aura free instance** at <https://console.neo4j.io>, then populate
   it from the laptop:
   ```
   NEO4J_URI=neo4j+s://<id>.databases.neo4j.io NEO4J_USER=neo4j \
   NEO4J_PASSWORD=<pw> make restore
   ```
   `load.py` reads the TwelveLabs cloud index, so this needs no local media and no
   graph importer has to exist. Skip it and the service still deploys — pages, search
   and video all work, graph endpoints 500.

Then, once:

```
NEO4J_URI=... NEO4J_PASSWORD=... python render_deploy.py
```

Idempotent: creates the service or updates env vars and redeploys.

**What differs from local, deliberately.** `PUBLIC_READONLY=1` 403s every route that
spends money or mutates state, kills Swagger and `/openapi.json`, closes
`/api/you/status` (it returned the account balance), and drops the `/docs` markdown
mount — locally Swagger shadows that path, so disabling Swagger would otherwise have
published the run of show and the Enid boundary note. Twelve probes cover it.

**Media.** The six clips live in the **private** S3 bucket `hack-video-gatwick-media`
(us-west-2, public access blocked). `MEDIA_URLS` carries presigned URLs so Render
holds time-limited links, never AWS credentials. **They expire after 7 days** —
re-running `render_deploy.py` renews them. Sign against the regional endpoint; the
global host answers with its own 307.

---

## Enid boundary — read before writing anything

Business context and use case are shared **by agreement**. The **trust-grading ladder is
not**, and appears nowhere in this repo.

John's decision on 29 July: variable names and reference-data names **do not need
sanitising**. So `covenant_code`, `unit_kind`, `canonical_scale`, the `unit_kind` / `scale`
term sets, and the `cta_senior_*` concept codes stay as they are.

The repo is **private**. An earlier scope note in `docs/05` falsely claimed nothing was
reproduced; it has been corrected to say what is actually true.

---

## Open — and only John can close these

**Blocking, unsent, and it is now the day before:**

1. Is registration confirmed, or is that link an invite?
2. **What must the 16:00 submission contain?** It sets the 14:30 freeze.
3. **Is pre-built work allowed?** This changes everything — if yes, all of this walks in with
   him; if no, it must be rebuilt live inside 3h30m.
4. What are the prizes and judging criteria?

**Technical, decided but not done:**

- ~~Beat 4 has no data.~~ **Closed 29 July.** A Firstpost clip on the water outage
  (`dKEpA70WhXU`, 4:13, hash `78a3514f49df`) is indexed, linked and assessed. `glm-5.2`
  proposed **could_affect: true** on `senior_icr`; John **rejected** it at 16:59, signed and
  timestamped, and the rejection is kept rather than deleted. `senior_rar` is deliberately
  left `proposed` — the queue is not meant to look finished. The pair is now closed to the
  model: `make assert` makes zero API calls and returns in 0.2s.
- **No UK broadcaster put the water outage on YouTube.** BBC, Sky, ITV, GB News, LBC,
  Guardian, Telegraph, Independent, Reuters, AP all swept and all empty; ITV ran text only.
  Do not spend time re-searching. Five other candidates exist and all are small channels —
  `bLprsy_tLs0` (LONDONER) is the best second source if corroboration is wanted, but it is a
  10-subscriber channel and that is a credibility trade John should make deliberately.
- **Covenant thresholds are `not_sourced`** and deliberately null. A You.com search surfaced
  the actual Gatwick Funding prospectus PDF on gatwickairport.com — that is the lead.
- **No controlled-lane source is loaded.** Both lanes exist in the schema; only `observed` has
  data. Loading the prospectus would populate the other side.
- **Extraction reads transcripts only**, so every modality came back `spoken`. The on-screen
  figures Pegasus reported are not captured; that needs a per-segment OCR pass.

---

## Standing rules that do not move

- **Freeze at 14:30.** After it, only three moves are legal: SUBTRACT, SUBMIT, REHEARSE.
- The watchable moment gets named before anything is built.
- A number changing on screen is not a watchable moment, nor any disguise of it.
- **Absence is reported, never filled.** "Not sourced" and "unknown" are valid answers.
- Live in the room is 1–0. Submitted with nobody there is 0–3.
