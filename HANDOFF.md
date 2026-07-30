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

If the graph is empty or wrong: `make rebuild` — 23 seconds, and human attestations
survive it. `make check` reports the health of every moving part.

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
- **Following the TwelveLabs quickstart can gut `.venv`.** Found 30 July 08:15: site-packages
  held only `twelvelabs` + `httpx`; `fastapi`, `uvicorn`, `python-dotenv`, `neo4j`,
  `python-multipart`, `strands-agents` and `openai` were all gone. The app on `:8000` kept
  serving 200 the whole time because it had loaded its imports at 01:14 and was running on
  deleted files — **`make check` cannot see this**. Any restart would have been fatal.
  Fixed with `.venv/bin/python -m pip install -r requirements.txt`, which is why that file is
  pinned. If a vendor doc says `uv venv`, do not run it in this directory.
- **`video/` and `audio/` can go missing from the main tree** while surviving in
  `.claude/worktrees/hackathon-prep-vendors-698297/`. Also found 30 July. Beat 1 plays from
  `/media/<file>` (`static/index.html:256` → `VIDEO_DIR`), so a missing `video/` breaks the
  watchable moment and every narration line at once. `make check`'s `corpus` row is the tell —
  **it read `0 clips`**. It reads `6 clips` when this is right.

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
graph/knowledge_store.py  multi-turn Q&A over the corpus — off the run-of-show path
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

## The knowledge store — a spare wheel, not a beat

Wired 30 July, ~08:30, on the explicit basis that it might come up and should not be built
under time pressure if it does. **It is not on the run-of-show and beat 1 does not touch it.**

`ks_019fb38e-c2fb-7922-921d-712cd764210f`, 6 items, all `ready`. Same six assets the
`GATWICK` index holds, ingested into TwelveLabs' newer `responses` surface — a *different*
surface from `/search` and `/analyze`, so the index id is not a store id and the two share
nothing but the underlying assets. Ingest took 261s and is already paid for.

```bash
make ks-status              # per-item state
make ask Q="your question"  # ~30-40s, cites sources with timestamps
```

Also `GET /api/ks` and `POST /api/ks/ask` (`{"question": ..., "session_id": ...}` — the
response carries a `session_id` back, so multi-turn works). Both additive; no existing route
changed.

**What it is good for.** It corroborates across clips in one answer and cites each source with
a timecode. Asked whether any clip states a covenant threshold, it answered *"absent from the
material I could verify here"* on three runs out of three — the thesis, reached independently
by a vendor surface that was not built to argue it. That is the answer worth having in reserve.

**Two things to know before showing it to anyone.**

- **It cannot reliably name the broadcasters.** It reads on-screen branding, not the filenames
  the graph keys on, so it confidently identifies two to four of the six and calls the rest
  unknown — and the count moves between runs. **Do not ask it "which broadcasters are in this
  corpus" in front of a judge**: the graph's answer is six and its answer is not, and the
  weaker number is the one that would stick. Ask it about content, not provenance.
- **It is not streamed, on purpose.** On some questions the model fans out a per-video analysis
  and streams those deltas concurrently with the final answer, interleaving them into
  unreadable text. It is intermittent and did not reproduce on demand, so it could not be
  filtered with confidence. The one-shot call returns the final message cleanly every time.
  Cost is ~30-40s with nothing on screen. **If it gets shown, say what it is doing while it
  runs.**

---

## Standing rules that do not move

- **Freeze at 14:30.** After it, only three moves are legal: SUBTRACT, SUBMIT, REHEARSE.
- The watchable moment gets named before anything is built.
- A number changing on screen is not a watchable moment, nor any disguise of it.
- **Absence is reported, never filled.** "Not sourced" and "unknown" are valid answers.
- Live in the room is 1–0. Submitted with nobody there is 0–3.
