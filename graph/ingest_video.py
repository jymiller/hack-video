"""Search finds a clip, the clip becomes corpus. The observed lane's way to grow.

The other half of graph/research_ingest.py, and the opposite lane. That module takes a
You.com *research* answer and asks which citations are the document itself, because a
prospectus or an RNS is CONTROLLED and may source a covenant threshold. This module
takes a You.com *search* result, keeps the ones that are videos, and pulls them into
the corpus — and everything it touches is OBSERVED, permanently and by construction.

    A broadcast is not a filing. Nobody in the deal produced it and nobody warrants it.

So this path may never create a Fact, may never supply a number a covenant is tested
on, and may never mint a controlled Source. That is not a policy this file asks nicely
about, it is where the lane is decided:

  · graph/load.py writes every video Source with provenance_class='observed', hard-
    coded, for every video in the index. There is no branch. A clip that arrives here
    is observed the moment it is loaded, whatever it says about itself.
  · The upload stamps provenance_class='observed' into TwelveLabs user_metadata too,
    so the lane travels with the asset rather than being reconstructed from a filename.
  · `loop` re-runs the standing invariant afterwards (0 segments reaching a covenant,
    0 non-observed Sources under a Segment) and says the number out loud. If a change
    somewhere else ever lets video reach the controlled lane, this is where it shows.

And a search result is not evidence about the deal. A query for the Gatwick runway
returns airport vlogs, flight-sim landings and a documentary about a different
airport entirely. So `find` reports candidates and stops. Nothing is fetched that a
human did not choose — `loop` needs --yes, and `dry` spends nothing at all.

    python -m graph.ingest_video find  "gatwick northern runway"
    python -m graph.ingest_video dry   "gatwick northern runway"
    python -m graph.ingest_video fetch https://www.youtube.com/watch?v=...
    python -m graph.ingest_video index "video/<id>__<Publisher>__<Title>.mp4"
    python -m graph.ingest_video loop  "gatwick northern runway" [--yes]
"""
import json, os, pathlib, re, subprocess, sys, time
from urllib.parse import urlparse, parse_qs

import httpx
from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
# You.com's key lives in the hack-you project — same convention as server.py
load_dotenv(os.environ.get("YOU_ENV", pathlib.Path.home() / "Downloads/source/hack-you/.env"))

VIDEO_DIR = ROOT / "video"
YT_DLP = "/opt/homebrew/bin/yt-dlp"
BASE = "https://api.twelvelabs.io/v1.3"
GATWICK = os.environ.get("TL_INDEX", "6a694d8b7724e9379237179d")
PROVENANCE = "observed"  # not a default. the only value this path can produce.

# 480p-class ceiling: the corpus wants tens of MB per clip, not hundreds, and Marengo
# indexes speech and scene — neither improves at 1080p, it just costs upload minutes.
# Both dimensions are bounded, not just height. A vertical news clip is 480x854, so a
# bare [height<=480] reads the LONG edge, throws away the 360p and 480p renditions and
# leaves 240x426 as the best match — which TwelveLabs then rejects for being too small.
# The floor is TwelveLabs' own: it wants >=360 on both axes.
MIN_DIM = 360
_BOX = "[width>=360][height>=360][width<=856][height<=856]"
FORMAT = f"bv*{_BOX}+ba/b{_BOX}/bv*[width>=360][height>=360]+ba/b[width>=360][height>=360]/bv*+ba/b"
OUT_TMPL = "%(id)s__%(uploader)s__%(title).60s.%(ext)s"

VIDEO_HOSTS = {
    "youtube.com": "youtube", "www.youtube.com": "youtube", "m.youtube.com": "youtube",
    "youtu.be": "youtube", "vimeo.com": "vimeo",
    "dailymotion.com": "dailymotion", "www.dailymotion.com": "dailymotion",
}


def _key(name):
    v = os.environ.get(name, "")
    if not v:
        sys.exit(f"{name} not set")
    return v


def video_url(u: str):
    """Is this a page whose subject IS a video we can pull? Returns a reason if not."""
    p = urlparse(u)
    host = VIDEO_HOSTS.get(p.netloc.lower())
    if not host:
        return None, "not a video host"
    if host == "youtube":
        if p.netloc.lower() == "youtu.be":
            return f"https://www.youtube.com/watch?v={p.path.strip('/')}", None
        if p.path.startswith("/shorts/"):
            return f"https://www.youtube.com/watch?v={p.path.split('/')[2]}", None
        vid = parse_qs(p.query).get("v", [None])[0]
        if not vid:
            return None, "youtube page with no video id (channel, playlist or search)"
        return f"https://www.youtube.com/watch?v={vid}", None
    if host == "dailymotion" and not p.path.startswith("/video/"):
        return None, "dailymotion page that is not a video"
    return u, None


def yt_id(u: str):
    return parse_qs(urlparse(u).query).get("v", [None])[0]


def have():
    """{youtube id: filename} for the clips already on disk."""
    return {p.name.split("__")[0]: p.name for p in VIDEO_DIR.glob("*.mp4")}


def probe(url: str):
    """One metadata read, no download. Gives us publisher and duration so a human
    can tell a 9-minute news package from a 28-second Short before spending."""
    r = subprocess.run(
        [YT_DLP, "--skip-download", "--no-warnings", "--print",
         "%(id)s\t%(uploader)s\t%(duration)s\t%(title)s", url],
        capture_output=True, text=True, timeout=60,
    )
    if r.returncode != 0:
        return {"error": (r.stderr.strip().splitlines() or ["yt-dlp failed"])[-1][:160]}
    bits = r.stdout.strip().split("\t")
    if len(bits) < 4:
        return {"error": "unexpected yt-dlp output"}
    dur = None if bits[2] in ("NA", "None", "") else int(float(bits[2]))
    return {"id": bits[0], "publisher": bits[1], "duration": dur, "title": bits[3]}


def dims(path: pathlib.Path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True,
    )
    try:
        w, h = r.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except ValueError:
        return None, None


def you_search(query: str):
    r = httpx.get("https://api.you.com/v1/search", params={"query": query},
                  headers={"X-API-Key": _key("YDC_API_KEY")}, timeout=60.0)
    r.raise_for_status()
    out = []
    for items in r.json().get("results", {}).values():
        for it in items or []:
            out.append({"title": it.get("title"), "url": it.get("url")})
    return out


def find(query: str, limit: int = 6):
    """You.com -> video candidates. Yields events; returns nothing implicitly."""
    yield {"stage": "find", "query": query}
    rows = you_search(query)
    known, cands, rejected, seen = have(), [], [], set()
    # A plain web search mostly returns articles. If it returned no video at all,
    # narrow once and say so, rather than reporting an empty result as an answer.
    # The first pass's rejects are kept: they are most of what the query actually hit.
    if not any(video_url(r["url"])[0] for r in rows):
        narrowed = f"site:youtube.com {query}"
        yield {"note": f"no video in the open web results — retrying as: {narrowed}"}
        rejected = [{"url": r["url"], "why": video_url(r["url"])[1]} for r in rows]
        rows = you_search(narrowed)

    for r in rows:
        canon, why = video_url(r["url"])
        if not canon:
            rejected.append({"url": r["url"], "why": why})
            continue
        if canon in seen:
            continue
        seen.add(canon)
        cands.append({"url": canon, "title": r["title"]})

    for c in cands[:limit]:
        vid = yt_id(c["url"])
        if vid and vid in known:
            c["have"] = known[vid]
            c["why"] = "already in the corpus"
            continue
        m = probe(c["url"])
        if m.get("error"):
            c["why"] = m["error"]
            c["unavailable"] = True
            continue
        c.update(publisher=m["publisher"], duration=m["duration"], title=m["title"] or c["title"])
        c["why"] = "new — not in the corpus"

    yield {"candidates": cands[:limit], "rejected": rejected}


def fetch(url: str):
    canon, why = video_url(url)
    if not canon:
        yield {"error": f"not a fetchable video url — {why}"}
        return
    vid = yt_id(canon)
    known = have()
    if vid and vid in known:
        yield {"error": f"already in the corpus: {known[vid]}"}
        return

    yield {"stage": "fetch", "url": canon}
    printed = subprocess.run(
        [YT_DLP, "--skip-download", "--no-warnings", "--print", "filename",
         "-f", FORMAT, "--merge-output-format", "mp4", "-o", OUT_TMPL, canon],
        capture_output=True, text=True, timeout=60,
    ).stdout.strip()
    # None, not VIDEO_DIR / "" — that is the directory, and it always exists.
    dest = VIDEO_DIR / (pathlib.Path(printed).stem + ".mp4") if printed else None
    if dest and dest.exists():
        yield {"error": f"already in the corpus: {dest.name}"}
        return

    p = subprocess.Popen(
        [YT_DLP, "--newline", "--no-warnings", "-f", FORMAT, "--merge-output-format", "mp4",
         "--write-info-json", "--write-subs", "--write-auto-subs", "--sub-langs", "en.*",
         "-o", OUT_TMPL, "-P", str(VIDEO_DIR), canon],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    last = 0.0
    for line in p.stdout:
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m and float(m.group(1)) - last >= 2:
            last = float(m.group(1))
            yield {"progress": {"pct": last, "note": "download"}}
    if p.wait() != 0:
        yield {"error": "yt-dlp failed"}
        return

    if dest is None or not dest.exists():
        hits = sorted(VIDEO_DIR.glob(f"{vid}__*.mp4")) if vid else []
        if not hits:
            yield {"error": "download finished but no mp4 landed"}
            return
        dest = hits[0]
    w, h = dims(dest)
    yield {"fetched": {"file": dest.name, "size_mb": round(dest.stat().st_size / 1e6, 1),
                       "resolution": f"{w}x{h}" if w else None}}


def index(name: str, index_id: str = GATWICK):
    """Push one local file into the GATWICK index and wait for it to be searchable."""
    path = VIDEO_DIR / pathlib.Path(name).name
    if not path.exists():
        yield {"error": f"no such file: {path}"}
        return
    size = round(path.stat().st_size / 1e6, 1)
    # Check the floor here rather than discovering it in a 400 after the upload has
    # already been paid for. TwelveLabs wants >=360 on both axes.
    w, h = dims(path)
    if w and min(w, h) < MIN_DIM:
        yield {"error": f"{w}x{h} is below TwelveLabs' {MIN_DIM}px floor — not uploaded. "
                        "Delete it and re-fetch, or pick a clip with a better source."}
        return
    yield {"stage": "index", "file": path.name, "size_mb": size, "index_id": index_id,
           "resolution": f"{w}x{h}" if w else None}

    hdr = {"x-api-key": _key("TWELVELABS_API_KEY")}
    # The corpus check upstream is a filesystem check, and it cannot see a file that
    # is on disk but already uploaded. Ask the index itself, so clicking the button
    # twice costs one upload rather than two and the graph gets one Source, not two.
    existing = httpx.get(f"{BASE}/indexes/{index_id}/videos", headers=hdr,
                         params={"page_limit": 50}, timeout=60.0).json().get("data", [])
    for v in existing:
        fn = ((v.get("user_metadata") or {}).get("filename")
              or (v.get("system_metadata") or {}).get("filename"))
        if fn == path.name:
            yield {"error": f"already in the index as {v['_id']} — not uploaded again"}
            return

    t0 = time.time()
    # The lane rides with the asset. load.py hardcodes observed anyway; this means the
    # index itself carries the claim rather than it being inferred from a filename.
    meta = json.dumps({"filename": path.name, "provenance_class": PROVENANCE,
                       "ingest_path": "search"})
    with httpx.Client(timeout=1800.0) as http:
        with open(path, "rb") as fh:
            r = http.post(f"{BASE}/tasks", headers=hdr,
                          data={"index_id": index_id, "user_metadata": meta},
                          files={"video_file": (path.name, fh, "video/mp4")})
        if r.status_code >= 300:
            yield {"error": f"upload HTTP {r.status_code}: {r.text[:200]}"}
            return
        task_id = r.json()["_id"]
        yield {"progress": {"pct": None, "note": f"uploaded {size}MB · task {task_id}"}}

        while True:
            time.sleep(5)
            t = http.get(f"{BASE}/tasks/{task_id}", headers=hdr).json()
            st, el = t.get("status"), round(time.time() - t0)
            if st == "ready":
                yield {"video_id": t["video_id"], "seconds": el, "task_id": task_id}
                return
            if st in ("failed", "error"):
                yield {"error": f"indexing {st}: {str(t)[:200]}"}
                return
            yield {"progress": {"pct": None, "note": f"{st} · {el}s"}}


def lane_guard():
    """The standing invariant, re-run after every ingest. Both must be 0."""
    import graph.db as db
    drv = db.driver()
    with drv.session() as s:
        reach = s.run("MATCH (:Covenant)-[:MEASURED_BY]->(co:Concept)<-[:CANDIDATE_FOR]-(seg:Segment) "
                      "RETURN count(seg) AS n").single()["n"]
        lane = s.run("MATCH (:Segment)-[:PART_OF]->(s:Source) "
                     "WHERE s.provenance_class <> 'observed' RETURN count(s) AS n").single()["n"]
    drv.close()
    return {"segments_reaching_a_covenant": reach, "non_observed_video_sources": lane}


NEXT = """
  make graph                         re-run concept-driven retrieval over the index
  .venv/bin/python -m graph.entities extract    entities and topics on the new segments
  .venv/bin/python -m graph.embed backfill      embed the new segments
"""


def run(query=None, url=None, index_id=GATWICK):
    """One generator for the CLI and the endpoint. A query lists candidates and stops;
    a url is a human's choice and runs fetch -> index."""
    if url:
        name = None
        for ev in fetch(url):
            if ev.get("error"):
                yield ev
                return
            if ev.get("fetched"):
                name = ev["fetched"]["file"]
            yield ev
        for ev in index(name, index_id):
            yield ev
            if ev.get("error"):
                return
            if ev.get("video_id"):
                yield {"done": {"file": name, "video_id": ev["video_id"],
                                "provenance_class": PROVENANCE, "next": NEXT.strip()}}
        return
    for ev in find(query):
        yield ev
    yield {"done": {"picked": None, "note": "a human picks. nothing was fetched."}}


def _print(ev):
    if "candidates" in ev:
        print(f"\n{len(ev['candidates'])} video candidate(s):")
        for c in ev["candidates"]:
            tag = ("HAVE" if c.get("have") else "----" if c.get("unavailable") else "NEW ")
            dur = f"{c['duration'] // 60}:{c['duration'] % 60:02d}" if c.get("duration") else "  — "
            print(f"  [{tag}] {dur:>6}  {(c.get('publisher') or '?')[:22]:24} {(c.get('title') or '')[:56]}")
            print(f"           {c['url']}")
            print(f"           {c['why']}")
        print(f"\nrejected {len(ev['rejected'])} non-video result(s):")
        for r in ev["rejected"][:10]:
            print(f"  {r['why']:46} {r['url'][:70]}")
    elif "done" in ev:
        d = ev["done"]
        print(f"\n{json.dumps(d, indent=2) if d.get('video_id') else d.get('note', '')}")
    elif "progress" in ev:
        p = ev["progress"]
        pct = "" if p["pct"] is None else f" {p['pct']}%"
        print(f"  {p['note']}{pct}")
    else:
        print("  " + json.dumps(ev))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    arg = sys.argv[2] if len(sys.argv) > 2 else ""
    if cmd in ("find", "dry") and arg:
        for ev in find(arg):
            _print(ev)
        if cmd == "dry":
            print("\nplan — nothing fetched, nothing spent:")
            print("  fetch <url>   ->  video/<id>__<Publisher>__<Title>.mp4  (<=480p)")
            print(f"  index <file>  ->  TwelveLabs {GATWICK}, provenance_class={PROVENANCE}")
            print(NEXT)
    elif cmd == "fetch" and arg:
        for ev in fetch(arg):
            _print(ev)
    elif cmd == "index" and arg:
        for ev in index(arg):
            _print(ev)
    elif cmd == "loop" and arg:
        cands = None
        for ev in find(arg):
            _print(ev)
            if "candidates" in ev:
                cands = [c for c in ev["candidates"] if not c.get("have") and not c.get("unavailable")]
        if not cands:
            sys.exit("\nno new video candidate — nothing to do.")
        top = cands[0]
        print(f"\ntop candidate: {top.get('publisher')} — {top.get('title')}\n  {top['url']}")
        if "--yes" not in sys.argv:
            sys.exit("\nA search result is not evidence about the deal. Look at it, then\n"
                     f"  python -m graph.ingest_video loop {arg!r} --yes\n"
                     "or fetch a different candidate by url.")
        for ev in run(url=top["url"]):
            _print(ev)
        try:
            print(f"\nlane guard: {json.dumps(lane_guard())}")
        except Exception as e:
            print(f"\nlane guard unavailable: {str(e)[:120]}")
    else:
        sys.exit(__doc__)
