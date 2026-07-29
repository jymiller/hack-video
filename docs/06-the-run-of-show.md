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
| **0:00–0:25** | Video page. Type *"jobs created by the expansion"*. Counter reads **10 hits · 4 sources**. Click rank 1 — **playhead jumps to 14.4s, Channel 4 says "two point two billion pounds"** | `01-open` | The event. Buys the room's attention before any claim is made |
| **0:25–1:00** | Graph page → corroboration. Three publishers, same figure, linked | `02-corroborate` | Establishes the machine is reading, not tagging |
| **1:00–1:40** | Graph page → coverage table. Green counts, then **0 · 0** on the two covenant rows | `03-the-question`, `04-the-zero` | **The finding.** The contrast is the whole demo |
| **1:40–2:20** | Attestation panel. Model proposed. Human rejected. Signed, timestamped, kept | `05-the-model` | The part a credit audience believes |
| **2:20–2:45** | Explainer, attestation path — one still frame | `06-close` | Lands it |
| **2:45–3:00** | — | — | Slack. Something will run long |

### Two corrections to beat 1, measured 29 July — decide these in rehearsal

This row said *"Hits from five broadcasters. Click rank 1 — Reeves says the line"* until it
was checked against a live search. Neither half was true, and neither is a regression from
the sixth clip: Firstpost scores nowhere near the top ten, so this has been wrong in every
rehearsal so far.

- **Rank 1 is Channel 4 News at 14.4s**, a reporter in voiceover: *"…runway would cost two
  point two billion pounds…"*. Reeves speaks only in the London Standard clip, which does
  **not appear in the default top ten at all** — audio-only search puts her at rank 9, 59.0s.
  The Channel 4 line is arguably the better cue: it lands the exact figure `01-open` says out
  loud. If Reeves is wanted, she has to be clicked by name, not by rank.
- **The counter reads `10 hits · 4 sources`**, not five — Channel 4, Runway Radar, SussexWorld,
  TalkTV. The graph genuinely holds five publishers on `jobs_claimed`; this one query surfaces
  four of them. `01-open` says *"Five broadcasters ran it"*, which is true of the corpus and
  does not match the number on screen. **Either change the line or do not draw the eye to the
  counter.** Left as-is deliberately: it is a stage decision, not a fact to correct.

Beat 3 likewise said **0 · 0 · 0**. The table has **two** covenant-labelled zero rows
(`cta_senior_icr`, `cta_senior_rar`) and four zero rows in all. Point at two.

### The line that has to land

> *"One hundred and six links between video and concept, across six broadcasters. **Zero**
> reach a covenant."*

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
- [ ] **Hard-reload every tab** (`Cmd+Shift+R`). The browser caches `chassis.css` hard, and a
      stale stylesheet at 17:15 would be a stupid way to lose
- [ ] **macOS Appearance set to Light.** The app is light; the six explainers follow the system
      setting, so on a dark-mode laptop beat 6 jumps from a white page to a black one

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
No — and that is the point. Five real broadcasters on the runway approval, one on the water
outage, all of them on the actual events. News
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

## Beat 4 — closed 29 July

The water-outage clip is in the corpus: **Firstpost, 4:13, 27 July 2026**,
`https://www.youtube.com/watch?v=dKEpA70WhXU`, hash `78a3514f49df`. Indexed, linked to the
`Airport water supply failure` event, and assessed. `zai-org/glm-5.2` proposed:

> `senior_icr` · **could_affect: true** · decreases —
> *"An airport water supply failure is an operational incident that could disrupt operations
> and reduce revenue, lowering the interest cover ratio."*

**That is wrong, and checkably so.** No flight was cancelled, the airport never closed, and
water was back across the campus inside about eleven hours. The model reacted to the loudest
reading of the footage. This is the beat.

**John rejected it at 16:59 on 29 July**, signed and timestamped, with the note *"No flights
cancelled, the airport never closed, water restored across the campus in about eleven hours.
A terminal-services failure, not an air-operations one."* The card reads **rejected — kept
for the record, read by nothing**, which is the sentence the beat exists to earn.

`senior_rar` is deliberately **left proposed**. The same overreach, unanswered — because a
queue that is entirely worked looks staged, and one rejection is enough for the beat. It also
gives an easy answer if a judge asks what happens next.

The pair is now closed to the model. `make assert` sends nothing, spends nothing and returns
in 0.2 seconds — the attestation rule, demonstrable live if anyone doubts it. The decision
survives `make rebuild`: `graph/attestations.py` restores it with a `MERGE`, so it reattaches
even though the rebuild does not re-run the assertion pass.

**Do not re-run `make assert` between rehearsals unless something is wrong.** It is safe —
it makes no model calls — but it writes an `ExtractionRun` audit node each time, so the node
count in the header creeps upward and stops matching the documented figure.

**No search for a UK broadcaster clip is worth repeating.** BBC, Sky, ITV, GB News, LBC,
Guardian, Telegraph, Independent, Reuters and AP were all swept: none put this event on
YouTube. ITV ran text only. Firstpost is the only outlet with real editorial standing that
did. That is a finding about the coverage, not a gap in the search.
