// The counter-example: evidence that DOES reach a covenant, because it is admissible.
// Source is a compliance certificate — the artifact a lender is actually sent.
// Every number here is from Gatwick's own filings; see docs/07-the-counter-example.md.

CREATE CONSTRAINT ratio_key IF NOT EXISTS
  FOR (r:RatioTest) REQUIRE (r.covenant_code, r.as_of) IS UNIQUE;

MERGE (s:Source {id:'gal-compliance-2021-12'})
SET s.provenance_class = 'controlled', s.kind = 'compliance_certificate',
    s.publisher = 'Gatwick Airport Limited / Ivy Bidco Limited',
    s.title = 'Compliance Certificate, Calculation Date 31 December 2021',
    s.addressed_to = 'Deutsche Trustee Company Limited, Borrower Security Trustee',
    s.signed_by = 'Stewart Wingate (CEO), Jim Butler (CFO)',
    s.as_of = date('2021-12-31'), s.dated = date('2022-03-07'),
    s.url = 'https://www.gatwickairport.com/on/demandware.static/-/Sites-Gatwick-Library/default/dw6bbd5197/images/Corporate-PDFs/Reports%20financial%20/2022/Compliance%20certificate%20December%202021.pdf';

MATCH (s:Source {id:'gal-compliance-2021-12'}), (d:Deal {legal_name:'Gatwick Funding Limited'})
MERGE (s)-[:EVIDENCES]->(d);

// The ratio history. Trigger and default tiers are from the Common Terms Agreement
// dated 15 February 2011, identical across the March 2019 and March 2021 prospectuses —
// so the SAME test governed both the drone and the pandemic.
UNWIND [
  {cov:'senior_icr', as_of:'2019-03-31', v: 2.93, note:'the drone year'},
  {cov:'senior_rar', as_of:'2019-03-31', v: 0.59, note:'the drone year'},
  {cov:'senior_icr', as_of:'2019-12-31', v: 3.15, note:''},
  {cov:'senior_rar', as_of:'2019-12-31', v: 0.60, note:''},
  {cov:'senior_icr', as_of:'2020-12-31', v:-1.29, note:'cash from operations went negative'},
  {cov:'senior_rar', as_of:'2020-12-31', v: 0.94, note:'before the agreed adjustments'},
  {cov:'senior_icr', as_of:'2021-12-31', v:-1.49, note:'absent the waiver this was an event of default'},
  {cov:'senior_rar', as_of:'2021-12-31', v: 0.81, note:'through the trigger, inside the default ceiling'}
] AS t
MATCH (c:Covenant {covenant_code:t.cov})
MERGE (r:RatioTest {covenant_code:t.cov, as_of:date(t.as_of)})
SET r.value = t.v, r.note = t.note, r.provenance_class = 'controlled',
    // Two tiers, and which one was broken is a shape, not a boolean.
    r.tier = CASE
      WHEN t.cov = 'senior_icr' AND t.v <= 1.10 THEN 'default'
      WHEN t.cov = 'senior_icr' AND t.v <  1.50 THEN 'trigger'
      WHEN t.cov = 'senior_rar' AND t.v >  0.85 THEN 'default'
      WHEN t.cov = 'senior_rar' AND t.v >  0.70 THEN 'trigger'
      ELSE 'clear' END
WITH r, c
MERGE (r)-[:MEASURES]->(c)
WITH r
MATCH (s:Source {id:'gal-compliance-2021-12'})
MERGE (r)-[:FROM]->(s);

// A breach is an edge, not a flag, so "in lock-up but not in default" is visible.
MATCH (r:RatioTest)-[:MEASURES]->(c:Covenant) WHERE r.tier <> 'clear'
MERGE (r)-[b:BREACHED]->(c)
SET b.tier = r.tier,
    b.consequence = CASE r.tier
      WHEN 'default' THEN 'Loan Event of Default — lenders may accelerate, 30-day cure available'
      ELSE 'Trigger Event — cash lock-up, distributions to shareholders prohibited' END;

// The waiver. It changes the CONSEQUENCE of a breach. It never deletes the breach.
MERGE (w:Waiver {waiver_id:'awa-2021-09-08'})
SET w.name = 'Amendment and Waiver Agreement',
    w.dated = date('2021-09-08'),
    w.approved_by = 'Qualifying Borrower Secured Creditors',
    w.covers = 'Any Default relating to Senior ICR and Senior RAR at the calculation dates falling December 2021 and June 2022',
    w.also = 'Temporary amendment to the Senior RAR calculation until June 2024',
    w.provenance_class = 'controlled';

MATCH (w:Waiver {waiver_id:'awa-2021-09-08'}), (s:Source {id:'gal-compliance-2021-12'})
MERGE (w)-[:FROM]->(s);

MATCH (w:Waiver {waiver_id:'awa-2021-09-08'}),
      (r:RatioTest) WHERE r.as_of = date('2021-12-31') AND r.tier <> 'clear'
MERGE (w)-[:WAIVES]->(r);
