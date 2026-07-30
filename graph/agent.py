"""A Strands agent over the graph, on GPT-5.6.

The agent is a reader. It has no tool that writes, and no tool that can reach a
covenant from observed evidence — the invariant is enforced by the schema, not by
asking the model nicely.

    python graph/agent.py "which broadcasters corroborate the cost figure?"
    python graph/agent.py --tools           list tools and exit
"""
import os, sys, json, pathlib
from dotenv import load_dotenv
from neo4j import GraphDatabase
from strands import Agent
from strands.tools import tool
from strands.models.openai_responses import OpenAIResponsesModel

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL_ID = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra")
drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))

WRITE = ("CREATE", "DELETE", "MERGE", "SET ", "DROP", "REMOVE", "DETACH", "CALL DB.CREATE")


def rows(cypher, **params):
    with drv.session() as s:
        return [dict(r) for r in s.run(cypher, **params)]


@tool
def search_moments(query: str) -> str:
    """Find video moments by meaning. Returns publisher, timestamp, transcript and any
    extracted value. Use this for anything about what was said or shown in the footage."""
    from graph.embed import embed, INDEX
    return json.dumps(rows(
        f"CALL db.index.vector.queryNodes('{INDEX}', 5, $v) YIELD node, score "
        "MATCH (node)-[:PART_OF]->(src:Source) "
        "OPTIONAL MATCH (o:Observation)-[:CITES]->(node) "
        "RETURN src.publisher AS publisher, node.start AS start_sec, round(score,3) AS score, "
        "node.transcript AS transcript, o.value AS value, o.concept_code AS concept "
        "ORDER BY score DESC", v=embed(query)), default=str)


@tool
def concept_coverage() -> str:
    """How much video evidence reaches each concept, and which concepts are covenant-linked.
    Use this to answer 'what does the corpus actually cover' and 'what is missing'."""
    return json.dumps(rows(
        "MATCH (c:Concept) "
        "OPTIONAL MATCH (seg:Segment)-[:CANDIDATE_FOR]->(c) "
        "OPTIONAL MATCH (cov:Covenant)-[:MEASURED_BY]->(c) "
        "RETURN c.code AS concept, count(DISTINCT seg) AS video_segments, "
        "cov.covenant_code AS covenant, cov.threshold_status AS threshold "
        "ORDER BY video_segments DESC"), default=str)


@tool
def covenant_facts() -> str:
    """The covenant values as stated by controlled sources (filings), with the quote and
    the document they came from. Observed video can never produce these."""
    return json.dumps(rows(
        "MATCH (f:Fact)-[:FROM]->(s:Source) OPTIONAL MATCH (f)-[:TESTS]->(c:Covenant) "
        "RETURN f.concept_code AS concept, f.value AS value, f.as_stated AS as_stated, "
        "f.quote AS quote, s.title AS source, s.provenance_class AS lane, "
        "c.covenant_code AS covenant, c.direction AS direction, "
        "c.threshold_value AS threshold_value, c.threshold_default AS threshold_default, "
        "c.threshold_status AS threshold_status, c.threshold_citation AS threshold_citation, "
        "CASE c.direction WHEN 'min' THEN round(100.0*(f.value-c.threshold_value)/c.threshold_value,1) "
        "ELSE round(100.0*(c.threshold_value-f.value)/c.threshold_value,1) END AS headroom_pct"),
        default=str)


@tool
def attestation_queue() -> str:
    """Model-proposed covenant impacts and their human decisions. status is one of
    proposed, validated, rejected. A proposed edge is read by nothing."""
    return json.dumps(rows(
        "MATCH (a)-[m:MAY_AFFECT]->(c:Covenant) "
        "RETURN m.status AS status, c.covenant_code AS covenant, m.asserted_by AS asserted_by, "
        "m.rationale AS rationale, m.validated_by AS decided_by, toString(m.validated_at) AS decided_at "
        "ORDER BY m.status"), default=str)


@tool
def run_cypher(query: str) -> str:
    """Run a read-only Cypher query against the graph. Rejected if it would write."""
    if any(w in query.upper() for w in WRITE):
        return json.dumps({"error": "read-only: this agent may not write to the graph"})
    try:
        return json.dumps(rows(query)[:50], default=str)
    except Exception as e:
        return json.dumps({"error": str(e)[:300]})


SYSTEM = """You answer questions about a credit-analysis graph built over UK news footage
about Gatwick airport.

The design you must respect and explain accurately:
- Sources are either `controlled` (filings, accounts — things a lender is sent by somebody
  accountable) or `observed` (news footage).
- Observed sources produce Observations. They may NEVER produce a Fact or reach a covenant.
- Only controlled sources produce Facts.
- A model may only ever propose an edge. A proposed edge is read by nothing until a human
  signs it. Rejected proposals are kept, not deleted.

Absence is a finding, not a gap to fill. If the graph does not have something, say so plainly
and say why the design means it should not have it. Never invent a covenant threshold.
Cite the publisher and timestamp whenever you use video evidence."""


def build(callback_handler=None):
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY not set — add it to .env")
    # Responses API, not chat completions: GPT-5.6 refuses function tools on
    # /v1/chat/completions unless reasoning is off entirely. max_output_tokens bounds
    # reasoning and output together — leave headroom or multi-tool answers truncate.
    model = OpenAIResponsesModel(
        client_args={"api_key": os.environ["OPENAI_API_KEY"]},
        model_id=MODEL_ID,
        params={"max_output_tokens": 16000},
    )
    kw = {"callback_handler": callback_handler} if callback_handler else {}
    return Agent(model=model, system_prompt=SYSTEM, tools=[
        search_moments, concept_coverage, covenant_facts, attestation_queue, run_cypher,
    ], **kw)


if __name__ == "__main__":
    if "--tools" in sys.argv:
        for t in (search_moments, concept_coverage, covenant_facts, attestation_queue, run_cypher):
            print(f"  {t.tool_name}: {(t.tool_spec.get('description') or '').splitlines()[0]}")
        sys.exit()
    agent = build()
    print(f"[{MODEL_ID}]")
    # Strands already streams the answer to stdout via its default callback handler;
    # printing the return value as well prints everything twice.
    agent(sys.argv[1] if len(sys.argv) > 1 else "What does this corpus cover, and what does it not?")
    print()
