"""Load graph/dump/graph-export.json into NEO4J_URI. The missing half of the export.

The graph was reproducible only by re-deriving it: `make graph` queries the TwelveLabs
cloud index, and `extract.py` / `assert_impact.py` then spend ~95 model calls to rebuild
Observations, corroboration and the proposed assertions. That is fine on a laptop with
network and a key. It is the wrong tool for standing up a copy — a remote database, a
CI run, a machine with no vendor credentials — because it is slow, costs money, and
cannot reproduce the graph exactly.

This does it deterministically and offline: same nodes, same relationships, same
properties, including the human attestations. Nothing is inferred.

    NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io NEO4J_USER=xxxx \\
    NEO4J_PASSWORD=... python graph/import_dump.py

Refuses to run against a database that already has nodes, unless --force is passed —
so it cannot silently double a graph or clobber a live one.

Caveat worth knowing: the exporter stringified temporal values, so dates arrive as ISO
strings rather than Neo4j date/datetime types. Every query in the app either wraps them
in toString() or orders them lexicographically, which ISO-8601 makes correct, so this
renders identically. It is not a faithful round-trip of the type system, and a query
doing date arithmetic would need the export fixed first.
"""
import json, os, pathlib, sys

from neo4j import GraphDatabase

ROOT = pathlib.Path(__file__).resolve().parent.parent
DUMP = ROOT / "graph/dump/graph-export.json"
FORCE = "--force" in sys.argv

drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                           auth=(os.environ.get("NEO4J_USER", "neo4j"),
                                 os.environ.get("NEO4J_PASSWORD", "hackvideo2026")))

d = json.loads(DUMP.read_text())
nodes, rels = d["nodes"], d["relationships"]
print(f"{DUMP.relative_to(ROOT)}: {len(nodes)} nodes, {len(rels)} relationships")

with drv.session() as s:
    existing = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
    if existing and not FORCE:
        sys.exit(f"REFUSED: target already holds {existing} nodes. Pass --force to add anyway.")

    # Labels come from the dump, so they cannot be parameterised. They are our own
    # export, not user input, but validate anyway rather than formatting blind.
    for n in nodes:
        labels = [l for l in n["labels"] if l.replace("_", "").isalnum()]
        if len(labels) != len(n["labels"]):
            sys.exit(f"REFUSED: suspicious label in {n['labels']}")
        s.run(f"CREATE (x:{':'.join(labels)}) SET x = $props, x._dump_id = $id",
              props=n["props"], id=n["id"])
    print(f"  {len(nodes)} nodes created")

    s.run("CREATE INDEX dump_id IF NOT EXISTS FOR (n:_All) ON (n._dump_id)")
    made = 0
    for r in rels:
        t = r["type"]
        if not t.replace("_", "").isalnum():
            sys.exit(f"REFUSED: suspicious relationship type {t!r}")
        res = s.run(f"""MATCH (a) WHERE a._dump_id = $src
                        MATCH (b) WHERE b._dump_id = $dst
                        CREATE (a)-[x:{t}]->(b) SET x = $props
                        RETURN count(x) AS n""",
                    src=r["src"], dst=r["dst"], props=r["props"]).single()
        made += res["n"]
    print(f"  {made} relationships created")

    # The scaffolding must not outlive the import — a _dump_id left on every node
    # would show up in the explainers' property panels and in any SET x = $props.
    s.run("MATCH (n) WHERE n._dump_id IS NOT NULL REMOVE n._dump_id")
    s.run("DROP INDEX dump_id IF EXISTS")

    n = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
    e = s.run("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
    leftover = s.run("MATCH (n) WHERE n._dump_id IS NOT NULL RETURN count(n) AS n").single()["n"]
    print(f"\nnow in target: {n} nodes, {e} relationships, {leftover} with leftover _dump_id")
    if (n, e, leftover) != (len(nodes), len(rels), 0):
        sys.exit("MISMATCH against the dump — do not trust this database")
    print("matches the dump exactly")

drv.close()
