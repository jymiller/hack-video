"""Knowledge store over the existing TwelveLabs assets — the `responses` surface.

Separate from the GATWICK index, which powers /search and /analyze and carries the
demo. Nothing here is on the run-of-show path; this exists so the capability is
available if a judge asks for multi-turn Q&A over the corpus.

    python graph/knowledge_store.py build          create/reuse store, ingest assets
    python graph/knowledge_store.py status         per-item ingestion state
    python graph/knowledge_store.py ask "..."      one-shot question, streamed
"""
import os, sys, json, time, pathlib
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

load_dotenv(pathlib.Path(__file__).resolve().parent.parent / ".env")

NAME = os.environ.get("TL_STORE_NAME", "gatwick")
STATE = pathlib.Path(__file__).resolve().parent / "dump" / "knowledge-store.json"

client = TwelveLabs(api_key=os.environ["TWELVELABS_API_KEY"])


def store_id():
    for s in client.knowledge_stores.list():
        if s.name == NAME:
            return s.id
    return None


def build():
    sid = store_id()
    if sid:
        print(f"store: {sid} (reused)")
    else:
        sid = client.knowledge_stores.create(
            name=NAME,
            description="Gatwick corpus — same assets as the GATWICK index",
        ).id
        print(f"store: {sid} (created)")

    have = {i.asset_id for i in client.knowledge_store_items.list(sid)}
    assets = [a for a in client.assets.list(page_limit=50) if a.status == "ready"]
    todo = [a for a in assets if a.id not in have]
    print(f"assets: {len(assets)} ready, {len(have)} already in store, {len(todo)} to add")

    for a in todo:
        item = client.knowledge_store_items.create(knowledge_store_id=sid, asset_id=a.id)
        print(f"  + {item.id}  {a.filename[:52]}")

    t0 = time.time()
    while True:
        items = list(client.knowledge_store_items.list(sid))
        by = {}
        for i in items:
            by[i.status] = by.get(i.status, 0) + 1
        print(f"  [{time.time() - t0:6.1f}s] " + "  ".join(f"{k}={v}" for k, v in sorted(by.items())))
        if all(i.status in ("ready", "failed") for i in items):
            break
        time.sleep(15)

    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({
        "knowledge_store_id": sid,
        "name": NAME,
        "items": [{"item_id": i.id, "asset_id": i.asset_id, "status": i.status} for i in items],
    }, indent=2))
    print(f"\n{sid}  ->  {STATE}")


def status():
    sid = store_id()
    if not sid:
        sys.exit(f"no store named {NAME!r} — run: python graph/knowledge_store.py build")
    print(f"store: {sid}")
    for i in client.knowledge_store_items.list(sid):
        print(f"  {i.status:10} {i.id}  {i.asset_id}")


def ask(question):
    sid = store_id()
    if not sid:
        sys.exit(f"no store named {NAME!r} — run: python graph/knowledge_store.py build")
    # Not streamed on purpose. On some questions the model fans out a per-video analysis
    # and streams those deltas concurrently with the final answer, interleaving them into
    # unreadable text. It is intermittent and not reproducible on demand, so it cannot be
    # filtered with confidence. The one-shot call returns the final message only.
    resp = client.responses.create(
        knowledge_store_id=sid,
        input=[{"type": "message", "role": "user", "content": question}],
    )
    for out in resp.output:
        if out.type == "message":
            for part in out.content:
                print(part.text)
    print(f"\n[session {resp.session_id}]")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "build":
        build()
    elif cmd == "status":
        status()
    elif cmd == "ask":
        ask(sys.argv[2])
    else:
        sys.exit(__doc__)
