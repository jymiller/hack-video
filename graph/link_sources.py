"""Attach sources to the events they report, so provenance runs through a link.

Without this an assertion is about an event *name* — no URL, nothing to hash,
nothing to attest against. The link is itself asserted, so it records how it was
determined rather than appearing as fact.
"""
import os
from neo4j import GraphDatabase

drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                     auth=(os.environ.get("NEO4J_USER", "neo4j"),
                           os.environ.get("NEO4J_PASSWORD", "hackvideo2026")))

# Determined by reading the clips: five report the runway approval, one the water
# supply failure. None covers the court ruling or the prospectus.
REPORTS = {
    "Northern Runway development consent granted": [
        "https://www.youtube.com/watch?v=0rV_N6ktnRA",
        "https://www.youtube.com/watch?v=hzPZsDHIREo",
        "https://www.youtube.com/watch?v=hXE6OY5ZLTU",
        "https://www.youtube.com/watch?v=vuM3pFQ4vZg",
        "https://www.youtube.com/watch?v=KLnxVX-m-Ng",
    ],
    "Airport water supply failure": [
        "https://www.youtube.com/watch?v=dKEpA70WhXU",
    ],
}

with drv.session() as s:
    n = 0
    for event, urls in REPORTS.items():
        for u in urls:
            r = s.run("""MATCH (e:Event {name:$ev}), (src:Source {url:$u})
                         MERGE (src)-[x:REPORTS]->(e)
                           ON CREATE SET x.basis='manual — clip reviewed',
                                         x.asserted_by='human'
                         RETURN src.publisher AS p""", ev=event, u=u).single()
            if r:
                n += 1
    print(f"{n} REPORTS edges")

    print("\n=== event coverage ===")
    # ORDER BY must use a projected alias once the RETURN aggregates
    for r in s.run("""MATCH (e:Event)
                      OPTIONAL MATCH (src:Source)-[:REPORTS]->(e)
                      RETURN e.name AS event, toString(e.date) AS date,
                             count(src) AS sources,
                             collect(left(src.url_sha256,8))[0..3] AS hashes
                      ORDER BY date""").data():
        flag = "" if r["sources"] else "   ← no source: cannot be assessed from evidence"
        print(f"  {r['date']}  {r['sources']} src  {r['event'][:44]:46}{flag}")

drv.close()
