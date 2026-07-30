"""Replay graph/dump/graph-export.json into a target Neo4j (Aura or local).

The export carries the 512-dim Marengo embeddings, so this migrates meaning as well
as structure — no TwelveLabs re-embed, no API spend, no drift between corpus and query.

Temporal properties are JSON strings and must be cast back, or Event.date arrives as
a STRING and every date comparison silently stops matching.

    NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io NEO4J_PASSWORD=... \
      .venv/bin/python -m graph.migrate load
    ... -m graph.migrate verify
"""
import json, os, pathlib, sys
from collections import defaultdict
from neo4j import GraphDatabase

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPORT = ROOT / "graph" / "dump" / "graph-export.json"
SCHEMA = ROOT / "graph" / "schema.cypher"

INDEX, DIM = "segment_embedding", 512

# (label|reltype, property) -> Cypher cast. Verified against the live graph with
# valueType(); everything not listed here round-trips as a plain JSON scalar.
TEMPORAL = {
    ("Event", "date"): "date",
    ("Fact", "as_of"): "date",
    ("Source", "as_of"): "date",
    ("ExtractionRun", "started_at"): "datetime",
    ("MAY_AFFECT", "asserted_at"): "datetime",
    ("MAY_AFFECT", "validated_at"): "datetime",
}


def target():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ.get("NEO4J_PASSWORD", "hackvideo2026")
    print(f"target: {uri}")
    return GraphDatabase.driver(uri, auth=(user, pw))


def casts(kind, keys):
    """SET clauses that put temporals back into native types."""
    return "".join(
        f" SET n.{k} = {TEMPORAL[(kind, k)]}(n.{k})"
        for k in keys if (kind, k) in TEMPORAL
    )


def load():
    data = json.loads(EXPORT.read_text())
    nodes, rels = data["nodes"], data["relationships"]
    drv = target()
    with drv.session() as s:
        existing = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        if existing:
            sys.exit(f"refusing to load: target already has {existing} nodes. "
                     "Wipe it first with `-m graph.migrate wipe`.")

        print("==> constraints")
        for stmt in [x.strip() for x in SCHEMA.read_text().split(";") if x.strip()]:
            if not stmt.startswith("//"):
                s.run(stmt)

        print(f"==> {len(nodes)} nodes")
        by_label = defaultdict(list)
        for n in nodes:
            by_label[tuple(n["labels"])].append(n)
        for labels, group in by_label.items():
            lab = ":".join(labels)
            keys = {k for g in group for k in g["props"]}
            q = (f"UNWIND $rows AS row CREATE (n:{lab}) "
                 f"SET n = row.props SET n._mig = row.id" + casts(labels[0], keys))
            s.run(q, rows=[{"id": g["id"], "props": g["props"]} for g in group])
            print(f"    {lab:<14} {len(group)}")

        print(f"==> {len(rels)} relationships")
        by_type = defaultdict(list)
        for r in rels:
            by_type[r["type"]].append(r)
        for rtype, group in by_type.items():
            keys = {k for g in group for k in (g.get("props") or {})}
            q = ("UNWIND $rows AS row "
                 "MATCH (a {_mig: row.src}) MATCH (b {_mig: row.dst}) "
                 f"CREATE (a)-[n:{rtype}]->(b) SET n = row.props" + casts(rtype, keys))
            s.run(q, rows=[{"src": g["src"], "dst": g["dst"],
                            "props": g.get("props") or {}} for g in group])
            print(f"    {rtype:<14} {len(group)}")

        s.run("MATCH (n) REMOVE n._mig")

        print("==> vector index")
        s.run(f"CREATE VECTOR INDEX {INDEX} IF NOT EXISTS FOR (s:Segment) "
              "ON (s.embedding) OPTIONS {indexConfig: {`vector.dimensions`: $d, "
              "`vector.similarity_function`: 'cosine'}}", d=DIM)
        s.run("CALL db.awaitIndexes(300)")
    drv.close()
    verify()


def verify():
    drv = target()
    with drv.session() as s:
        one = lambda q: s.run(q).single()[0]
        print(f"nodes            {one('MATCH (n) RETURN count(n)')}")
        print(f"relationships    {one('MATCH ()-[r]->() RETURN count(r)')}")
        print(f"embedded         {one('MATCH (s:Segment) WHERE s.embedding IS NOT NULL RETURN count(s)')}")
        dims = s.run("MATCH (s:Segment) WHERE s.embedding IS NOT NULL "
                     "RETURN DISTINCT size(s.embedding) AS d").value()
        print(f"embedding dims   {dims}")
        types = s.run("MATCH (e:Event) RETURN DISTINCT valueType(e.date) AS t").value()
        print(f"Event.date type  {types}")
        idx = s.run("SHOW INDEXES YIELD name, type, state WHERE type='VECTOR' "
                    "RETURN name, state").data()
        print(f"vector index     {idx}")
        # The invariant the whole schema exists to protect.
        leak = one("MATCH (c:Covenant)-[:MEASURED_BY]->(co:Concept) "
                   "OPTIONAL MATCH (seg:Segment)-[:CANDIDATE_FOR]->(co) RETURN count(seg)")
        print(f"video->covenant  {leak}   (must be 0)")
    drv.close()


def wipe():
    drv = target()
    with drv.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    drv.close()
    print("target emptied")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    {"load": load, "verify": verify, "wipe": wipe}[cmd]()
