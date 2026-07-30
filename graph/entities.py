"""Who and what the segments are about, and the order they came in.

The graph already knows that a segment measured £2.2bn. It does not know that
Channel 4 and TalkTV were talking about the *same airport*. This layer adds the
two things that make a pile of clips into a corpus:

    (:Segment)-[:MENTIONS {surface_form}]->(:Entity {name_normalized, name, type})
    (:Segment)-[:ABOUT]->(:Topic {name_normalized, name})
    (:Segment)-[:NEXT]->(:Segment)     within one video, in time order

The entire value is in the MERGE collapsing across broadcasters. That does not
happen for free. Extraction runs once per video and has no memory of earlier
runs, so "use the same canonical name every time" is an instruction the model
physically cannot follow — it has no idea what it chose for the last clip. So
before each video we read the names already in the graph and hand them back to
the model as the vocabulary to reuse. Without that step the merge is a coin
flip and Gatwick ends up as three nodes.

Segments are the unit of work and they already exist; nothing here creates or
edits one. Five of the sixty-three carry no usable transcript. They get no
entities. That is the honest answer for a segment with nothing said in it.

    python -m graph.entities extract [--force]
    python -m graph.entities chain
    python -m graph.entities status
"""
import os
import sys
import pathlib
import difflib
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI

import graph.db as db

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

# The bare 'gpt-5.6' alias routes to the flagship tier at ~25x the price. This
# job is high-volume and structured; it wants the cheap sibling, named exactly.
MODEL = os.environ.get("HACK_ENTITY_MODEL", "gpt-5.6-luna")
MIN_TRANSCRIPT = 25
VOCAB_LIMIT = 400

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

EntityType = Literal[
    "person", "organization", "location", "object", "product", "brand", "event", "concept"
]


class Mention(BaseModel):
    name: str
    type: EntityType
    surface_form: str


class SegmentEntities(BaseModel):
    index: int
    entities: list[Mention]
    topics: list[str]


class VideoEntities(BaseModel):
    segments: list[SegmentEntities]


SYSTEM = """You label fragments of broadcast news with the entities and topics they refer to.

The transcripts are raw speech-to-text and are noisy. "Getwork" and "Gatwig" are
Gatwick, "heatrows" is Heathrow, "Bow Beach" is Bough Beech. Give `name` as the
real-world thing, correctly spelled, and put the words that actually appear in
that segment in `surface_form`.

For every segment you are given, return:
  - entities: the specific things named or clearly referred to IN THAT SEGMENT.
    People, organizations, locations, objects, products, brands, events. A
    `concept` only for a named abstraction that behaves like a thing (Judicial
    Review, Sustainable Aviation Fuel), not for a subject matter.
  - topics: 1 to 3 subject matters that segment is about, as short noun phrases
    (Airport Expansion, Carbon Emissions, Judicial Review). Topics are the
    subject; entities are the things.

Rules that decide whether this merges across videos:
  - Name each entity in its plainest canonical form. "Gatwick Airport", not
    "Gatwick", "Gatwick Airport's second runway plan", or "the Sussex hub".
    No adjectives, qualifiers or possessives unless genuinely part of the name.
  - A person is named in full where the transcript supports it, otherwise by
    the name given.
  - Do not invent. If a segment names nothing, return empty lists for it.
  - Never emit a segment index you were not given.
  - Numbers, sums of money and dates are not entities."""

VOCAB_HEAD = """
Canonical names already in the graph from other broadcasters' coverage of the
same story. If this video refers to the same real-world thing, reuse the
existing name CHARACTER FOR CHARACTER so the two collapse into one node. Do not
add a qualifier to an existing name. Only invent a new name when nothing below
is the same thing."""


def norm(name):
    return " ".join(name.strip().lower().split())


def ensure_schema(s):
    """UNIQUE only. NODE KEY is Enterprise and would abort the whole run here."""
    s.run("CREATE CONSTRAINT entity_key IF NOT EXISTS "
          "FOR (e:Entity) REQUIRE e.name_normalized IS UNIQUE")
    s.run("CREATE CONSTRAINT topic_key IF NOT EXISTS "
          "FOR (t:Topic) REQUIRE t.name_normalized IS UNIQUE")


def vocabulary(s):
    ents = s.run("MATCH (e:Entity) RETURN e.name AS name, e.type AS type "
                 "ORDER BY e.name LIMIT $n", n=VOCAB_LIMIT).data()
    tops = s.run("MATCH (t:Topic) RETURN t.name AS name "
                 "ORDER BY t.name LIMIT $n", n=VOCAB_LIMIT).data()
    if not ents and not tops:
        return "", 0, 0
    block = (VOCAB_HEAD
             + "\nExisting entities: "
             + ("; ".join(f"{e['name']} ({e['type']})" for e in ents) or "(none)")
             + "\nExisting topics: "
             + ("; ".join(t["name"] for t in tops) or "(none)"))
    return block, len(ents), len(tops)


def ask(publisher, rows, vocab):
    body = "\n".join(
        f"[{i}] {r['start']:.1f}s-{r['end']:.1f}s: {r['transcript']}"
        for i, r in enumerate(rows))
    resp = client.responses.parse(
        model=MODEL,
        input=[{"role": "system", "content": SYSTEM + vocab},
               {"role": "user",
                "content": f"Broadcaster: {publisher}\nSegments of one clip, in order:\n\n{body}"}],
        text_format=VideoEntities,
    )
    if resp.output_parsed is None:
        raise RuntimeError(f"no structured output for {publisher}")
    return resp.output_parsed


WRITE = """
MATCH (s:Segment {video_id:$vid, start:$start})
FOREACH (ent IN $entities |
  MERGE (e:Entity {name_normalized: ent.key})
    ON CREATE SET e.name = ent.name, e.type = ent.type
  MERGE (s)-[m:MENTIONS]->(e)
    SET m.surface_form = ent.surface_form)
FOREACH (top IN $topics |
  MERGE (t:Topic {name_normalized: top.key})
    ON CREATE SET t.name = top.name
  MERGE (s)-[:ABOUT]->(t))
SET s.entities_at = datetime()
"""


def extract(force=False):
    drv = db.driver()
    with drv.session() as s:
        ensure_schema(s)

        videos = s.run("""
            MATCH (seg:Segment)-[:PART_OF]->(src:Source)
            WITH seg.video_id AS vid, src.publisher AS publisher,
                 count(*) AS n_total,
                 sum(CASE WHEN seg.transcript IS NOT NULL
                          AND size(seg.transcript) > $min THEN 1 ELSE 0 END) AS n_usable,
                 sum(CASE WHEN seg.entities_at IS NOT NULL THEN 1 ELSE 0 END) AS n_done
            RETURN vid, publisher, n_total, n_usable, n_done
            ORDER BY n_usable DESC, vid""", min=MIN_TRANSCRIPT).data()

        skipped_thin = sum(v["n_total"] - v["n_usable"] for v in videos)
        print(f"{len(videos)} video(s), {sum(v['n_total'] for v in videos)} segments, "
              f"{sum(v['n_usable'] for v in videos)} with a usable transcript "
              f"(>{MIN_TRANSCRIPT} chars); {skipped_thin} too thin to label\n")

        for v in videos:
            if not force and v["n_done"] >= v["n_usable"]:
                print(f"  = {v['publisher']:20} already extracted ({v['n_done']} segments)")
                continue

            rows = s.run("""
                MATCH (seg:Segment {video_id:$vid})
                WHERE seg.transcript IS NOT NULL AND size(seg.transcript) > $min
                RETURN seg.start AS start, seg.end AS end, seg.transcript AS transcript
                ORDER BY seg.start""", vid=v["vid"], min=MIN_TRANSCRIPT).data()

            vocab, n_ents, n_tops = vocabulary(s)
            print(f"  > {v['publisher']:20} {len(rows):2} segments, canonicalizing against "
                  f"{n_ents} known entit{'y' if n_ents == 1 else 'ies'}, {n_tops} topic(s)")

            parsed = ask(v["publisher"], rows, vocab)

            n_e = n_t = 0
            for out in parsed.segments:
                if not 0 <= out.index < len(rows):
                    print(f"      ! model returned index {out.index}, ignored")
                    continue
                row = rows[out.index]
                ents = [{"key": norm(m.name), "name": m.name.strip(), "type": m.type,
                         "surface_form": m.surface_form.strip()}
                        for m in out.entities if m.name.strip()]
                tops = [{"key": norm(t), "name": t.strip()} for t in out.topics if t.strip()]
                # Dedupe within the segment so the last surface form does not
                # silently overwrite an earlier one twice in the same write.
                ents = list({e["key"]: e for e in ents}.values())
                tops = list({t["key"]: t for t in tops}.values())
                s.run(WRITE, vid=v["vid"], start=row["start"], entities=ents, topics=tops)
                n_e += len(ents)
                n_t += len(tops)
            print(f"      {n_e} mentions, {n_t} topic links")

        if s.run("MATCH (:Segment)-[r:NEXT]->() RETURN count(r)").single()[0] == 0:
            print("\nno :NEXT chain yet — run `python -m graph.entities chain`")
    drv.close()


def chain():
    """Rebuilt wholesale, never patched.

    An incremental chain is wrong the moment a segment is inserted between two
    others: the old a->b edge survives and the graph claims two successors.
    Deleting first costs nothing at this size and cannot be stale.
    """
    drv = db.driver()
    with drv.session() as s:
        gone = s.run("MATCH (:Segment)-[:NEXT]->(:Segment) RETURN count(*)").single()[0]
        s.run("MATCH (:Segment)-[r:NEXT]->(:Segment) DELETE r")
        vids = s.run("""
            MATCH (s:Segment)-[:PART_OF]->(src:Source)
            RETURN DISTINCT s.video_id AS vid, src.publisher AS pub ORDER BY pub""").data()
        total = 0
        for v in vids:
            rec = s.run("""
                MATCH (s:Segment {video_id:$vid})
                WITH s ORDER BY s.start
                WITH collect(s) AS segs
                UNWIND range(0, size(segs)-2) AS i
                WITH segs[i] AS a, segs[i+1] AS b
                MERGE (a)-[:NEXT]->(b)
                RETURN count(*) AS n""", vid=v["vid"]).single()
            n = rec["n"] if rec else 0
            total += n
            print(f"  {v['pub']:22} {n} link(s)")
        crossing = s.run("MATCH (a:Segment)-[:NEXT]->(b:Segment) "
                         "WHERE a.video_id <> b.video_id RETURN count(*)").single()[0]
        print(f"\n{gone} old link(s) removed, {total} rebuilt across {len(vids)} video(s); "
              f"{crossing} crossing a video boundary")
    drv.close()


def status():
    drv = db.driver()
    with drv.session() as s:
        one = lambda q: s.run(q).single()[0]  # noqa: E731
        n_ent = one("MATCH (e:Entity) RETURN count(e)")
        n_top = one("MATCH (t:Topic) RETURN count(t)")
        n_men = one("MATCH ()-[r:MENTIONS]->() RETURN count(r)")
        n_abt = one("MATCH ()-[r:ABOUT]->() RETURN count(r)")
        n_nxt = one("MATCH ()-[r:NEXT]->() RETURN count(r)")
        nodes = s.run("MATCH (n) RETURN count(n)").single()[0]
        rels = s.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
        labelled = s.run("MATCH (s:Segment) WHERE s.entities_at IS NOT NULL "
                         "RETURN count(s)").single()[0]
        bare = s.run("MATCH (s:Segment) WHERE NOT (s)-[:MENTIONS]->() "
                     "RETURN count(s)").single()[0]
        print(f"{n_ent} entities, {n_top} topics")
        print(f"{n_men} MENTIONS, {n_abt} ABOUT, {n_nxt} NEXT")
        print(f"{labelled} segments labelled, {bare} with no entity")
        print(f"graph: {nodes} nodes, {rels} relationships")

        print("\n=== most mentioned ===")
        for r in s.run("""
                MATCH (s:Segment)-[:MENTIONS]->(e:Entity)
                MATCH (s)-[:PART_OF]->(src:Source)
                RETURN e.name AS name, e.type AS type, count(DISTINCT s) AS segs,
                       count(DISTINCT s.video_id) AS videos,
                       count(DISTINCT src.publisher) AS pubs
                ORDER BY segs DESC, name LIMIT 20""").data():
            print(f"  {r['name'][:38]:38} {r['type'][:12]:13} {r['segs']:3} seg  "
                  f"{r['videos']} video  {r['pubs']} pub")

        print("\n=== the money query: one node, more than one broadcaster ===")
        rows = s.run("""
            MATCH (s:Segment)-[:MENTIONS]->(e:Entity)
            MATCH (s)-[:PART_OF]->(src:Source)
            WITH e, collect(DISTINCT src.publisher) AS pubs, count(DISTINCT s) AS segs
            WHERE size(pubs) > 1
            RETURN e.name AS name, e.type AS type, size(pubs) AS n, pubs, segs
            ORDER BY n DESC, segs DESC, name""").data()
        for r in rows:
            print(f"  {r['name'][:34]:34} {r['type'][:12]:13} {r['n']}  "
                  f"{', '.join(sorted(r['pubs']))}")
        multi_vid = s.run("""
            MATCH (s:Segment)-[:MENTIONS]->(e:Entity)
            WITH e, count(DISTINCT s.video_id) AS v WHERE v > 1
            RETURN count(e)""").single()[0]
        print(f"  -- {len(rows)} entities cross a publisher, {multi_vid} cross a video")

        print("\n=== topics across publishers ===")
        for r in s.run("""
                MATCH (s:Segment)-[:ABOUT]->(t:Topic)
                MATCH (s)-[:PART_OF]->(src:Source)
                WITH t, collect(DISTINCT src.publisher) AS pubs, count(DISTINCT s) AS segs
                RETURN t.name AS name, size(pubs) AS n, segs ORDER BY n DESC, segs DESC
                LIMIT 12""").data():
            print(f"  {r['name'][:38]:38} {r['n']} pub  {r['segs']} seg")

        print("\n=== type distribution ===")
        for r in s.run("MATCH (e:Entity) RETURN e.type AS type, count(*) AS n "
                       "ORDER BY n DESC").data():
            print(f"  {r['type']:14} {r['n']:3}")

        print("\n=== chain ===")
        for r in s.run("""
                MATCH (s:Segment)-[:PART_OF]->(src:Source)
                OPTIONAL MATCH (s)-[n:NEXT]->()
                RETURN src.publisher AS pub, count(DISTINCT s) AS segs, count(n) AS links
                ORDER BY pub""").data():
            print(f"  {r['pub']:22} {r['segs']:2} segments  {r['links']:2} links")
        bad = s.run("MATCH (a:Segment)-[:NEXT]->(b:Segment) "
                    "WHERE a.video_id <> b.video_id OR a.start >= b.start "
                    "RETURN count(*)").single()[0]
        print(f"  {bad} link(s) crossing a video or going backwards in time")

        # Canonicalization is the weak spot and pretending otherwise helps
        # nobody. Surface near-identical names so a human can see the misses.
        names = s.run("MATCH (e:Entity) RETURN e.name_normalized AS k, e.name AS n "
                      "ORDER BY k").data()
        pairs = []
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i]["k"], names[j]["k"]
                ratio = difflib.SequenceMatcher(None, a, b).ratio()
                if a in b or b in a or ratio >= 0.82:
                    pairs.append((round(ratio, 2), names[i]["n"], names[j]["n"]))
        print(f"\n=== possible unmerged duplicates ({len(pairs)}) ===")
        for ratio, a, b in sorted(pairs, reverse=True):
            print(f"  {ratio}  {a}  ~  {b}")
    drv.close()


client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "extract":
        extract(force="--force" in sys.argv)
    elif cmd == "chain":
        chain()
    elif cmd == "status":
        status()
    else:
        print(__doc__)
        sys.exit(2)
