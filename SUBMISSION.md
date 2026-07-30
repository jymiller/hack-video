# Submission — Material Witness

Copy-paste source for the Hacker Squad form. Everything here is checked against the code.

---

## PROJECT.NAME

```
Material Witness
```

---

## PROJECT.README

Paste this. It is deliberately short — the organisers said reviewers skip walls of generated text.

```
Credit systems run on a controlled document supply chain: things a lender is sent by
somebody accountable. News footage is none of that. So what is video actually worth to
a credit desk?

Material Witness indexes six UK broadcasters covering Gatwick's second runway with
TwelveLabs, extracts entities, topics and timed segments with GPT-5.6, and builds a
Neo4j graph whose schema encodes the answer rather than decorating it.

Sources are controlled or observed. Observed sources produce Observations and may never
produce a Fact or supply a covenant number. Measured, not asserted: 106 links between
video and concept across six broadcasters, and zero reach either covenant.

The useful half is the bridge. Observations attach to Risk nodes — channels of exposure
like capital programme delivery — and covenants are exposed to the same risks. Risk is a
sink: both arrows point in, so reaching a covenant means traversing that edge backwards,
in the query text, in front of the person being asked to believe it. Video can move where
an analyst looks. It can never move what they read.

A model may only ever propose. Every proposal is inert until a human signs it, and a
rejection is kept, not deleted. On 29 July the model claimed an eleven-hour water outage
could hit the interest cover ratio. A human rejected it, signed and timestamped, and that
"no" is still in the graph.

A Strands agent on GPT-5.6 answers questions over the graph with five read-only tools.
Ask it which covenant has least headroom and it says Senior RAR, 12.9%, from the
borrower's own audited accounts — then refuses to let any footage speak to a breach.
```

---

## PROJECT.STACK

Verified by grepping the repo, not by memory.

| Checkbox | Verdict | Where |
|---|---|---|
| **TwelveLabs** | tick | Marengo + Pegasus indexing, search, 512-dim embeddings, Jockey knowledge store — `server.py`, `graph/load.py`, `graph/embed.py`, `graph/knowledge_store.py` |
| **OpenAI** | tick | GPT-5.6 Terra (agent) and Luna (extraction), Responses API + structured outputs — `graph/agent.py`, `graph/entities.py` |
| **Neo4j** | tick | 231 nodes / 651 relationships, vector index, 30 files touch it |
| **Strands Agents** | tick | `OpenAIResponsesModel`, 5 read-only tools — `graph/agent.py` |
| **AWS** | **untick it** | see below |

**Untick AWS.** `grep` finds zero direct uses — no boto3 call, no Bedrock invoke, no AWS
service in the runtime path. Strands is an AWS open-source project and that is already
covered by the Strands checkbox. `aws-bedrock-token-generator` is present only as a
transitive dependency of `strands-agents[openai]` and is never called.

Given this project's entire argument is that provenance should be honest, claiming a
vendor we do not call is the wrong first impression. Leaving it ticked is also the kind of
thing a judge checks.

**other stack** — replace with:

```
Render, Neo4j Aura, You.com
```

---

## GIT.REMOTE

```
https://github.com/jymiller/hack-video
```

Live app: https://hack-video-v6kg.onrender.com

---

## Recording script — 90 seconds, no demo page needed

Record this today against what already works. Screen share plus camera. Re-record freely;
judges only see the latest.

**Before you hit record:** hard-refresh every tab (`Cmd+Shift+R`), set macOS Appearance to
Light, and hit the Render URL once to wake it — free tier sleeps after 15 minutes and the
cold start is ~50 seconds.

| Time | On screen | Say |
|---|---|---|
| **0:00–0:12** | Your face | "Credit runs on documents somebody is accountable for. News footage is not that. So I spent two days asking what video is actually worth to a credit desk — and building the answer as a graph." |
| **0:12–0:30** | Video page. Search already reads *jobs created by the expansion*. Click rank 1. | "Six UK broadcasters on Gatwick's second runway, indexed with TwelveLabs. I ask in English, and it takes me to the second Channel 4 says the number." *(let the clip say "two point two billion pounds")* |
| **0:30–0:48** | Graph page, coverage table | "Every claim is linked to the concept it bears on. A hundred and six links, six broadcasters. And on the two covenant rows — zero. Not a gap. News does not carry covenant data, and a system that pretended otherwise would be lying." |
| **0:48–1:08** | Graph page, the risk chain | "So here is the useful half. Observations attach to risks — channels of exposure. Covenants are exposed to the same risks. But risk is a sink: both arrows point in. To get from footage to a covenant you traverse that edge backwards, and you can see it in the query. Video moves where I look. It never moves what I read." |
| **1:08–1:26** | Attestation panel — the rejected edge | "The model proposed that an eleven-hour water outage could hit interest cover. It could not: no flight was cancelled, the airport never closed. I rejected it, signed and timestamped — and the rejection is still there. Kept, and read by nothing." |
| **1:26–1:40** | Ask the graph → least headroom | "Ask which covenant is tightest and it says Senior RAR — twelve point nine per cent of headroom, from the borrower's own audited accounts. Never from the footage." |
| **1:40–1:50** | Your face | "Strands and GPT-5.6 over TwelveLabs and Neo4j. The graph declines to bridge a gap that doesn't exist, and saying so is the product." |

**If a live call hangs**, keep talking and move on — every beat after the first reads from
the local graph and needs no network.

**One line to have ready** if a judge asks whether the containment is proven:

> "It has had exactly one live test — the water outage — and it held. I am not going to
> claim more than that. The corpus never mentions gearing or interest cover once, so the
> barrier has mostly been holding back material that was never going to reach a covenant."

That answer is worth more than a confident overclaim, and it is true.
