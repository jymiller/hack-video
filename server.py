import os, json, glob, pathlib, subprocess, time
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()
# You.com key lives in the hack-you project; read it there rather than duplicating the secret
load_dotenv(os.environ.get("YOU_ENV", pathlib.Path.home() / "Downloads/source/hack-you/.env"))
KEY = os.environ["TWELVELABS_API_KEY"]
BASE = "https://api.twelvelabs.io/v1.3"
HDR = {"x-api-key": KEY}
VIDEO_DIR = pathlib.Path("video")

app = FastAPI()
client = httpx.AsyncClient(timeout=600.0)


async def tl(method, path, **kw):
    r = await client.request(method, f"{BASE}{path}", headers=HDR, **kw)
    try:
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception:
        return JSONResponse({"error": r.text}, status_code=r.status_code)


@app.get("/api/indexes")
async def indexes():
    return await tl("GET", "/indexes", params={"page_limit": 50})


@app.post("/api/indexes")
async def create_index(req: Request):
    body = await req.json()
    models = [
        {"model_name": m, "model_options": body.get("options", ["visual", "audio"])}
        for m in body.get("models", ["marengo3.0", "pegasus1.2"])
    ]
    return await tl("POST", "/indexes", json={
        "index_name": body["index_name"], "models": models, "addons": ["thumbnail"],
    })


@app.put("/api/indexes/{index_id}")
async def rename_index(index_id: str, req: Request):
    body = await req.json()
    return await tl("PUT", f"/indexes/{index_id}", json={"index_name": body["index_name"]})


@app.delete("/api/indexes/{index_id}")
async def delete_index(index_id: str):
    return await tl("DELETE", f"/indexes/{index_id}")


@app.get("/api/indexes/{index_id}/videos")
async def videos(index_id: str):
    return await tl("GET", f"/indexes/{index_id}/videos", params={"page_limit": 50})


@app.get("/api/tasks/{task_id}")
async def task(task_id: str):
    return await tl("GET", f"/tasks/{task_id}")


_dur_cache = {}


def duration(p: pathlib.Path):
    key = (p.name, p.stat().st_mtime)
    if key not in _dur_cache:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(p)], capture_output=True, text=True,
        )
        try:
            _dur_cache[key] = round(float(r.stdout.strip()))
        except ValueError:
            _dur_cache[key] = None
    return _dur_cache[key]


@app.get("/api/local-videos")
async def local_videos():
    return [
        {
            "name": p.name,
            "size_mb": round(p.stat().st_size / 1e6, 1),
            "duration": duration(p),
        }
        for p in sorted(VIDEO_DIR.glob("*.mp4"))
    ]


@app.post("/api/index-local")
async def index_local(req: Request):
    body = await req.json()
    path = VIDEO_DIR / body["name"]
    meta = json.dumps({"filename": path.name})
    with open(path, "rb") as f:
        return await tl("POST", "/tasks", data={
            "index_id": body["index_id"], "user_metadata": meta,
        }, files={"video_file": (path.name, f, "video/mp4")})


@app.post("/api/upload")
async def upload(index_id: str = Form(...), file: UploadFile = None):
    data = await file.read()
    dest = VIDEO_DIR / file.filename
    if not dest.exists():
        dest.write_bytes(data)
    meta = json.dumps({"filename": file.filename})
    return await tl("POST", "/tasks", data={
        "index_id": index_id, "user_metadata": meta,
    }, files={"video_file": (file.filename, data, "video/mp4")})


@app.post("/api/search")
async def search(req: Request):
    body = await req.json()
    parts = [
        ("index_id", (None, body["index_id"])),
        ("query_text", (None, body["query"])),
    ]
    for o in body.get("options", ["visual", "audio"]):
        parts.append(("search_options", (None, o)))
    return await tl("POST", "/search", files=parts)


@app.post("/api/analyze")
async def analyze(req: Request):
    body = await req.json()
    payload = {
        "video_id": body["video_id"],
        "prompt": body["prompt"],
        "temperature": body.get("temperature", 0.2),
    }

    async def gen():
        async with client.stream("POST", f"{BASE}/analyze", headers=HDR, json=payload) as r:
            async for line in r.aiter_lines():
                if line.strip():
                    yield line + "\n"

    return StreamingResponse(gen(), media_type="text/plain")


IA_UA = {"User-Agent": "hack-video-playground/0.1 (Claude Code; claude-opus-5)"}
IA_SEARCH = "https://archive.org/advancedsearch.php"
IA_FTS = "https://be-api.us.archive.org/ia-pub-fts-api"


@app.get("/api/ia/search")
async def ia_search(q: str, collection: str = "", mediatype: str = "", rows: int = 30):
    parts = [q]
    if collection:
        parts.append(f"collection:{collection}")
    if mediatype:
        parts.append(f"mediatype:{mediatype}")
    params = [("q", " AND ".join(p for p in parts if p)), ("rows", str(rows)),
              ("output", "json"), ("sort[]", "date desc")]
    for f in ("identifier", "title", "date", "mediatype", "collection", "downloads"):
        params.append(("fl[]", f))
    r = await client.get(IA_SEARCH, params=params, headers=IA_UA)
    try:
        return JSONResponse(r.json().get("response", {}))
    except Exception:
        return JSONResponse({"error": r.text[:400]}, status_code=502)


@app.get("/api/ia/fulltext")
async def ia_fulltext(q: str, rows: int = 15):
    """Full-text search inside OCR'd documents and transcripts."""
    r = await client.get(IA_FTS, params={"q": q, "size": rows}, headers=IA_UA)
    if r.status_code != 200:
        return JSONResponse({"error": f"FTS {r.status_code}"}, status_code=502)
    out = []
    for h in r.json().get("hits", {}).get("hits", []):
        f = h.get("fields", {})
        out.append({
            "identifier": (f.get("identifier") or [""])[0],
            "title": (f.get("meta_title") or [""])[0],
            "mediatype": (f.get("meta_mediatype") or [""])[0],
            "year": (f.get("meta_year") or [None])[0],
            "snippets": h.get("highlight", {}).get("text", [])[:4],
        })
    return {"hits": out}


@app.get("/api/ia/item/{identifier}")
async def ia_item(identifier: str):
    r = await client.get(f"https://archive.org/metadata/{identifier}", headers=IA_UA)
    d = r.json()
    if not d:
        return JSONResponse({"error": "not found"}, status_code=404)
    md = d.get("metadata", {})
    vids = [
        {"name": f["name"], "format": f.get("format"),
         "size_mb": round(int(f.get("size", 0)) / 1e6, 1) if f.get("size") else None}
        for f in d.get("files", [])
        if f["name"].lower().endswith((".mp4", ".mpg", ".mkv", ".webm", ".ogv", ".avi", ".mov"))
    ]
    return {
        "identifier": identifier,
        "title": md.get("title"),
        "date": md.get("date"),
        "collection": md.get("collection"),
        "restricted": md.get("access-restricted-item") in (True, "true"),
        "videos": sorted(vids, key=lambda v: v["size_mb"] or 0),
        "n_files": len(d.get("files", [])),
    }


@app.post("/api/ia/fetch")
async def ia_fetch(req: Request):
    """Pull one file from an IA item straight into the local video library."""
    b = await req.json()
    ident, name = b["identifier"], b["name"]
    url = f"https://archive.org/download/{ident}/{name}"
    dest = VIDEO_DIR / f"IA_{ident}__{name}".replace("/", "_")
    async with client.stream("GET", url, headers=IA_UA, follow_redirects=True) as r:
        if r.status_code != 200:
            return JSONResponse(
                {"error": f"HTTP {r.status_code} — item is access-restricted"},
                status_code=r.status_code,
            )
        with open(dest, "wb") as fh:
            async for chunk in r.aiter_bytes():
                fh.write(chunk)
    return {"saved": dest.name, "size_mb": round(dest.stat().st_size / 1e6, 1)}


YOU_KEY = os.environ.get("YDC_API_KEY", "")


@app.get("/api/you/status")
async def you_status():
    if not YOU_KEY:
        return {"ok": False, "error": "YDC_API_KEY not set"}
    r = await client.get("https://api.you.com/v1/billing/account_balance",
                         headers={"X-API-Key": YOU_KEY})
    if r.status_code != 200:
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    return {"ok": True, "balance": r.json().get("data", {}).get("attributes", {}).get("balance")}


@app.get("/api/you/search")
async def you_search(q: str):
    r = await client.get("https://api.you.com/v1/search", params={"query": q},
                         headers={"X-API-Key": YOU_KEY})
    if r.status_code != 200:
        return JSONResponse({"error": f"HTTP {r.status_code}"}, status_code=r.status_code)
    res = r.json().get("results", {})
    out = []
    for kind, items in res.items():
        for it in items or []:
            out.append({
                "kind": kind,
                "title": it.get("title"),
                "url": it.get("url"),
                "description": it.get("description") or " ".join(it.get("snippets", [])[:2]),
                "age": it.get("page_age"),
            })
    out.sort(key=lambda x: x.get("age") or "", reverse=True)
    return {"results": out}


import asyncio, uuid

# Jobs live on the server, not in a page. Navigating away, or closing the tab,
# no longer kills the work — a deep research call is 30-120s and used to be
# aborted the moment you clicked another tab.
JOBS: dict[str, dict] = {}


async def _run_research(job_id: str, query: str):
    j = JOBS[job_id]
    try:
        r = await client.post("https://api.you.com/v1/research",
                              headers={"X-API-Key": YOU_KEY, "Content-Type": "application/json"},
                              json={"input": query}, timeout=600.0)
        if r.status_code != 200:
            # an upstream failure was being filed as a successful job with no content
            j["status"], j["error"] = "failed", f"upstream HTTP {r.status_code}: {r.text[:200]}"
            j["finished_at"] = time.time()
            return
        d = r.json()
        out = d.get("output") or {}
        # the key is `sources`, not `citations` — reading the wrong one meant the
        # SOURCES list was always empty and silently so
        srcs = (out.get("sources") if isinstance(out, dict) else None) or d.get("sources") or []
        j["result"] = {
            "content": out.get("content") if isinstance(out, dict) else out,
            "citations": srcs,
        }
        j["status"] = "done"
    except Exception as e:
        j["status"], j["error"] = "failed", str(e)[:300]
    j["finished_at"] = time.time()


@app.post("/api/you/research")
async def you_research(req: Request):
    b = await req.json()
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"id": job_id, "kind": "research", "query": b["query"],
                    "status": "running", "started_at": time.time(),
                    "result": None, "error": None, "finished_at": None}
    asyncio.create_task(_run_research(job_id, b["query"]))
    return {"job_id": job_id, "status": "running"}


@app.get("/api/jobs")
async def jobs_list():
    return sorted(
        [{k: v for k, v in j.items() if k != "result"} |
         {"has_result": j["result"] is not None} for j in JOBS.values()],
        key=lambda j: j["started_at"], reverse=True,
    )[:20]


@app.get("/api/jobs/{job_id}")
async def job_get(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    return j


@app.delete("/api/jobs/{job_id}")
async def job_del(job_id: str):
    JOBS.pop(job_id, None)
    return {"ok": True}


from neo4j import GraphDatabase

neo = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))


def cy(q, **kw):
    with neo.session() as s:
        return [r.data() for r in s.run(q, **kw)]


@app.get("/api/graph/stats")
async def graph_stats():
    try:
        return {
            "nodes": cy("MATCH (n) RETURN coalesce(labels(n)[0],'?') AS label, count(*) AS n "
                        "ORDER BY n DESC"),
            "edges": cy("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY n DESC"),
        }
    except Exception as e:
        return JSONResponse({"error": str(e)[:200]}, status_code=503)


@app.get("/api/graph/coverage")
async def graph_coverage():
    return cy("""
      MATCH (co:Concept)
      OPTIONAL MATCH (seg:Segment)-[:CANDIDATE_FOR]->(co)
      OPTIONAL MATCH (seg)-[:PART_OF]->(src:Source)
      OPTIONAL MATCH (cov:Covenant)-[:MEASURED_BY]->(co)
      RETURN co.code AS concept, co.name AS name, co.unit_kind AS unit,
             co.reachable_by AS lane, count(DISTINCT seg) AS segments,
             count(DISTINCT src) AS sources, collect(DISTINCT cov.covenant_code)[0] AS covenant
      ORDER BY segments DESC, concept""")


@app.get("/api/graph/vocabularies")
async def graph_vocabs():
    return cy("""MATCH (v:Vocabulary)-[:HAS_TERM]->(t:Term)
                 RETURN v.name AS name, v.description AS description,
                        collect({value:t.value, description:t.description}) AS terms
                 ORDER BY name""")


@app.get("/api/graph/assertions")
async def graph_assertions():
    return cy("""
      MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant)
      RETURN elementId(m) AS id, e.name AS event, toString(e.date) AS date, e.kind AS kind,
             c.covenant_code AS covenant, c.direction AS covenant_direction,
             m.status AS status, m.asserted_by AS asserted_by, m.direction AS direction,
             m.rationale AS rationale, m.model AS model,
             m.validated_by AS validated_by, toString(m.validated_at) AS validated_at
      ORDER BY m.status, e.date""")


@app.post("/api/graph/validate")
async def graph_validate(req: Request):
    b = await req.json()
    if b.get("status") not in ("validated", "rejected"):
        return JSONResponse({"error": "humans may only validate or reject"}, status_code=400)

    # Never invent an attester. An unsigned decision is not a decision, and
    # defaulting the name meant an anonymous caller could sign as someone else.
    who = (b.get("who") or "").strip()
    if not who:
        return JSONResponse({"error": "who is required — a decision must be signed"},
                            status_code=400)

    cur = cy("MATCH ()-[m:MAY_AFFECT]->() WHERE elementId(m) = $id "
             "RETURN m.status AS status, m.validated_by AS by, "
             "toString(m.validated_at) AS at", id=b["id"])
    if not cur:
        return JSONResponse({"error": "not found"}, status_code=404)

    # A settled pair is closed — to the model AND to a second HTTP caller.
    # Reopening is possible but must be deliberate and is recorded as such.
    if cur[0]["status"] != "proposed" and not b.get("reopen"):
        return JSONResponse({
            "error": "already decided",
            "status": cur[0]["status"], "by": cur[0]["by"], "at": cur[0]["at"],
            "hint": "pass reopen:true to overturn — it is recorded, not silent",
        }, status_code=409)

    rows = cy("""MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant) WHERE elementId(m) = $id
                 SET m.status = $status, m.validated_by = $who, m.validated_at = datetime(),
                     m.human_note = $note,
                     m.reopened = CASE WHEN $reopen THEN coalesce(m.reopened,0)+1 ELSE m.reopened END,
                     m.previous_status = CASE WHEN $reopen THEN $prev ELSE m.previous_status END
                 RETURN m.status AS status, m.validated_by AS by,
                        coalesce(m.reopened,0) AS reopened""",
              id=b["id"], status=b["status"], who=who, note=b.get("note"),
              reopen=bool(b.get("reopen")), prev=cur[0]["status"])
    return rows[0]


@app.get("/api/graph/model")
async def graph_model():
    """Live schema + instance counts, for the explainer. No hardcoded samples."""
    return {
        "labels": cy("MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC"),
        "rels": cy("MATCH (a)-[r]->(b) RETURN labels(a)[0] AS from, type(r) AS type, "
                   "labels(b)[0] AS to, count(*) AS n ORDER BY n DESC"),
        "vocabularies": cy("MATCH (v:Vocabulary)-[:HAS_TERM]->(t:Term) "
                           "RETURN v.name AS name, v.description AS description, "
                           "collect(t.value) AS terms ORDER BY name"),
        "samples": {
            "Source": cy("MATCH (s:Source) RETURN s.publisher AS publisher, s.kind AS kind, "
                         "s.provenance_class AS provenance_class ORDER BY s.publisher"),
            "Concept": cy("MATCH (c:Concept) RETURN c.code AS code, c.unit_kind AS unit, "
                          "c.reachable_by AS lane ORDER BY c.code"),
            "Segment": cy("MATCH (s:Segment) RETURN s.video_id AS video_id, s.start AS start, "
                          "left(s.transcript, 70) AS transcript ORDER BY s.start LIMIT 4"),
            "Observation": cy("MATCH (o:Observation) RETURN o.concept_code AS concept, "
                              "o.value AS value, o.unit_kind AS unit, o.modality AS modality "
                              "ORDER BY o.concept_code LIMIT 4"),
            "Fact": cy("MATCH (f:Fact) RETURN f.value AS value, f.unit_kind AS unit LIMIT 4"),
            "Deal": cy("MATCH (d:Deal) RETURN d.legal_name AS legal_name, d.deal_type AS deal_type"),
            "Covenant": cy("MATCH (c:Covenant) RETURN c.covenant_code AS code, "
                           "c.direction AS direction, c.threshold_status AS threshold"),
            "Event": cy("MATCH (e:Event) RETURN e.name AS name, toString(e.date) AS date, "
                        "e.kind AS kind ORDER BY e.date"),
        },
    }


@app.get("/api/graph/attestation")
async def graph_attestation():
    """The full assertion lifecycle, for the visual path."""
    return cy("""
      MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant)
      OPTIONAL MATCH (c)-[:MEASURED_BY]->(co:Concept)
      OPTIONAL MATCH (f:Facility)-[:GOVERNED_BY]->(c)<-[:GOVERNED_BY]-(f2:Facility)
      OPTIONAL MATCH (d:Deal)-[:HAS_FACILITY]->(fac:Facility)-[:GOVERNED_BY]->(c)
      RETURN elementId(m) AS id, e.name AS event, toString(e.date) AS date, e.kind AS event_kind,
             m.asserted_by AS asserted_by, m.model AS model, m.status AS status,
             m.direction AS direction, m.rationale AS rationale,
             m.validated_by AS validated_by, toString(m.validated_at) AS validated_at,
             m.human_note AS human_note,
             m.evidence_url AS evidence_url, m.could_affect AS could_affect,
             c.covenant_code AS covenant, c.direction AS covenant_direction,
             co.code AS concept, d.legal_name AS deal, fac.governing_doc AS governing_doc
      ORDER BY e.date DESC""")


@app.post("/api/graph/query")
async def graph_query(req: Request):
    b = await req.json()
    q = b["cypher"]
    if any(w in q.upper() for w in ("CREATE ", "DELETE", "MERGE ", "SET ", "DROP ", "REMOVE ")):
        return JSONResponse({"error": "read-only from this page"}, status_code=400)
    try:
        return {"rows": cy(q)}
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=400)


@app.get("/media/{name}")
async def media(name: str):
    p = VIDEO_DIR / name
    if not p.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(p, media_type="video/mp4")


# mounted before "/" — order matters, Starlette takes the first match
app.mount("/docs", StaticFiles(directory="docs", html=True), name="docs")
# Served from the app, not opened as file://, so the explainers can read live
# graph data same-origin instead of shipping hardcoded samples.
app.mount("/explainers", StaticFiles(directory="docs/explainers", html=True), name="explainers")
app.mount("/", StaticFiles(directory="static", html=True), name="static")
