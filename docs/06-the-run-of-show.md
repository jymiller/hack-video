# The run of show

*Three minutes, live, in the room. The surface with a 1–0 record.*

---

## The watchable moment, named

Per the desk's own rule, this gets named before anything else and it is not negotiable:

> **A stranger types a question in English, and the video seeks itself to the second where
> the answer is spoken.**

It is an *event*, not a capability. Nobody needs the graph explained to understand what just
happened. It is already working, and it is the only thing on this page that would survive
being shown with the sound off.

Everything after it is argument, and the argument is carried on **voice over footage the
judge is already watching** — the channel this desk has actually won on.

**What this demo refuses:** a graph blooming, a force layout settling, a counter ticking up.
The graph is on screen for eleven seconds total and never animates.

---

## The three minutes

| Time | On screen | Voice | Why it earns the seconds |
|---|---|---|---|
| **0:00–0:25** | Video page. Type *"jobs created by the expansion"*. Hits from five broadcasters. Click rank 1 — **playhead jumps, Reeves says the line** | `01-open` | The event. Buys the room's attention before any claim is made |
| **0:25–1:00** | Graph page → corroboration. Three publishers, same figure, linked | `02-corroborate` | Establishes the machine is reading, not tagging |
| **1:00–1:40** | Graph page → coverage table. Green counts, then **0 · 0 · 0** on the covenant rows | `03-the-question`, `04-the-zero` | **The finding.** The contrast is the whole demo |
| **1:40–2:20** | Attestation panel. Model proposed. Human rejected. Signed, timestamped, kept | `05-the-model` | The part a credit audience believes |
| **2:20–2:45** | Explainer, attestation path — one still frame | `06-close` | Lands it |
| **2:45–3:00** | — | — | Slack. Something will run long |

### The line that has to land

> *"Ninety-six links between video and concept, across five broadcasters. **Zero** reach a
> covenant."*

Said at **1:20**, over the coverage table. If only one sentence survives, it is that one.

---

## Why the zeros are legal under the desk's own rules

The rule is that *a number changing on screen* is not a watchable moment, and neither is any
disguise of it. The coverage table does not change. It is not animated, revealed, or counted
up — it is simply read, and the zeros sit beside green numbers that make them mean something.

The absence is the finding. Pointing at it is not the same as watching it happen.

**If a judge is unconvinced by a table**, the fallback is to run query 3 live and let it
return no rows at all. Less legible, more visceral. Decide in rehearsal, not on stage.

---

## Setup, and the order it must happen in

```bash
make check          # every moving part, before anything else
make serve          # app on :8000
make demo-reset     # graph into the exact state the script assumes
```

Then, and only then, open in this order and **leave all four tabs open**:

1. `http://127.0.0.1:8000/` — Video
2. `http://127.0.0.1:8000/graph.html` — Graph
3. `http://127.0.0.1:8000/explainers/the-graph.html` — Explainer
4. `audio/` — narration, pre-rendered

**Pre-flight, every time:**

- [ ] `make check` all green
- [ ] The search box already contains *"jobs created by the expansion"* — do not type it live
- [ ] The clip is loaded and paused, not cold
- [ ] Wifi off for one rehearsal. The video, the audio and the graph are all local; only
      TwelveLabs search needs the network. **Know what the demo looks like without it.**
- [ ] Audio out of the laptop tested in the actual room, at the actual volume

---

## What breaks, and what to say

| If | Then |
|---|---|
| TwelveLabs search is slow or down | The graph already holds the segments. Skip to the coverage table — the finding does not need a live search |
| Neo4j is down | `make up` takes ~20s. Talk over it: this is why the rebuild is one command |
| The whole graph is wrong | `make rebuild` — 23 seconds, and attestations survive it |
| Wifi is gone entirely | Video plays, audio plays, graph is local. **Only live search dies.** Say so plainly and carry on |
| A judge asks for the covenant threshold | *"Not sourced. The graph says so rather than inventing one."* That is a better answer than a number |

---

## The three questions to expect

**"Isn't the answer just that your corpus is bad?"**
No — and that is the point. The corpus is five real broadcasters on the actual event. News
does not carry covenant data, and a system that pretended otherwise would be lying. The graph
declining to bridge that gap *is* the product.

**"So what does the video actually buy you?"**
Lead time. The broadcast exists the same afternoon; the filing that settles it arrives months
later. An observation cannot change a covenant test, but it tells you which test to go and
look at, early.

**"Did the model decide that?"**
No. The model proposes and may only ever propose. Every edge it writes is inert until a human
signs it, and a rejected proposal is kept rather than deleted. *Then show the rejection.*

---

## The 16:00 submission

A separate artifact from this, and it sets the **14:30 freeze**. Its contents are still
unconfirmed with the organisers — one of the four unsent questions. Until answered, assume it
needs a repo link and a written summary, and budget the last thirty minutes before the freeze
for it.

After 14:30 only three moves are legal: **SUBTRACT, SUBMIT, REHEARSE.**

---

## Known gap in this script

**Beat 4 currently has no data.** The narration line `05-the-model` describes the model
falling for the water outage and a human overruling it — which genuinely happened, on
28 July, with deepseek. But the assertion was rebuilt under the URL-hash rule, and the water
outage **has no source in the corpus**, so it is no longer assessed and the edge no longer
exists.

Two honest options:

1. **Add a water-outage clip** to the corpus (candidates were found on 28 July), index it,
   link it, let the model assess it. Restores the beat as a live artifact. ~15 minutes.
2. **Re-point beat 4** at the Northern Runway assertions, which do exist and are signed. The
   story becomes "the model proposed, a human validated" — true, but weaker, because
   agreement is less interesting than correction.

Option 1 is better and it is a corpus decision, not a code one.
