"""Embed segment transcripts so the graph can be searched by meaning, not keyword.

Marengo text embeddings, 512-dim, cosine. The same model must serve both corpus and
query — mixing models silently returns nonsense rather than an error.

    python graph/embed.py backfill     embed every segment that lacks one
    python graph/embed.py verify       indexed count vs embedded count
    python graph/embed.py ask "..."    vector search, joined back to source + observation
"""
import os, sys, pathlib
from dotenv import load_dotenv
from neo4j import GraphDatabase
from twelvelabs import TwelveLabs

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

MODEL = "marengo3.0"
DIM = 512
INDEX = "segment_embedding"

tl = TwelveLabs(api_key=os.environ["TWELVELABS_API_KEY"])
drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))


def embed(text):
    r = tl.embed.create(model_name=MODEL, text=text)
    return r.text_embedding.segments[0].float_


def ensure_index(s):
    s.run(
        f"CREATE VECTOR INDEX {INDEX} IF NOT EXISTS FOR (s:Segment) ON (s.embedding) "
        "OPTIONS {indexConfig: {`vector.dimensions`: $d, `vector.similarity_function`: 'cosine'}}",
        d=DIM,
    )


def backfill():
    with drv.session() as s:
        ensure_index(s)
        todo = s.run(
            "MATCH (seg:Segment) WHERE seg.transcript IS NOT NULL AND size(seg.transcript) > 25 "
            "AND seg.embedding IS NULL RETURN elementId(seg) AS id, seg.transcript AS t"
        ).data()
        print(f"{len(todo)} segment(s) to embed")
        for i, row in enumerate(todo, 1):
            vec = embed(row["t"])
            if len(vec) != DIM:
                sys.exit(f"dimension mismatch: got {len(vec)}, index expects {DIM}")
            # setNodeVectorProperty validates the vector; a plain SET does not, and a
            # wrong-length array is then dropped from the index with no error at all.
            s.run(
                "MATCH (seg) WHERE elementId(seg) = $id "
                "CALL db.create.setNodeVectorProperty(seg, 'embedding', $v)",
                id=row["id"], v=vec,
            )
            print(f"  [{i}/{len(todo)}] {row['t'][:58]}")
    verify()


def verify():
    with drv.session() as s:
        n = s.run("MATCH (seg:Segment) WHERE seg.embedding IS NOT NULL RETURN count(seg) AS n").single()["n"]
        total = s.run("MATCH (seg:Segment) RETURN count(seg) AS n").single()["n"]
        state = s.run(
            "SHOW VECTOR INDEXES YIELD name, state WHERE name = $i RETURN state", i=INDEX
        ).single()
        reach = 0
        if n:
            probe = s.run(
                "MATCH (seg:Segment) WHERE seg.embedding IS NOT NULL RETURN seg.embedding AS v LIMIT 1"
            ).single()["v"]
            reach = len(s.run(
                f"CALL db.index.vector.queryNodes('{INDEX}', $k, $v) YIELD node RETURN node", k=n, v=probe
            ).data())
        print(f"embedded {n}/{total} segments · index {state['state'] if state else 'MISSING'} · reachable {reach}/{n}")
        if n and reach != n:
            print("  ! silent exclusion — some vectors are not in the index")


def ask(question):
    qv = embed(question)
    with drv.session() as s:
        rows = s.run(
            f"CALL db.index.vector.queryNodes('{INDEX}', 5, $v) YIELD node, score "
            "MATCH (node)-[:PART_OF]->(src:Source) "
            "OPTIONAL MATCH (o:Observation)-[:CITES]->(node) "
            "RETURN src.publisher AS publisher, node.video_id AS vid, node.start AS start, "
            "score, node.transcript AS t, o.value AS value ORDER BY score DESC",
            v=qv,
        ).data()
    for r in rows:
        val = f"  value={r['value']}" if r["value"] is not None else ""
        print(f"{r['score']:.3f}  {r['publisher']}  @{r['start']:.1f}s{val}\n       {r['t'][:96]}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "backfill":
        backfill()
    elif cmd == "verify":
        verify()
    elif cmd == "ask":
        ask(sys.argv[2])
    else:
        sys.exit(__doc__)
    drv.close()
