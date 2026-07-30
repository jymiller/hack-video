"""Video evidence reaches a RISK. It never reaches a number.

    (:Observation)-[:SUGGESTS_RISK]->(:Risk)<-[:EXPOSED_TO]-(:Covenant)-[:MEASURED_BY]->(:Concept)

A :Risk carries no value and no threshold, so this is the only join in the graph
where an observed claim and a covenant meet without one of them contaminating the
other. EXPOSED_TO is structural and seeded by hand (graph/risk.cypher).
SUGGESTS_RISK is the evidence-driven half, and it is attested exactly like
MAY_AFFECT: written 'proposed' by the model, moved to 'validated' or 'rejected'
by a human, and a rejected edge is kept as a rejected edge. No computation reads
a proposed edge.

THE ATTESTATION RULE APPLIES HERE TOO. Once a human has decided an
(observation, risk) pair, that pair is closed and is never re-derived. The
worklist is computed before a single write.

    python -m graph.risk seed | propose | status | chain
"""
import re, pathlib, sys
import graph.db as db

RULES = "graph.risk/concept-map-v1"

# What a concept, OBSERVED in video, is evidence of. A channel of exposure —
# never a value, never a threshold. `confidence` is how strongly the observation
# ties to the channel. It is not a probability of breach and nothing computes on it.
SUGGESTS = {
    "scheme_cost": [(
        "RISK_CAPEX_DELIVERY", 0.7,
        "A stated scheme cost is a direct read on the size of the capital programme, "
        "which is exactly the channel this risk describes. It sizes the programme. "
        "It does not measure either covenant and supplies no ratio.")],
    "air_traffic_movements": [(
        "RISK_VOLUME_DEMAND", 0.55,
        "A claimed increase in annual movements is a claim about future traffic, which "
        "is the demand channel. Held at moderate confidence because this is a broadcast "
        "figure for permitted capacity, not realised traffic, and permitted is not flown.")],
    # jobs_claimed is deliberately absent. Fourteen thousand jobs is an advocacy
    # figure repeated by three broadcasters and contested by the rally footage; it
    # is a planning argument, not a channel through which either covenant moves.
    # Wiring it to a risk would be the model reaching for coverage.
}

# The 26 July water supply failure proposes nothing here, and that is correct twice
# over. Structurally: Firstpost's nine segments yielded no Observation at all, so
# this layer has no evidence node to start from. Substantively: a human already
# rejected the claim that the outage could affect senior_icr — no flights cancelled,
# the airport never closed, water back across the campus in about eleven hours, a
# terminal-services failure rather than an air-operations one. Routing the same
# overreach through a :Risk node would be the same claim wearing a different edge
# type, so no operational-resilience risk is seeded for it to land on either.

drv = db.driver()


def seed(s):
    text = (pathlib.Path(__file__).resolve().parent / "risk.cypher").read_text()
    for stmt in re.split(r";\s*\n", text):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("//"))
        if body.strip():
            s.run(stmt)
    print("risk.cypher applied")
    for r in s.run("MATCH (c:Covenant)-[e:EXPOSED_TO]->(x:Risk) "
                   "RETURN c.covenant_code AS cov, x.risk_id AS risk, "
                   "e.likelihood AS l, e.impact AS i ORDER BY cov, risk").data():
        print(f"  {r['cov']:11} EXPOSED_TO {r['risk']:24} likelihood {r['l']:6} impact {r['i']}")


def propose(s):
    # Settled pairs, computed before anything is written. A human decision is
    # final rather than merely respected, so these are never re-derived.
    settled = {(r["vid"], r["start"], r["cc"], r["risk"]): (r["status"], r["by"]) for r in s.run(
        """MATCH (o:Observation)-[x:SUGGESTS_RISK]->(r:Risk)
           WHERE x.status <> 'proposed'
           RETURN o.video_id AS vid, o.start AS start, o.concept_code AS cc,
                  r.risk_id AS risk, x.status AS status, x.validated_by AS by""").data()}

    # Observed sources only. This edge exists to carry third-party evidence to a
    # channel; the controlled lane has Facts and needs no such bridge.
    obs = s.run(
        """MATCH (o:Observation)-[:CITES]->(:Segment)-[:PART_OF]->(src:Source)
           WHERE src.provenance_class = 'observed'
           RETURN o.video_id AS vid, o.start AS start, o.concept_code AS cc,
                  src.publisher AS pub, src.url_sha256 AS h, src.url AS url
           ORDER BY o.concept_code, src.publisher""").data()

    quiet = sorted({o["cc"] for o in obs} - set(SUGGESTS))
    if quiet:
        print(f"NO CHANNEL — observed but tied to no risk ({len(quiet)}): {', '.join(quiet)}")
    skipped = [(o, rid) for o in obs for rid, _, _ in SUGGESTS.get(o["cc"], [])
               if (o["vid"], o["start"], o["cc"], rid) in settled]
    if skipped:
        print(f"SETTLED — a human has decided these, not re-derived ({len(skipped)}):")
        for o, rid in skipped:
            st, by = settled[(o["vid"], o["start"], o["cc"], rid)]
            print(f"  · {o['pub'][:18]:20} {o['cc']:22} {rid:24} {st} by {by}")

    n = 0
    for o in obs:
        for rid, conf, why in SUGGESTS.get(o["cc"], []):
            if (o["vid"], o["start"], o["cc"], rid) in settled:
                continue
            # The WHERE guard is belt-and-braces: even a bug in the worklist above
            # cannot overwrite a human decision, and the model cannot write a status
            # other than 'proposed'.
            s.run(
                """MATCH (o:Observation {video_id:$vid, start:$start, concept_code:$cc}),
                         (r:Risk {risk_id:$rid})
                   MERGE (o)-[x:SUGGESTS_RISK {evidence_sha256:$h}]->(r)
                     ON CREATE SET x.status='proposed', x.validated_by=null, x.validated_at=null
                   WITH x WHERE x.status = 'proposed'
                   SET x.asserted_by='model', x.model=$rules, x.asserted_at=datetime(),
                       x.confidence=$conf, x.rationale=$why, x.evidence_url=$url""",
                vid=o["vid"], start=o["start"], cc=o["cc"], rid=rid, h=o["h"],
                url=o["url"], rules=RULES, conf=conf, why=why)
            n += 1
            print(f"  → proposed [{conf:.2f}] {o['pub'][:18]:20} {o['cc']:22} → {rid}")
    print(f"\n{n} edge(s) proposed. Nothing validated — no computation reads any of them.")


def status(s):
    print("=== risks and covenant exposure (structural, not evidence) ===")
    for r in s.run("MATCH (c:Covenant)-[e:EXPOSED_TO]->(x:Risk) "
                   "RETURN x.risk_id AS risk, x.category AS cat, c.covenant_code AS cov, "
                   "e.likelihood AS l, e.impact AS i ORDER BY risk, cov").data():
        print(f"  {r['risk']:24} {r['cat']:14} → {r['cov']:11} {r['l']}/{r['i']}")

    print("\n=== SUGGESTS_RISK — every edge and its attestation state ===")
    rows = s.run(
        """MATCH (o:Observation)-[x:SUGGESTS_RISK]->(r:Risk)
           MATCH (o)-[:CITES]->(:Segment)-[:PART_OF]->(src:Source)
           RETURN src.publisher AS pub, o.concept_code AS cc, r.risk_id AS risk,
                  x.status AS status, x.asserted_by AS by, x.confidence AS conf,
                  x.validated_by AS who, x.rationale AS why
           ORDER BY x.status, risk, pub""").data()
    for r in rows:
        sign = f" by {r['who']}" if r["who"] else ""
        print(f"  [{r['status']:9} by {r['by']:5}{sign}] {r['pub'][:18]:20} "
              f"{r['cc']:22} → {r['risk']:24} conf {r['conf']}")
    live = [r for r in rows if r["status"] == "validated"]
    print(f"\n  {len(rows)} edge(s), {len(live)} validated — a computation reads {len(live)}.")

    print("\n=== invariants (the whole claim of the layer) ===")
    for label, q, want in [
        ("Fact from an observed source",
         "MATCH (f:Fact)-[:FROM]->(s:Source) WHERE s.provenance_class='observed' "
         "RETURN count(*) AS n", 0),
        ("Fact without a controlled source",
         "MATCH (f:Fact) WHERE NOT (f)-[:FROM]->(:Source {provenance_class:'controlled'}) "
         "RETURN count(*) AS n", 0),
        ("Observation on a concept a covenant measures",
         "MATCH (:Observation)-[:OF_CONCEPT]->(:Concept)<-[:MEASURED_BY]-(:Covenant) "
         "RETURN count(*) AS n", 0),
        ("Concept carrying both an Observation and a Fact",
         "MATCH (:Observation)-[:OF_CONCEPT]->(:Concept)<-[:OF_CONCEPT]-(:Fact) "
         "RETURN count(*) AS n", 0),
        ("Observation with any edge into the deal lane",
         "MATCH (:Observation)--(n) "
         "WHERE any(l IN labels(n) WHERE l IN ['Fact','Covenant','Facility','Deal']) "
         "RETURN count(*) AS n", 0),
        ("Value-bearing edge into a covenant from a non-controlled source",
         "MATCH (:Covenant)<-[:TESTS]-(f:Fact)-[:FROM]->(s:Source) "
         "WHERE s.provenance_class <> 'controlled' RETURN count(*) AS n", 0),
        ("SUGGESTS_RISK edge not written 'proposed' by the model",
         "MATCH ()-[x:SUGGESTS_RISK]->() "
         "WHERE x.asserted_by='model' AND x.status<>'proposed' RETURN count(*) AS n", 0),
    ]:
        n = s.run(q).single()["n"]
        print(f"  {'ok  ' if n == want else 'FAIL'} {label}: {n} (want {want})")

    # Case analysis rather than path enumeration: everything that touches a
    # Covenant, and what it is. Only TESTS carries a number, and it comes from
    # the controlled lane. The two edges reachable from video are both attested.
    print("\n  every edge incident on a Covenant:")
    for r in s.run(
        """MATCH (c:Covenant)-[x]-(n)
           RETURN type(x) AS type, labels(n)[0] AS other, count(*) AS n
           ORDER BY type""").data():
        note = {"TESTS": "carries a number — controlled lane only",
                "MAY_AFFECT": "attested", "SUGGESTS_RISK": "attested",
                "EXPOSED_TO": "structural, carries no number",
                "MEASURED_BY": "names the concept, carries no number",
                "GOVERNED_BY": "deal structure"}.get(r["type"], "")
        print(f"    {r['n']:3}  {r['type']:14} {r['other']:12} {note}")

    print("\n  routes an Observation can take to a Covenant:")
    for r in s.run(
        """MATCH p = shortestPath((o:Observation)-[*1..6]-(c:Covenant))
           RETURN [x IN relationships(p) | type(x)] AS route, count(*) AS n
           ORDER BY n DESC""").data():
        crosses = [t for t in r["route"] if t in ("SUGGESTS_RISK", "MAY_AFFECT")]
        print(f"    {r['n']:3}  {' → '.join(r['route'])}"
              f"{'  [crosses ' + crosses[0] + ']' if crosses else '  [UNATTESTED]'}")


def chain(s):
    rows = s.run(
        """MATCH (o:Observation)-[x:SUGGESTS_RISK]->(r:Risk)<-[e:EXPOSED_TO]-(c:Covenant)
                 -[:MEASURED_BY]->(co:Concept)
           MATCH (o)-[:CITES]->(:Segment)-[:PART_OF]->(src:Source)
           RETURN src.publisher AS pub, o.text AS said, x.status AS status,
                  x.confidence AS conf, r.risk_id AS risk, e.likelihood AS l, e.impact AS i,
                  c.covenant_code AS cov, c.direction AS dir, co.code AS concept
           ORDER BY risk, cov, pub""").data()
    w = "  {:<16} {:<42} {:<9} {:<24} {:<14} {:<17} {:<15}"
    print(w.format("SOURCE", "WHAT WAS SAID ON VIDEO", "STATE", "RISK", "LIKELY/IMPACT",
                   "COVENANT", "MEASURED BY"))
    print("  " + "-" * 143)
    for r in rows:
        said = r["said"] if len(r["said"]) <= 42 else r["said"][:41] + "…"
        print(w.format(r["pub"][:16], said, r["status"], r["risk"],
                       f"{r['l']}/{r['i']}", f"{r['cov']} ({r['dir']})", r["concept"]))
    inert = sum(1 for r in rows if r["status"] == "proposed")
    print(f"\n  {len(rows)} chain(s). {inert} rest on a proposed edge and are inert — the "
          f"covenant column is reachable, the covenant's number is not.")


CMDS = {"seed": seed, "propose": propose, "status": status, "chain": chain}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in CMDS:
        sys.exit(f"usage: python -m graph.risk [{' | '.join(CMDS)}]")
    with drv.session() as s:
        CMDS[cmd](s)
    drv.close()
