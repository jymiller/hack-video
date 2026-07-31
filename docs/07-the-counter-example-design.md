# The counter-example — how it is modelled

*Design note, 30 July. Companion to [`07-the-counter-example.md`](07-the-counter-example.md),
which establishes the facts. This file establishes the shape.*

> **Validated, not asserted.** Every block of Cypher below was executed against a throwaway
> Neo4j 5.26.28 container seeded from this repo's own `graph/schema.cypher`,
> `graph/seed.cypher` and `graph/risk.cypher`. The loader runs clean, is idempotent
> (re-run → identical 125 nodes / 150 relationships), the invariant suite returns fifteen
> zeros, and each of its checks was proved to fire by deliberately injecting the violation it
> exists to catch. **Nothing was written to `hackgraph`.** Where a claim below is a
> recommendation rather than a measurement, it says so.

---

## 0 · The one-paragraph version

The demo's finding is a **zero**: no video evidence reaches either covenant. A zero is only
worth showing if the same machinery can be seen reaching a covenant when the evidence is
admissible. It can, and the real Gatwick record supplies it: two covenant breaches at
Calculation Dates in December 2020 and December 2021, both evidenced by filings, both waived
by the secured creditors, and **both still on the record after the waiver**. This note
specifies that as: `:Threshold` nodes with a validity window, breach as an **edge** from a
`:Fact` to a `:Threshold`, and a waiver as a **triangle that closes over** that edge without
touching it. The provenance invariant survives untouched, and gets stronger — because a
breach can only ever hang off a `:Fact`, and a `:Fact` can only ever come from a controlled
source.

---

## 1 · Test vs Fact — the collision, and the recommendation

### The recommendation: **keep `(:Fact)-[:TESTS]->(:Covenant)`. Do not introduce `:Test`.**

The Enid model at `/Users/johnmiller/Downloads/covenant-graph-hackathon.md` uses
`(:Test {period_end, observed})-[:TESTS]->(:Covenant)` and derives headroom onto the `:Test`
node. It is a good model *for that graph*. It is the wrong one here, for a reason that is
specific to this repo's thesis rather than a matter of taste:

> **A `:Test` node is a value-bearing node with no provenance edge.** In the Enid seed its
> basis is a free-text string (`t.basis = 'ILLUSTRATIVE — constructed for this
> demonstration'`). This graph's entire argument is that a number reaching a covenant must be
> traceable to an accountable party. `:Fact` is the only node type in the graph with a
> mandatory `[:FROM]->(:Source)` edge. Adding a second, weaker one next to it opens exactly
> the hole the invariant exists to close.

So: **a covenant test *is* a Fact with a period end.** The history comes from having more
Facts, one per Calculation Date, each with its own controlled Source. The derived quantities
Enid puts on the `:Test` node go on the `TESTS` **edge** instead — which is where they belong
anyway, because headroom is a function of *both* endpoints, not a property of either.

### The collision, stated precisely — and measured

If both models coexist and both use `:TESTS`, the damage is **not** a false alarm. It is a
**silent false negative**, and it lands in the one query the repo relies on.

`graph/risk.py:162` is the guard:

```cypher
MATCH (:Covenant)<-[:TESTS]-(f:Fact)-[:FROM]->(s:Source)
WHERE s.provenance_class <> 'controlled' RETURN count(*) AS n
```

It is label-guarded on `f:Fact`. A `:Test` node is not a `:Fact`, so it **never enters the
match at all**. Measured, in the throwaway container: with an Enid-style `:Test` node carrying
`observed: 0.40` — a catastrophic breach — sitting on a `:TESTS` edge into `senior_icr`, with
no `:FROM` edge and no source of any kind, that query returns:

```
n
0
```

The check passes. It reports the graph is clean. It is not clean.

The second casualty is `graph/risk.py:176`, the case analysis over every edge incident on a
Covenant. Same injection, actual output:

```
type, other, n
"TESTS", "Test", 1
"TESTS", "Fact", 8
```

…which the hardcoded note dict at `graph/risk.py:179` then annotates with
`"TESTS": "carries a number — controlled lane only"`. **The verification tool prints a false
statement about the node that violates the thing it is verifying.** That is worse than no
check.

Third casualty, non-technical: `docs/05-the-data-model.md:154` states the rule in a comment —
`(:Fact)-[:TESTS]->(:Covenant)  // only Facts test covenants`. That sentence simply becomes
untrue, and it is one of the lines the demo argues from.

### If someone adds `:Test` anyway, this is the check that catches it

Not label-guarded, so it cannot be evaded by arriving with a new label:

```cypher
MATCH (x)-[:TESTS]->(:Covenant) WHERE NOT x:Fact RETURN count(*) AS n;   // must be 0
```

Verified: returns `1` with the injected `:Test` node present, `0` after removing it. It is
check 3 in §5.

### A second collision the brief did not name: `:NEXT`

Enid chains periods with `(:Test)-[:NEXT]->(:Test)`. **`:NEXT` is already taken in this graph
— 57 edges, all `Segment→Segment`** (measured on `hackgraph`). Reusing it makes "walk the
chain" return two unrelated kinds of thing interleaved, with no error. The period chain below
uses **`:SUCCEEDED_BY`**.

---

## 2 · Breach as an edge

Adopted from Enid, unchanged in spirit: `(:Fact)-[:BREACHED]->(:Threshold)`, never a boolean.
"In lock-up but not in default" becomes one edge present and another absent — a shape on a
projector — rather than a comparison a human has to perform correctly twice.

Two things this design adds on top.

**(a) The tail is a `:Fact`, and that is load-bearing.** A breach cannot be evidenced by
anything that is not a Fact, and a Fact cannot come from an observed source. The breach
inherits the provenance guarantee rather than needing its own. No new enforcement machinery —
one query proves it (§5).

**(b) `breach_test` is per-threshold, and is not derivable from `direction`.** Enid's model
assumes on-the-line always passes. The actual Gatwick drafting is asymmetric:

| Covenant | Trigger Event | Loan Event of Default |
|---|---|---|
| Senior ICR | `< 1.50` — on the line **passes** | `≤ 1.10` — on the line **fails** |
| Senior RAR | `> 0.70` — on the line **passes** | `> 0.85` — on the line **passes** |

Three of four are strict; one is not. A single global convention gets that wrong silently, at
the exact boundary where it costs the most. So each `:Threshold` carries
`breach_test ∈ {strictly_worse, at_or_worse}` and the breach derivation reads it.

### The shape, on real data

Measured output for Calculation Date 31 December 2021:

```
covenant,     observed, tier,      level, state,      by
"senior_icr", -1.49,    "default", 1.1,   "BREACHED", 2.59
"senior_icr", -1.49,    "lock_up", 1.5,   "BREACHED", 2.99
"senior_rar",  0.81,    "default", 0.85,  "intact",   NULL
"senior_rar",  0.81,    "lock_up", 0.7,   "BREACHED", 0.11
```

**On one test date, one covenant is through both tiers and the other is through the lock-up
only.** Three red edges and one conspicuous gap. That is stronger than the Enid demo's
picture, which had both covenants in the same state — and it is real rather than constructed.

---

## 3 · The waiver — the genuinely new part

A waiver exists in neither model. It is a controlled document, it has a date, it has parties,
it has a price, and **it changes the consequence of a breach without changing the fact that
the breach happened.**

### The shape: a triangle that closes over the breach edge

Neo4j cannot point an edge at an edge, so a waiver binds to both endpoints of the breach:

```
        BREACHED
  (:Fact) ───────────────► (:Threshold)
      │                         ▲
      │ WAIVED_BY               │ WAIVES
      └──────► (:Waiver) ───────┘
```

A breach is covered **if and only if the triangle closes.** Both edges are required and
neither alone waives anything. No false triangle can form, because the `BREACHED` edge has
already pinned the exact `(Fact, Threshold)` pair — a waiver naming a different covenant, or a
different tier, or a different test date, simply leaves the triangle open, and that is visible
rather than argued.

**The `BREACHED` edge is never touched.** Measured: deleting the entire `:Waiver` node and all
its edges leaves the breach count at `7`, unchanged; restoring it leaves it at `7`.

Both edges are scoped **from the instrument**, never inferred. A blanket cartesian product of
waiver × threshold was the first draft and is wrong as a pattern: it makes every waiver look
like a blanket one, and a waiver that covered one covenant and not the other would be
mis-modelled as covering both.

### A waiver is priced, and the price is the interesting part

The September 2020 instrument is the good example, and its conditions go on the node as a
list, because *this is what a waiver actually costs*:

- quarterly information packages to secured creditors, Sept 2020 → June 2021
- Available Cash less Required Expenditure below **£225m** → a remedial plan is required
- below **£150m**, failure to provide or execute that plan is **itself a Loan Event of
  Default** — the waiver creates a new default trigger while suspending an old one
- no Restricted Payments before 31 December 2021; thereafter a tighter Senior RAR
  distribution test (0.60 to June 2022, then 0.65, adjusted basis)

`w.consequence_after` supersedes `h.consequence` for covered dates, and every read does
`coalesce(w.consequence_after, b.consequence)` so the un-waived case needs no special path.

### A waiver granted before its test date covers tiers that may not break — and that is correct

The 8 September 2021 agreement covers the 31 December 2021 Calculation Date. At the moment of
grant nobody knew which tiers would break. So `senior_rar#default` is inside the waiver's scope
and was never breached.

This killed a check in my first draft — *"waiver covering a breach that does not exist"* — which
fired 9 times on correct data. **It is not an invariant. It is the normal state of a
prospective waiver.** It has been replaced (§5) with checks that are actually invariant:
the waived date must be one the instrument names, and the `WAIVES` tier must match the
threshold's tier.

### Three kinds of consent, and only one of them is a waiver

The real September 2021 instrument is an *"Amendment and Waiver Agreement"*. Modelling it as a
waiver alone would misrepresent the document. The three are structurally different and the
graph should not blur them:

| Kind | What moves | How it is modelled |
|---|---|---|
| **waiver** | the consequence, for named test dates | `:Waiver` + the triangle. Breach stands, level stands. |
| **threshold amendment** | the level, prospectively | close the `:Threshold` (`effective_to`), open a successor. Historic tests keep their level. This is Enid's step-down. |
| **calculation amendment** | how the observed ratio is *computed* | `:Amendment {kind:'calculation_amendment'}` hanging off the `:Fact`. Neither breach nor level moves. |

**The third kind is in neither model, and it is the one Gatwick actually did** — pandemic-quarter
EBITDA replaced with the 2017/2018/2019 average in the Senior RAR calculation, until June 2024.
Block 10 of the loader is that, and it is marked cuttable if the demo needs to be smaller.

It also disciplines a real trap: the December 2020 RAR of **0.94 is stated *without* the agreed
adjustments**. The Fact carries `calculation_basis` saying so, or the graph reports a number
under a basis it was not computed on.

### Verified: the threshold amendment mechanism, and a bug it exposed in my own draft

Applying a step-down (close `senior_rar#lock_up` at 2020-12-31, open a successor at 0.75 from
2021-01-01), then re-running the loader **twice**:

```
id,                              v,    from,         to
"senior_rar#lock_up#2011-02-15", 0.7,  "2011-02-15", "2020-12-31"
"senior_rar#lock_up#2021-01-01", 0.75, "2021-01-01", "9999-12-31"
```

Historic tests kept their original level; only the test inside the new window re-graded. But
that only works because of a fix: **`MERGE … SET x.effective_to = date('9999-12-31')` re-opens
a level an amendment has closed**, silently, on the next run — I hit this and measured it
(both windows open, headroom non-deterministic, the amendment gone). The window must be
`ON CREATE SET`. It is, in block 3, with a comment saying why.

That episode also produced a real invariant: **two thresholds of one tier in force at once**
(check 14). And a second one, which fired legitimately after the step-down: the legacy
`Covenant.threshold_value` scalar is now a *second source of truth* and it drifts. Check 15
catches it. See §7 for why the scalar has to stay anyway.

---

## 4 · The loader

Community-safe throughout: **`UNIQUE` constraints and range indexes only.** No `NODE KEY`, no
`IS NOT NULL` — both are Enterprise and, as `graph/schema.cypher:6-8` already notes, abort the
whole file at the first one.

Save as `graph/covenant_history.cypher`, run after `graph/seed.cypher`.

```cypher
// graph/covenant_history.cypher — periods, thresholds, breach, waiver.
// Additive to schema.cypher + seed.cypher. Idempotent; derived edges rebuilt each run.

// ---------------------------------------------------------------- 0. schema
CREATE CONSTRAINT fact_key      IF NOT EXISTS FOR (f:Fact)      REQUIRE (f.concept_code, f.as_of) IS UNIQUE;
CREATE CONSTRAINT threshold_key IF NOT EXISTS FOR (h:Threshold) REQUIRE h.threshold_id IS UNIQUE;
CREATE CONSTRAINT waiver_id     IF NOT EXISTS FOR (w:Waiver)    REQUIRE w.waiver_id    IS UNIQUE;
CREATE CONSTRAINT party_id      IF NOT EXISTS FOR (p:Party)     REQUIRE p.party_id     IS UNIQUE;

CREATE INDEX fact_as_of     IF NOT EXISTS FOR (f:Fact)      ON (f.as_of);
CREATE INDEX threshold_tier IF NOT EXISTS FOR (h:Threshold) ON (h.tier);
CREATE INDEX waiver_granted IF NOT EXISTS FOR (w:Waiver)    ON (w.granted_on);

// ---------------------------------------------------------------- 1. vocabulary
UNWIND [
  {n:'threshold_tier', d:'What crossing this level costs',
   t:[['lock_up','Trigger Event. Distributions to shareholders prohibited, extra disclosure in Investor Reports. Not a default.'],
      ['default','Loan Event of Default. Acceleration risk, subject to the 30-day cure.']]},
  {n:'breach_test', d:'Whether landing exactly on the number breaches',
   t:[['strictly_worse','Breach only past the number. On the line passes.'],
      ['at_or_worse','Breach at the number. On the line fails.']]},
  {n:'consent_kind', d:'What a lender consent actually changes',
   t:[['waiver','The consequence is suspended for named test dates. The breach stands.'],
      ['threshold_amendment','The level itself changes prospectively. Historic tests keep their level.'],
      ['calculation_amendment','How the observed ratio is computed changes. Neither breach nor level moves.']]}
] AS v
MERGE (vo:Vocabulary {name:v.n}) SET vo.description = v.d
WITH vo, v UNWIND v.t AS term
MERGE (t:Term {vocabulary:v.n, value:term[0]}) SET t.description = term[1]
MERGE (vo)-[:HAS_TERM]->(t);

MATCH (vo:Vocabulary {name:'source_kind'})
UNWIND [['compliance_certificate','Borrower certificate of covenant compliance, signed by officers'],
        ['base_prospectus','Bond programme base prospectus']] AS term
MERGE (t:Term {vocabulary:'source_kind', value:term[0]}) SET t.description = term[1]
MERGE (vo)-[:HAS_TERM]->(t);

// ---------------------------------------------------------------- 2. sources
// All controlled. url_sha256 is left for graph/urls.py to fill — a Source with no
// hash is a Source nobody has actually fetched.
UNWIND [
  {id:'gal-compliance-cert-2021-12', kind:'compliance_certificate',
   publisher:'Gatwick Airport Limited and Ivy Bidco Limited',
   title:'Compliance Certificate for the Calculation Date 31 December 2021',
   as_of:date('2022-03-07'),
   signatories:'Stewart Wingate (CEO), Jim Butler (CFO)',
   addressed_to:'Deutsche Trustee Company Limited as Borrower Security Trustee',
   url:'https://www.gatwickairport.com/on/demandware.static/-/Sites-Gatwick-Library/default/dw6bbd5197/images/Corporate-PDFs/Reports%20financial%20/2022/Compliance%20certificate%20December%202021.pdf'},
  {id:'gfl-base-prospectus-2021-03', kind:'base_prospectus',
   publisher:'Gatwick Funding Limited',
   title:'Gatwick Funding Limited Base Prospectus, March 2021',
   as_of:date('2021-03-01'), signatories:null, addressed_to:null,
   url:'https://www.gatwickairport.com/on/demandware.static/-/Sites-Gatwick-Library/default/dw65b113d4/images/Corporate-PDFs/Reports%20financial%20/Prospectus/Gatwick_Funding_Limited_Base_Prospectus_March_2021.pdf'},
  {id:'ivy-holdco-ar-2019', kind:'accounts',
   publisher:'Ivy Holdco Limited',
   title:'Annual Report and Financial Statements for the year ended 31 March 2019',
   as_of:date('2019-03-31'), signatories:null, addressed_to:null, url:null}
] AS s
MERGE (x:Source {id:s.id})
SET x.provenance_class = 'controlled', x.kind = s.kind, x.publisher = s.publisher,
    x.title = s.title, x.as_of = s.as_of, x.url = s.url,
    x.signatories = s.signatories, x.addressed_to = s.addressed_to,
    x.basis = 'filed';

MATCH (s:Source) WHERE s.id IN ['gal-compliance-cert-2021-12','gfl-base-prospectus-2021-03','ivy-holdco-ar-2019']
MATCH (d:Deal {legal_name:'Gatwick Funding Limited'})
MERGE (s)-[:EVIDENCES]->(d);

// ---------------------------------------------------------------- 3. thresholds
// The two scalars already on :Covenant become nodes, one per tier, each with a
// validity window the headroom derivation genuinely filters on. The scalars STAY —
// graph/agent.py and both explainers read them — and check 15 proves they agree.
//
// breach_test is per-threshold and NOT derivable from direction. Senior ICR's
// Trigger is "< 1.50" but its Event of Default is "<= 1.10": a test landing exactly
// on 1.10 IS a default while one landing exactly on 1.50 is not.
UNWIND [
  {cov:'senior_icr', tier:'lock_up', value:1.50, test:'strictly_worse',
   consequence:'Trigger Event. Distributions to shareholders prohibited; additional ratio disclosure in Investor Reports; escalating consequences if it runs 12 months or more.',
   comparison:'Breach is Senior ICR < 1.50. A test landing exactly on 1.50 passes.', cure:null},
  {cov:'senior_icr', tier:'default', value:1.10, test:'at_or_worse',
   consequence:'Loan Event of Default. Acceleration risk.',
   comparison:'Breach is Senior ICR <= 1.10. A test landing exactly on 1.10 IS a breach.',
   cure:'No Loan Event of Default if, within 30 days of the Calculation Date, GAL procures Additional SP Contributions applied in prepayment of Senior Debt such that Senior RAR < 0.85 and Senior ICR > 1.10.'},
  {cov:'senior_rar', tier:'lock_up', value:0.70, test:'strictly_worse',
   consequence:'Trigger Event. Distributions to shareholders prohibited; additional ratio disclosure in Investor Reports.',
   comparison:'Breach is Senior RAR > 0.70. A test landing exactly on 0.70 passes.', cure:null},
  {cov:'senior_rar', tier:'default', value:0.85, test:'strictly_worse',
   consequence:'Loan Event of Default. Acceleration risk.',
   comparison:'Breach is Senior RAR > 0.85. A test landing exactly on 0.85 passes.',
   cure:'No Loan Event of Default if, within 30 days of the Calculation Date, GAL procures Additional SP Contributions applied in prepayment of Senior Debt such that Senior RAR < 0.85 and Senior ICR > 1.10.'}
] AS h
MATCH (c:Covenant {covenant_code:h.cov})
MERGE (x:Threshold {threshold_id: h.cov + '#' + h.tier + '#2011-02-15'})
// The window is ON CREATE ONLY. A plain SET here re-opens a level that an amendment
// has closed, and every historic test silently re-grades on the next run of this
// file. Measured: it does exactly that.
ON CREATE SET x.effective_from = date('2011-02-15'),
              x.effective_to   = date('9999-12-31')
SET x.tier = h.tier, x.value = h.value, x.direction = c.direction,
    x.breach_test = h.test, x.comparison = h.comparison,
    x.consequence = h.consequence, x.cure = h.cure,
    x.basis = 'filed',
    x.source = 'gfl-base-prospectus-2021-03',
    x.citation = 'Common Terms Agreement dated 15 February 2011. Levels unchanged between the March 2019 and March 2021 base prospectuses. Tested bi-annually at 30 June and 31 December.'
MERGE (c)-[:HAS_THRESHOLD]->(x);

// ---------------------------------------------------------------- 4. period Facts
// Every one of these is filed. None is illustrative.
// The grain is mixed on purpose: 31 March rows are financial year ends from
// accounts, 31 December rows are contractual Calculation Dates. Both are real, and
// flattening them into one undifferentiated "period" would be the lie.
UNWIND [
  {cov:'senior_icr', c:'cta_senior_icr', p:'2017-03-31', v: 3.96, src:'gal-arfs-2018',
   stated:'3.96', grain:'financial_year_end',
   quote:'The Senior ICR for the year ended 31 March 2018 was 3.59 (2017: 3.96).'},
  {cov:'senior_icr', c:'cta_senior_icr', p:'2019-03-31', v: 2.93, src:'ivy-holdco-ar-2019',
   stated:'2.93', grain:'financial_year_end',
   quote:'Covenant table, FY March 2019 — tested and complied with. The drone year.'},
  {cov:'senior_icr', c:'cta_senior_icr', p:'2019-12-31', v: 3.15, src:'gfl-base-prospectus-2021-03',
   stated:'3.15', grain:'calculation_date', quote:null},
  {cov:'senior_icr', c:'cta_senior_icr', p:'2020-12-31', v:-1.29, src:'gfl-base-prospectus-2021-03',
   stated:'(1.29)', grain:'calculation_date',
   quote:'Interest cover inverted — cash generated from operations was negative.'},
  {cov:'senior_icr', c:'cta_senior_icr', p:'2021-12-31', v:-1.49, src:'gal-compliance-cert-2021-12',
   stated:'(1.49)', grain:'calculation_date',
   quote:'a Default has occurred and is continuing'},
  {cov:'senior_rar', c:'cta_senior_rar', p:'2017-03-31', v: 0.51, src:'gal-arfs-2018',
   stated:'0.51', grain:'financial_year_end',
   quote:"As at 31 March 2018, the Group's Senior RAR ratio was 0.61 (2017: 0.51)."},
  {cov:'senior_rar', c:'cta_senior_rar', p:'2019-03-31', v: 0.59, src:'ivy-holdco-ar-2019',
   stated:'0.59', grain:'financial_year_end',
   quote:'Covenant table, FY March 2019 — tested and complied with. The drone year.'},
  {cov:'senior_rar', c:'cta_senior_rar', p:'2019-12-31', v: 0.60, src:'gfl-base-prospectus-2021-03',
   stated:'0.60', grain:'calculation_date', quote:null},
  {cov:'senior_rar', c:'cta_senior_rar', p:'2020-12-31', v: 0.94, src:'gfl-base-prospectus-2021-03',
   stated:'0.94', grain:'calculation_date',
   quote:'Stated WITHOUT the agreed adjustments. Read the calculation basis before reading the number.'},
  {cov:'senior_rar', c:'cta_senior_rar', p:'2021-12-31', v: 0.81, src:'gal-compliance-cert-2021-12',
   stated:'0.81', grain:'calculation_date',
   quote:'Senior Debt net of cash GBP 2,859.3m divided by RAB GBP 3,549.2m = 0.81.'}
] AS x
MERGE (f:Fact {concept_code:x.c, as_of:date(x.p)})
SET f.value = x.v, f.unit_kind = 'ratio_x', f.as_stated = x.stated, f.quote = x.quote,
    f.provenance_class = 'controlled', f.basis = 'filed', f.period_grain = x.grain,
    f.concept_unit_mismatch = (x.c = 'cta_senior_rar')
WITH f, x
MATCH (s:Source {id:x.src})              MERGE (f)-[:FROM]->(s)
WITH f, x
MATCH (co:Concept {code:x.c})            MERGE (f)-[:OF_CONCEPT]->(co)
WITH f, x
MATCH (c:Covenant {covenant_code:x.cov}) MERGE (f)-[:TESTS]->(c);

// the two Facts seeded before f.basis existed
MATCH (f:Fact) WHERE f.basis IS NULL SET f.basis = 'filed', f.period_grain = 'financial_year_end';

// ---------------------------------------------------------------- 5. period chain
// NOT :NEXT. :NEXT already means Segment->Segment (57 edges in the live graph) and
// reusing it makes "walk the chain" return two unrelated kinds of thing.
MATCH (:Fact)-[r:SUCCEEDED_BY]->(:Fact) DELETE r;

MATCH (f:Fact)-[:TESTS]->(c:Covenant)
WITH c, f ORDER BY f.as_of
WITH c, collect(f) AS fs
UNWIND range(0, size(fs) - 2) AS i
WITH fs[i] AS a, fs[i+1] AS b
MERGE (a)-[:SUCCEEDED_BY]->(b);

// ---------------------------------------------------------------- 6. headroom
// Derived onto the TESTS edge, not onto a new node. The derivation is a function of
// BOTH endpoints, so the edge is where it belongs — and no value-bearing node gets
// created that lacks a [:FROM]->(:Source) edge.
// Sign-normalised: positive is safe for a floor and for a ceiling alike.
MATCH (f:Fact)-[t:TESTS]->(c:Covenant)
OPTIONAL MATCH (c)-[:HAS_THRESHOLD]->(lu:Threshold {tier:'lock_up'})
  WHERE f.as_of >= lu.effective_from AND f.as_of <= lu.effective_to
OPTIONAL MATCH (c)-[:HAS_THRESHOLD]->(df:Threshold {tier:'default'})
  WHERE f.as_of >= df.effective_from AND f.as_of <= df.effective_to
WITH f, t, c, lu, df,
     CASE WHEN lu IS NULL        THEN null
          WHEN c.direction='min' THEN round(f.value - lu.value, 3)
          ELSE                        round(lu.value - f.value, 3) END AS hr_lu,
     CASE WHEN df IS NULL        THEN null
          WHEN c.direction='min' THEN round(f.value - df.value, 3)
          ELSE                        round(df.value - f.value, 3) END AS hr_df
WITH f, t, lu, df, hr_lu, hr_df,
     (lu IS NOT NULL AND (hr_lu < 0 OR (hr_lu = 0 AND lu.breach_test = 'at_or_worse'))) AS lu_broken,
     (df IS NOT NULL AND (hr_df < 0 OR (hr_df = 0 AND df.breach_test = 'at_or_worse'))) AS df_broken
SET t.period_end        = f.as_of,
    t.headroom_lock_up  = hr_lu,
    t.headroom_default  = hr_df,
    t.binding_tier      = CASE WHEN lu IS NULL THEN 'default' ELSE 'lock_up' END,
    t.binding_threshold = CASE WHEN lu IS NULL THEN df.value  ELSE lu.value  END,
    t.headroom          = CASE WHEN lu IS NULL THEN hr_df     ELSE hr_lu     END,
    t.status            = CASE WHEN df_broken THEN 'default'
                               WHEN lu_broken THEN 'lock_up'
                               ELSE                'headroom' END;

// ---------------------------------------------------------------- 7. BREACH as an EDGE
// Not a boolean. The tail is a :Fact and only ever a :Fact — that is what makes a
// breach structurally unreachable from the observed lane. It inherits the Fact rule.
MATCH (:Fact)-[b:BREACHED]->(:Threshold) DELETE b;

MATCH (f:Fact)-[:TESTS]->(c:Covenant)-[:HAS_THRESHOLD]->(h:Threshold)
WHERE f.as_of >= h.effective_from AND f.as_of <= h.effective_to
WITH f, h,
     round(CASE c.direction WHEN 'min' THEN f.value - h.value
                            ELSE            h.value - f.value END, 3) AS hr
WHERE hr < 0 OR (hr = 0 AND h.breach_test = 'at_or_worse')
MERGE (f)-[b:BREACHED]->(h)
SET b.by          = round(-hr, 3),
    b.by_pct      = round(100.0 * -hr / abs(h.value), 1),
    b.period_end  = f.as_of,
    b.consequence = h.consequence;

// ---------------------------------------------------------------- 8. parties
// A new :Party label, NOT the existing :Entity. :Entity holds 27 nodes extracted
// from video and research by a model — it is an observed-lane label, and hanging a
// lender off it would put a model-extracted string inside the covenant lane.
UNWIND [
  {party_id:'GAL',  role:'borrower',     name:'Gatwick Airport Limited'},
  {party_id:'IVY',  role:'obligor',      name:'Ivy Bidco Limited'},
  {party_id:'DTCL', role:'trustee',      name:'Deutsche Trustee Company Limited, as Borrower Security Trustee'},
  {party_id:'QBSC', role:'lender_group', name:'Qualifying Borrower Secured Creditors'}
] AS p
MERGE (x:Party {party_id:p.party_id}) SET x.name = p.name, x.role = p.role;

// ---------------------------------------------------------------- 9. WAIVERS
UNWIND [
  {waiver_id:'WVR-2020-09-22',
   instrument:'22 September 2020 Amendments — amendment and waiver agreement',
   granted_on:date('2020-09-22'),
   from:date('2020-12-31'), to:date('2021-06-30'),
   covenants:['senior_icr','senior_rar'], tiers:['lock_up','default'],
   consequence_after:'Trigger Event consequences not enforced at these Calculation Dates. Distributions remain blocked — by the waiver conditions, not by the covenant. The Default stands on the record.',
   price:['Quarterly information packages to secured creditors, September 2020 to June 2021',
          'Liquidity test: Available Cash less Required Expenditure below GBP 225m requires a remedial plan',
          'Below GBP 150m, failure to provide or execute that plan is itself a Loan Event of Default',
          'No Restricted Payments before the Calculation Date on 31 December 2021',
          'Thereafter a tighter Senior RAR distribution test — 0.60 to June 2022, then 0.65, adjusted basis'],
   source:'gfl-base-prospectus-2021-03',
   note:'Also approved up to GBP 300,000,000 of unsecured commercial paper under the CCFF, and waived certain technical Defaults arising from government COVID action.'},
  {waiver_id:'WVR-2021-09-08',
   instrument:'Amendment and Waiver Agreement dated 8 September 2021',
   granted_on:date('2021-09-08'),
   from:date('2021-12-31'), to:date('2022-06-30'),
   covenants:['senior_icr','senior_rar'], tiers:['lock_up','default'],
   consequence_after:'Senior ICR and Senior RAR not required to be complied with at these two Calculation Dates. Absent this waiver, 31 December 2021 was a Loan Event of Default on Senior ICR.',
   price:[],
   source:'gal-compliance-cert-2021-12',
   note:'Named and dated inside the compliance certificate. We hold the certificate that references the agreement, not the agreement itself.'}
] AS w
MERGE (x:Waiver {waiver_id:w.waiver_id})
SET x.instrument = w.instrument, x.granted_on = w.granted_on,
    x.effective_from = w.from, x.effective_to = w.to,
    x.covers_covenants = w.covenants, x.covers_tiers = w.tiers,
    x.scope = 'named_calculation_dates',
    x.consequence_after = w.consequence_after,
    x.conditions = w.price, x.note = w.note, x.basis = 'filed',
    x.does_not = 'A waiver suspends a consequence. It does not unmake a test result, it does not amend a level, and it never deletes a BREACHED edge.'
WITH x, w
MATCH (s:Source {id:w.source})    MERGE (x)-[:FROM]->(s)
WITH x
MATCH (p:Party {party_id:'QBSC'}) MERGE (x)-[:GRANTED_BY]->(p)
WITH x
MATCH (p:Party {party_id:'GAL'})  MERGE (x)-[:GRANTED_TO]->(p);

// The triangle. Both edges are scoped from the instrument, never inferred — a
// waiver that covered one covenant and not the other must be expressible, or the
// model flatters every waiver into a blanket one.
MATCH (f:Fact)-[:TESTS]->(c:Covenant), (w:Waiver)
WHERE f.as_of >= w.effective_from AND f.as_of <= w.effective_to
  AND c.covenant_code IN w.covers_covenants
MERGE (f)-[:WAIVED_BY {period_end:f.as_of}]->(w);

MATCH (w:Waiver)
UNWIND w.covers_covenants AS cc
UNWIND w.covers_tiers AS tt
MATCH (:Covenant {covenant_code:cc})-[:HAS_THRESHOLD]->(h:Threshold {tier:tt})
MERGE (w)-[:WAIVES {covenant:cc, tier:tt}]->(h);

// ---------------------------------------------------------------- 10. the third kind
// Neither a waiver nor a step-down. Cut this block if the demo needs to be smaller.
MERGE (a:Amendment {amendment_id:'AMD-2021-09-08-RAR-EBITDA'})
SET a.kind = 'calculation_amendment',
    a.instrument = 'Amendment and Waiver Agreement dated 8 September 2021',
    a.effective_from = date('2021-07-01'), a.effective_to = date('2024-06-30'),
    a.description = 'Relevant EBITDA for each quarter of the pandemic period replaced, in the Senior RAR calculation, with the average of the corresponding quarters of financial years 2017, 2018 and 2019.',
    a.basis = 'filed';

MATCH (a:Amendment {amendment_id:'AMD-2021-09-08-RAR-EBITDA'}),
      (s:Source {id:'gal-compliance-cert-2021-12'})
MERGE (a)-[:FROM]->(s);

// The 0.94 at December 2020 is stated WITHOUT the agreed adjustments. Say so on the
// node, or the graph reports a number under a basis it was not computed on.
MATCH (f:Fact {concept_code:'cta_senior_rar', as_of:date('2020-12-31')})
SET f.calculation_basis = 'unadjusted — stated without the agreed amendments';
```

**Measured result.** 125 nodes / 150 relationships, identical on re-run. Deltas against the
`schema + seed + risk` baseline: `Fact 2→12`, `Source 1→4`, `Term 51→60`, `Vocabulary 14→17`,
new `Threshold 4`, `Party 4`, `Waiver 2`, `Amendment 1`. New edges: `BREACHED 7`,
`HAS_THRESHOLD 4`, `SUCCEEDED_BY 10`, `WAIVED_BY 4`, `WAIVES 8`, `GRANTED_BY 2`,
`GRANTED_TO 2`.

> **Note on `covers_calculation_dates`.** An earlier draft stored the named dates as a
> `LIST<DATE>` property. **Do not** — see §7. The window (`effective_from`/`effective_to`) plus
> `covers_covenants` builds byte-identical `WAIVED_BY` edges (verified: 4 either way) and
> carries no migration hazard.

---

## 5 · The invariant still holds — the verification query

**The rule is unchanged: an observed source may never produce a Fact, and may never reach a
covenant value. A breach is only ever evidenced by a controlled source.**

This design does not add an exception; it adds a *derived consequence*. `BREACHED` hangs off a
`:Fact`, `:Fact` hangs off a `:Source`, and so a breach that could be evidenced by news is not
prohibited by a rule — it is unconstructible without first violating the Fact rule, which
already has a check.

Run as a single statement. **Every row must be `0`.**

```cypher
CALL () { MATCH (f:Fact)-[:FROM]->(s:Source) WHERE s.provenance_class <> 'controlled'
          RETURN count(*) AS n }
RETURN 'Fact from a non-controlled source' AS check, n
UNION ALL
CALL () { MATCH (f:Fact) WHERE NOT (f)-[:FROM]->(:Source)
          RETURN count(*) AS n }
RETURN 'Fact with no source at all' AS check, n
UNION ALL
CALL () { MATCH (x)-[:TESTS]->(:Covenant) WHERE NOT x:Fact
          RETURN count(*) AS n }
RETURN 'Non-Fact node testing a covenant' AS check, n
UNION ALL
CALL () { MATCH (x)-[:BREACHED]->(:Threshold) WHERE NOT x:Fact
          RETURN count(*) AS n }
RETURN 'Non-Fact node breaching a threshold' AS check, n
UNION ALL
CALL () { MATCH (f:Fact)-[:BREACHED]->(:Threshold), (f)-[:FROM]->(s:Source)
          WHERE s.provenance_class <> 'controlled'
          RETURN count(*) AS n }
RETURN 'Breach evidenced by an observed source' AS check, n
UNION ALL
CALL () { MATCH (o:Observation)-[r]->(m)
          WHERE type(r) IN ['TESTS','BREACHED','WAIVED_BY','WAIVES','HAS_THRESHOLD']
             OR any(l IN labels(m) WHERE l IN ['Covenant','Threshold','Waiver','Fact','Party'])
          RETURN count(*) AS n }
RETURN 'Observation with an edge into the covenant lane' AS check, n
UNION ALL
CALL () { MATCH (w:Waiver) WHERE NOT (w)-[:FROM]->(:Source {provenance_class:'controlled'})
          RETURN count(*) AS n }
RETURN 'Waiver not evidenced by a controlled source' AS check, n
UNION ALL
CALL () { MATCH (w:Waiver) WHERE NOT (w)-[:GRANTED_BY]->(:Party)
          RETURN count(*) AS n }
RETURN 'Waiver with no granting party' AS check, n
UNION ALL
CALL () { MATCH (f:Fact)-[r:WAIVED_BY]->(w:Waiver)
          WHERE r.period_end < w.effective_from OR r.period_end > w.effective_to
          RETURN count(*) AS n }
RETURN 'Waiver applied outside the window the instrument names' AS check, n
UNION ALL
CALL () { MATCH (f:Fact)-[r:WAIVED_BY]->(:Waiver) WHERE r.period_end <> f.as_of
          RETURN count(*) AS n }
RETURN 'WAIVED_BY period disagrees with the Fact it hangs off' AS check, n
UNION ALL
CALL () { MATCH (w:Waiver)-[x:WAIVES]->(h:Threshold) WHERE x.tier <> h.tier
          RETURN count(*) AS n }
RETURN 'WAIVES edge naming a tier the threshold is not' AS check, n
UNION ALL
// A waiver suspends a consequence. If one ever removes a BREACHED edge, this fires.
CALL () { MATCH (f:Fact)-[:WAIVED_BY]->(w:Waiver)-[:WAIVES]->(h:Threshold)
          WHERE (f)-[:TESTS]->(:Covenant)-[:HAS_THRESHOLD]->(h)
            AND NOT (f)-[:BREACHED]->(h)
            AND ((h.direction = 'min' AND (f.value < h.value
                    OR (f.value = h.value AND h.breach_test = 'at_or_worse')))
              OR (h.direction = 'max' AND (f.value > h.value
                    OR (f.value = h.value AND h.breach_test = 'at_or_worse'))))
          RETURN count(*) AS n }
RETURN 'Waived breach that has lost its BREACHED edge' AS check, n
UNION ALL
CALL () { MATCH (c:Covenant)-[:HAS_THRESHOLD]->(lu:Threshold {tier:'lock_up'}),
                (c)-[:HAS_THRESHOLD]->(df:Threshold {tier:'default'})
          WHERE (c.direction='min' AND lu.value <= df.value)
             OR (c.direction='max' AND lu.value >= df.value)
          RETURN count(*) AS n }
RETURN 'Lock-up tier not tighter than default tier' AS check, n
UNION ALL
CALL () { MATCH (c:Covenant)-[:HAS_THRESHOLD]->(a:Threshold),
                (c)-[:HAS_THRESHOLD]->(b:Threshold)
          WHERE a.tier = b.tier AND elementId(a) < elementId(b)
            AND a.effective_from <= b.effective_to
            AND b.effective_from <= a.effective_to
          RETURN count(*) AS n }
RETURN 'Two thresholds of one tier in force at once' AS check, n
UNION ALL
CALL () { MATCH (c:Covenant)-[:HAS_THRESHOLD]->(h:Threshold)
          WHERE h.effective_to = date('9999-12-31')
            AND ((h.tier='lock_up' AND h.value <> c.threshold_value)
              OR (h.tier='default' AND h.value <> c.threshold_default))
          RETURN count(*) AS n }
RETURN 'Threshold in force disagrees with the legacy scalar' AS check, n;
```

### Proved to fire, not just to pass

A verification suite that has never been seen to fail is not evidence. Each check was tested by
injecting the violation it exists to catch. Measured, all three at once:

| Injected | Check that fired |
|---|---|
| A `:Fact` sourced from a broadcast news `:Source`, with a `BREACHED` edge | 1 *Fact from a non-controlled source* → `1`, and 5 *Breach evidenced by an observed source* → `1` |
| An Enid-style `:Test {observed: 0.40}` on a `:TESTS` edge into `senior_icr` | 3 *Non-Fact node testing a covenant* → `1` |
| Deleting the `BREACHED` edge under a waived breach | 12 *Waived breach that has lost its BREACHED edge* → `1` |

Removing all three returns the suite to fifteen zeros.

### A trap worth naming, because it bites verification queries specifically

The first version of this suite was written as `RETURN 'label' AS check, count(*) AS n`. That
**groups by the literal**, so when a check is clean it returns *zero rows* rather than a row
containing `0`. The whole suite printed nothing at all — indistinguishable from a suite that
had failed to run. Compute the count in the subquery and attach the label in the outer
`RETURN`, exactly as above.

> Any "must return zero rows" idiom has this property. A check whose pass state and whose
> broken state look identical on screen is not a check. Worth a look at
> `graph/risk.py`, which uses `RETURN count(*) AS n` and is therefore fine.

---

## 6 · The demo beat

### Which page: `static/graph.html`, as a new **§2**

Insert between the existing §1 (the coverage table — *"It reaches neither loan promise"*) and
the existing §2 (the risk chain); renumber the existing 2/3/4 → 3/4/5.

**Why there, and not a new page or the video page.** The zeros live in §1. A counter-example
has to sit next to the thing it counters, or the audience has to hold the contrast in memory
across a navigation. Reading order carries the whole argument by itself: *nothing the cameras
filmed reached these two covenants — and here is what reaching one actually looks like.*

Mechanically it is cheap: `graph.html:368-384` already fetches `Q_CHAIN` and `Q_UNLINKED`
through `POST /api/graph/query`, and the `tscroll` / `qt` table styles already exist. Add one
query constant and one table. **Both queries below are read-only and pass `server.py:633`'s
`CREATE|DELETE|MERGE|SET|DROP|REMOVE` filter — verified.**

### The twenty seconds

Both tables on screen at once — §1's zeros above, the new one below. Nothing animates.

| Time | On screen | Voice |
|---|---|---|
| **0:00–0:06** | §1 coverage table, finger on the two zero rows | *"Those two zeros are the video lane. A hundred and six links from footage to concept, and nothing it filmed reaches either covenant."* |
| **0:06–0:15** | Scroll to §2. Table already rendered | *"Same two covenants, from filings. December twenty twenty-one. Interest cover minus one point four nine, against a floor of one point one."* |
| **0:15–0:20** | Finger on the last column | *"Waived, eighth of September. The consequence changed. The breach is still there."* |

Forty-eight spoken words. About twenty seconds at 140 wpm with the scroll.

**The line that has to land:** *"News cannot reach a covenant. A compliance certificate can, and
the graph is the same graph."*

### Q-A — the table for §2

```cypher
MATCH (f:Fact)-[b:BREACHED]->(h:Threshold)<-[:HAS_THRESHOLD]-(c:Covenant)
MATCH (f)-[:FROM]->(src:Source)
OPTIONAL MATCH (f)-[:WAIVED_BY]->(w:Waiver)-[:WAIVES]->(h)
RETURN toString(b.period_end) AS calc_date, c.covenant_code AS covenant,
       f.value AS observed, h.tier AS tier, h.value AS level,
       src.provenance_class AS lane, src.kind AS document,
       CASE WHEN w IS NULL THEN 'ENFORCED' ELSE 'WAIVED ' + toString(w.granted_on) END AS consequence
ORDER BY calc_date, covenant, tier;
```

**Verified output** — seven rows, every `lane` reading `controlled`:

| calc_date | covenant | observed | tier | level | lane | document | consequence |
|---|---|---|---|---|---|---|---|
| 2020-12-31 | senior_icr | −1.29 | default | 1.1 | controlled | base_prospectus | WAIVED 2020-09-22 |
| 2020-12-31 | senior_icr | −1.29 | lock_up | 1.5 | controlled | base_prospectus | WAIVED 2020-09-22 |
| 2020-12-31 | senior_rar | 0.94 | default | 0.85 | controlled | base_prospectus | WAIVED 2020-09-22 |
| 2020-12-31 | senior_rar | 0.94 | lock_up | 0.7 | controlled | base_prospectus | WAIVED 2020-09-22 |
| 2021-12-31 | senior_icr | −1.49 | default | 1.1 | controlled | compliance_certificate | WAIVED 2021-09-08 |
| 2021-12-31 | senior_icr | −1.49 | lock_up | 1.5 | controlled | compliance_certificate | WAIVED 2021-09-08 |
| 2021-12-31 | senior_rar | 0.81 | lock_up | 0.7 | controlled | compliance_certificate | WAIVED 2021-09-08 |

Note the last row has **no default line above it** — RAR at 0.81 never crossed 0.85. That gap
in the table is the "in lock-up, not in default" shape, sitting on the same date as an ICR that
*is* in default.

### Q-B — the reserve, if a judge doubts the table

One query, two rows, the whole thesis:

```cypher
MATCH (s:Source)
OPTIONAL MATCH (s)<-[:FROM]-(f:Fact)-[:BREACHED]->(:Threshold)
RETURN s.provenance_class AS lane, count(DISTINCT s) AS sources,
       count(DISTINCT f)  AS covenant_values,
       count(f)           AS breaches
ORDER BY lane;
```

**Verified output** (against a graph carrying the eight observed sources):

| lane | sources | covenant_values | breaches |
|---|---|---|---|
| controlled | 4 | 4 | 7 |
| observed | **8** | **0** | **0** |

Eight news sources. Zero covenant values. Zero breaches. Not a filter, not a flag — there is no
edge for that row to travel along.

### Run of show: this is a **reserve**, not a new scripted beat

`docs/06-the-run-of-show.md` is already full at 2:45 with fifteen seconds of slack, and its own
rule is that after 14:30 only SUBTRACT, SUBMIT, REHEARSE are legal. **Do not add a seventh
beat.** Add it instead as a fourth entry under *"The three questions to expect"*:

> **"Fine — so show me one that *does* reach a covenant."**
> Graph page, section 2. Same two covenant nodes that read zero from the video read −1.49 and
> 0.81 from a compliance certificate signed by two officers, against a threshold, a tier and a
> consequence. Both breaches waived, both still on the record. The system is not incapable, it
> is discriminating.

That also upgrades the existing *"A judge asks for the covenant threshold"* row in the
what-breaks table, which currently answers with 2018 headroom only.

---

## 7 · What this costs — flagged honestly

### Re-seeding: **not required.** This is purely additive

No node is deleted, no property removed. The only writes to pre-existing nodes are: `f.basis`
and `f.period_grain` stamped onto the two seeded Facts, `HAS_THRESHOLD` edges added to the two
Covenants, and `SET f.calculation_basis` on one Fact. `Covenant.threshold_value`,
`threshold_default`, `threshold_status`, `threshold_citation`, `latest_value` and
`latest_as_of` are all left exactly as they are.

### Attestation edges: **safe — with one hard rule**

`graph/attestations.py` restores on:

```cypher
MATCH (e:Event {name:$event}), (c:Covenant {covenant_code:$covenant})
MERGE (e)-[m:MAY_AFFECT {evidence_sha256:$evidence_sha256}]->(c)
```

So the twelve `MAY_AFFECT` edges — including John's signed rejection at 16:59 on 29 July, the
one unrebuildable thing in the graph — survive as long as **`Event.name` and
`Covenant.covenant_code` are unchanged.** This design changes neither.

> **The rule: never rename `covenant_code`, and never re-key `:Covenant`.** Adding properties
> and edges to a Covenant is safe. Changing its key orphans every signed decision permanently,
> and no amount of care afterwards recovers them. That is the single thing in this note that
> would be unrecoverable if got wrong.

### Two rebuild traps — one pre-existing, one created by this change

**(a) `make rebuild` overwrites the attestation backup *before* it checks anything.** The
target is `attest-save clean-graph graph attest-load` (`Makefile:61`), and `attest-save`
writes `attestations.json` unconditionally. If the graph is already damaged, the damaged state
is saved over the good backup. **Install this file with `make up` plus a direct
`cypher-shell -f`, never via `make rebuild`.** Copy `attestations.json` aside first regardless.
This trap exists today; it is not introduced here, but installing new Cypher is exactly when it
gets triggered.

**(b) `make graph` does not know about the new file, so the next rebuild silently drops all of
it.** The `graph:` target runs `schema → seed → load → urls → link`. Add the loader after
`seed`, or the demo works today and is gone tomorrow with no error — attestations survive,
covenant history does not. That asymmetry is the nastiest possible failure mode, because
`make status` would look healthy.

### Migration: `graph/migrate.py` is stale and will corrupt every new date

`graph/export.py` **discovers** temporals from the live graph with `valueType()` and embeds the
map in the dump — it self-heals for new date properties. `graph/migrate.py` does not: it
carries a **hardcoded `TEMPORAL` dict** (`migrate.py:25-32`) listing six properties, none of
which are new here. Every one of these would land in Aura as a `STRING`:

`Threshold.effective_from`, `Threshold.effective_to`, `Waiver.granted_on`,
`Waiver.effective_from`, `Waiver.effective_to`, `Amendment.effective_from`,
`Amendment.effective_to`, and the relationship properties `TESTS.period_end`,
`BREACHED.period_end`, `WAIVED_BY.period_end`.

Consequence: every `f.as_of >= h.effective_from` window comparison silently stops matching, so
headroom derives against nothing and the breach count goes to zero — with no error. **Retire
`migrate.py`, or point it at `data["temporal"]` the way `export.py:156` already does.**

### And a hazard that defeats even `export.py`

Do **not** store a list of dates. A `LIST<DATE>` property reports
`valueType() = 'LIST<DATE NOT NULL> NOT NULL'`; `export.py`'s `base_type()` strips only
`" NOT NULL"`, yielding `LIST<DATE>`, which is not a key in `CASTS` — so no cast is emitted and
the list round-trips as strings. Measured on the built graph. This is why §4 stores the waiver
window as two scalar dates and drives the edges from `covers_covenants`; verified to build the
identical four `WAIVED_BY` edges.

### Code that will now report the wrong thing unless updated

- **`graph/agent.py:63-70`** (`covenant_facts`) returns 2 rows today and **12** after this
  change, and computes `headroom_pct` from `c.threshold_value` — the lock-up scalar only. It
  therefore knows nothing about the default tier, and would silently report the wrong level
  after any threshold amendment. If the agent is on stage in §4 of `graph.html`, it will
  contradict the new §2. Point it at the `:Threshold` nodes.
- **`graph/risk.py:162`** — add the four provenance checks from §5. The existing one is not
  wrong, it is *insufficient*, as §1 measures.
- **`graph/risk.py:179`** — the note dict needs a `HAS_THRESHOLD` entry, or the case analysis
  prints a blank annotation next to a new edge type on a Covenant.
- **Node counts.** +36 nodes. `docs/06-the-run-of-show.md:180` already warns that the header
  figure creeps and stops matching the documented number; anything that hardcodes it needs
  bumping.

### The legacy scalars stay — and that is a deliberate, costed choice

`Covenant.threshold_value` / `threshold_default` are read by `graph/agent.py`,
`docs/explainers/the-graph.html` and `docs/explainers/the-data-model.html`. Removing them
breaks three surfaces the day before a demo. Keeping them creates a genuine second source of
truth that **drifts the moment a threshold is amended** — measured: after a step-down, check 15
fired immediately. The mitigation is that check, not a promise. Retire the scalars after the
hackathon, not during it.

### Naming — one decision for John, unchanged in substance either way

`docs/05-the-data-model.md` flags Enid identifier reuse as John's line to draw. Sorting this
design's vocabulary against it:

- **Gatwick's own public drafting, safe:** `Senior ICR`, `Senior RAR`, `Common Terms
  Agreement`, `Calculation Date`, `Trigger Event`, `Loan Event of Default`, `Restricted
  Payments`, `Additional SP Contributions`. All appear in the published prospectus.
- **Enid's conventions, adopted here:** `threshold_id`, the `lock_up` / `default` tier names,
  `headroom`, `headroom_pct`, `binding_tier`, `BREACHED`, `HAS_THRESHOLD`.

**Recommendation: switch the tier term values to the public drafting** — `trigger_event` and
`loan_event_of_default` instead of `lock_up` and `default`. It is both safer on the Enid line
*and* more accurate, since "lock-up" is a generic market term while "Trigger Event" is what
Gatwick's agreement actually calls it. It is a one-line change to the vocabulary block and the
four threshold rows; nothing else in the design depends on the spelling.

---

## 8 · Open, and deliberately not decided here

- **Which document supplies the FY2019 and Dec-2019 ratios.** `07-the-counter-example.md`
  lists the Ivy Holdco FY2019 annual report and the March 2021 base prospectus among documents
  held; the per-row attribution in block 4 follows that, but has not been re-checked against
  the page.
- **Whether the `:Amendment` block (10) survives to the demo.** It is the most interesting
  modelling idea here and the least necessary one. Cut it first if anything has to go.
- **`url_sha256` on the three new Sources.** `graph/urls.py` fills these; it has not been run
  against them. A Source with no hash is a Source nobody has fetched, and the demo says so out
  loud about the video lane — the covenant lane should not get a pass.
- **Whether a model may ever propose a `:Waiver`.** It cannot today; the loader is hand-written
  from primary documents. If `research_ingest.py` ever proposes one, it must go through the
  same `status='proposed'` attestation gate as `MAY_AFFECT`, and a proposed waiver must be
  inert — read by no query that computes a consequence.
