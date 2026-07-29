"""The model proposes MAY_AFFECT edges. It may never do more than propose.

Every edge is written status='proposed', asserted_by='model'. No query that
computes anything reads a proposed edge. A human moves it to validated or
rejected, and a rejected edge is kept, never deleted.

THE ATTESTATION RULE
--------------------
Once a human has decided an (event, covenant) pair, that pair is CLOSED. The
model is not asked about it again — not to re-check it, not to record whether
it would now disagree. Re-examining a settled question is revisiting it, however
politely the result is filed.

So the worklist is computed BEFORE any model call, and settled pairs are never
sent. This is cheaper, it is idempotent, and it means a human decision is final
rather than merely respected.
"""
import os, json, time, pathlib
import httpx
from dotenv import load_dotenv
from neo4j import GraphDatabase

root = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")
load_dotenv(pathlib.Path.home() / "Downloads/source/hack-you/.env")

KEY = os.environ["NOVITA_API_KEY"]
# glm-5.2: fastest of the models tested (~17s vs ~120s for deepseek-pro) and the
# only quick one supporting strict json_schema, which removes hand-rolled parsing.
# Accuracy between models was inside run-to-run noise — see graph/bakeoff.py.
MODEL = os.environ.get("HACK_MODEL", "zai-org/glm-5.2")
URL = "https://api.novita.ai/v3/openai/chat/completions"

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"assessments": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "properties": {
            "covenant_code": {"type": "string"},
            "could_affect": {"type": "boolean"},
            "direction": {"type": "string"},
            "rationale": {"type": "string"},
        },
        "required": ["covenant_code", "could_affect", "direction", "rationale"]}}},
    "required": ["assessments"],
}


def parse(text):
    """Models wrap JSON in markdown fences or prose. Dig it out."""
    t = text.strip()
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

drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))
http = httpx.Client(timeout=180.0)

PROMPT = """You are assessing whether a news event could affect a debt covenant.

EVENT: {event} (kind: {kind}, date: {date})

COVENANTS AVAILABLE:
{covenants}

For EACH covenant, decide whether this event could plausibly affect it.
Be sceptical. Most news events affect no covenant at all.

Reply as JSON only:
{{"assessments":[{{"covenant_code":"...","could_affect":true|false,
  "direction":"increases|decreases|none","rationale":"one sentence"}}]}}"""


def ask(event, kind, date, covenants):
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(
            event=event, kind=kind, date=date,
            covenants="\n".join(f"- {c['code']} ({c['name']}, must stay {c['dir']})"
                                for c in covenants))}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "a", "strict": True, "schema": SCHEMA}},
        "max_tokens": 3000,          # reasoning models spend budget thinking first
        "temperature": 0.2,
    }
    r = http.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json=body)
    if r.status_code != 200:
        # not every model on Novita takes json_schema; fall back rather than fail
        body["response_format"] = {"type": "json_object"}
        r = http.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json=body)
    if r.status_code != 200:
        print(f"  ! {r.status_code} {r.text[:120]}")
        return []
    msg = r.json()["choices"][0]["message"]
    # some models leave `content` empty and put everything in `reasoning_content`
    content = (msg.get("content") or "").strip() or (msg.get("reasoning_content") or "").strip()
    if not content:
        print("  ! empty content")
        return []
    d = parse(content)
    if d is None:
        print(f"  ! unparseable: {content[:120]}")
        return []
    return d.get("assessments", [])


with drv.session() as s:
    covenants = s.run(
        "MATCH (c:Covenant) RETURN c.covenant_code AS code, c.name AS name, c.direction AS dir"
    ).data()
    events = s.run(
        "MATCH (e:Event) RETURN e.name AS name, toString(e.date) AS date, e.kind AS kind ORDER BY e.date"
    ).data()

    run_id = f"{MODEL}-{int(time.time())}"
    s.run("MERGE (r:ExtractionRun {id:$id}) SET r.model=$m, r.purpose='covenant impact assertion', "
          "r.started_at=datetime()", id=run_id, m=MODEL)

    # ---- the worklist, computed before a single token is spent ----------
    # Identity is the source URL hash. Seen is seen; unseen is unseen. Nothing
    # fuzzier, and no re-examination of a pair a human has already closed.
    seen = {(r["h"], r["covenant"]): (r["status"], r["by"]) for r in s.run(
        """MATCH (src:Source)-[:REPORTS]->(:Event)-[m:MAY_AFFECT]->(c:Covenant)
           WHERE m.evidence_sha256 = src.url_sha256
           RETURN src.url_sha256 AS h, c.covenant_code AS covenant,
                  m.status AS status, m.validated_by AS by""").data()}

    # every (source, event, covenant) triple the corpus can actually support
    triples = s.run(
        """MATCH (src:Source)-[:REPORTS]->(e:Event), (c:Covenant)
           RETURN src.url_sha256 AS h, src.url AS url, src.publisher AS publisher,
                  e.name AS event, toString(e.date) AS date, e.kind AS kind,
                  c.covenant_code AS covenant, c.name AS cov_name, c.direction AS dir
           ORDER BY e.date, src.publisher""").data()

    unsourced = s.run("""MATCH (e:Event) WHERE NOT (e)<-[:REPORTS]-(:Source)
                         RETURN e.name AS name, toString(e.date) AS date""").data()
    if unsourced:
        print(f"NO SOURCE — cannot be assessed from evidence ({len(unsourced)}):")
        for u in unsourced:
            print(f"  · {u['date']}  {u['name']}")
        print()

    work: dict[tuple, list] = {}
    skipped = []
    for t in triples:
        key = (t["h"], t["covenant"])
        if key in seen:
            st, by = seen[key]
            skipped.append((t["publisher"], t["event"], t["covenant"], st, by, t["h"]))
            continue
        work.setdefault((t["h"], t["event"], t["date"], t["kind"], t["publisher"], t["url"]),
                        []).append({"code": t["covenant"], "name": t["cov_name"], "dir": t["dir"]})

    if skipped:
        print(f"SEEN — hash already processed, not sent to the model ({len(skipped)}):")
        for pub, e, c, st, by, h in skipped:
            print(f"  · {h[:8]} {pub[:18]:20} {c:12} {st} by {by}")
    if not work:
        print("\nNothing unseen. No model call made, no tokens spent.")
        raise SystemExit(0)
    print(f"\nUNSEEN — {sum(len(v) for v in work.values())} (source × covenant) "
          f"pair(s) go to the model\n")

    for (h, ev_name, ev_date, ev_kind, publisher, url), open_covs in work.items():
        ev = {"name": ev_name, "date": ev_date, "kind": ev_kind}
        print(f"{publisher} — {ev_name} ({ev_date})")
        print(f"  source {h[:12]} · {url}")
        for a in ask(ev["name"], ev["kind"], ev["date"], open_covs):
            # a model may answer about something it wasn't asked — drop it
            if (h, a.get("covenant_code")) in seen:
                print(f"  ! {a.get('covenant_code')}: model answered a seen hash — discarded")
                continue
            # A negative assessment is still a judgement. Record it, so it can be
            # attested once and never re-asked — and so the graph shows what the
            # model considered and dismissed, not only what it flagged.
            could = bool(a.get("could_affect"))
            # Only ever writes an undecided pair — settled ones never reach here.
            # The WHERE guard is belt-and-braces: even a bug upstream cannot
            # overwrite a human decision.
            s.run(
                """MATCH (e:Event {name:$ev}), (c:Covenant {covenant_code:$cv})
                   MERGE (e)-[m:MAY_AFFECT {evidence_sha256:$h}]->(c)
                     ON CREATE SET m.status='proposed', m.validated_by=null, m.validated_at=null
                   WITH m WHERE m.status = 'proposed'
                   SET m.asserted_by='model', m.model=$model, m.asserted_at=datetime(),
                       m.could_affect=$could, m.evidence_url=$url,
                       m.direction=CASE WHEN $could THEN $dir ELSE 'none' END,
                       m.rationale=$why""",
                ev=ev["name"], cv=a["covenant_code"], dir=a.get("direction"),
                why=a.get("rationale"), model=MODEL, could=could, h=h, url=url,
            )
            verdict = "MAY AFFECT" if could else "no effect "
            print(f"  → proposed [{verdict}] {a['covenant_code']}: "
                  f"{a.get('rationale','')[:58]}")

    print("\n=== proposed edges now in the graph ===")
    for r in s.run(
        """MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant)
           RETURN e.name AS event, c.covenant_code AS covenant,
                  m.status AS status, m.asserted_by AS by, m.direction AS dir"""
    ).data():
        print(f"  [{r['status']:9} by {r['by']:5}] {r['event'][:44]:46} → {r['covenant']} ({r['dir']})")

    print("\n=== what a computation would read (validated only) ===")
    rows = s.run(
        """MATCH (e:Event)-[m:MAY_AFFECT {status:'validated'}]->(c:Covenant)
           RETURN e.name AS event, c.covenant_code AS cov"""
    ).data()
    print(f"  {len(rows)} validated edges — nothing computes off a model's guess")

drv.close()
