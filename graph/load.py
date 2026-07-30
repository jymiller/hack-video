"""Load video evidence into the graph, driven by the concept vocabulary.

The point: we never hand-write a search string. Each Concept carries `probes`,
so the same vocabulary that structures storage also structures retrieval.
"""
import os, sys, json, time, pathlib
import httpx
from dotenv import load_dotenv
import graph.db as db

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

TL = os.environ["TWELVELABS_API_KEY"]
BASE = "https://api.twelvelabs.io/v1.3"
HDR = {"x-api-key": TL}
INDEX = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TL_INDEX")

drv = db.driver()
http = httpx.Client(timeout=120.0)


def videos():
    r = http.get(f"{BASE}/indexes/{INDEX}/videos", headers=HDR, params={"page_limit": 50})
    r.raise_for_status()
    return r.json().get("data", [])


def search(query):
    parts = [("index_id", (None, INDEX)), ("query_text", (None, query))]
    for o in ("visual", "audio"):
        parts.append(("search_options", (None, o)))
    r = http.post(f"{BASE}/search", headers=HDR, files=parts)
    if r.status_code != 200:
        print(f"    ! search failed {r.status_code}")
        return []
    return r.json().get("data", [])


def publisher_of(filename):
    bits = filename.split("__")
    return bits[1] if len(bits) > 1 else filename


SOURCE_KIND = {
    "SussexWorld": "rally_footage",
    "TalkTV": "commentary",
}

with drv.session() as s:
    # ---- 1. sources + the run ---------------------------------------------
    run_id = f"marengo3.0-{int(time.time())}"
    s.run(
        "MERGE (r:ExtractionRun {id:$id}) SET r.model='marengo3.0', r.purpose='concept-driven retrieval', "
        "r.started_at=datetime()", id=run_id,
    )

    vids = videos()
    print(f"{len(vids)} videos in index")
    by_id = {}
    for v in vids:
        sm = v.get("system_metadata", {}) or {}
        fn = (v.get("user_metadata") or {}).get("filename") or sm.get("filename") or v["_id"]
        pub = publisher_of(fn)
        by_id[v["_id"]] = fn
        s.run(
            """MERGE (src:Source {id:$id})
               SET src.provenance_class='observed', src.kind=$kind,
                   src.publisher=$pub, src.filename=$fn, src.duration=$dur""",
            id=v["_id"], kind=SOURCE_KIND.get(pub, "broadcast_news"),
            pub=pub, fn=fn, dur=sm.get("duration"),
        )
    print(f"  {len(vids)} Source nodes")

    # ---- 2. concept-driven retrieval --------------------------------------
    concepts = s.run(
        "MATCH (c:Concept) WHERE size(c.probes) > 0 RETURN c.code AS code, c.probes AS probes"
    ).data()

    total_seg = 0
    for c in concepts:
        seen = set()
        print(f"\n{c['code']}")
        for probe in c["probes"]:
            hits = search(probe)
            print(f"  probe: {probe[:52]:54} {len(hits)} hits")
            for h in hits:
                key = (h["video_id"], round(h["start"], 1))
                if key in seen:
                    continue
                seen.add(key)
                s.run(
                    """MATCH (src:Source {id:$vid})
                       MERGE (seg:Segment {video_id:$vid, start:$start})
                         SET seg.end=$end, seg.transcript=$tx
                       MERGE (seg)-[:PART_OF]->(src)
                       WITH seg
                       MATCH (co:Concept {code:$code})
                       MERGE (seg)-[e:CANDIDATE_FOR]->(co)
                         SET e.probe=$probe, e.rank=$rank
                       WITH seg
                       MATCH (r:ExtractionRun {id:$run})
                       MERGE (seg)-[:PRODUCED_BY]->(r)""",
                    vid=h["video_id"], start=round(h["start"], 1), end=round(h["end"], 1),
                    tx=h.get("transcription"), code=c["code"], probe=probe,
                    rank=h.get("rank"), run=run_id,
                )
                total_seg += 1
        print(f"  -> {len(seen)} distinct segments")

    print(f"\n{total_seg} segment-concept links written")

    # ---- 3. what did we get? ----------------------------------------------
    print("\n=== coverage by concept ===")
    for row in s.run(
        """MATCH (co:Concept)
           OPTIONAL MATCH (seg:Segment)-[:CANDIDATE_FOR]->(co)
           OPTIONAL MATCH (seg)-[:PART_OF]->(src:Source)
           RETURN co.code AS concept, co.reachable_by AS lane,
                  count(DISTINCT seg) AS segments, count(DISTINCT src) AS sources
           ORDER BY segments DESC"""
    ).data():
        print(f"  {row['concept']:24} {row['lane']:11} {row['segments']:3} segs  "
              f"{row['sources']} sources")

drv.close()
