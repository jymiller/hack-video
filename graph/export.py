"""Regenerate graph/dump/graph-export.json from a live Neo4j.

The dump is the only copy of this graph that survives a container rm, and it carries
the 512-dim Marengo embeddings, so a reload costs no TwelveLabs spend and drifts
nothing between corpus and query. It was previously produced ad hoc, which is why it
went stale.

Native temporal types (DATE, ZONED DATETIME, ...) have no JSON representation and
come back as plain strings. Uncast, Event.date arrives as a STRING and every date
comparison silently stops matching -- no error, just zero rows. So the dump records
which properties are temporal, discovered from the live graph with valueType() rather
than from a hand-kept list that a new label can fall off of. The reader applies that
map; nobody has to remember it.

    make graph-dump
    .venv/bin/python -m graph.export dump
    .venv/bin/python -m graph.export fingerprint     # counts/types of the live db
    .venv/bin/python -m graph.export load            # replay into $NEO4J_URI

Shape is unchanged from graph/migrate.py -- {nodes:[{id,labels,props}],
relationships:[{src,dst,type,props}]} -- with the temporal map added alongside.
"""
import json, os, pathlib, sys
from collections import defaultdict

from neo4j import GraphDatabase
from neo4j.time import Date, DateTime, Duration, Time

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPORT = ROOT / "graph" / "dump" / "graph-export.json"
SCHEMA = ROOT / "graph" / "schema.cypher"

INDEX, DIM = "segment_embedding", 512

# valueType() base name -> the Cypher function that casts the string back.
CASTS = {
    "DATE": "date",
    "ZONED DATETIME": "datetime",
    "LOCAL DATETIME": "localdatetime",
    "ZONED TIME": "time",
    "LOCAL TIME": "localtime",
    "DURATION": "duration",
}


def driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    pw = os.environ.get("NEO4J_PASSWORD", "hackvideo2026")
    print(f"target: {uri}", file=sys.stderr)
    return GraphDatabase.driver(uri, auth=(user, pw))


def base_type(t):
    """'ZONED DATETIME NOT NULL' -> 'ZONED DATETIME'."""
    return t.replace(" NOT NULL", "").strip()


def discover_temporals(s):
    """{'Event.date': 'date', ...} for nodes and rels, straight from the live graph.

    Anything whose valueType() is temporal gets a cast. Everything else -- including
    Covenant.latest_as_of, which is a genuine STRING -- is left alone.
    """
    found = {"nodes": {}, "relationships": {}}
    mixed = []
    scans = [
        ("nodes", s.run("CALL db.labels() YIELD label RETURN label").value(),
         "MATCH (n:`{}`) UNWIND keys(n) AS k "
         "RETURN k, collect(DISTINCT valueType(n[k])) AS types"),
        ("relationships",
         s.run("CALL db.relationshipTypes() YIELD relationshipType AS t RETURN t").value(),
         "MATCH ()-[n:`{}`]->() UNWIND keys(n) AS k "
         "RETURN k, collect(DISTINCT valueType(n[k])) AS types"),
    ]
    for kind, names, tmpl in scans:
        for name in names:
            for row in s.run(tmpl.format(name)):
                types = {base_type(t) for t in row["types"]}
                temporal = types & set(CASTS)
                if not temporal:
                    continue
                if len(types) > 1:
                    mixed.append(f"{name}.{row['k']} {sorted(types)}")
                found[kind][f"{name}.{row['k']}"] = CASTS[sorted(temporal)[0]]
    for m in mixed:
        print(f"    WARNING mixed types, casting anyway: {m}", file=sys.stderr)
    return found


def encode(v):
    """Native -> JSON. Temporals become ISO strings; the map says how to undo it."""
    if isinstance(v, (Date, DateTime, Time, Duration)):
        return str(v)
    if isinstance(v, list):
        return [encode(x) for x in v]
    return v


def dump():
    drv = driver()
    with drv.session() as s:
        temporal = discover_temporals(s)
        print(f"==> temporal properties: {len(temporal['nodes'])} node, "
              f"{len(temporal['relationships'])} relationship", file=sys.stderr)
        for scope in ("nodes", "relationships"):
            for k, fn in sorted(temporal[scope].items()):
                print(f"    {k:<30} {fn}()", file=sys.stderr)

        nodes = [
            {"id": r["id"], "labels": sorted(r["labels"]),
             "props": {k: encode(v) for k, v in sorted(r["props"].items())}}
            for r in s.run("MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, "
                           "properties(n) AS props")
        ]
        rels = [
            {"src": r["src"], "dst": r["dst"], "type": r["type"],
             "props": {k: encode(v) for k, v in sorted(r["props"].items())}}
            for r in s.run("MATCH (a)-[r]->(b) RETURN elementId(a) AS src, "
                           "elementId(b) AS dst, type(r) AS type, properties(r) AS props")
        ]
    drv.close()

    # Stable order so the committed file diffs meaningfully instead of reshuffling.
    nodes.sort(key=lambda n: (n["labels"], n["id"]))
    rels.sort(key=lambda r: (r["type"], r["src"], r["dst"]))

    payload = {
        "temporal": temporal,
        "nodes": nodes,
        "relationships": rels,
    }
    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    EXPORT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")

    labels = defaultdict(int)
    for n in nodes:
        labels[":".join(n["labels"])] += 1
    print(f"==> wrote {EXPORT.relative_to(ROOT)}", file=sys.stderr)
    print(f"    {len(nodes)} nodes, {len(rels)} relationships", file=sys.stderr)
    for lab, c in sorted(labels.items()):
        print(f"    {lab:<16} {c}", file=sys.stderr)


def casts(scope, name, keys, temporal):
    return "".join(
        f" SET n.{k} = {temporal[scope][f'{name}.{k}']}(n.{k})"
        for k in sorted(keys) if f"{name}.{k}" in temporal[scope]
    )


def load():
    """Replay the dump into $NEO4J_URI, casting temporals per the embedded map."""
    data = json.loads(EXPORT.read_text())
    nodes, rels = data["nodes"], data["relationships"]
    temporal = data.get("temporal") or {"nodes": {}, "relationships": {}}
    drv = driver()
    with drv.session() as s:
        existing = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        if existing:
            sys.exit(f"refusing to load: target already has {existing} nodes")

        print("==> constraints", file=sys.stderr)
        for stmt in [x.strip() for x in SCHEMA.read_text().split(";") if x.strip()]:
            if not stmt.startswith("//"):
                s.run(stmt)

        print(f"==> {len(nodes)} nodes", file=sys.stderr)
        by_label = defaultdict(list)
        for n in nodes:
            by_label[tuple(n["labels"])].append(n)
        for labels, group in by_label.items():
            keys = {k for g in group for k in g["props"]}
            cast = "".join(casts("nodes", lab, keys, temporal) for lab in labels)
            s.run(f"UNWIND $rows AS row CREATE (n:{':'.join(labels)}) "
                  f"SET n = row.props SET n._mig = row.id" + cast,
                  rows=[{"id": g["id"], "props": g["props"]} for g in group])

        print(f"==> {len(rels)} relationships", file=sys.stderr)
        by_type = defaultdict(list)
        for r in rels:
            by_type[r["type"]].append(r)
        for rtype, group in by_type.items():
            keys = {k for g in group for k in (g.get("props") or {})}
            s.run("UNWIND $rows AS row MATCH (a {_mig: row.src}) MATCH (b {_mig: row.dst}) "
                  f"CREATE (a)-[n:{rtype}]->(b) SET n = row.props"
                  + casts("relationships", rtype, keys, temporal),
                  rows=[{"src": g["src"], "dst": g["dst"],
                         "props": g.get("props") or {}} for g in group])

        s.run("MATCH (n) REMOVE n._mig")
        print("==> vector index", file=sys.stderr)
        s.run(f"CREATE VECTOR INDEX {INDEX} IF NOT EXISTS FOR (s:Segment) "
              "ON (s.embedding) OPTIONS {indexConfig: {`vector.dimensions`: $d, "
              "`vector.similarity_function`: 'cosine'}}", d=DIM)
        s.run("CALL db.awaitIndexes(300)")
    drv.close()


def fingerprint():
    """Everything the round trip has to preserve, as comparable JSON."""
    drv = driver()
    with drv.session() as s:
        one = lambda q: s.run(q).single()[0]
        fp = {
            "nodes": one("MATCH (n) RETURN count(n)"),
            "relationships": one("MATCH ()-[r]->() RETURN count(r)"),
            "labels": {r["l"]: r["c"] for r in s.run(
                "MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c ORDER BY l")},
            "reltypes": {r["t"]: r["c"] for r in s.run(
                "MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c ORDER BY t")},
            "embedded": one("MATCH (s:Segment) WHERE s.embedding IS NOT NULL RETURN count(s)"),
            "embedding_dims": sorted(s.run(
                "MATCH (s:Segment) WHERE s.embedding IS NOT NULL "
                "RETURN DISTINCT size(s.embedding) AS d").value()),
            "temporal": discover_temporals(s),
            # Signed human decisions. Not rebuildable -- if these drift, stop.
            "attestations": [dict(r) for r in s.run(
                "MATCH (a)-[r]->(b) WHERE r.status IS NOT NULL "
                "RETURN type(r) AS type, r.status AS status, "
                "r.validated_by AS validated_by, toString(r.validated_at) AS validated_at, "
                "r.asserted_by AS asserted_by, toString(r.asserted_at) AS asserted_at, "
                "r.human_note AS human_note, r.evidence_sha256 AS evidence_sha256 "
                "ORDER BY type, status, asserted_at, evidence_sha256")],
        }
    drv.close()
    print(json.dumps(fp, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "dump"
    {"dump": dump, "load": load, "fingerprint": fingerprint}[cmd]()
