# STATUS — read this before believing anything else

**As of 28 July 2026. The event is 30 July. We are two days out and in the working phase.**

The rest of this repo is written with more confidence than it has earned, because plans
read badly when hedged in every sentence. This file is where the hedging lives. Three
columns: what we actually know, what we have assumed, and what nobody has checked.

---

## Verified — checked against a source

| Fact | Source |
|---|---|
| Event is 30 July, 09:30–20:00, AWS Builder Loft, 525 Market St, in person | The event page |
| Hacking opens 11:00; submissions due 16:00; demos 17:15; awards 19:00 | The event page |
| Sponsors are OpenAI, Neo4j, AWS, TwelveLabs, Strands Agents | The event page |
| The brief: video in, Neo4j context graph out, via TwelveLabs | The event page, quoted |
| **No video or dataset is provided.** We bring our own | The event page |
| **Prizes and judging criteria are not announced** | *"Prize categories and judging details are still to come"* |
| TwelveLabs does OCR on on-screen text, plus audio and transcription | TwelveLabs modality docs |
| TwelveLabs free tier: 600 minutes shared across indexing, analysis, segmentation | TwelveLabs pricing |
| TwelveLabs free-tier index data is cleared after 90 days | TwelveLabs pricing |
| Marengo 2.7 was sunset 30 March 2026 | TwelveLabs release notes |
| Strands Agents is AWS's open-source agent SDK, model-agnostic, MCP native | strandsagents.com, AWS docs |
| Gatwick Funding Ltd has ~£2.5bn of listed secured bonds, maturities 2024–2050 | Gatwick financial statements |
| Senior ICR was 3.59× for the year ended 31 Mar 2018, down from 3.96×; Senior RAR 0.61 (2017: 0.51) | GAL ARFS March 2018 |
| Senior ICR: Trigger Event < 1.50, Loan Event of Default ≤ 1.10. Senior RAR: Trigger Event > 0.70, Loan Event of Default > 0.85. Tested 30 Jun and 31 Dec | Common Terms Agreement dated 15 Feb 2011, via the March 2019 and March 2021 base prospectuses |
| Two waivers, not one. The **22 September 2020 Amendments** waived both ratios at the Dec 2020 and Jun 2021 test points; the **Amendment and Waiver Agreement dated 8 September 2021** waived both at Dec 2021 and Jun 2022, on £2.8bn of reference net debt. August 2021 is when discussions began | Compliance certificate 31 Dec 2021 (signed CEO + CFO, dated 7 Mar 2022); March 2021 base prospectus; VINCI press release |
| Drone year FY March 2019 tested Senior ICR **2.93** and Senior RAR **0.59** — both clear, "all financial covenants have been tested and complied with". The word "drone" appears zero times in the 103-page report | Ivy Holdco Ltd Annual Report, y/e 31 Mar 2019 |
| Gatwick's own March 2019 prospectus puts the drone at **31 hours** and **164,000 fewer passengers**, with 115 sightings 19–23 Dec — not the ~33–36 hours / ~140,000 that ran on television | Gatwick Funding Ltd Base Prospectus, March 2019, "Drone Risk" |
| December 2020 tested ICR **(1.29)** / RAR **0.94** — both through Event of Default. December 2021 tested ICR **(1.49)** / RAR **0.81** — ICR through Default, RAR through Trigger only | Compliance certificate 31 Dec 2021; March 2021 base prospectus |
| 894 items match Gatwick in the Internet Archive's film collections | Live `ia` search, 28 July |
| The archive holds BBC's *The Gatwick Drone Attack* and Al Jazeera's hour-by-hour coverage of the shutdown | Live `ia` search, 28 July |
| The `ia` CLI is installed and working locally | Run directly |

## Refuted — checked on 30 July, and wrong

Full working in [`docs/07-the-counter-example.md`](docs/07-the-counter-example.md).

| What this repo carried | What the filings say |
|---|---|
| **"Gatwick's 2020 pre-tax loss was around £2bn"** — carried since the first commit | **£2.01bn is Heathrow's number.** Gatwick's Security Group (Ivy Holdco Ltd consolidated) reported loss before tax of **£525.9m** in 2020 and **£368.7m** in 2021 — under £900m combined. Out by roughly 4x, and borrowed from a competitor |
| "The lenders waived in August 2021" | Imprecise on both counts. The agreement is dated **8 September 2021**; August is when discussions started. And there were **two** waivers — the 22 September 2020 one covers the worse breach |
| "~£1.4m cost to Gatwick" stated flat | **News-only and contested.** The Guardian, 18 June 2019. It does not appear in Gatwick's annual report, and airport-technology puts it at £15m unattributed. Attribute it or drop it |
| "The covenant is 1.50" | Incomplete. 1.50 is the **Trigger Event** (cash lock-up). The **Loan Event of Default** is 1.10. Same for RAR: 0.70 trigger, 0.85 default |
| "Senior RAR 0.61, 12.9% headroom" quoted without a date | Arithmetically right, but it is the **31 March 2018** vintage. Say the date, or use 31 March 2019 (0.59 and 2.93) |

## Assumed — reasonable, but not established

| Assumption | If it's wrong |
|---|---|
| The 16:00 submission is a real gate that binds the freeze | If 16:00 is soft, we get 45 more minutes. If it needs a video, we need far more time than planned |
| Gatwick is a good corpus because Enid already holds data on it | John said so; nobody has looked at what is actually in there yet |
| Four videos is the right corpus size | Rests entirely on indexing time, which is unmeasured |
| A news-event-to-covenant chain is legible to a judge in three minutes | Untested. It is two inferential hops, which may be one too many |
| Using Strands scores points because AWS hosts and judges | Reasonable at a sponsor event, but the criteria are unpublished so this is inference |
| The drone-versus-pandemic contrast is the best opening | It is the most interesting thing we have. It is also the most complicated. **Stronger since 30 July**: both sides are now sourced to filings — 2.93 / 0.59 clear in the drone year, −1.49 / 0.81 at December 2021 |
| Precise Gatwick passenger figures | ~~Sources conflicted.~~ **Settled 30 July for the drone**: Gatwick's own March 2019 prospectus says 164,000 fewer passengers. The news figure of ~140,000 is a different number for the same event — quote whichever, but say which document it came from |

## Unknown — nobody has checked

| Question | Why it matters |
|---|---|
| **How long does TwelveLabs take to index an hour of video?** | The single most likely way a 3h30m build ends with nothing on screen |
| **Is pre-built work allowed?** | Decides whether we index Wednesday or lose an hour Thursday |
| **What must the 16:00 submission contain?** | Shapes the last two hours of the build |
| What are the prizes, cash or credits? | Cannot rank this against anything else on the calendar |
| What are the judging criteria? | Changes where the hours go |
| Is registration confirmed, or is the link an invite? | Everything else is wasted if this is wrong |
| What Gatwick data does Enid actually hold? | Decides how much we build versus reuse |
| Does the current TwelveLabs model handle news footage well? | Marengo 2.7 is gone; the replacement is untested by us |
| Neo4j — cloud instance or local? | Neither stood up yet |

---

## What is decided

Only two things, and both are reversible:

1. **The corpus is Gatwick**, not the invented Meridian company from the DataHub work.
   Real, public, checkable, and on video.
2. **The moment is carried on sound** — a voice stating the finding over footage the judge
   is already watching. Not a graph animating, which this desk refuses as a chart redrawing.

Everything else is a proposal.

---

## The standing rules that do not move

- **Freeze at 14:30.** After it, only three moves are legal: SUBTRACT, SUBMIT, REHEARSE.
- **The watchable moment gets named before anything is built**, and building does not start
  until it is.
- **A number changing on screen is not a watchable moment**, and neither is any disguise of
  it — a counter, a badge, a chart redrawing, a graph blooming.
- **Absence is reported, never filled.** "Not stated" and "unknown" are valid answers;
  silence is not.
