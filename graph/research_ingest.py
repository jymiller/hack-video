"""Research findings become graph proposals. The controlled lane's only way to grow.

Video is observed, always and by construction: nobody in the deal produced it and
nobody warrants it, so it may never produce a Fact and may never supply a covenant
number. That is the whole argument of this graph — and it leaves a problem. If the
controlled lane can only ever be pre-loaded by hand, the demo is a fixture.

This is the other half. A You.com research call comes back with citations; some of
them are the document itself — a prospectus, an RNS, an annual report, a judgment —
and those are CONTROLLED. A covenant threshold can therefore arrive live, sourced
rather than typed in. Most of them are a journalist writing about the document, and
those are OBSERVED and may never reach a number.

    A news article about a filing is not the filing.

Get that line wrong and every downstream claim in the graph is worthless, so the
classifier is told to be conservative and the pipeline is built to be safe when it
is wrong anyway:

  · The model writes status='proposed' and nothing else. Ever. Enforced in Cypher
    (`ON CREATE SET status='proposed'` then `WITH x WHERE x.status='proposed'`), not
    by asking nicely, so a human decision cannot be overwritten by a later run.
  · A covenant number is only written from a source the classifier called controlled.
    If it called it observed and extracted a number anyway, the number is REFUSED and
    the refusal is printed. Structure, not prompt discipline.
  · Identity is sha256 of the canonical URL, exactly as graph/urls.py has it. A hash
    already in the graph is seen, and seen is settled — it is never re-derived and
    never sent to the model.

    python -m graph.research_ingest dry     <job_id|file.json>
    python -m graph.research_ingest propose <job_id|file.json>
    python -m graph.research_ingest status
"""
import hashlib
import json
import os
import pathlib
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

import graph.db as db

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# The bare `gpt-5.6` alias routes to the flagship tier at ~25x the price for what is
# a handful of short structured completions. Pin terra and refuse the alias even if
# the environment hands it over. Same guard as graph/nl2cypher.py.
MODEL_ID = os.environ.get("OPENAI_RESEARCH_MODEL", "gpt-5.6-terra")
if MODEL_ID == "gpt-5.6":
    MODEL_ID = "gpt-5.6-terra"

APP = os.environ.get("HACK_APP", "http://127.0.0.1:8000")
BATCH = 8          # citations per completion — bounded so one bad batch is not the run
SNIPPET = 1400     # chars of citation text sent per result

_drv = None


def driver():
    global _drv
    if _drv is None:
        _drv = db.driver()
    return _drv


# ---------------------------------------------------------------------------
# identity — sha256 of the canonical URL, matching graph/urls.py
# ---------------------------------------------------------------------------

TRACKING = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref_src", "_hsenc")


def canonical(url: str) -> str:
    """Canonical form: lowercase scheme+host, no fragment, no tracking params, no
    trailing slash. So the same document found twice hashes once — and so a research
    hit on a video already in the corpus lands on the corpus Source, not beside it."""
    p = urlsplit((url or "").strip())
    if not p.scheme:
        p = urlsplit("https://" + (url or "").strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
         if not any(k.lower().startswith(t) for t in TRACKING)]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(),
                       p.path.rstrip("/") or "/", urlencode(q), ""))


def sha(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()


# ---------------------------------------------------------------------------
# what the model may say
# ---------------------------------------------------------------------------

class CovenantClaim(BaseModel):
    covenant_code: str        # senior_icr | senior_rar — validated against the graph
    stated_value: float | None
    direction: str            # min | max | unknown
    quote: str                # the words in the result that carry the number
    basis: str                # why this document would be the one that states it


class Classified(BaseModel):
    n: int                    # the citation number as given, so nothing is reordered
    lane: str                 # controlled | observed
    kind: str                 # prospectus, rns, annual_report, court_judgment, news_article…
    publisher: str
    lane_evidence: str        # what in the url/title/text decided the lane
    rationale: str
    confidence: float
    is_primary_document: bool
    # A list, not one: a prospectus states both thresholds in the same paragraph, and
    # a single-claim field silently threw the second one away.
    covenant_claims: list[CovenantClaim]
    reports_event: str | None  # exact Event name from the list, or null
    relevant: bool             # is this about Gatwick's debt/deal/expansion at all


class Batch(BaseModel):
    results: list[Classified]


SYSTEM = """You classify web research results for a credit-analysis knowledge graph
about Gatwick Airport and the Gatwick Funding Limited secured bond programme.

THE ONE RULE THAT MATTERS. Every Source in this graph sits in one of two lanes.

controlled — THE DOCUMENT ITSELF, published by a party who is accountable in the
  deal's document chain and liable if it is wrong: the issuer, the borrower, their
  auditor, a regulator, an exchange, a court. Bond prospectus, base prospectus,
  supplementary prospectus, final terms, Common Terms Agreement, RNS regulatory
  announcement, annual report and financial statements, Companies House filing,
  investor report or compliance certificate published by the obligor, a CAA or CMA
  decision, a court judgment, a rating agency's own published rating action.

observed — EVERYTHING ELSE. A news article, a wire report, a trade publication, a
  blog, an aggregator, a listicle, a law-firm client briefing, a broker note write-up,
  an encyclopedia entry, a search-engine snippet, a PDF hosted by a third party that
  merely quotes a filing, a page you cannot identify.

A NEWS ARTICLE ABOUT A FILING IS NOT THE FILING. Reuters reporting the prospectus is
observed. The prospectus on the issuer's own site or the exchange's own site is
controlled. A journalist's write-up of an RNS is observed; the RNS is controlled.
A university or campaign group reproducing an extract is observed.

Only a controlled source may ever produce a Fact or supply a number a covenant is
tested on. A wrong 'controlled' is therefore the most expensive mistake available to
you, and a wrong 'observed' costs almost nothing — the item is simply held as
commentary. WHEN YOU ARE NOT SURE, SAY observed. Unsure is not a failure. A false
controlled is.

Judge the lane from WHO PUBLISHED THE PAGE YOU ARE LOOKING AT, not from what it
talks about. The domain is your strongest signal. If the host is a news organisation,
the lane is observed however authoritative the content sounds.

FIELDS
- lane: exactly 'controlled' or 'observed'.
- kind: short snake_case document type — prospectus, supplementary_prospectus,
  rns_announcement, annual_report, companies_house_filing, court_judgment,
  regulatory_decision, rating_action, investor_report, news_article, trade_press,
  blog, aggregator, encyclopedia, unknown.
- publisher: the organisation that published THIS page.
- lane_evidence: one short clause naming what decided it — the domain, a title word
  like 'Prospectus', a filing reference. Be specific and checkable.
- rationale: one sentence a credit analyst would accept.
- confidence: 0-1 on the LANE decision. Below 0.7 means you are guessing, and you
  must then choose observed.
- is_primary_document: true only if this URL resolves to the document itself rather
  than a page describing it.
- relevant: false if the page is not about Gatwick's debt, deal, accounts, ownership
  or expansion at all.
- reports_event: if the page reports one of the listed events, its EXACT name from
  the list. Otherwise null.
- covenant_claims: one entry for EACH listed covenant whose threshold or tested level
  the text actually states — a prospectus usually states both in one sentence, so do
  not stop at the first. Quote the words that carry each number. If the page merely
  mentions covenants in general, return an empty list. Do not infer a number, do not
  convert one, do not recall one from memory. An empty list is a normal and correct
  answer.

You are reading a title, a URL and an extract. You are not reading the document. Say
what those three support and nothing more."""


def _client():
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set — add it to .env")
    return OpenAI(api_key=key)


def classify(cites, covenants, events, client=None):
    """One structured completion per batch. Returns {n: Classified}."""
    out = {}
    client = client or _client()
    cov = "\n".join(f"- {c['code']} ({c['name']}, must stay {c['dir']}, "
                    f"currently sourced from: {c['src'] or 'nothing'})" for c in covenants)
    ev = "\n".join(f"- {e['name']} ({e['date']}, {e['kind']})" for e in events)
    for i in range(0, len(cites), BATCH):
        chunk = cites[i:i + BATCH]
        body = "\n\n".join(
            f"[{c['n']}] TITLE: {c['title'] or '(none)'}\nURL: {c['url']}\n"
            f"EXTRACT: {(c['text'] or '(none)')[:SNIPPET]}" for c in chunk)
        user = (f"COVENANTS IN THE GRAPH:\n{cov}\n\nEVENTS IN THE GRAPH:\n{ev}\n\n"
                f"RESEARCH RESULTS TO CLASSIFY — return one entry per number, "
                f"{len(chunk)} in total:\n\n{body}")
        r = client.responses.parse(
            model=MODEL_ID, instructions=SYSTEM, input=user,
            text_format=Batch,
            max_output_tokens=12000,   # bounds reasoning too — leave headroom
        )
        parsed = r.output_parsed
        if parsed is None:
            raise RuntimeError(f"model returned no parsed batch (status={r.status})")
        for c in parsed.results:
            out[c.n] = c
    return out


# ---------------------------------------------------------------------------
# the job
# ---------------------------------------------------------------------------

def normalise(result: dict) -> list[dict]:
    """You.com hands back `citations` of varying shape — dicts with url/title and one
    of several text keys, or bare url strings. Flatten, canonicalise, de-duplicate."""
    cites, seen = [], set()
    for it in (result or {}).get("citations") or []:
        if isinstance(it, str):
            it = {"url": it}
        url = (it.get("url") or "").strip()
        if not url:
            continue
        cu = canonical(url)
        if cu in seen:
            continue
        seen.add(cu)
        # `snippets` (plural, a list) is what You.com actually sends. Reading only
        # the singular key sent the model a URL and a title and nothing else, which
        # is exactly how a prospectus gets classified as unknown.
        text = next((it[k] for k in ("snippets", "snippet", "text", "description",
                                     "content", "summary", "extract") if it.get(k)), "")
        if isinstance(text, list):
            text = "\n".join(str(x) for x in text)
        cites.append({"n": len(cites) + 1, "url": cu, "raw_url": url,
                      "title": it.get("title") or it.get("name") or "",
                      "text": str(text), "sha": sha(cu)})
    return cites


def load_job(ref: str) -> dict:
    """A job id off the running app, or a path to a saved json job/result."""
    p = pathlib.Path(ref)
    if p.exists():
        d = json.loads(p.read_text())
        return d if "result" in d else {"id": p.stem, "query": d.get("query", ""),
                                        "result": d}
    r = httpx.get(f"{APP}/api/jobs/{ref}", timeout=20.0)
    if r.status_code != 200:
        raise RuntimeError(f"no job {ref} on {APP} ({r.status_code}) — "
                           "is the app running, and is the job still in memory?")
    return r.json()


def _graph_context(s):
    covenants = [{"code": r["code"], "name": r["name"], "dir": r["dir"], "src": r["src"]}
                 for r in s.run("MATCH (c:Covenant) RETURN c.covenant_code AS code, "
                                "c.name AS name, c.direction AS dir, "
                                "c.threshold_source AS src ORDER BY code").data()]
    events = [{"name": r["name"], "date": r["date"], "kind": r["kind"]}
              for r in s.run("MATCH (e:Event) RETURN e.name AS name, "
                             "toString(e.date) AS date, e.kind AS kind "
                             "ORDER BY e.date").data()]
    # Seen is a hash comparison and nothing fuzzier. Anything already in the graph —
    # the pre-loaded corpus (status null) or an earlier proposal — is settled and is
    # not sent to the model again.
    known = {r["h"]: {"publisher": r["pub"], "lane": r["pc"], "status": r["st"]}
             for r in s.run("MATCH (n:Source) WHERE n.url_sha256 IS NOT NULL "
                            "RETURN n.url_sha256 AS h, n.publisher AS pub, "
                            "n.provenance_class AS pc, n.status AS st").data()}
    return covenants, events, known


def run(job: dict, dry: bool = False):
    """Yields NDJSON-shaped events. The server streams these straight to the page.

    {model} {context} {seen} {stage} {proposal} {refused} {written} {done} {error}
    """
    result = job.get("result") or {}
    cites = normalise(result)
    yield {"model": MODEL_ID, "job": job.get("id"), "query": job.get("query"),
           "citations": len(cites), "dry": dry}
    if not cites:
        yield {"done": {"proposed_sources": 0, "proposed_edges": 0, "refused": 0,
                        "dry": dry, "note": "the research job cited nothing"}}
        return

    drv = driver()
    with drv.session() as s:
        covenants, events, known = _graph_context(s)
        cov_codes = {c["code"] for c in covenants}
        ev_names = {e["name"] for e in events}
        yield {"context": {"covenants": sorted(cov_codes), "events": len(ev_names),
                           "sources_in_graph": len(known)}}

        # ---- the worklist, computed before a single token is spent -----------
        work, settled = [], []
        for c in cites:
            if c["sha"] in known:
                k = known[c["sha"]]
                settled.append({**c, "already": k})
            else:
                work.append(c)
        if settled:
            yield {"seen": [{"n": c["n"], "url": c["url"], "title": c["title"],
                             "publisher": c["already"]["publisher"],
                             "lane": c["already"]["lane"],
                             "status": c["already"]["status"] or "loaded"}
                            for c in settled]}
        if not work:
            yield {"done": {"proposed_sources": 0, "proposed_edges": 0, "refused": 0,
                            "dry": dry,
                            "note": "every citation is already a Source in the graph — "
                                    "nothing unseen, no model call made"}}
            return

        yield {"stage": "classify", "unseen": len(work),
               "batches": (len(work) + BATCH - 1) // BATCH}
        try:
            verdicts = classify(work, covenants, events)
        except Exception as e:
            yield {"error": f"{type(e).__name__}: {str(e)[:300]}"}
            return

        run_id = f"research-{MODEL_ID}-{int(time.time())}"
        if not dry:
            s.run("MERGE (r:ExtractionRun {id:$id}) SET r.model=$m, "
                  "r.purpose='research ingest — source classification', "
                  "r.started_at=datetime(), r.query=$q",
                  id=run_id, m=MODEL_ID, q=job.get("query"))

        n_src = n_edge = n_ref = 0
        for c in work:
            v = verdicts.get(c["n"])
            if v is None:
                yield {"dropped": {"n": c["n"], "url": c["url"],
                                   "why": "the model returned no verdict for this result"}}
                continue

            # A model may answer about something it was not asked. Drop it rather
            # than trust it — the same guard assert_impact.py applies to covenants.
            lane = v.lane if v.lane in ("controlled", "observed") else "observed"
            forced = v.lane not in ("controlled", "observed")
            # Its own stated confidence is held to the rule it was given. A
            # controlled call under 0.7 is not a controlled call.
            if lane == "controlled" and (v.confidence or 0) < 0.7:
                lane, forced = "observed", True

            claims = []
            for claim in v.covenant_claims or []:
                refusal = None
                if claim.covenant_code not in cov_codes:
                    refusal = f"no covenant '{claim.covenant_code}' in the graph"
                elif lane == "observed":
                    # THE MOMENT. An observed source may never supply a covenant
                    # number, whatever the model extracted. Structure refuses it; the
                    # prompt does not have to hold.
                    refusal = ("observed source — a covenant number may not come from "
                               "third-party observation, however plausible it reads")
                if refusal:
                    n_ref += 1
                    yield {"refused": {"n": c["n"], "url": c["url"],
                                       "publisher": v.publisher, "lane": lane,
                                       "covenant_code": claim.covenant_code,
                                       "stated_value": claim.stated_value,
                                       "quote": claim.quote[:300], "why": refusal}}
                    continue
                claims.append(claim)

            reports = v.reports_event if v.reports_event in ev_names else None

            prop = {
                "n": c["n"], "url": c["url"], "title": c["title"],
                "sha": c["sha"], "lane": lane, "kind": v.kind,
                "publisher": v.publisher, "confidence": v.confidence,
                "lane_evidence": v.lane_evidence, "rationale": v.rationale,
                "is_primary_document": v.is_primary_document,
                "relevant": v.relevant, "lane_forced": forced,
                "reports_event": reports,
                "covenant_claims": [x.model_dump() for x in claims],
                "status": "proposed",
            }
            yield {"proposal": prop}

            if dry:
                n_src += 1
                n_edge += (1 if reports else 0) + len(claims)
                continue

            # ---- the write. status='proposed' and nothing else, ever. --------
            # MERGE on the url hash: identity is the URL. The WHERE guard means a
            # Source a human has already decided — or one the corpus loaded, which
            # carries no status at all — is never touched by a later run.
            s.run(
                """MERGE (n:Source {url_sha256:$h})
                     ON CREATE SET n.status='proposed', n.id=$id, n.url=$url,
                                   n.validated_by=null, n.validated_at=null,
                                   n.first_seen=datetime()
                   WITH n WHERE n.status = 'proposed'
                   SET n.provenance_class=$lane, n.kind=$kind, n.publisher=$pub,
                       n.title=$title, n.origin='you.com research',
                       n.asserted_by='model', n.model=$model, n.asserted_at=datetime(),
                       n.rationale=$why, n.lane_evidence=$eviq, n.confidence=$conf,
                       n.is_primary_document=$prim, n.research_job=$job,
                       n.evidence_url=$url, n.evidence_sha256=$h
                   WITH n MATCH (r:ExtractionRun {id:$run})
                   MERGE (n)-[:PRODUCED_BY]->(r)""",
                h=c["sha"], id=f"you:{c['sha'][:16]}", url=c["url"], lane=lane,
                kind=v.kind, pub=v.publisher, title=c["title"], model=MODEL_ID,
                why=v.rationale, eviq=v.lane_evidence, conf=v.confidence,
                prim=bool(v.is_primary_document), job=job.get("id"), run=run_id)
            n_src += 1
            written = []

            if reports:
                s.run(
                    """MATCH (n:Source {url_sha256:$h}), (e:Event {name:$ev})
                       WHERE n.status = 'proposed'
                       MERGE (n)-[x:REPORTS]->(e)
                         ON CREATE SET x.status='proposed', x.validated_by=null,
                                       x.validated_at=null
                       WITH x WHERE x.status = 'proposed'
                       SET x.asserted_by='model', x.model=$model, x.asserted_at=datetime(),
                           x.basis=$basis, x.evidence_sha256=$h, x.evidence_url=$url""",
                    h=c["sha"], ev=reports, model=MODEL_ID, url=c["url"],
                    basis="research result classified as reporting this event")
                n_edge += 1
                written.append({"type": "REPORTS", "to": reports})

            for claim in claims:
                # A controlled document that states a threshold is a candidate for
                # where that threshold comes FROM. It is not the threshold. Nothing
                # computes on this edge until a human moves it off 'proposed' — and
                # the covenant's own threshold_value is not touched here at all.
                # The provenance_class guard is the belt to the classifier's braces:
                # even a bug above cannot land this edge on an observed source.
                s.run(
                    """MATCH (n:Source {url_sha256:$h}), (c:Covenant {covenant_code:$cc})
                       WHERE n.status = 'proposed' AND n.provenance_class = 'controlled'
                       MERGE (n)-[x:MAY_SOURCE_THRESHOLD]->(c)
                         ON CREATE SET x.status='proposed', x.validated_by=null,
                                       x.validated_at=null
                       WITH x WHERE x.status = 'proposed'
                       SET x.asserted_by='model', x.model=$model, x.asserted_at=datetime(),
                           x.stated_value=$val, x.direction=$dir, x.quote=$quote,
                           x.rationale=$basis, x.evidence_sha256=$h, x.evidence_url=$url""",
                    h=c["sha"], cc=claim.covenant_code, model=MODEL_ID,
                    val=claim.stated_value, dir=claim.direction, quote=claim.quote[:600],
                    basis=claim.basis[:600], url=c["url"])
                n_edge += 1
                written.append({"type": "MAY_SOURCE_THRESHOLD", "to": claim.covenant_code,
                                "stated_value": claim.stated_value})
            yield {"written": {"n": c["n"], "source": "proposed", "edges": written}}

        yield {"done": {"proposed_sources": n_src, "proposed_edges": n_edge,
                        "refused": n_ref, "dry": dry, "run": None if dry else run_id,
                        "note": "nothing validated — no computation reads a proposed "
                                "node or edge; a human decides next"}}


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------

def _cli_stream(job, dry):
    for ev in run(job, dry=dry):
        if "model" in ev:
            print(f"{'DRY RUN — nothing will be written' if ev['dry'] else 'PROPOSE'} · "
                  f"{ev['model']} · job {ev['job']}")
            print(f"  query: {(ev['query'] or '')[:100]}")
            print(f"  {ev['citations']} distinct citation(s)\n")
        elif "context" in ev:
            c = ev["context"]
            print(f"graph: {c['sources_in_graph']} sources, {len(c['covenants'])} "
                  f"covenants, {c['events']} events")
        elif "seen" in ev:
            print(f"\nSEEN — already a Source, not re-derived ({len(ev['seen'])}):")
            for x in ev["seen"]:
                print(f"  · [{x['status']:9}] {(x['publisher'] or '?')[:22]:24} "
                      f"{x['lane'] or '?':11} {x['url'][:60]}")
        elif "stage" in ev:
            print(f"\nUNSEEN — {ev['unseen']} result(s) to the model "
                  f"in {ev['batches']} batch(es)\n")
        elif "proposal" in ev:
            p = ev["proposal"]
            mark = "CONTROLLED" if p["lane"] == "controlled" else "observed  "
            note = "  (forced down — low confidence)" if p["lane_forced"] else ""
            print(f"  → proposed  {mark} [{p['confidence']:.2f}] "
                  f"{(p['publisher'] or '?')[:24]:26} {p['kind']}{note}")
            print(f"      {p['url'][:100]}")
            print(f"      lane evidence: {p['lane_evidence'][:90]}")
            if p["reports_event"]:
                print(f"      REPORTS → {p['reports_event']}")
            for cc in p["covenant_claims"]:
                print(f"      MAY_SOURCE_THRESHOLD → {cc['covenant_code']} "
                      f"= {cc['stated_value']}  «{cc['quote'][:60]}»")
        elif "refused" in ev:
            r = ev["refused"]
            print(f"  ✗ REFUSED   {(r['publisher'] or '?')[:24]:26} "
                  f"{r['covenant_code']} = {r['stated_value']}")
            print(f"      {r['why']}")
        elif "dropped" in ev:
            print(f"  ! dropped [{ev['dropped']['n']}] {ev['dropped']['why']}")
        elif "error" in ev:
            print(f"\nERROR {ev['error']}")
        elif "done" in ev:
            d = ev["done"]
            print(f"\n{d['proposed_sources']} source(s) proposed, "
                  f"{d['proposed_edges']} edge(s) proposed, {d['refused']} refused"
                  f"{' — DRY, nothing written' if d['dry'] else ''}.")
            print(f"  {d.get('note','')}")


def cmd_dry(argv):
    if not argv:
        sys.exit("usage: python -m graph.research_ingest dry <job_id|file.json>")
    _cli_stream(load_job(argv[0]), dry=True)


def cmd_propose(argv):
    if not argv:
        sys.exit("usage: python -m graph.research_ingest propose <job_id|file.json>")
    _cli_stream(load_job(argv[0]), dry=False)


def cmd_status(argv):
    with driver().session() as s:
        rows = s.run(
            """MATCH (n:Source) WHERE n.origin = 'you.com research'
               RETURN n.publisher AS pub, n.provenance_class AS lane, n.kind AS kind,
                      n.status AS status, n.confidence AS conf, n.url AS url,
                      n.validated_by AS by, n.lane_evidence AS why
               ORDER BY n.provenance_class, n.status, n.publisher""").data()
        print("=== sources proposed by research ingest ===")
        if not rows:
            print("  none — run: python -m graph.research_ingest propose <job_id>")
        for r in rows:
            sign = f" by {r['by']}" if r["by"] else ""
            print(f"  [{r['status']:9}{sign}] {r['lane']:11} {(r['pub'] or '?')[:24]:26} "
                  f"{r['kind']:22} {r['conf']}")
            print(f"      {(r['why'] or '')[:96]}")
            print(f"      {r['url'][:96]}")

        print("\n=== edges into the deal lane from research ===")
        for r in s.run(
            """MATCH (n:Source)-[x:MAY_SOURCE_THRESHOLD]->(c:Covenant)
               RETURN n.publisher AS pub, n.provenance_class AS lane,
                      c.covenant_code AS cov, x.stated_value AS val, x.status AS st,
                      x.validated_by AS by, x.quote AS quote
               ORDER BY st, cov""").data():
            print(f"  [{r['st']:9}] {r['lane']:11} {(r['pub'] or '?')[:22]:24} "
                  f"→ {r['cov']} = {r['val']}")
            print(f"      «{(r['quote'] or '')[:88]}»")

        print("\n=== invariants ===")
        for label, q, want in [
            ("Source proposed by the model with a status other than 'proposed'",
             "MATCH (n:Source) WHERE n.asserted_by='model' AND n.status<>'proposed' "
             "RETURN count(*) AS n", 0),
            ("MAY_SOURCE_THRESHOLD from an observed source",
             "MATCH (n:Source)-[:MAY_SOURCE_THRESHOLD]->(:Covenant) "
             "WHERE n.provenance_class <> 'controlled' RETURN count(*) AS n", 0),
            ("MAY_SOURCE_THRESHOLD asserted by the model, not 'proposed'",
             "MATCH ()-[x:MAY_SOURCE_THRESHOLD]->() "
             "WHERE x.asserted_by='model' AND x.status<>'proposed' RETURN count(*) AS n", 0),
            ("Fact from an observed source",
             "MATCH (f:Fact)-[:FROM]->(s:Source) WHERE s.provenance_class='observed' "
             "RETURN count(*) AS n", 0),
            ("Fact hanging off a proposed source",
             "MATCH (f:Fact)-[:FROM]->(s:Source) WHERE s.status='proposed' "
             "RETURN count(*) AS n", 0),
            ("Covenant threshold_source pointing at a proposed source",
             "MATCH (c:Covenant), (s:Source {status:'proposed'}) "
             "WHERE c.threshold_source = s.id RETURN count(*) AS n", 0),
            ("Research source with no url hash",
             "MATCH (n:Source) WHERE n.origin='you.com research' AND "
             "n.url_sha256 IS NULL RETURN count(*) AS n", 0),
        ]:
            n = s.run(q).single()["n"]
            print(f"  {'ok  ' if n == want else 'FAIL'} {label}: {n} (want {want})")

        print("\n=== what a computation reads ===")
        n = s.run("MATCH (n:Source) WHERE n.origin='you.com research' AND "
                  "n.status='validated' RETURN count(*) AS n").single()["n"]
        print(f"  {n} validated research source(s) — everything else is inert.")


CMDS = {"propose": cmd_propose, "status": cmd_status, "dry": cmd_dry}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in CMDS:
        sys.exit(f"usage: python -m graph.research_ingest [{' | '.join(CMDS)}] [job_id]")
    CMDS[cmd](sys.argv[2:])
    if _drv is not None:
        _drv.close()
