# The data model

*Proposed, for the 30 July hackathon. Built from public sources only.*

> **Scope note — corrected 29 July.** An earlier version of this note claimed that nothing
> here reproduced Enid table names, column names or vocabularies. **That claim was false**,
> and an audit found it contradicted by this file's own concept section. The accurate
> position:
>
> - **Clean:** Enid's trust-grading ladder appears nowhere, in any form. Neither do its
>   table names, its provenance constraints, or its medallion pipeline.
> - **Present, and pending John's decision:** the column names `covenant_code`,
>   `unit_kind` and `canonical_scale`; the `unit_kind` and `scale` term sets, which are
>   subsets of Enid's SQL CHECK lists; and the concept codes `cta_senior_icr`,
>   `cta_senior_rar`, `cta_senior_net_debt`.
> - **Mitigating:** Senior ICR, Senior RAR and Common Terms Agreement are publicly
>   disclosed Gatwick covenant terminology. Only the `cta_` prefix convention is Enid's.
>
> The repository is private. Nothing above is exposed, and none of it is settled — the line
> between "public financial term" and "Enid identifier" is John's to draw, not this file's
> to assume.

---

## The question the graph exists to answer

> **Which of these events actually threatens the debt — and where did every number come from?**

Two halves that pull in different directions. The first wants a **spine**: events connected
through to the ratio the bonds are tested on. The second wants a **ledger**: every claim
traceable to the second of video or the page of a filing it came from.

They reconcile if **Claim is the centre**. A Claim points backwards to its evidence and
forwards to what it affects. One node type, both jobs.

---

## The idea this is actually testing

Credit systems are built for a **controlled document supply chain** — things the lender is
sent: signed agreements, audited accounts, compliance certificates. Every one arrives from a
known party who is accountable if it is wrong.

**News footage is none of those things.** Nobody sent it. Nobody is on the hook for it. It
was not produced for the lender and it carries no obligation to be right.

So the hackathon question is not "can we put video in a graph." It is:

> **How does a credit graph admit external, third-party, uncontrolled observation without
> letting it contaminate the record?**

That is the contribution, and it is worth building because the answer is not obvious.

### Why it is worth having at all: observed data is *early*

The controlled document is authoritative and **late**. Audited accounts reflecting the
runway decision arrive many months after the decision. The broadcast is unauthoritative and
**immediate** — it exists the same afternoon.

```
Sep 2025   news reports the runway approval          ← observed, weak, immediate
Jun 2026   court dismisses the challenge             ← observed, weak, immediate
     ?     accounts reflecting the capex land        ← controlled, strong, late
```

**The lead time is the product.** An observed signal cannot change a covenant test, but it
can tell you which covenant test to go and look at, months before the document that settles
it exists. That is a real thing a credit desk would want and it needs no internal IP to
demonstrate.

---

## The two provenance classes

One axis, and it is the whole design:

| Class | Meaning | Examples | May become a Fact? |
|---|---|---|---|
| **`controlled`** | Produced by an accountable party in the deal's document chain | Published accounts, bond prospectus, RNS announcement, court judgment | **Yes** |
| **`observed`** | Third-party observation nobody in the deal produced or warrants | News broadcast, rally footage, commentary, web article | **Never** |

Deliberately two values, not a ladder. A finer ranking is a different conversation and is not
needed to make Thursday's point.

### The rule

> **An `observed` source can never produce a `Fact`. It produces only an `Observation`.**

An Observation may **corroborate**, **contradict**, or **flag** a Fact. It may never become
one, and it may never be what a covenant test reads.

This is enforceable rather than aspirational:

```cypher
// integrity check — must return zero rows
MATCH (f:Fact)-[:FROM]->(s:Source {provenance_class:'observed'}) RETURN f;
```

---

## Nodes

| Node | What it is | Key properties |
|---|---|---|
| `Source` | One retrievable thing | `id`, `provenance_class`, `kind`, `url`, `publisher`, `published_at`, `retrieved_at`, `sha256` |
| `Segment` | A timecoded span of a video | `video_id`, `start`, `end`, `transcript` |
| `Observation` | An assertion from an `observed` source | `text`, `value`, `unit`, `currency`, `confidence`, `modality` |
| `Fact` | An assertion from a `controlled` source | `value`, `unit`, `currency`, `as_of`, `effective_date` |
| `Concept` | What is being measured or named | `code`, `name`, `unit_kind`, `canonical_scale`, `aliases[]` |
| `Event` | Something that happened on a date | `name`, `date`, `kind` |
| `Deal` | The lending relationship | `legal_name`, `borrower`, `issuer`, `deal_type`, `currency`, `inception_date`, `final_maturity` |
| `Facility` | A tranche within the deal | `facility_code`, `label`, `facility_type`, `governing_doc`, `citation` |
| `Covenant` | A tested financial condition | `covenant_code`, `threshold_value`, `direction`, `test_frequency`, `test_dates[]` |
| `ExtractionRun` | One model pass that produced nodes | `model`, `version`, `prompt_hash`, `tokens_in/out`, `cost_usd`, `started_at` |

### The Deal lane, which the first draft missed entirely

A covenant does not belong to Gatwick. **Somebody lent Gatwick the money, and they are who
wrote the covenants and agreed them.** The condition attaches to the lending relationship, not
to the borrower — so `Deal → Facility → Covenant` is its own lane, sourced from the deal
documents rather than from either the news or the accounts.

This matters for the demo because it is the answer to "says who?". A threshold with no
`Facility` behind it, and no `governing_doc` on that Facility, is a number somebody typed in.

`Segment` is separate from `Source` on purpose. An Observation evidenced by "Channel 4 News,
somewhere" is worthless. One evidenced by "Channel 4 News at 4:31–4:38" seeks the playhead to
the proof. **The timecode is the product.**

`ExtractionRun` exists so every generated node can be traced to the model and prompt that made
it — and so cost is visible. It is also the honest answer to "did a human write this or did a
model?"

---

## Edges

```cypher
(:Segment)-[:PART_OF]->(:Source)
(:Observation)-[:CITES {start, end, bbox, modality}]->(:Segment)
(:Observation)-[:FROM]->(:Source)
(:Fact)-[:FROM]->(:Source)                          // controlled only — enforced
(:Observation|:Fact)-[:OF_CONCEPT]->(:Concept)
(:Observation)-[:CORROBORATES|CONTRADICTS {basis}]->(:Observation|:Fact)
(:Observation|:Fact)-[:ABOUT]->(:Event)
(:Observation|:Fact)-[:PRODUCED_BY]->(:ExtractionRun)

// the deal lane
(:Deal)-[:HAS_FACILITY]->(:Facility)-[:GOVERNED_BY]->(:Covenant)
(:Source {provenance_class:'controlled'})-[:EVIDENCES]->(:Deal)

// consequence — two verbs, deliberately different
(:Event)-[:MAY_AFFECT {asserted_by, status, rationale, validated_by, validated_at}]->(:Covenant)
(:Fact)-[:TESTS]->(:Covenant)                       // only Facts test covenants
```

Note the asymmetry between `MAY_AFFECT` and `TESTS`. An Event *may affect* a Covenant — a
judgement, hedged, and reversible. A Fact *tests* it — a computation. Different verbs because
they carry different weight, and blurring them is how a demo starts lying.

### The model guesses; a human decides

Asking a model *"which covenant could this news event threaten?"* is the interesting question
and the dangerous one. So `MAY_AFFECT` splits the two acts rather than blending them:

| Property | Values | Who may write it |
|---|---|---|
| `asserted_by` | `model` \| `human` | — |
| `status` | `proposed` \| `validated` \| `rejected` | model may only write `proposed` |
| `rationale` | free text | whoever asserted |
| `validated_by`, `validated_at` | who signed it off, and when | human only |

**No query that computes anything reads a `proposed` edge.** It is visible, it is dashed on
screen, and it is inert until a human moves it.

And a rejected guess is **kept, not deleted**:

```cypher
// what the model proposed, and what a human made of it
MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant)
RETURN e.name, c.covenant_code, m.asserted_by, m.status, m.rationale, m.validated_by;
```

That query is the honest one. Every other team will show a model asserting something. Showing
the model assert, then showing a human overrule it — with both preserved and
distinguishable — is the part a credit audience will believe.

### `modality` and the trap under it

`modality` takes `spoken`, `on_screen_text`, or `visual`. It is the field the demo turns on
— and it is the one **TwelveLabs cannot be trusted to fill.** In testing, Pegasus labelled
demonstrably spoken content as on-screen text and then asserted that *nothing* was spoken
aloud. Derive `modality` by cross-checking the search transcript against a separate
OCR-focused prompt, and record `confidence` honestly. Never take one prompt's word for it.

---

## Worked example — the real corpus

```cypher
// observed: weak, immediate, timecoded
(:Observation {text:'Second runway scheme costs £2.2bn', value:2.2e9, currency:'GBP'})
  -[:CITES {start:26.5, end:35.9, modality:'on_screen_text'}]->
  (:Segment {video_id:'KLnxVX-m-Ng'})-[:PART_OF]->
  (:Source {provenance_class:'observed', publisher:'The London Standard'})

// observed: and the sources disagree with each other
(jobs:Observation {text:'Expansion creates 14,000 jobs', value:14000})
(:Observation {text:'Job figures overstated; aviation is automating'})
  -[:CONTRADICTS {basis:'employment methodology'}]->(jobs)

// controlled: late, authoritative, and the only thing that tests anything
(:Fact {value:2.5e9, currency:'GBP', as_of:date('2026-02-10')})
  -[:FROM]->(:Source {provenance_class:'controlled',
                      kind:'prospectus', publisher:'Gatwick Funding Ltd'})
  -[:TESTS]->(:Covenant {name:'Senior debt ratio'})
```

### The three queries that make the case

```cypher
// 1. Where did this number come from, and may we believe it?
MATCH (o:Observation)-[c:CITES]->(s:Segment)-[:PART_OF]->(src:Source)
WHERE o.value = 14000
RETURN src.publisher, src.provenance_class, s.start, s.end, c.modality, o.confidence;

// 2. What do our sources disagree about?
MATCH (a)-[x:CONTRADICTS]-(b) RETURN a.text, x.basis, b.text;

// 3. What is the covenant actually tested on?
MATCH (f:Fact)-[:TESTS]->(c:Covenant), (f)-[:FROM]->(src:Source)
RETURN c.name, f.value, src.publisher, src.provenance_class;
```

Query 3 returns **no observed sources at all**, by construction — no `Fact` exists for a
covenant to be tested on. The water outage — the loudest, most recent, most watched event in
the corpus — does not appear in it.

Since 29 July the outage does have exactly one path to a `Covenant`: a `MAY_AFFECT` edge the
model proposed, claiming the outage could lower interest cover. That edge is inert. It is not
a `Fact`, it carries `status='proposed'`, and no computation reads it. **A model may gesture
at a covenant. It may not reach one.**

**The graph excludes the loud event by structure rather than by opinion.** That is a stronger
argument than any narration, and it is the moment worth demoing.

---

## Where the data comes from — all public

| Node | Public source |
|---|---|
| `Observation` | The six broadcast clips in `video/`, via TwelveLabs |
| `Source` (controlled) | Gatwick Funding Ltd prospectus and supplement (London Stock Exchange RNS) |
| `Fact` | Published Gatwick accounts, filed and public |
| `Covenant` | Disclosed covenant terms in the bond documentation |
| `Event` | DCO grant 21 Sep 2025; High Court ruling 23 Jun 2026 — both matters of record |

A judge can check every one. That is worth more in a three-minute demo than any figure they
would have to take on trust.

---

## Concepts — proposed pick

Nine concepts, chosen to make one unbroken chain from footage to covenant. Codes and the
`unit_kind` / `canonical_scale` idea follow an existing internal catalogue, reviewed with John
on 28 July; the ratio definitions themselves are disclosed in Gatwick's public bond
documentation.

| Code | Unit | Why it earns a place |
|---|---|---|
| `passenger_traffic` | `count` | **The hinge.** The only concept both a news clip and a set of accounts genuinely talk about |
| `air_traffic_movements` | `count` | Second operational measure; corroborates or contradicts the first |
| `revenue_per_passenger` | `currency` | Turns traffic into money — the step that makes the chain a chain |
| `scheme_cost` | `currency` | The £2.2bn every clip states. Observed only |
| `jobs_claimed` | `count` | The 14,000 the sources disagree about. Observed only, and the point of `CONTRADICTS` |
| `cta_senior_net_debt` | `currency` | Numerator of the debt ratio |
| `cta_senior_icr` | `ratio_x` | Senior interest cover — a covenant |
| `cta_senior_rar` | `percent` | Senior debt ratio — the other covenant |
| `two_pct_rab_deduction` | `currency` | Part of the ICR definition; included so the ratio is derivable rather than asserted |

**`ratio_x` and `percent` are different `unit_kind`s and must stay that way.** ICR is a
multiple with a floor; RAR is a percentage with a ceiling. Conflating them inverts the answer,
which is why `direction` (`min` / `max`) sits on the Covenant.

`scheme_cost` and `jobs_claimed` are invented for this corpus — they are the two figures the
broadcasts actually assert, and neither appears in a set of accounts. That asymmetry is the
point: **the concepts the video can reach and the concepts a covenant is tested on barely
overlap, and `passenger_traffic` is nearly the whole overlap.**

## Still open

- **Where the covenant thresholds come from.** They are agreed in the deal documentation and
  disclosed publicly for a listed bond. Which filing carries the current levels — prospectus,
  supplement, or accounts — is not yet established, and John is asking the Enid side where
  these already exist rather than re-deriving them.
- **Concept aliasing.** "London Gatwick" / "Gatwick Airport Ltd" / "LGW" are one Concept.
  Currently a hand-written alias list. Whether anything more is needed is John's call.
- **Which covenant figures** to load, and from which filing. Public, but not yet gathered.
- **Observation extraction.** Which model turns a Pegasus paragraph into discrete
  Observations with values and units. Novita is wired and its configured model does not
  support strict JSON schema, only `json_object` — so validation is on us.
- **Whether `MAY_AFFECT` is asserted by a human or a model,** and how that is recorded.
  Leaning human-asserted for the demo, because a model guessing at covenant impact is exactly
  the kind of thing that should not be automated in front of a judge.
