"""Smallest honest test of Strands: one custom tool over the live Neo4j graph,
driven by Novita's OpenAI-compatible endpoint. No AWS credentials involved.

Run: .venv/bin/python graph/strands_hello.py
"""

import logging
import os
import sys

import urllib.request
import json

from dotenv import dotenv_values
from neo4j import GraphDatabase
from strands import Agent, tool
from strands.models.openai import OpenAIModel

# GLM-5.2 is a reasoning model; Strands strips reasoningContent from history on
# every multi-turn cycle and WARNs about it. Cosmetic, but it spams the console.
logging.getLogger("strands.models.openai").setLevel(logging.ERROR)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "hackvideo2026")

NOVITA_BASE_URL = "https://api.novita.ai/v3/openai"
# Deliberately NOT read from NOVITA_MODEL: that var in hack-you/.env says
# deepseek/deepseek-v4-flash, which is not what this test is about.
MODEL_ID = "zai-org/glm-5.2"

# A "covenant concept" is a Concept some Covenant is MEASURED_BY.
COVENANT_REACH_CYPHER = """
MATCH (cov:Covenant)-[:MEASURED_BY]->(c:Concept)
WITH collect(DISTINCT c) AS covenant_concepts
UNWIND covenant_concepts AS cc
OPTIONAL MATCH (s:Segment)
WHERE (s)-[:CANDIDATE_FOR]->(cc)
   OR (s)<-[:CITES]-(:Observation)-[:OF_CONCEPT]->(cc)
RETURN count(DISTINCT s) AS segments_reaching,
       size(covenant_concepts) AS covenant_concept_count,
       [x IN covenant_concepts | x.code] AS covenant_concept_codes
"""


@tool
def segments_reaching_covenant_concepts() -> str:
    """Count how many video Segment nodes in the knowledge graph reach a covenant concept.

    A covenant concept is a Concept node that a Covenant is MEASURED_BY. A segment
    "reaches" one either by a direct CANDIDATE_FOR edge or through an Observation
    that CITES the segment and is OF_CONCEPT that concept.
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with driver.session() as session:
            rec = session.run(COVENANT_REACH_CYPHER).single()
            return (
                f"segments_reaching={rec['segments_reaching']} "
                f"covenant_concepts={rec['covenant_concept_count']} "
                f"({', '.join(rec['covenant_concept_codes'])})"
            )
    finally:
        driver.close()


def assert_model_slug_is_live(api_key: str) -> None:
    """Standing trap #2: pull the live model list, never trust a slug from a sample."""
    req = urllib.request.Request(
        f"{NOVITA_BASE_URL}/models", headers={"Authorization": f"Bearer {api_key}"}
    )
    with urllib.request.urlopen(req) as resp:
        ids = {m["id"] for m in json.load(resp)["data"]}
    if MODEL_ID not in ids:
        sys.exit(f"FAIL: {MODEL_ID} is not in the live Novita model list ({len(ids)} models)")
    print(f"model check: {MODEL_ID} present in live list of {len(ids)} models")


def main() -> None:
    # dotenv_values, not load_dotenv: that file also carries AWS_* keys, and
    # injecting them would mask an accidental Bedrock fallback.
    api_key = dotenv_values(os.path.expanduser("~/Downloads/source/hack-you/.env"))["NOVITA_API_KEY"]
    for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE", "AWS_REGION"):
        assert var not in os.environ, f"{var} is set; the no-AWS claim is not being tested"
    assert_model_slug_is_live(api_key)

    ground_truth = segments_reaching_covenant_concepts()
    print(f"ground truth (tool called directly): {ground_truth}")

    model = OpenAIModel(
        client_args={"api_key": api_key, "base_url": NOVITA_BASE_URL},
        model_id=MODEL_ID,
        params={"max_tokens": 2000, "temperature": 0.2},
    )
    agent = Agent(model=model, tools=[segments_reaching_covenant_concepts])

    result = agent(
        "How many video segments reach a covenant concept? "
        "Use the tool. Answer with the number and one sentence of context."
    )

    # Standing trap #1, generalised: a call that returns is not a call that worked.
    # Assert the tool was actually invoked rather than answered from the model's head.
    tool_usage = result.metrics.get_summary()["tool_usage"]
    print(f"\ntool_usage: {json.dumps(tool_usage, indent=2, default=str)}")
    calls = (
        tool_usage.get("segments_reaching_covenant_concepts", {})
        .get("execution_stats", {})
        .get("call_count", 0)
    )
    if calls < 1:
        sys.exit("FAIL: agent answered without invoking the tool")
    print(f"PASS: tool invoked {calls}x; answer grounded in a real Cypher query")


if __name__ == "__main__":
    main()
