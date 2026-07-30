PY := .venv/bin/python
NEO := docker exec hackgraph cypher-shell -u neo4j -p hackvideo2026
IDX ?= $(shell curl -s --max-time 20 -H "x-api-key: $$TWELVELABS_API_KEY" \
        https://api.twelvelabs.io/v1.3/indexes 2>/dev/null | \
        $(PY) -c "import json,sys;d=json.load(sys.stdin)['data'];print(next((i['_id'] for i in d if i['video_count']>0),''))" 2>/dev/null)

.PHONY: help graph rebuild rebuild-hard restore up down serve check clean-graph reset status assert attest-save attest-load demo demo-reset voice

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
	@echo "==> load  (index $(IDX))"; $(PY) graph/load.py $(IDX)
	@echo "==> urls";    $(PY) graph/urls.py
	@echo "==> link";    $(PY) graph/link_sources.py
	@$(MAKE) --no-print-directory status

clean-graph: up
	@$(NEO) "MATCH (n) DETACH DELETE n;" >/dev/null
	@echo "graph emptied"

# Human decisions are not rebuildable — they exist only because somebody read the
# evidence and signed. A rebuild that silently destroyed them would be the same
# mistake as letting the model overwrite them.
#
# Writes via a temp file and REFUSES to replace a good file with an empty export.
# Without that guard, pointing any rebuild at a fresh database — an empty Aura
# instance, say — exports zero rows and overwrites the only copy of the decisions
# with []. The file is the one artefact here that cannot be regenerated.
attest-save: up
	@$(PY) graph/attestations.py export > .attest.tmp.json
	@if grep -q '"event"' .attest.tmp.json; then \
	  mv .attest.tmp.json attestations.json; \
	  echo "saved -> attestations.json"; \
	else \
	  rm -f .attest.tmp.json; \
	  echo "REFUSED: export held no decisions — attestations.json left untouched."; \
	  echo "         (expected when the target database is empty, e.g. a fresh Aura)"; \
	fi

attest-load: up
	@test -s attestations.json && $(PY) graph/attestations.py restore < attestations.json \
	  || echo "no attestations.json — nothing to restore"

# Safe rebuild: decisions survive it. But it stops after `graph`, so it does NOT
# restore Observations, CORROBORATES or proposed edges — beat 2 and beat 4 both need
# those. Not a stage fallback. See docs/06-the-run-of-show.md.
rebuild: attest-save clean-graph graph attest-load
	@$(MAKE) --no-print-directory status

# The rebuild that actually restores the demo. Minutes, not seconds, and needs network.
# attest-load runs BEFORE assert on purpose: once the human decisions are back in the
# graph, assert_impact sees them as settled and never re-asks the model about a pair a
# human has already closed. Reversing these two would re-send closed pairs.
restore: attest-save clean-graph graph attest-load
	@echo "==> extract"; $(PY) graph/extract.py
	@echo "==> assert";  $(PY) graph/assert_impact.py
	@$(MAKE) --no-print-directory status

# When you really do want a clean slate, decisions included.
rebuild-hard: clean-graph graph

assert: up
	@$(PY) graph/assert_impact.py

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
	@$(PY) graph/attestations.py export > attestations.json 2>/dev/null || true
	@echo "--- graph state ---"
	@$(MAKE) --no-print-directory status
	@echo "--- narration ---"
	@ls audio/*.aiff 2>/dev/null | wc -l | tr -d ' ' | xargs -I{} echo "  {} lines rendered"

voice:
	@$(PY) graph/voice.py --voice $(VOICE)
VOICE ?= Daniel

# Everything a cold laptop needs, in order.
demo: check serve demo-reset
	@echo
	@echo "  Video     http://127.0.0.1:8000/"
	@echo "  Graph     http://127.0.0.1:8000/graph.html"
	@echo "  Explainer http://127.0.0.1:8000/explainers/the-graph.html"
	@echo
	@echo "  run of show: docs/06-the-run-of-show.md"
