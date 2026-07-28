# Open questions

**Two days out.** Ordered by what breaks if the answer is bad.

---

## Blocking — one message each, and still unsent

### 1 · Is registration actually confirmed?

The invitation link carries a token, which suggests an invite rather than a completed
registration. Everything else on this page is wasted if this is wrong. **Owner: John.**

### 2 · What must the 16:00 submission contain?

A repo? A video? A form? It sets the freeze at 14:30 and therefore shapes the last two hours
of the build. If it needs a recorded video, the plan changes substantially.
**Owner: John, to the organisers.**

### 3 · What are the prizes — cash, credits, or neither?

*"Prize categories and judging details are still to come."* Until this lands we cannot rank
Thursday against the DataHub prep it displaces, and the desk's rule is that cash and credits
are never summed. **Owner: John, to the organisers.**

### 4 · Is pre-built work allowed?

Decides whether we index video the night before or lose an hour on the day. Most one-day
events allow a prepared chassis; this one has not said. **Owner: John, to the organisers.**

---

## Technical — settle before Thursday, not on it

### 5 · How long does TwelveLabs take to index an hour of video?

**The single most important unknown on this page.** Free tier gives 600 minutes, which is
plenty of *quota* for four news clips. The question is wall-clock processing time. If a
60-minute broadcast takes 20 minutes to index, four of them consumes 40% of the entire build
window before a line of agent code runs.

*Test:* pull one Al Jazeera clip from the archive, index it, time it. Nothing else on this
list is worth doing first.

### 6 · Which TwelveLabs model, exactly?

Marengo 2.7 was sunset on 30 March 2026. Pull the live model list rather than trusting any
code sample. Trap 11 in the desk's own record: model slugs drift.

### 7 · Strands or CrewAI?

An hour on a hello-world Strands agent with one tool decides it. Strands scores with the
hosts and speaks MCP; CrewAI is known and safe. If the hour goes badly, fall back and lose
nothing.

### 8 · Neo4j — cloud or local?

Neither stood up. Ten dummy nodes proves the connection and the driver before any real data
exists. Cheapest possible de-risking.

### 9 · Does the TTS voice actually render?

Hash the output and listen to it. A bad voice id returns HTTP 200 and silence, and the voice
carries the entire watchable moment.

---

## Corpus

### 10 · What Gatwick data does Enid already hold?

John has said there is sample data in Enid covering Gatwick. Nobody has looked at what is
actually in it. It is the third source in the reconciliation — the covenant ground truth —
and it decides how much we build versus reuse.

### 11 · Which four clips?

Proposed: two from the Al Jazeera rolling coverage of the drone shutdown as it happened, one
from the BBC documentary, one from the pandemic period. Not yet pulled or reviewed.

### 12 · Covenant figures by year

Senior ICR and Senior RAR across the relevant years, plus the 2021 waiver, from the published
accounts. These are the ground truth the graph resolves to. We have 2018 (3.59×, down from
3.96×) and the waiver; the years between are not yet gathered.

### 13 · Does the drone open the video, or the pandemic?

The drone is the better footage and the wrong answer. Opening on it and then overturning it
is the strongest three minutes available — and the most complicated, in a format where the
moment must land in the first fifteen seconds. **Undecided.**

---

## Not yet asked

- Is anyone else on the team for this one? Andrew Lewis is on the DataHub team; nothing has
  been said about Thursday.
- Does the venue have reliable wifi, and does the demo survive without it? The desk's own
  record says keep a local copy of the moment that plays with no network.
