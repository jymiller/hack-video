"""Plain English in, Cypher out, whole nodes back so the answer can be drawn.

Two things make this different from asking a model to "write some Cypher".

1. The schema is read out of the database on every call — labels, relationship
   triples, property keys, and the actual low-cardinality values (`senior_rar`,
   `rejected`, `Channel 4 News`). A hardcoded schema string is wrong the moment
   somebody loads a node; this one cannot go stale, and the sampled values are
   what let the model write a WHERE clause that matches something.

2. Read-only is enforced by the database, not by a regex. The generated query
   runs inside session.execute_read on a READ-access session, so a write is
   refused by the server with Neo.ClientError.Statement.AccessMode whatever
   creative spelling it arrives in. The keyword scan below is a cheap first
   pass that gives a clearer message — it is not the guarantee.

    python -m graph.nl2cypher "which broadcasters mention Gatwick Airport?"
"""
import json, os, pathlib, re, sys
from typing import Literal

import neo4j
from dotenv import load_dotenv
from neo4j.graph import Node, Path, Relationship
from openai import OpenAI
from pydantic import BaseModel

import graph.db as db

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# The bare `gpt-5.6` alias routes to the flagship Sol tier at ~25x the price for a
# job that is one short structured completion. Pin the terra tier and refuse the
# alias even if the environment hands it over.
MODEL_ID = os.environ.get("OPENAI_NL2CYPHER_MODEL", "gpt-5.6-terra")
if MODEL_ID == "gpt-5.6":
    MODEL_ID = "gpt-5.6-terra"

MAX_ROWS = 100
SKIP_PROPS = {"embedding"}          # 768 floats per Segment; never worth serialising
_ident = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_drv = None


def driver():
    """One driver for the process. A driver per request leaks a connection pool per
    question, which a long demo notices and a short test does not."""
    global _drv
    if _drv is None:
        _drv = db.driver()
    return _drv


# ---------------------------------------------------------------------------
# live schema
# ---------------------------------------------------------------------------

def _short(v, n=60):
    s = str(v).replace("\n", " ")
    return s if len(s) <= n else s[:n] + "…"


def _label_props(tx, label):
    # LIMIT before UNWIND so a big label does not walk every node; keys() is per-node
    # in this graph, not a schema, so sampling is the only honest way to list them.
    # values come back raw and are stringified in Python — toString() throws on the
    # list-valued properties (Concept.probes, Risk.sectors) that live in this graph
    q = (f"MATCH (n:`{label}`) WITH n LIMIT 200 "
         "UNWIND [k IN keys(n) WHERE NOT k IN $skip] AS k "
         "WITH k, count(DISTINCT n[k]) AS nd, collect(DISTINCT n[k])[0..12] AS vals "
         "RETURN k, nd, vals ORDER BY k")
    return [r.data() for r in tx.run(q, skip=sorted(SKIP_PROPS))]


def _rel_props(tx, rtype):
    q = (f"MATCH ()-[r:`{rtype}`]->() WITH r LIMIT 200 UNWIND keys(r) AS k "
         "WITH k, count(DISTINCT r[k]) AS nd, collect(DISTINCT r[k])[0..12] AS vals "
         "RETURN k, nd, vals ORDER BY k")
    return [r.data() for r in tx.run(q)]


def _fmt_props(rows):
    out = []
    for r in rows:
        if not _ident.match(r["k"]):
            continue
        # a property with few distinct values is an enum and the model needs all of
        # them; anything wider only needs a taste of the shape
        if r["nd"] <= 12 and r["vals"]:
            out.append(f"{r['k']} ∈ {{{', '.join(_short(v, 40) for v in r['vals'])}}}")
        elif r["vals"]:
            out.append(f"{r['k']} (e.g. {_short(r['vals'][0])})")
        else:
            out.append(r["k"])
    return out


def _schema_tx(tx):
    labels = [r["label"] for r in tx.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
              if _ident.match(r["label"])]
    types = [r["relationshipType"] for r in
             tx.run("CALL db.relationshipTypes() YIELD relationshipType "
                    "RETURN relationshipType ORDER BY relationshipType")
             if _ident.match(r["relationshipType"])]
    counts = {r["label"]: r["n"] for r in
              tx.run("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n")}
    triples = [r.data() for r in tx.run(
        "MATCH (a)-[r]->(b) RETURN labels(a)[0] AS f, type(r) AS t, labels(b)[0] AS to, "
        "count(*) AS n ORDER BY n DESC")]

    lines = ["NODE LABELS (count) and properties:"]
    for lbl in labels:
        props = _fmt_props(_label_props(tx, lbl))
        lines.append(f"  (:{lbl}) x{counts.get(lbl, 0)} — {'; '.join(props) or 'no properties'}")

    lines.append("")
    lines.append("RELATIONSHIPS (only these directions exist):")
    rp = {t: _fmt_props(_rel_props(tx, t)) for t in types}
    for t in triples:
        props = rp.get(t["t"]) or []
        tail = f"  [props: {'; '.join(props)}]" if props else ""
        lines.append(f"  (:{t['f']})-[:{t['t']}]->(:{t['to']}) x{t['n']}{tail}")
    return "\n".join(lines)


def schema(drv=None):
    """The schema as the database has it right now. Read every call — never cached."""
    drv = drv or driver()
    with drv.session(default_access_mode=neo4j.READ_ACCESS) as s:
        return s.execute_read(_schema_tx)


# ---------------------------------------------------------------------------
# the model
# ---------------------------------------------------------------------------

class Plan(BaseModel):
    answerable: bool
    shape: Literal["graph", "table", "scalar", "none"]
    cypher: str
    explanation: str


SYSTEM = """You translate a question about a credit-analysis knowledge graph into ONE
read-only Cypher query for Neo4j 5. The graph was built over UK news footage about
Gatwick airport plus the borrower's filed accounts.

WHAT THE GRAPH MEANS — respect this or the answer will be wrong:
- A Source is `controlled` (filings, accounts) or `observed` (news footage). Publishers
  like Channel 4 News are observed sources; "broadcaster" means a Source with
  provenance_class 'observed'.
- Observed sources produce Observations. They may never produce a Fact and may never
  reach a Covenant. Only controlled sources produce Facts.
- A model may only ever PROPOSE an edge. MAY_AFFECT and SUGGESTS_RISK carry
  status ('proposed' | 'validated' | 'rejected'), asserted_by, rationale, and — once a
  human signs — validated_by, validated_at and human_note. A proposed edge is unsigned:
  validated_by is null. "Has a human signed it" = validated_by IS NOT NULL.
- A video is a Source; Segment.video_id and (:Segment)-[:PART_OF]->(:Source) both
  identify which footage a segment came from.

HOW TO SHAPE THE RETURN — this drives a graph picture, not just a table:
- If the answer is a SHAPE (which things connect to which, a path, a subgraph, "show me",
  "what is exposed to", "who mentions"), RETURN WHOLE NODES AND WHOLE RELATIONSHIPS as
  bound variables — `RETURN src, r, seg, m, e` — never `src.publisher`. Bind the
  relationship too (`-[r:MENTIONS]->`) and return it, or the picture has no edges.
  Set shape='graph'.
- If the answer is a NUMBER or a COUNT, return scalar columns and set shape='scalar'.
- If the answer is genuinely a list of values with no useful shape (a ranking, a table
  of statuses), return scalar columns and set shape='table'. Prefer 'graph' when in
  doubt — a drawable answer is worth more here than a tidy table.
- You may mix: `RETURN src, r, seg, count(*) AS n` is fine.

RULES:
- Read-only. No CREATE, MERGE, SET, DELETE, REMOVE, DROP, FOREACH, LOAD CSV or write
  procedure. A write is refused by the database and wastes the question.
- Use ONLY labels, relationship types and properties from the schema below. Never invent
  one. The property values listed in braces are the real values in the database — use
  them literally.
- Match user words case-insensitively and loosely:
  `toLower(e.name) CONTAINS toLower('gatwick airport')`, not `e.name = 'Gatwick'`.
- A user's phrase may land on ANY of a label's identifying properties, and people say
  the code out loud: "senior RAR" is covenant_code 'senior_rar', not the name "Senior
  debt ratio". So match across all of them with OR — code, name, id, legal_name —
  rather than betting the question on one:
  `WHERE toLower(c.covenant_code) CONTAINS $t OR toLower(c.name) CONTAINS $t`
  (inline the literal; do not use parameters). Normalise spaces to underscores when you
  compare against a *_code or *_id.
- Always end with a LIMIT (50 unless the question implies otherwise).
- Do not put a semicolon at the end.
- If the graph cannot answer the question — the data simply is not in it — set
  answerable=false, shape='none', cypher='' and explain in one or two sentences what
  the graph does hold instead. Never invent a query that would return nothing just to
  have returned something, and never answer from world knowledge.

`explanation` is one or two plain sentences for a credit analyst saying what the query
asks for and how to read the result. No Cypher jargon, no markdown."""


def _client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set — add it to .env")
    return OpenAI(api_key=key)


def plan(question, schema_text, prior=None, error=None, client=None):
    """One structured completion. `prior`/`error` feed a failed query back for a retry."""
    user = f"SCHEMA (live, read from the database just now):\n{schema_text}\n\nQUESTION: {question}"
    if error:
        user += (f"\n\nYour previous query FAILED and must be rewritten:\n{prior}\n\n"
                 f"The database said:\n{error}\n\n"
                 "Fix it against the schema above. Do not repeat the same query.")
    # Responses API with a Pydantic text_format: the model returns a parsed Plan or
    # nothing, so there is no fenced-code-block scraping. max_output_tokens, not
    # max_tokens — GPT-5.6 rejects the latter — and it bounds reasoning too, so leave
    # headroom or the parse comes back empty.
    r = (client or _client()).responses.parse(
        model=MODEL_ID,
        instructions=SYSTEM,
        input=user,
        text_format=Plan,
        max_output_tokens=6000,
    )
    out = r.output_parsed
    if out is None:
        raise RuntimeError(f"model returned no parsed plan (status={r.status})")
    return out


# ---------------------------------------------------------------------------
# read-only, twice
# ---------------------------------------------------------------------------

# Cheap first pass. Stripping quoted strings and comments first, so a publisher called
# "Merge Media" is not a write and `MATCH (n) /*x*/ CREATE` still is. This exists for a
# clear error message; the READ transaction below is the actual guarantee.
_STRIP = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`(?:[^`])*`|//[^\n]*|/\*.*?\*/", re.S)
_WRITE = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV|CALL\s*\{[^}]*\bCREATE)\b",
    re.I)
_WRITE_PROC = re.compile(r"\b(apoc\.(create|merge|refactor|periodic|trigger|atomic)|db\.create)\b", re.I)


def looks_like_write(cypher):
    bare = _STRIP.sub(" ", cypher)
    m = _WRITE.search(bare) or _WRITE_PROC.search(bare)
    return m.group(0).strip() if m else None


def _jsonable(v):
    """Nodes and relationships keep the keys nvl.js walks for: a node is anything with
    elementId+labels, a relationship anything with type+startNodeElementId."""
    if isinstance(v, Node):
        return {**{k: _jsonable(x) for k, x in v.items() if k not in SKIP_PROPS},
                "elementId": v.element_id, "labels": list(v.labels)}
    if isinstance(v, Relationship):
        return {**{k: _jsonable(x) for k, x in v.items() if k not in SKIP_PROPS},
                "elementId": v.element_id, "type": v.type,
                "startNodeElementId": v.start_node.element_id,
                "endNodeElementId": v.end_node.element_id}
    if isinstance(v, Path):
        return [_jsonable(x) for x in list(v.nodes) + list(v.relationships)]
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def execute(cypher, drv=None):
    """Run in a READ transaction. The server refuses a write here — not this code."""
    hit = looks_like_write(cypher)
    if hit:
        raise PermissionError(f"read-only: refusing a query containing {hit.upper()}")
    drv = drv or driver()
    with drv.session(default_access_mode=neo4j.READ_ACCESS) as s:
        return s.execute_read(
            lambda tx: [{k: _jsonable(v) for k, v in r.items()}
                        for r in tx.run(cypher)][:MAX_ROWS])


# A model that wrote bad Cypher can usually fix it when shown the error. A model that
# tried to write to the database cannot be retried into permission.
RETRYABLE = ("SyntaxError", "TypeError", "ArgumentError", "SemanticError", "ParameterMissing")


def _retryable(e):
    code = getattr(e, "code", "") or ""
    return code.startswith("Neo.ClientError.Statement.") and code.split(".")[-1] in RETRYABLE


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def run(question, drv=None):
    """Yields progress events: {stage}, {cypher}, {rows}, {explanation}, {error}."""
    drv = drv or driver()
    yield {"stage": "schema"}
    sch = schema(drv)
    yield {"stage": "model", "model": MODEL_ID, "schema_chars": len(sch)}

    try:
        p = plan(question, sch)
    except Exception as e:
        yield {"error": f"{type(e).__name__}: {str(e)[:300]}"}
        return

    if not p.answerable or not p.cypher.strip():
        # Absence is a finding. Say the graph does not hold it rather than inventing.
        yield {"unanswerable": True, "explanation": p.explanation, "cypher": ""}
        return

    yield {"cypher": p.cypher, "shape": p.shape}

    # One retry, spent on whichever failure comes first. A syntax error is the obvious
    # one; zero rows is the more common and more damaging one, because a query that
    # matched on the wrong property looks like a confident finding of nothing. Showing
    # the model its own empty result usually gets the second guess right.
    tries = 0
    while True:
        yield {"stage": "run"}
        try:
            rows = execute(p.cypher, drv)
        except PermissionError as e:
            yield {"error": str(e)}
            return
        except Exception as e:
            if tries or not _retryable(e):
                yield {"error": f"{getattr(e, 'code', type(e).__name__)}: {str(e)[:300]}"}
                return
            why, feedback = "syntax", str(e)[:600]
        else:
            if rows or tries:
                break
            why, feedback = "empty", (
                "The query is valid Cypher but matched nothing — zero rows. Something in "
                "the WHERE clause does not exist in the data. Check the property values "
                "listed in the schema and match across the identifying properties (code, "
                "name, id) with OR, or loosen the match. If the graph genuinely does not "
                "hold this, set answerable=false instead of returning an empty query.")

        tries += 1
        # `detail`, not `error` — a retry is not a failure, and a page watching for
        # {"error"} should not paint one when the second attempt is about to succeed
        yield {"stage": "retry", "why": why, "detail": feedback[:300]}
        try:
            p = plan(question, sch, prior=p.cypher, error=feedback)
        except Exception as e2:
            yield {"error": f"retry failed — {type(e2).__name__}: {str(e2)[:300]}", "retried": True}
            return
        if not p.answerable or not p.cypher.strip():
            yield {"unanswerable": True, "explanation": p.explanation, "cypher": "", "retried": True}
            return
        yield {"cypher": p.cypher, "shape": p.shape, "retried": True}

    yield {"rows": rows, "n": len(rows)}
    yield {"explanation": p.explanation}


def ask(question, drv=None):
    """The whole thing, collected: {cypher, rows, explanation}."""
    out = {"cypher": "", "rows": [], "explanation": "", "error": None,
           "unanswerable": False, "retried": False}
    for ev in run(question, drv):
        for k in ("cypher", "rows", "explanation", "error", "shape"):
            if k in ev:
                out[k] = ev[k]
        if ev.get("retried"):
            out["retried"] = True
        if ev.get("unanswerable"):
            out["unanswerable"] = True
    return out


if __name__ == "__main__":
    if "--schema" in sys.argv:
        print(schema())
        sys.exit()
    q = sys.argv[1] if len(sys.argv) > 1 else "which broadcasters mention Gatwick Airport?"
    for ev in run(q):
        print(json.dumps(ev, default=str)[:2000])
