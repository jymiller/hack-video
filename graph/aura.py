"""Replay the local graph into Neo4j Aura, so the Render-hosted app has a database it can reach.

Driver to driver — no JSON in the middle. That is deliberate: dates and datetimes cross
Bolt as neo4j.time values in both directions and never touch a string, so Event.date arrives
as a DATE and every date comparison keeps matching. A JSON hop is where temporals go to die.

Identity is content-derived, not elementId. `_mig` is a hash of each node's natural key (the
property the local UNIQUE constraint already names) so a re-push after the local graph is
rebuilt still updates the same remote node instead of doubling it.

Vectors go through db.create.setNodeVectorProperty, which stores them compactly and rejects
non-finite components. It does NOT check length against the index — measured, on both 5.26 and
2026.06, a 511-dim vector is accepted by the procedure and by a plain SET, then dropped from a
512-dim index with no error at all. Nothing on the write path catches that, which is why
`verify` compares what the index can return against what is stored.

    AURA_URI=neo4j+s://xxxxxxxx.databases.neo4j.io AURA_USER=neo4j AURA_PASSWORD=... \
      .venv/bin/python -m graph.aura push
    ... -m graph.aura verify
    .venv/bin/python -m graph.aura plan      # reads local only, writes nothing, needs no creds
"""
import hashlib, json, os, sys
from collections import Counter
from neo4j import GraphDatabase
from neo4j.time import Date, DateTime, Time, Duration
import graph.db as db

VECTOR_PROP = "embedding"

# Label -> natural key, taken from the UNIQUE constraints the schema already declares.
# Labels absent here are hashed on their whole property map; they have no natural key
# and are only ever reachable through their relationships anyway.
NATURAL_KEY = {
    "Source": ("id",),
    "Concept": ("code",),
    "Vocabulary": ("name",),
    "Term": ("vocabulary", "value"),
    "Deal": ("legal_name",),
    "Facility": ("facility_code",),
    "Covenant": ("covenant_code",),
    "Event": ("name", "date"),
    "Segment": ("video_id", "start"),
    "ExtractionRun": ("id",),
}


def target():
    missing = [v for v in ("AURA_URI", "AURA_USER", "AURA_PASSWORD") if not os.environ.get(v)]
    if missing:
        sys.exit(f"set {', '.join(missing)} first (see graph/AURA.md)")
    uri = os.environ["AURA_URI"]
    print(f"target: {uri}  user={os.environ['AURA_USER']}")
    return GraphDatabase.driver(uri, auth=(os.environ["AURA_USER"], os.environ["AURA_PASSWORD"]))


def scalar(v):
    """Hashable, stable rendering of a property value. Temporals stringify only here."""
    if isinstance(v, (Date, DateTime, Time, Duration)):
        return str(v)
    if isinstance(v, list):
        return [scalar(x) for x in v]
    return v


def key(labels, props, discriminator=""):
    lab = sorted(labels)
    nk = next((NATURAL_KEY[l] for l in lab if l in NATURAL_KEY), None)
    body = ({k: scalar(props.get(k)) for k in nk} if nk
            else {k: scalar(props[k]) for k in sorted(props) if k != VECTOR_PROP})
    blob = json.dumps([lab, body, discriminator], sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()[:24]


def read_local():
    """The whole graph, plus the schema that has to exist before it lands."""
    drv = db.driver()
    with drv.session() as s:
        cons = [r["createStatement"] for r in
                s.run("SHOW CONSTRAINTS YIELD createStatement RETURN createStatement")]
        idx = s.run("SHOW INDEXES YIELD name, type, owningConstraint, createStatement, options, "
                    "labelsOrTypes, properties RETURN *").data()
        nodes = s.run("MATCH (n) RETURN labels(n) AS labels, properties(n) AS props").data()
        rels = s.run(
            "MATCH (a)-[r]->(b) RETURN labels(a) AS al, properties(a) AS ap, "
            "labels(b) AS bl, properties(b) AS bp, type(r) AS type, properties(r) AS props"
        ).data()
    drv.close()

    for n in nodes:
        n["key"] = key(n["labels"], n["props"])
    for r in rels:
        r["src"] = key(r["al"], r["ap"])
        r["dst"] = key(r["bl"], r["bp"])
        # Parallel MAY_AFFECT edges between the same Event and Covenant are distinct
        # assertions about distinct evidence. Without this they collapse into one.
        r["key"] = key([r["type"]], r["props"], r["src"] + r["dst"])

    # LOOKUP indexes exist on every database already and cannot be renamed into place;
    # constraint-backed indexes come with their constraint. Neither is ours to create.
    schema = [c if " IF NOT EXISTS " in c else c.replace(" FOR ", " IF NOT EXISTS FOR ", 1)
              for c in cons]
    vector = []
    for i in idx:
        if i["owningConstraint"] or i["type"] == "LOOKUP":
            continue
        if i["type"] == "VECTOR":
            vector.append(i)
        else:
            schema.append(i["createStatement"].replace(" FOR ", " IF NOT EXISTS FOR ", 1))
    return schema, vector, nodes, rels


def vector_stmt(i):
    """Rebuild rather than replay. The local createStatement carries quantization settings
    that Aura's newer server deprecates; dimensions and similarity are the parts that matter."""
    cfg = i["options"]["indexConfig"]
    return (f"CREATE VECTOR INDEX `{i['name']}` IF NOT EXISTS FOR (n:`{i['labelsOrTypes'][0]}`) "
            f"ON (n.`{i['properties'][0]}`) OPTIONS {{indexConfig: {{"
            f"`vector.dimensions`: {int(cfg['vector.dimensions'])}, "
            f"`vector.similarity_function`: '{cfg['vector.similarity_function'].lower()}'}}}}")


def grouped(nodes, rels):
    by_label, by_type = {}, {}
    for n in nodes:
        by_label.setdefault(":".join(sorted(n["labels"])), []).append(n)
    for r in rels:
        by_type.setdefault(r["type"], []).append(r)
    return by_label, by_type


def plan():
    schema, vector, nodes, rels = read_local()
    by_label, by_type = grouped(nodes, rels)
    embedded = [n for n in nodes if n["props"].get(VECTOR_PROP)]
    dims = sorted({len(n["props"][VECTOR_PROP]) for n in embedded})

    print(f"source: {db.URI}\n")
    print(f"==> {len(schema)} constraint/index statement(s)")
    for s in schema:
        print(f"    {s}")
    print(f"\n==> {len(vector)} vector index")
    for i in vector:
        print(f"    {vector_stmt(i)}")

    print(f"\n==> {len(nodes)} nodes, MERGE on _mig (re-runnable)")
    for lab, group in sorted(by_label.items()):
        props = sorted({k for g in group for k in g["props"]})
        temporal = sorted({k for g in group for k, v in g["props"].items()
                           if isinstance(v, (Date, DateTime, Time, Duration))})
        note = f"  temporal: {', '.join(temporal)}" if temporal else ""
        print(f"    {lab:<14} {len(group):>4}   {', '.join(p for p in props if p != VECTOR_PROP)[:88]}{note}")

    print(f"\n==> {len(embedded)} embedding(s) via db.create.setNodeVectorProperty, dims {dims}")
    if len(dims) > 1:
        print("    ! mixed dimensions — the odd ones out land but never enter the index; "
              "verify will catch them")

    print(f"\n==> {len(rels)} relationships")
    att = 0
    for rtype, group in sorted(by_type.items()):
        signed = [g for g in group if g["props"].get("validated_by")]
        att += len(signed)
        mark = f"   {len(signed)} human-signed" if signed else ""
        print(f"    {rtype:<14} {len(group):>4}{mark}")
    print(f"\n==> {att} attestation edge(s) carried verbatim "
          "(status / validated_by / validated_at)")
    for r in rels:
        if r["props"].get("validated_by"):
            p = r["props"]
            print(f"    {p.get('status', '?'):<10} {p['validated_by']:<6} {p.get('validated_at')}  "
                  f"{r['ap'].get('name', '')[:34]} -> {r['bp'].get('covenant_code', '')}")
    print("\nnothing was written.")


def push():
    schema, vector, nodes, rels = read_local()
    by_label, by_type = grouped(nodes, rels)
    drv = target()
    with drv.session() as s:
        print(f"==> schema ({len(schema)})")
        for stmt in schema:
            s.run(stmt)
        # _mig is the join key for the whole push; without an index the MERGEs go quadratic.
        s.run("CREATE INDEX mig_key IF NOT EXISTS FOR (n:Migrated) ON (n._mig)")

        print(f"==> {len(nodes)} nodes")
        for lab, group in sorted(by_label.items()):
            marks = "".join(f":`{l}`" for l in lab.split(":"))
            s.run(
                f"UNWIND $rows AS row MERGE (n:Migrated {{_mig: row.key}}) "
                f"SET n{marks} SET n += row.props",
                rows=[{"key": g["key"],
                       "props": {k: v for k, v in g["props"].items() if k != VECTOR_PROP}}
                      for g in group],
            )
            print(f"    {lab:<14} {len(group):>4}")

        embedded = [n for n in nodes if n["props"].get(VECTOR_PROP)]
        print(f"==> {len(embedded)} embedding(s)")
        s.run("UNWIND $rows AS row MATCH (n:Migrated {_mig: row.key}) "
              "CALL db.create.setNodeVectorProperty(n, $p, row.v)",
              p=VECTOR_PROP,
              rows=[{"key": n["key"], "v": n["props"][VECTOR_PROP]} for n in embedded])

        print(f"==> {len(rels)} relationships")
        for rtype, group in sorted(by_type.items()):
            s.run(
                "UNWIND $rows AS row "
                "MATCH (a:Migrated {_mig: row.src}) MATCH (b:Migrated {_mig: row.dst}) "
                f"MERGE (a)-[r:`{rtype}` {{_mig: row.key}}]->(b) SET r += row.props",
                rows=[{"src": g["src"], "dst": g["dst"], "key": g["key"], "props": g["props"]}
                      for g in group],
            )
            print(f"    {rtype:<14} {len(group):>4}")

        print(f"==> vector index ({len(vector)})")
        for i in vector:
            s.run(vector_stmt(i))
        s.run("CALL db.awaitIndexes(600)")
    drv.close()
    verify()


def census(s):
    one = lambda q: s.run(q).single()[0]
    labels = Counter()
    for r in s.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c"):
        if r["l"] != "Migrated":
            labels[r["l"]] = r["c"]
    return {
        "nodes": one("MATCH (n) RETURN count(n)"),
        "rels": one("MATCH ()-[r]->() RETURN count(r)"),
        "labels": labels,
        "embedded": one(f"MATCH (n:Segment) WHERE n.{VECTOR_PROP} IS NOT NULL RETURN count(n)"),
        "attested": one("MATCH ()-[r]->() WHERE r.validated_by IS NOT NULL RETURN count(r)"),
        "dates": sorted(s.run("MATCH (e:Event) RETURN DISTINCT valueType(e.date) AS t").value()),
    }


def reach(s, i):
    """How many stored vectors the index can actually return, against how many are stored.
    A wrong-length vector is accepted on write and then dropped from the index with no error —
    the search just quietly returns less, forever. The probe is taken at the index's own
    dimensionality so a corrupt vector shows up as a shortfall, not as a crashed query."""
    label, prop = i["labelsOrTypes"][0], i["properties"][0]
    dim = int(i["options"]["indexConfig"]["vector.dimensions"])
    n = s.run(f"MATCH (x:`{label}`) WHERE x.`{prop}` IS NOT NULL RETURN count(x)").single()[0]
    probe = s.run(f"MATCH (x:`{label}`) WHERE size(x.`{prop}`) = $d RETURN x.`{prop}` AS v LIMIT 1",
                  d=dim).single()
    if not n or probe is None:
        return 0, n
    hits = s.run("CALL db.index.vector.queryNodes($i, $k, $v) YIELD node RETURN count(node)",
                 i=i["name"], k=n, v=probe["v"]).single()[0]
    return hits, n


VEC_META = ("SHOW VECTOR INDEXES YIELD name, labelsOrTypes, properties, options, state, "
            "populationPercent RETURN *")


def verify():
    src = db.driver()
    with src.session() as s:
        vec = s.run(VEC_META).data()
        local = census(s)
        lreach = reach(s, vec[0]) if vec else (0, 0)
    src.close()
    name = vec[0]["name"] if vec else None

    drv = target()
    with drv.session() as s:
        remote = census(s)
        idx = next((r for r in s.run(VEC_META).data() if r["name"] == name), None)
        rreach = reach(s, idx) if idx else (0, 0)
    drv.close()

    bad = 0
    def row(label, a, b):
        nonlocal bad
        ok = a == b
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {label:<22} local {str(a):<28} remote {b}")

    print("\n           local vs remote")
    row("nodes", local["nodes"], remote["nodes"])
    row("relationships", local["rels"], remote["rels"])
    row("embedded segments", local["embedded"], remote["embedded"])
    row("attestation edges", local["attested"], remote["attested"])
    row("Event.date type", local["dates"], remote["dates"])
    for lab in sorted(set(local["labels"]) | set(remote["labels"])):
        row(f"  :{lab}", local["labels"][lab], remote["labels"][lab])

    state = idx["state"] if idx else "MISSING"
    ok = state == "ONLINE"
    bad += not ok
    print(f"  {'ok ' if ok else 'BAD'} {'vector index':<22} {name} {state} "
          f"{idx['populationPercent'] if idx else ''}")

    ok = rreach[0] == rreach[1] and rreach == lreach
    bad += not ok
    print(f"  {'ok ' if ok else 'BAD'} {'queryNodes reach':<22} local {lreach[0]}/{lreach[1]:<20} "
          f"remote {rreach[0]}/{rreach[1]}")
    if rreach[0] != rreach[1]:
        print("      ! silent exclusion — vectors are stored but not indexed, search under-returns")

    print("\nremote matches local." if not bad else f"\n{bad} mismatch(es).")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    {"plan": plan, "push": push, "verify": verify}.get(cmd, lambda: sys.exit(__doc__))()
