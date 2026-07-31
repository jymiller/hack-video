"""Load the one controlled source, so the two-lane argument has both lanes.

Until now the graph asserted a distinction it could only demonstrate on one side: six
`observed` sources, 106 links from video to concept, and zero `controlled` sources or
`Fact` nodes. A portfolio manager's next question after "zero reach a covenant" is
"then what does?", and the honest answer was "nothing is loaded".

This loads GATWICK AIRPORT LIMITED's Annual Report and Financial Statements for the year
ended 31 March 2018 — an accountable party in the deal's own document chain, kind
`accounts`, which is a legal term in the source_kind vocabulary. Every number below is
quoted from that document, not inferred:

    "All financial covenants have been tested and complied with as at 31 March 2018"

    Covenant                                      31 Mar 2018   Trigger   Default
    Minimum interest cover ratio ("Senior ICR")          3.59    < 1.50    < 1.10
    Maximum net indebtedness to the total
      regulatory asset base ("Senior RAR")               0.61    > 0.70    > 0.85

    "As at 31 March 2018, the Group's Senior RAR ratio was 0.61 (2017: 0.51). The
     Senior ICR for the year ended 31 March 2018 was 3.59 (2017: 3.96)."

So the covenant thresholds stop being `not_sourced`. That is a real change to what the
demo can claim: headroom becomes computable from a cited document rather than declined.

ONE DISCREPANCY, REPORTED NOT PAPERED OVER. The seeded concept `cta_senior_rar` declares
unit_kind `percent`, but the governing document states RAR as a ratio (0.61, not 61%).
The Fact is stored as the document states it and flagged with `concept_unit_mismatch`.
Fixing the concept is a seed change and a judgement call, so it is surfaced rather than
made silently at the last minute.

Idempotent. Run with NEO4J_URI unset for local, or set for Aura.
"""
import hashlib
import os

from neo4j import GraphDatabase

DOC_URL = ("https://www.gatwickairport.com/on/demandware.static/-/Sites-Gatwick-Library/"
           "default/dw639ca5a8/images/Corporate-PDFs/Reports%20financial%20/"
           "Other_Financial_Documents/Previous_annual_reports/"
           "Gatwick%20Airport%20Limited%20ARFS%20March%202018.pdf")

SOURCE = {
    "id": "gal-arfs-2018",
    "publisher": "Gatwick Airport Limited",
    "kind": "accounts",                    # legal source_kind term
    "provenance_class": "controlled",
    "filename": "Gatwick Airport Limited ARFS March 2018.pdf",
    "title": "Annual Report and Financial Statements for the year ended 31 March 2018",
    "company_number": "1991018",
    "url": DOC_URL,
    "url_sha256": hashlib.sha256(DOC_URL.strip().encode()).hexdigest(),
}

# value / trigger / default exactly as tabulated in the document.
FACTS = [
    {"concept": "cta_senior_icr", "covenant": "senior_icr",
     "value": 3.59, "prior_value": 3.96, "unit_kind": "ratio_x",
     "trigger": 1.50, "default": 1.10, "mismatch": False,
     "as_stated": "3.59 (2017: 3.96)",
     "quote": 'The Senior ICR for the year ended 31 March 2018 was 3.59 (2017: 3.96).'},
    {"concept": "cta_senior_rar", "covenant": "senior_rar",
     "value": 0.61, "prior_value": 0.51, "unit_kind": "ratio_x",
     "trigger": 0.70, "default": 0.85, "mismatch": True,
     "as_stated": "0.61 (2017: 0.51)",
     "quote": "As at 31 March 2018, the Group's Senior RAR ratio was 0.61 (2017: 0.51)."},
]

drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                          auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                os.environ.get("NEO4J_PASSWORD", "hackvideo2026")))

with drv.session() as s:
    s.run("""MERGE (src:Source {id:$id})
             SET src += $props, src.as_of = date('2018-03-31')""",
          id=SOURCE["id"], props=SOURCE)
    # One statement: a Cypher variable does not survive a statement boundary, and
    # splitting this would silently create anonymous nodes. The repo paid for that once.
    s.run("""MATCH (src:Source {id:$id}), (d:Deal)
             MERGE (src)-[:EVIDENCES]->(d)""", id=SOURCE["id"])
    print(f"source: {SOURCE['publisher']} — {SOURCE['kind']} — {SOURCE['url_sha256'][:12]}")

    for f in FACTS:
        s.run("""
            MATCH (src:Source {id:$sid}), (co:Concept {code:$concept}),
                  (cov:Covenant {covenant_code:$covenant})
            MERGE (fact:Fact {concept_code:$concept, as_of:date('2018-03-31')})
              SET fact.value = $value, fact.prior_value = $prior,
                  fact.unit_kind = $unit, fact.as_stated = $as_stated,
                  fact.quote = $quote, fact.provenance_class = 'controlled',
                  fact.concept_unit_mismatch = $mismatch
            MERGE (fact)-[:FROM]->(src)
            MERGE (fact)-[:OF_CONCEPT]->(co)
            MERGE (fact)-[:TESTS]->(cov)
            SET cov.threshold_value = $trigger,
                cov.threshold_default = $default,
                cov.threshold_status = 'sourced',
                cov.threshold_source = $sid,
                cov.threshold_citation = $citation,
                cov.latest_value = $value, cov.latest_as_of = '2018-03-31'
            """,
              sid=SOURCE["id"], concept=f["concept"], covenant=f["covenant"],
              value=f["value"], prior=f["prior_value"], unit=f["unit_kind"],
              as_stated=f["as_stated"], quote=f["quote"], mismatch=f["mismatch"],
              trigger=f["trigger"], default=f["default"],
              citation=f"{SOURCE['title']} (company {SOURCE['company_number']}), "
                       f"financial covenants table")
        head = "headroom" if f["covenant"] == "senior_icr" else "headroom"
        gap = (f["value"] - f["trigger"]) if f["covenant"] == "senior_icr" \
            else (f["trigger"] - f["value"])
        flag = "  [unit mismatch vs concept]" if f["mismatch"] else ""
        print(f"  fact {f['concept']:16} {f['value']:>5}  trigger {f['trigger']:>4}  "
              f"{head} {gap:+.2f}{flag}")

    print("\n=== the rule, enforced not asserted ===")
    bad = s.run("""MATCH (f:Fact)-[:FROM]->(x:Source {provenance_class:'observed'})
                   RETURN count(f) AS n""").single()["n"]
    print(f"  Facts sourced from an observed Source: {bad}  (must be 0)")
    if bad:
        raise SystemExit("LANE VIOLATION — an observed source produced a Fact")

    print("\n=== what now reaches each covenant ===")
    for r in s.run("""
            MATCH (cov:Covenant)
            OPTIONAL MATCH (f:Fact)-[:TESTS]->(cov)
            OPTIONAL MATCH (cov)-[:MEASURED_BY]->(co:Concept)<-[:CANDIDATE_FOR]-(seg:Segment)
            RETURN cov.covenant_code AS code, cov.direction AS dir,
                   cov.threshold_value AS trigger, cov.threshold_status AS status,
                   count(DISTINCT f) AS facts, count(DISTINCT seg) AS video_segments
            ORDER BY code""").data():
        print(f"  {r['code']:12} must stay {r['dir']:3} of {r['trigger']}  "
              f"({r['status']})  facts={r['facts']}  video_segments={r['video_segments']}")

drv.close()
