# hack-video

> ## ⚠️ WORKING DRAFT — nothing here is settled
>
> This repo is thinking-in-progress for a hackathon **two days away**. Ideas below are
> proposals, not decisions. Several rest on facts nobody has verified yet, and at least one
> will probably turn out to be wrong. **Read [`STATUS.md`](STATUS.md) before acting on any
> of it** — it separates what we know from what we have merely assumed.

Build repo for **Hack the Video Agent Context Graph** — Thursday **30 July 2026**,
AWS Builder Loft, 525 Market St, San Francisco.

Sponsors and tools: **OpenAI · Neo4j · AWS · TwelveLabs · Strands Agents**

---

## The event, in one table

| | |
|---|---|
| **Format** | In person, one day, San Francisco |
| **Doors** | 09:30 · talks 10:00 · **hacking opens 11:00** |
| **Gate 1** | **16:00 — submissions due** |
| **Gate 2** | **17:15 — demos and live judging.** Awards 19:00 |
| **Freeze** | **14:30** — the 16:00 submission minus 90 minutes |
| **Real build window** | **3 hours 30 minutes** |
| **Prizes** | Not announced. *"Prize categories and judging details are still to come"* |
| **Judging criteria** | Not published |
| **Team** | Solo or team |

**The build brief, from the organisers:** create a video agent that ingests raw video,
understands it across vision, audio and speech with TwelveLabs, and writes what it finds
into a Neo4j context graph — entities, scenes, tags, and the relationships between them.

### Why the freeze is 14:30 and not later

The agenda reads like a full day. It isn't. Two gates, and **the earlier one binds**: a
submitted artifact at 16:00 sets the freeze at 14:30, where the 17:15 demo alone would have
given 15:15. Getting that wrong costs 45 minutes of slack, and slack is the strongest
relationship in this desk's whole record.

---

## What we are proposing to build

**A video agent that watches news footage and works out whether it threatens a borrower's
loan covenants.**

The corpus is **London Gatwick Airport** — a real, publicly financed borrower with £2.5bn
of listed secured bonds through Gatwick Funding Ltd, disclosed covenants (Senior interest
cover ratio and Senior debt ratio), and two events extensively on video.

**And the two events point in opposite directions, which is the whole idea:**

| | The drone, Dec 2018 | The pandemic, from Mar 2020 |
|---|---|---|
| Coverage | Wall-to-wall, worldwide | Diffuse, months of it |
| Flights cancelled | ~1,000 | — |
| Passengers affected | ~140,000 | Traffic collapsed |
| **Cost to Gatwick** | **~£1.4m** | **~£2bn pre-tax loss, 2020** |
| **Covenant outcome** | **Nothing** | **Lenders waived Senior ICR and Senior RAR in Aug 2021** |

A system that reacts to the loudest footage gets this exactly backwards. One that follows
the footage through to passenger volumes, then earnings, then the ratio the bonds are
tested on, gets it right. **That is the argument for a context graph** — and every number
above is public and checkable.

---

## What's in here

| Document | Covers |
|---|---|
| [`STATUS.md`](STATUS.md) | **Read first.** Decided vs assumed vs unknown |
| [`docs/01-the-event.md`](docs/01-the-event.md) | The clock, the two gates, the gate surface |
| [`docs/02-the-corpus.md`](docs/02-the-corpus.md) | Gatwick, the credit structure, the trap case, the Internet Archive holdings |
| [`docs/03-the-vendors.md`](docs/03-the-vendors.md) | TwelveLabs and the rest, judged by the vendor test |
| [`docs/04-open-questions.md`](docs/04-open-questions.md) | Everything unresolved, by owner |
| [`docs/explainers/`](docs/explainers/) | The same material as visual HTML pages |

---

## Where the rest of it lives

Campaign Desk, the operations app that screens and plans these events, is in
[`jymiller/hackathon-prep`](https://github.com/jymiller/hackathon-prep).
The DataHub hackathon on 10 August has its own repo,
[`jymiller/hack-datahub`](https://github.com/jymiller/hack-datahub) — and if Gatwick works
here, it should replace the invented corpus over there too.
