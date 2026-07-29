"""Turn segments into Observations carrying typed values.

Until now a Segment merely pointed at a Concept — "this bit of video is about
scheme_cost". That is a pointer, not a number. This is the step that produces
"£2.2bn, currency, millions, at 26.5s in the London Standard clip".

Two disciplines carried over from the rest of the pipeline:

  * Work already done is never redone. Keyed on (video_id, start, concept),
    so a re-run costs nothing and a partial run resumes.
  * An Observation is never promoted to a Fact. Observed sources produce
    Observations, full stop — see docs/05-the-data-model.md.

Modality is deliberately NOT taken from the model's own say-so. Pegasus was
measured claiming spoken content was on-screen text and then asserting nothing
was spoken at all. Here modality is derived: if the value's words appear in the
segment transcript it is `spoken`; otherwise the model may only say `visual` or
`on_screen_text`, and confidence is discounted accordingly.
"""
import os, json, re, sys, time, pathlib
import httpx
from dotenv import load_dotenv
from neo4j import GraphDatabase

root = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")
load_dotenv(pathlib.Path.home() / "Downloads/source/hack-you/.env")

KEY = os.environ["NOVITA_API_KEY"]
MODEL = os.environ.get("HACK_MODEL", "zai-org/glm-5.2")
URL = "https://api.novita.ai/v3/openai/chat/completions"

drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))
http = httpx.Client(timeout=180.0)

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"observations": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "found": {"type": "boolean"},
            "text": {"type": "string"},
            "value": {"type": "number"},
            "unit_kind": {"type": "string"},
            "scale": {"type": "string"},
            "currency": {"type": "string"},
            "confidence": {"type": "number"},
        },
        "required": ["found", "text", "value", "unit_kind", "scale", "currency", "confidence"],
    }}},
    "required": ["observations"],
}

PROMPT = """Extract any measurement of ONE specific concept from a fragment of news video.

CONCEPT: {code} — {name}
EXPECTED unit_kind: {unit} (use exactly this, or say found:false)
EXPECTED scale: {scale}

TRANSCRIPT OF THE SEGMENT ({start}s to {end}s):
"{transcript}"

Rules:
- Only extract a value that genuinely measures THIS concept. A different number
  in the same sentence is not a match — say found:false.
- Normalise to the expected scale. "2.2 billion pounds" with scale millions is 2200.
- currency is a 3-letter code, or "" if the concept is not monetary.
- If nothing measures this concept, return one entry with found:false and value:0.
- Be strict. A false extraction is worse than a miss.

JSON only: {{"observations":[{{"found":bool,"text":"the exact words","value":number,
"unit_kind":"...","scale":"...","currency":"...","confidence":0.0-1.0}}]}}"""


def parse(t):
    t = t.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                pass
    return None


def ask(prompt):
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000, "temperature": 0.1,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "o", "strict": True, "schema": SCHEMA}}}
    r = http.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json=body)
    if r.status_code != 200:
        body["response_format"] = {"type": "json_object"}
        r = http.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json=body)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    m = r.json()["choices"][0]["message"]
    c = (m.get("content") or "").strip() or (m.get("reasoning_content") or "").strip()
    if not c:
        return None, "empty content"
    d = parse(c)
    return (d.get("observations", []), None) if d else (None, "unparseable")


def derive_modality(text, transcript):
    """Never trust the model's own account of where it saw something."""
    if not transcript or not text:
        return "unverified", 0.5
    words = [w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in
             ("billion", "million", "thousand", "pound", "pounds")]
    if not words:
        return "unverified", 0.5
    tl = transcript.lower()
    hits = sum(1 for w in words if w in tl)
    if hits / len(words) >= 0.5:
        return "spoken", 1.0          # corroborated by the transcript
    return "not_in_transcript", 0.6   # on-screen or visual — not decidable from here


with drv.session() as s:
    todo = s.run("""
        MATCH (seg:Segment)-[:CANDIDATE_FOR]->(co:Concept)
        WHERE seg.transcript IS NOT NULL AND size(seg.transcript) > 25
          AND NOT EXISTS { (:Observation {concept_code: co.code})-[:CITES]->(seg) }
        MATCH (seg)-[:PART_OF]->(src:Source)
        RETURN seg.video_id AS vid, seg.start AS start, seg.end AS end,
               seg.transcript AS transcript, co.code AS code, co.name AS name,
               co.unit_kind AS unit, co.canonical_scale AS scale, src.publisher AS publisher
        ORDER BY co.code, seg.start""").data()

    if not todo:
        print("Nothing to extract — every candidate segment already has an Observation.")
        raise SystemExit(0)

    run_id = f"extract-{MODEL}-{int(time.time())}"
    s.run("MERGE (r:ExtractionRun {id:$i}) SET r.model=$m, r.purpose='observation extraction', "
          "r.started_at=datetime()", i=run_id, m=MODEL)

    print(f"{len(todo)} (segment × concept) pair(s) to extract, model {MODEL}\n")
    found = miss = fail = 0
    for t in todo:
        obs, err = ask(PROMPT.format(code=t["code"], name=t["name"], unit=t["unit"],
                                     scale=t["scale"], start=t["start"], end=t["end"],
                                     transcript=(t["transcript"] or "")[:900]))
        if obs is None:
            fail += 1
            print(f"  ! {t['code']:22} {t['start']:6.1f}s  {err}")
            continue
        hit = next((o for o in obs if o.get("found")), None)
        if not hit:
            miss += 1
            continue
        modality, conf_factor = derive_modality(hit.get("text", ""), t["transcript"])
        conf = round(float(hit.get("confidence", 0.5)) * conf_factor, 2)
        s.run("""
            MATCH (seg:Segment {video_id:$vid, start:$start})
            MATCH (co:Concept {code:$code})
            MERGE (o:Observation {concept_code:$code, video_id:$vid, start:$start})
              SET o.text=$text, o.value=$value, o.unit_kind=$unit, o.scale=$scale,
                  o.currency=$cur, o.confidence=$conf, o.modality=$modality,
                  o.provenance_class='observed'
            MERGE (o)-[:CITES {start:$start, end:$end, modality:$modality}]->(seg)
            MERGE (o)-[:OF_CONCEPT]->(co)
            WITH o MATCH (r:ExtractionRun {id:$run}) MERGE (o)-[:PRODUCED_BY]->(r)""",
            vid=t["vid"], start=t["start"], end=t["end"], code=t["code"],
            text=hit.get("text", "")[:300], value=float(hit.get("value", 0)),
            unit=hit.get("unit_kind"), scale=hit.get("scale"),
            cur=hit.get("currency") or None, conf=conf, modality=modality, run=run_id)
        found += 1
        print(f"  + {t['code']:22} {t['start']:6.1f}s  {hit.get('value')!s:>12} "
              f"{hit.get('unit_kind','')[:8]:9} [{modality:17}] conf {conf}  {t['publisher'][:18]}")

    print(f"\n{found} observations written, {miss} segments had nothing, {fail} failed")

    print("\n=== observations by concept ===")
    for r in s.run("""MATCH (o:Observation)-[:OF_CONCEPT]->(co:Concept)
                      RETURN co.code AS concept, count(o) AS n,
                             round(avg(o.value)) AS avg_value, co.unit_kind AS unit
                      ORDER BY n DESC""").data():
        print(f"  {r['concept']:24} {r['n']:3}  avg {r['avg_value']!s:>14} {r['unit']}")

    # Two independent sources measuring the same concept either agree or they do
    # not. Linking them is what makes the graph more than a pile of extractions —
    # and it is the only place a disagreement becomes a reviewable object.
    s.run("""
        MATCH (a:Observation)-[:OF_CONCEPT]->(co:Concept)<-[:OF_CONCEPT]-(b:Observation)
        WHERE a.video_id < b.video_id
        MATCH (a)-[:CITES]->(:Segment)-[:PART_OF]->(sa:Source),
              (b)-[:CITES]->(:Segment)-[:PART_OF]->(sb:Source)
        WHERE sa.url_sha256 <> sb.url_sha256
        WITH a, b, sa, sb,
             CASE WHEN a.value = 0 AND b.value = 0 THEN 0.0
                  ELSE abs(a.value - b.value) / (CASE WHEN abs(a.value) > abs(b.value)
                       THEN abs(a.value) ELSE abs(b.value) END) END AS diff
        FOREACH (_ IN CASE WHEN diff <= 0.02 THEN [1] ELSE [] END |
          MERGE (a)-[r:CORROBORATES]->(b) SET r.basis='independent sources, same figure')
        FOREACH (_ IN CASE WHEN diff > 0.02 THEN [1] ELSE [] END |
          MERGE (a)-[r:CONTRADICTS]->(b)
          SET r.basis='arithmetic', r.a_value=a.value, r.b_value=b.value)""")

    agree = s.run("""MATCH (a:Observation)-[r:CORROBORATES]->(b:Observation)
                     MATCH (a)-[:CITES]->(:Segment)-[:PART_OF]->(sa:Source)
                     MATCH (b)-[:CITES]->(:Segment)-[:PART_OF]->(sb:Source)
                     RETURN a.concept_code AS concept, a.value AS value,
                            collect(DISTINCT sa.publisher) + collect(DISTINCT sb.publisher) AS who
                     ORDER BY concept""").data()
    disagree = s.run("""MATCH (a:Observation)-[r:CONTRADICTS]->(b:Observation)
                        RETURN a.concept_code AS concept, r.a_value AS a, r.b_value AS b
                        ORDER BY concept""").data()
    print("\n=== independent sources agreeing ===")
    for r in agree:
        print(f"  {r['concept']:22} {r['value']!s:>12}  {', '.join(sorted(set(r['who'])))}")
    print(f"\n=== independent sources disagreeing ({len(disagree)}) ===")
    for r in disagree:
        print(f"  {r['concept']:22} {r['a']} vs {r['b']}")

    print("\n=== modality, derived not asserted ===")
    for r in s.run("""MATCH (o:Observation) RETURN o.modality AS modality, count(*) AS n
                      ORDER BY n DESC""").data():
        print(f"  {r['modality']:20} {r['n']}")

drv.close()
