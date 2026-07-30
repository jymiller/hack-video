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

// Thresholds and latest values both come from the controlled lane — GAL's own audited
// accounts, cited on the node. threshold_default is the programme default the covenant
// falls back to; threshold_value is what this filing actually states.
UNWIND [
  {code:'senior_icr', name:'Senior interest cover ratio', dir:'min', concept:'cta_senior_icr',
   thr:1.5, def:1.1, latest:3.59},
  {code:'senior_rar', name:'Senior debt ratio',           dir:'max', concept:'cta_senior_rar',
   thr:0.7, def:0.85, latest:0.61}
] AS cv
MERGE (c:Covenant {covenant_code:cv.code})
SET c.name = cv.name, c.direction = cv.dir,
    c.threshold_value = cv.thr, c.threshold_default = cv.def,
    c.threshold_status = 'sourced', c.threshold_source = 'gal-arfs-2018',
    c.threshold_citation = 'Annual Report and Financial Statements for the year ended 31 March 2018 (company 1991018), financial covenants table',
    c.latest_value = cv.latest, c.latest_as_of = '2018-03-31'
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

// ------------------------------------------------- the controlled lane (loaded 30 Jul)
// The first controlled-lane source: GAL's audited accounts, fetched from
// gatwickairport.com. Facts may only ever come from a controlled source; these
// two are the covenant ratios as the issuer itself states them.
MERGE (s:Source {id:'gal-arfs-2018'})
SET s.provenance_class = 'controlled', s.kind = 'accounts',
    s.publisher = 'Gatwick Airport Limited', s.company_number = '1991018',
    s.title = 'Annual Report and Financial Statements for the year ended 31 March 2018',
    s.filename = 'Gatwick Airport Limited ARFS March 2018.pdf',
    s.as_of = date('2018-03-31'),
    s.url = 'https://www.gatwickairport.com/on/demandware.static/-/Sites-Gatwick-Library/default/dw639ca5a8/images/Corporate-PDFs/Reports%20financial%20/Other_Financial_Documents/Previous_annual_reports/Gatwick%20Airport%20Limited%20ARFS%20March%202018.pdf',
    s.url_sha256 = '416d34bba3957ef0b7d79ca76e9dcc67812553695448df9bef0c61795350cd5b';

MATCH (s:Source {id:'gal-arfs-2018'}), (d:Deal {legal_name:'Gatwick Funding Limited'})
MERGE (s)-[:EVIDENCES]->(d);

// The RAR value is stated as a ratio against a percent-scaled concept; the
// mismatch is recorded honestly rather than silently converted.
UNWIND [
  {concept:'cta_senior_icr', covenant:'senior_icr', value:3.59, prior:3.96, mismatch:false,
   stated:'3.59 (2017: 3.96)',
   quote:'The Senior ICR for the year ended 31 March 2018 was 3.59 (2017: 3.96).'},
  {concept:'cta_senior_rar', covenant:'senior_rar', value:0.61, prior:0.51, mismatch:true,
   stated:'0.61 (2017: 0.51)',
   quote:"As at 31 March 2018, the Group's Senior RAR ratio was 0.61 (2017: 0.51)."}
] AS x
MERGE (f:Fact {concept_code:x.concept, as_of:date('2018-03-31')})
SET f.value = x.value, f.prior_value = x.prior, f.unit_kind = 'ratio_x',
    f.as_stated = x.stated, f.quote = x.quote,
    f.provenance_class = 'controlled', f.concept_unit_mismatch = x.mismatch
WITH f, x
MATCH (s:Source {id:'gal-arfs-2018'})
MERGE (f)-[:FROM]->(s)
WITH f, x
MATCH (c:Covenant {covenant_code:x.covenant})
MERGE (f)-[:TESTS]->(c);
