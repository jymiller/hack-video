// The risk layer. Video evidence reaches a CHANNEL of exposure, never a number.
//
//   (:Observation)-[:SUGGESTS_RISK]->(:Risk)<-[:EXPOSED_TO]-(:Covenant)-[:MEASURED_BY]->(:Concept)
//
// Read the two halves differently. EXPOSED_TO is structural: it says how a risk
// bites a covenant, and it is written from the shape of the credit agreement,
// not from anything anybody filmed. It is seeded here, once, by hand. Only
// SUGGESTS_RISK is evidence-driven, and that edge is attested exactly like
// MAY_AFFECT — see graph/risk.py.
//
// Nothing in this file lets an observation supply a value. A :Risk carries no
// number at all, so the join it makes is a join between a claim and a channel.
// Idempotent — MERGE throughout, safe to re-run.

CREATE CONSTRAINT risk_id IF NOT EXISTS FOR (r:Risk) REQUIRE r.risk_id IS UNIQUE;

// ---------------------------------------------------------------- vocabularies
UNWIND [
  {n:'risk_category', d:'What kind of channel a risk is',
   t:[['macro','Moves with published indices nobody at the asset controls'],
      ['regulatory','Set by periodic administrative determination'],
      ['demand','Scales with volume that actually turns up'],
      ['construction','Delivery and treatment of the capital programme']]},
  {n:'risk_grading', d:'Illustrative grading of an EXPOSED_TO edge',
   t:[['low','Unlikely, or small when it lands'],['medium','Plausible, and material'],
      ['high','Expected over the life of the deal, or large when it lands']]}
] AS v
MERGE (vo:Vocabulary {name:v.n}) SET vo.description = v.d
WITH vo, v UNWIND v.t AS term
MERGE (t:Term {vocabulary:v.n, value:term[0]}) SET t.description = term[1]
MERGE (vo)-[:HAS_TERM]->(t);

// ---------------------------------------------------------------- risks
// The four channels a UK regulated airport actually carries. `sectors` is kept
// as the taxonomy states it, so the shared-node idea survives — one indexation
// node would serve a wind farm and a railway too — but only the airport is
// instantiated here, because this graph holds one deal and it is Gatwick. The
// resource, power-price, offshore-availability and offtaker-counterparty risks
// belong to assets this graph does not contain, and are not seeded.
//
// The taxonomy is real. The gradings on the edges below are illustrative.
UNWIND [
  {risk_id:'RISK_VOLUME_DEMAND', name:'Traffic and volume demand', category:'demand',
   sectors:['airport','rail'],
   plain_english:'Revenue scales with how many passengers or aircraft movements actually turn up. A soft quarter cannot be recovered later.'},
  {risk_id:'RISK_REGULATED_REVENUE', name:'Regulated revenue reset', category:'regulatory',
   sectors:['airport','rail'],
   plain_english:'The top line is set by a periodic administrative determination rather than by a market. When the settlement moves, the ratio moves with it and the borrower cannot price its way out.'},
  {risk_id:'RISK_CAPEX_DELIVERY', name:'Capital programme delivery', category:'construction',
   sectors:['airport'],
   plain_english:'A large regulated asset is permanently mid-programme. Spend is debt-funded, and whether it earns a return depends on the regulator allowing it into the asset base at the pace assumed.'},
  {risk_id:'RISK_INDEXATION', name:'Inflation indexation mismatch', category:'macro',
   sectors:['airport','wind','rail'],
   plain_english:'Revenue and debt service are both linked to published inflation indices - but not always the same index, and not on the same dates. When they diverge, the cover or gearing ratio moves for reasons nobody at the asset chose and nobody at the asset can hedge away.'}
] AS r
MERGE (x:Risk {risk_id: r.risk_id})
SET x.name = r.name, x.category = r.category, x.sectors = r.sectors,
    x.plain_english = r.plain_english,
    x.basis = 'taxonomy real, gradings illustrative';

// ---------------------------------------------------- covenant exposure to risk
// The manifestation lives ON THE EDGE, because the same risk bites the cover
// ratio and the gearing ratio through different mechanisms. Both covenants are
// Gatwick's own, disclosed in the 2018 ARFS and already in the graph.
UNWIND [
  {cid:'senior_icr', rid:'RISK_VOLUME_DEMAND', likelihood:'medium', impact:'high',
   manifestation:'Passenger throughput drives both aeronautical and retail income, and feeds through to interest cover inside the same rolling window.'},
  {cid:'senior_icr', rid:'RISK_REGULATED_REVENUE', likelihood:'medium', impact:'high',
   manifestation:'The price control settlement fixes the allowed yield per passenger, which IS the numerator of interest cover. A tighter determination caps cover for the whole control period, not for one quarter.'},
  {cid:'senior_icr', rid:'RISK_CAPEX_DELIVERY', likelihood:'medium', impact:'medium',
   manifestation:'Debt drawn to fund the programme raises the senior interest bill immediately, while the traffic and the allowed return the spend is meant to unlock arrive later.'},
  {cid:'senior_icr', rid:'RISK_INDEXATION', likelihood:'medium', impact:'medium',
   manifestation:'Regulated charges are index-linked and part of the senior platform is index-linked debt. When the index feeding revenue and the index feeding debt service diverge, or land on different dates, cover moves with no operational change at all.'},
  {cid:'senior_rar', rid:'RISK_REGULATED_REVENUE', likelihood:'medium', impact:'high',
   manifestation:'The determination sets the rate at which the regulatory asset base rolls forward, and that base is the denominator of this ratio. A slower roll-forward lifts gearing on an unchanged debt balance.'},
  {cid:'senior_rar', rid:'RISK_CAPEX_DELIVERY', likelihood:'high', impact:'high',
   manifestation:'Capex enters the regulatory asset base broadly as incurred, so debt-funded spend lifts numerator and denominator together and the first-order gearing effect is small. The bite is second-order: disallowed spend, or spend admitted to the base more slowly than it is drawn, raises the ratio.'},
  {cid:'senior_rar', rid:'RISK_INDEXATION', likelihood:'high', impact:'high',
   manifestation:'The regulatory asset base is indexed and a large share of the senior debt is index-linked and accretes with the same family of indices. The ratio therefore moves on an index print alone, in either direction, before any cash has changed hands.'}
] AS e
MATCH (c:Covenant {covenant_code: e.cid}), (r:Risk {risk_id: e.rid})
MERGE (c)-[x:EXPOSED_TO]->(r)
SET x.manifestation = e.manifestation, x.likelihood = e.likelihood,
    x.impact = e.impact, x.basis = 'illustrative grading';
