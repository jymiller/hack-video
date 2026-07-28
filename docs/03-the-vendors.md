# The vendors

*Judged by the desk's standing test: **can somebody point at it doing a distinct thing on
screen?** Not a capability — an event. Every vendor costs integration time that would
otherwise be build time, and with 3h30m that trade is brutal. A sponsor prize never argues
one back in.*

**None of these has been run by anyone here.** `VERIFIED` is blank on all five on purpose —
by the desk's own rule they are stale, their verdicts read as unknown, and they are claims
to check rather than evidence.

---

## TwelveLabs — use, and it is the centre of the build

Video understanding. Indexes video and makes it searchable by what is seen, heard and said.

**Two models.** *Marengo* is the encoder — it turns video into embeddings you can search.
*Pegasus* is the video-language model — it answers questions about a clip in words. You
create an index, upload video, wait for it to process, then query.

**Three modalities:**
- **Visual** — actions, objects, events, brand logos, and **text on screen through OCR**
- **Audio** — ambient sound, music, effects
- **Transcription** — the spoken words

The OCR is what makes the reconciliation possible and it is not the obvious reason to reach
for this product.

**Watchable moment:** the agent jumps the playhead to the exact second the evidence appears
— the reporter says the number, the lower third confirms it. The video scrubs itself to the
proof. That passes the test because it is an event, not a capability: a stranger sees a
video seek itself to a moment somebody just asked about and understands instantly that the
machine watched it.

**Cost:** free tier is 600 minutes shared across indexing, analysis and segmentation, no
credit card. Then $0.042/min indexing, $0.0015/min infrastructure, $4 per 1,000 searches.

### Two traps that could cost the day

1. **Model slugs drift, and one already has.** Marengo 2.7 was sunset on 30 March 2026 —
   you can no longer index or search with it. Pull the model list before trusting a slug.
   Copying a code sample off a blog written last year is a live way to lose an hour.
2. **Indexing time is unmeasured.** 600 free minutes is plenty for four news clips. How
   long those minutes take to *process* is the open question, and it is the single most
   likely way a 3h30m build ends with nothing on screen. One clip indexed and timed
   beforehand settles it.

Also note: **free-tier index data is cleared after 90 days.**

---

## Neo4j — conditional

The graph database the findings are written into.

**The trap:** a graph blooming on screen is a chart redrawing, which this desk refuses
outright. It needs a caption to be understood and it is indistinguishable from any network
diagram in any demo. Judges have seen a hundred of them.

**Watchable moment:** a single path lighting up, one hop at a time, from a night in December
to a ratio in a bond covenant — with each hop named aloud as it fires.

The subject is the **path**, not the graph. A path is a story with a direction and an
ending. A graph is wallpaper. This is the same conclusion the desk reached about DataHub's
lineage view, and it holds here for the same reason.

---

## Strands Agents — conditional, but use it anyway

AWS's open-source agent SDK. Python and TypeScript, model-agnostic, MCP native, multi-agent
patterns and OpenTelemetry tracing built in. Native Bedrock integration but works with
Anthropic, OpenAI and Gemini, so nothing is locked. ~6,500 GitHub stars.

**Watchable moment:** none. A framework is invisible by nature and the vendor test alone
would cut it.

**Why it stays:** because AWS is hosting and judging. Same logic as "Use of DataHub" being
the first criterion on 10 August — at a sponsor event, using the sponsor's framework is
scored whether or not anyone can see it. It also speaks MCP, which is how it would reach
Neo4j.

### The framework decision

| Strands | CrewAI |
|---|---|
| The sponsor's own framework, at their venue, judged by their people. MCP native, so Neo4j and TwelveLabs both reachable. | What the desk already runs, with every trap paid for — the listener bug, the provider routing, the model pinning. |
| Cost: new to us, and the learning happens inside a 3h30m window. | Cost: uses none of the sponsor's stack. |

**Read: learn Strands beforehand, not on the day.** An hour building a hello-world agent
with one tool decides it. If that hour goes badly, CrewAI is the fallback and nothing is
lost.

---

## OpenAI — use, but for the voice

**As reasoning:** invisible. Nobody can point at a model thinking, and on the vendor test
alone that is a cut.

**As voice:** it speaks the finding out loud over the footage. That *is* the watchable
moment — the channel this desk has actually won on, and one almost nobody at a video
hackathon will use.

**The trap:** text-to-speech fails silently. A bad voice id returns HTTP 200 and produces
nothing, or the wrong voice. Hash the output and listen to it. Never trust the status code.

---

## AWS — cut as a vendor, it is the venue

Infrastructure is invisible by definition and a console screenshot is not an event. It
earns its place through Strands, which is AWS's. Adding Bedrock or a hosted deployment on
top would cost build time for something no judge sees, and at 3h30m that is the trade we
cannot afford.

---

## For the vendor library

```
# VENDOR | WHAT IT DOES | WATCHABLE MOMENT | NEEDS | COST | VERDICT | VERIFIED
#
# The 30 Jul video-context-graph stack. None run yet — VERIFIED blank on purpose.
TwelveLabs | indexes video so it can be searched by what is seen, heard and said | the playhead jumps to the exact second the evidence appears | account and API key | free 600 min, then $0.042/min | use | —
Neo4j | stores things and the relationships between them | one path lighting up hop by hop from a news event to a covenant ratio | an instance | free tier / self-hosted | conditional | —
OpenAI | reasoning, and text to speech | a voice states the finding out loud over the footage | key | pay as you go | use | —
Strands Agents | AWS agent SDK, model-agnostic, MCP native | nothing — a framework is invisible | none beyond a model key | free, open source | conditional | —
AWS | host and venue | nothing to point at on screen | account | n/a | cut | —
```
