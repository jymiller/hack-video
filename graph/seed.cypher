// Reference data and the deal lane. Idempotent — MERGE throughout.
// The vocabularies live IN the graph so the model is self-describing and
// queries can be validated against it rather than against a comment.

// ---------------------------------------------------------------- vocabularies
UNWIND [
  {n:'provenance_class', d:'Whether anyone is accountable for the source',
   t:[['controlled','Produced by an accountable party in the deal document chain'],
      ['observed','Third-party observation nobody in the deal produced or warrants']]},
  {n:'source_kind', d:'What sort of thing the source is',
   t:[['broadcast_news','Television news package'],['rally_footage','Campaign or protest recording'],
      ['commentary','Opinion or analysis programme'],['web_article','Online article'],
      ['prospectus','Bond offering document'],['accounts','Filed statutory accounts'],
      ['rns_announcement','Regulatory news service announcement'],
      ['court_judgment','Judgment of a court'],
      ['common_terms_agreement','The agreement defining the covenants']]},
  {n:'modality', d:'How evidence appeared in the video',
   t:[['spoken','Said aloud'],['on_screen_text','Rendered on screen — lower third, graphic'],
      ['visual','Shown but not stated']]},
  {n:'unit_kind', d:'What kind of quantity a value is',
   t:[['count','A number of things'],['currency','A monetary amount'],
      ['percent','A percentage — has a ceiling'],['ratio_x','A multiple — has a floor'],
      ['date','A date'],['text','Free text']]},
  {n:'scale', d:'Canonical scale of the stored number',
   t:[['units','As stated'],['thousands','Thousands'],['millions','Millions'],['none','Not applicable']]},
  {n:'covenant_code', d:'The covenants this deal discloses',
   t:[['senior_icr','Senior interest cover ratio'],['senior_rar','Senior debt ratio']]},
  {n:'direction', d:'Which way a threshold binds',
   t:[['min','Must stay above'],['max','Must stay below']]},
  {n:'deal_type', d:'Shape of the lending',
   t:[['secured_bond_programme','Listed secured bond programme'],['term_loan','Term loan'],['rcf','Revolving credit facility']]},
  {n:'facility_type', d:'Tranche type',
   t:[['senior_secured_notes','Senior secured notes'],['revolving_credit','Revolving credit']]},
  {n:'event_kind', d:'What sort of thing happened',
   t:[['regulatory_approval','A consent or approval granted'],['legal_challenge','A challenge and its outcome'],
      ['financing_event','An issuance, redemption or amendment'],
      ['operational_incident','A disruption to operations']]},
  {n:'contradiction_basis', d:'Why two sources disagree',
   t:[['methodology','They counted differently'],['timing','They refer to different periods'],
      ['scope','They cover different things'],['arithmetic','One of them is simply wrong']]},
  {n:'assertion_status', d:'Lifecycle of a MAY_AFFECT edge',
   t:[['proposed','Asserted by a model — inert, read by no computation'],
      ['validated','Signed off by a human'],['rejected','Overruled by a human — kept, never deleted']]}
] AS v
MERGE (vo:Vocabulary {name:v.n}) SET vo.description = v.d
WITH vo, v UNWIND v.t AS term
MERGE (t:Term {vocabulary:v.n, value:term[0]}) SET t.description = term[1]
MERGE (vo)-[:HAS_TERM]->(t);

// ---------------------------------------------------------------- concepts
// `probes` are the phrasings used to search video for this concept. The
// vocabulary drives retrieval as well as storage — one framework, both ends.
UNWIND [
  {c:'passenger_traffic', n:'Passenger traffic', u:'count', s:'millions', lane:'both',
   p:['passengers travelling through the airport','passenger numbers at the airport','how many people used the airport']},
  {c:'air_traffic_movements', n:'Air traffic movements', u:'count', s:'thousands', lane:'both',
   p:['number of flights per year','aircraft movements','flight capacity at the airport']},
  {c:'revenue_per_passenger', n:'Revenue per passenger', u:'currency', s:'units', lane:'controlled',
   p:['income earned per passenger','retail spend per passenger']},
  {c:'scheme_cost', n:'Scheme cost', u:'currency', s:'millions', lane:'observed',
   p:['the cost of the runway scheme in billions','how much the expansion will cost','privately financed cost']},
  {c:'jobs_claimed', n:'Jobs claimed', u:'count', s:'units', lane:'observed',
   p:['jobs created by the expansion','employment benefits of the runway','how many jobs it will create']},
  {c:'cta_senior_net_debt', n:'Senior net debt', u:'currency', s:'millions', lane:'controlled', p:[]},
  {c:'cta_senior_icr', n:'Senior interest cover ratio', u:'ratio_x', s:'none', lane:'controlled', p:[]},
  {c:'cta_senior_rar', n:'Senior debt ratio', u:'percent', s:'none', lane:'controlled', p:[]},
  {c:'two_pct_rab_deduction', n:'Two per cent of RAB deduction', u:'currency', s:'millions', lane:'controlled', p:[]}
] AS c
MERGE (co:Concept {code:c.c})
SET co.name = c.n, co.unit_kind = c.u, co.canonical_scale = c.s,
    co.probes = c.p, co.reachable_by = c.lane;

// ---------------------------------------------------------------- the deal lane
MERGE (d:Deal {legal_name:'Gatwick Funding Limited'})
SET d.borrower = 'Gatwick Airport Limited', d.issuer = 'Gatwick Funding Limited',
    d.deal_type = 'secured_bond_programme', d.currency = 'GBP',
    d.note = 'Listed secured bond programme. Public for a listed issuer.';

MERGE (f:Facility {facility_code:'GFL-SSN'})
SET f.label = 'Senior secured notes', f.facility_type = 'senior_secured_notes',
    f.governing_doc = 'Common Terms Agreement';

// NB: variables do not survive a statement boundary. Re-MATCH both ends or
// Cypher silently creates two anonymous nodes and links those instead.
MATCH (d:Deal {legal_name:'Gatwick Funding Limited'}),
      (f:Facility {facility_code:'GFL-SSN'})
MERGE (d)-[:HAS_FACILITY]->(f);

UNWIND [
  {code:'senior_icr', name:'Senior interest cover ratio', dir:'min', concept:'cta_senior_icr'},
  {code:'senior_rar', name:'Senior debt ratio',           dir:'max', concept:'cta_senior_rar'}
] AS cv
MERGE (c:Covenant {covenant_code:cv.code})
SET c.name = cv.name, c.direction = cv.dir,
    c.threshold_value = null,        // deliberately null — not yet sourced from a filing
    c.threshold_status = 'not_sourced'
WITH c, cv
MATCH (f:Facility {facility_code:'GFL-SSN'})
MERGE (f)-[:GOVERNED_BY]->(c)
WITH c, cv
MATCH (co:Concept {code:cv.concept})
MERGE (c)-[:MEASURED_BY]->(co);

// ---------------------------------------------------------------- events
UNWIND [
  {n:'Northern Runway development consent granted', d:date('2025-09-21'), k:'regulatory_approval'},
  {n:'High Court dismisses runway challenge',        d:date('2026-06-23'), k:'legal_challenge'},
  {n:'Bond programme supplementary prospectus',      d:date('2026-02-10'), k:'financing_event'},
  {n:'Airport water supply failure',                 d:date('2026-07-26'), k:'operational_incident'}
] AS e
MERGE (ev:Event {name:e.n, date:e.d}) SET ev.kind = e.k;
