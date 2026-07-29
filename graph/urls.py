"""Give every Source a fully-qualified URL and its sha256.

Identity of a source is its URL. Seen-ness is a hash comparison — nothing
fuzzier. If the hash is known we have processed it; if not, we have not.
"""
import hashlib, re
from neo4j import GraphDatabase

drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))

YT = re.compile(r"^([A-Za-z0-9_-]{11})__")


def canonical(filename: str) -> str | None:
    """Our corpus filenames start with the YouTube id. Canonical form is the
    watch URL — no playlist params, no timestamps, no tracking."""
    m = YT.match(filename or "")
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else None


def sha(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()


with drv.session() as s:
    rows = s.run("MATCH (n:Source) RETURN n.id AS id, n.filename AS fn, n.url AS url").data()
    done = missing = 0
    for r in rows:
        url = r["url"] or canonical(r["fn"] or "")
        if not url:
            missing += 1
            print(f"  ! no canonical url for {r['fn'] or r['id']}")
            continue
        s.run("MATCH (n:Source {id:$id}) SET n.url=$u, n.url_sha256=$h",
              id=r["id"], u=url, h=sha(url))
        done += 1
    print(f"{done} sources hashed, {missing} without a url")

    print("\n=== source identity ===")
    for r in s.run("""MATCH (n:Source)
                      RETURN n.publisher AS publisher, n.url AS url,
                             left(n.url_sha256,12) AS hash ORDER BY n.publisher""").data():
        print(f"  {r['publisher'][:22]:24} {r['hash']}  {r['url']}")

    dupes = s.run("""MATCH (n:Source) WHERE n.url_sha256 IS NOT NULL
                     WITH n.url_sha256 AS h, collect(n.publisher) AS who
                     WHERE size(who) > 1 RETURN h, who""").data()
    print(f"\n{len(dupes)} duplicate url(s)" + (" — same source ingested twice" if dupes else ""))

    # An Event with no Source is an assertion about nothing. Say so.
    orphans = s.run("""MATCH (e:Event) WHERE NOT (e)<-[:REPORTS]-(:Source)
                       RETURN e.name AS name, toString(e.date) AS date""").data()
    if orphans:
        print(f"\n{len(orphans)} event(s) with NO source in the graph:")
        for o in orphans:
            print(f"  · {o['date']}  {o['name']}")

drv.close()
