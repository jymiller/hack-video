# Material Witness

**What is news footage actually worth to a credit desk?**

Live: **https://hack-video-v6kg.onrender.com** · Built for *Hack the Video Agent Context
Graph*, 30 July 2026, AWS Builder Loft, San Francisco.

---

Credit systems consume a **controlled document supply chain** — things a lender is sent by
somebody accountable. Filings, accounts, compliance certificates. News footage is none of
that, and a system that quietly treats a broadcast like a filing is lying about where its
numbers came from.

So this indexes six UK broadcasters covering Gatwick's second runway with **TwelveLabs**,
extracts entities, topics and timed segments with **GPT-5.6**, and writes it all into a
**Neo4j** graph whose schema encodes that argument rather than decorating it.

---

## The finding, measured rather than asserted

Sources are `controlled` or `observed`. Observed sources produce `Observation`s and **may
never produce a `Fact` or supply a covenant number**.

| | |
|---|---|
| Links between video and concept | **106** |
| Broadcasters | **6** |
| Of those links reaching either covenant | **0** |

Not a gap in the corpus. News does not carry covenant data, and the graph declining to
bridge that gap is the product.

## The bridge — where video earns its place

The negative finding alone dead-ends. The useful half is this shape:

```
Observation ──SUGGESTS_RISK──▶ Risk ◀──EXPOSED_TO── Covenant ──▶ Threshold
                              (sink)                            ▲
                                                          Fact ─┘  (controlled only)
```

A `Risk` is a *channel of exposure* — capital programme delivery, volume demand, regulated
revenue reset. It carries **no value, no unit, no direction, no threshold**. Both arrows
point into it, so getting from a clip to a covenant means traversing `EXPOSED_TO`
**backwards** — visible in the query text, on screen, to the person being asked to believe
it. Safety by type, not by policy: the next engineer breaks policies, and cannot break types.

> **Video can move where a credit analyst looks. It can never move what they read.**

## A model may only ever propose

Every model-written edge is `status='proposed'` and **inert** — no computation reads it
until a human signs. A rejection is **kept**, never deleted.

On 29 July the model proposed that an eleven-hour water outage could hit the interest cover
ratio. It could not: no flight was cancelled, the airport never closed, water was back
across the campus inside eleven hours. A human rejected it, signed and timestamped, and
that "no" is still in the graph. Settled pairs are never sent to the model again — a fully
settled run makes zero API calls in 0.2s.

## The number the video never touched

| Covenant | Test | Latest | Headroom |
|---|---|---|---|
| Senior ICR | min 1.50 | 3.59 | 139% |
| **Senior RAR** | **max 0.70** | **0.61** | **12.9%** |

Both from Gatwick Airport Limited's own audited accounts, cited on the node. Ask the agent
which covenant is tightest and it names Senior RAR — then refuses to let any footage speak
to whether it will breach.

---

## Stack

| | Doing what |
|---|---|
| **TwelveLabs** | Marengo + Pegasus indexing, cross-video search, 512-dim segment embeddings, Jockey knowledge store |
| **OpenAI GPT-5.6** | Terra for the agent, Luna for entity/topic extraction — Responses API, structured outputs |
| **Neo4j** | 231 nodes, 651 relationships, vector index over segment transcripts |
| **Strands Agents** | Tool-calling agent, five read-only tools |
| **Render · Neo4j Aura** | The deployed app and its database |
| **You.com** | Research surface used to source the filings |

## Run it

```bash
uv venv && uv pip install -r requirements.txt
set -a; . ./.env; set +a
make demo
```

`make check` reports the health of every moving part. `make rebuild` rebuilds the graph
from nothing in ~23 seconds — and human attestations survive it, because they are the one
thing here that is not rebuildable.

```bash
make agent Q="which covenant has the least headroom?"
make vsearch Q="how many people will get work from this?"
```

## Where things live

```
server.py               FastAPI — all vendor calls, keys stay server-side
static/                 the pages; no build step, no CDN, edit and refresh
graph/db.py             one place the database lives
graph/load.py           concept-driven retrieval from TwelveLabs
graph/extract.py        segments -> Observations with typed values + corroboration
graph/entities.py       entities and topics, canonicalised across videos
graph/embed.py          Marengo embeddings + the vector index
graph/risk.py           the risk layer and its proposals
graph/agent.py          the Strands agent
graph/attestations.py   export/restore human decisions
graph/export.py         lossless dump; discovers temporal types at dump time
docs/05-the-data-model.md   the model    docs/06-the-run-of-show.md   the three minutes
```

---

## What this does not claim

The containment barrier has had **exactly one live test** — the water-outage proposal a
human refused — and it held. Claiming more would be overclaiming: a scan of all 63 segment
transcripts for 21 finance and regulation terms (inflation, RPI, RAB, gearing, covenant,
interest cover, price control, landing fee…) returns **zero hits**. The corpus is
financially mute, so the barrier has mostly been holding back material that was never going
to reach a covenant anyway.

Entity canonicalisation collapsed "Gatwick Airport" to one node across five broadcasters
through surface forms as mangled as *"get work"* and *"Getwork"* — but it left `Gatwick
Airport` and `Gatwick Airport Limited` as two nodes, and `graph/entities.py status` reports
that rather than hiding it.

Observed values on `Test` nodes are illustrative. Covenant structures, thresholds and
breach directions are real and cited.
