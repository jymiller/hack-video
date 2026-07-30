PY := .venv/bin/python
NEO := docker exec hackgraph cypher-shell -u neo4j -p hackvideo2026
IDX ?= $(shell curl -s --max-time 20 -H "x-api-key: $$TWELVELABS_API_KEY" \
        https://api.twelvelabs.io/v1.3/indexes 2>/dev/null | \
        $(PY) -c "import json,sys;d=json.load(sys.stdin)['data'];print(next((i['_id'] for i in d if i['video_count']>0),''))" 2>/dev/null)

.PHONY: help graph rebuild rebuild-hard up down serve check clean-graph reset status assert attest-save attest-load demo demo-reset voice ks ks-status ask embed embed-verify vsearch agent

help:
	@echo "make up         start neo4j (idempotent, waits for bolt)"
	@echo "make graph      schema + seed + load + link + hash   <- the one command"
	@echo "make rebuild    wipe the graph and rebuild it from nothing"
	@echo "make assert     run the model's covenant assertions (skips settled pairs)"
	@echo "make serve      start the app on :8000"
	@echo "make status     what is actually in the graph right now"
	@echo "make check      health of every moving part"
	@echo "make down       stop neo4j"

up:
	@docker start hackgraph >/dev/null 2>&1 || \
	  docker run -d --name hackgraph -p 7474:7474 -p 7687:7687 \
	    -e NEO4J_AUTH=neo4j/hackvideo2026 neo4j:5 >/dev/null
	@printf "neo4j: "
	@for i in $$(seq 1 60); do \
	  if $(NEO) "RETURN 1" >/dev/null 2>&1; then echo "up"; exit 0; fi; \
	  printf "."; sleep 2; \
	done; echo " FAILED to come up"; exit 1

# The whole graph, from nothing, in one command. Order matters and is enforced here
# rather than living in someone's memory:
#   schema -> constraints must exist before anything is written
#   seed   -> vocabularies, concepts, deal lane, events
#   load   -> concept-driven retrieval from TwelveLabs (needs seeded concepts+probes)
#   urls   -> canonical url + sha256 on every Source (needs loaded Sources)
#   link   -> Source-[:REPORTS]->Event (needs hashed Sources)
graph: up
	@test -n "$(IDX)" || { echo "no TwelveLabs index with videos found — is .env sourced?"; exit 1; }
	@echo "==> schema";  docker cp graph/schema.cypher hackgraph:/tmp/s.cypher && $(NEO) -f /tmp/s.cypher
	@echo "==> seed";    docker cp graph/seed.cypher   hackgraph:/tmp/d.cypher && $(NEO) -f /tmp/d.cypher
	@echo "==> load  (index $(IDX))"; $(PY) -m graph.load $(IDX)
	@echo "==> urls";    $(PY) -m graph.urls
	@echo "==> link";    $(PY) -m graph.link_sources
	@$(MAKE) --no-print-directory status

clean-graph: up
	@$(NEO) "MATCH (n) DETACH DELETE n;" >/dev/null
	@echo "graph emptied"

# Human decisions are not rebuildable — they exist only because somebody read the
# evidence and signed. A rebuild that silently destroyed them would be the same
# mistake as letting the model overwrite them.
attest-save: up
	@$(PY) -m graph.attestations export > attestations.json
	@echo "saved -> attestations.json"

attest-load: up
	@test -s attestations.json && $(PY) -m graph.attestations restore < attestations.json \
	  || echo "no attestations.json — nothing to restore"

# Safe rebuild: decisions survive it.
rebuild: attest-save clean-graph graph attest-load
	@$(MAKE) --no-print-directory status

# When you really do want a clean slate, decisions included.
rebuild-hard: clean-graph graph

assert: up
	@$(PY) -m graph.assert_impact

serve:
	@pkill -f "uvicorn server:app" 2>/dev/null || true
	@sleep 1
	@nohup $(PY) -m uvicorn server:app --port 8000 --host 127.0.0.1 > /tmp/hackvideo.log 2>&1 &
	@sleep 5
	@printf "app: "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 http://127.0.0.1:8000/

status: up
	@$(NEO) --format plain "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC;"
	@echo "--- can any video evidence reach a covenant? (must be 0) ---"
	@$(NEO) --format plain "MATCH (c:Covenant)-[:MEASURED_BY]->(co:Concept) \
	  OPTIONAL MATCH (seg:Segment)-[:CANDIDATE_FOR]->(co) \
	  RETURN c.covenant_code AS covenant, count(seg) AS video_segments;"
	@echo "--- attestation ---"
	@$(NEO) --format plain "MATCH ()-[m:MAY_AFFECT]->() \
	  RETURN m.status AS status, count(*) AS n ORDER BY n DESC;"

check:
	@printf "docker      "; docker info >/dev/null 2>&1 && echo ok || echo DOWN
	@printf "neo4j       "; $(NEO) "RETURN 1" >/dev/null 2>&1 && echo ok || echo DOWN
	@printf "app         "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 http://127.0.0.1:8000/ 2>/dev/null || echo DOWN
	@printf "twelvelabs  "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 \
	  -H "x-api-key: $$TWELVELABS_API_KEY" https://api.twelvelabs.io/v1.3/indexes 2>/dev/null || echo DOWN
	@printf "you.com     "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 15 http://127.0.0.1:8000/api/you/status 2>/dev/null || echo DOWN
	@printf "corpus      "; ls video/*.mp4 2>/dev/null | wc -l | tr -d ' ' | xargs -I{} echo "{} clips"

down:
	@docker stop hackgraph >/dev/null 2>&1 && echo "neo4j stopped" || true

reset: down
	@docker rm -f hackgraph >/dev/null 2>&1 || true
	@echo "container removed — 'make graph' will recreate it"

# ---- demo ------------------------------------------------------------------
# Puts the graph into the exact state the run-of-show assumes, so a rehearsal
# and the real thing look identical. Safe to run repeatedly.
demo-reset: up
	@$(PY) -m graph.attestations export > attestations.json 2>/dev/null || true
	@echo "--- graph state ---"
	@$(MAKE) --no-print-directory status
	@echo "--- narration ---"
	@ls audio/*.aiff 2>/dev/null | wc -l | tr -d ' ' | xargs -I{} echo "  {} lines rendered"

voice:
	@$(PY) -m graph.voice --voice $(VOICE)
VOICE ?= Daniel

# Strands agent on GPT-5.6, read-only over the graph.
agent:
	@$(PY) -m graph.agent "$(Q)"

# Semantic search over segment transcripts. Marengo 512-dim, cosine.
embed:
	@$(PY) -m graph.embed backfill

embed-verify:
	@$(PY) -m graph.embed verify

vsearch:
	@$(PY) -m graph.embed ask "$(Q)"

# Knowledge store — multi-turn Q&A over the same assets. Off the run-of-show path.
ks:
	@$(PY) -m graph.knowledge_store build

ks-status:
	@$(PY) -m graph.knowledge_store status

ask:
	@$(PY) -m graph.knowledge_store ask "$(Q)"

# Everything a cold laptop needs, in order.
demo: check serve demo-reset
	@echo
	@echo "  Video     http://127.0.0.1:8000/"
	@echo "  Graph     http://127.0.0.1:8000/graph.html"
	@echo "  Explainer http://127.0.0.1:8000/explainers/the-graph.html"
	@echo
	@echo "  run of show: docs/06-the-run-of-show.md"
