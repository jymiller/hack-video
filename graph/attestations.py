"""Export and restore human decisions, so a rebuild cannot destroy them.

The graph is reproducible from scripts. Human attestations are not — they exist
only because somebody read the evidence and signed. Treating them as rebuildable
would be the same mistake as letting the model overwrite them.

Keyed on (event name, covenant code, evidence_sha256), so a restore reattaches to
the right edge even though Neo4j element ids change on every rebuild.

    python graph/attestations.py export   > attestations.json
    python graph/attestations.py restore  < attestations.json
"""
import json, sys
from neo4j import GraphDatabase

drv = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "hackvideo2026"))

EXPORT = """
MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant)
WHERE m.status <> 'proposed'
RETURN e.name AS event, c.covenant_code AS covenant,
       m.evidence_sha256 AS evidence_sha256, m.status AS status,
       m.validated_by AS validated_by, toString(m.validated_at) AS validated_at,
       m.evidence_url AS evidence_url,
       m.human_note AS human_note, m.previous_status AS previous_status,
       m.reopened AS reopened, m.could_affect AS could_affect,
       m.direction AS direction, m.rationale AS rationale, m.model AS model
ORDER BY event, covenant
"""

RESTORE = """
MATCH (e:Event {name:$event}), (c:Covenant {covenant_code:$covenant})
MERGE (e)-[m:MAY_AFFECT {evidence_sha256:$evidence_sha256}]->(c)
SET m.status=$status, m.validated_by=$validated_by,
    m.validated_at=datetime($validated_at), m.human_note=$human_note,
    m.previous_status=$previous_status, m.reopened=$reopened,
    m.evidence_url=$evidence_url,
    m.could_affect=$could_affect, m.direction=$direction,
    m.rationale=$rationale, m.model=$model, m.asserted_by='model',
    m.restored=true
RETURN m.status AS status
"""


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "export"
    with drv.session() as s:
        if cmd == "export":
            rows = s.run(EXPORT).data()
            json.dump(rows, sys.stdout, indent=1)
            print(f"\n{len(rows)} attestation(s) exported", file=sys.stderr)

        elif cmd == "restore":
            rows = json.load(sys.stdin)
            ok = skipped = 0
            for r in rows:
                # never clobber a decision made since the backup was taken
                cur = s.run("""MATCH (e:Event {name:$e})-[m:MAY_AFFECT {evidence_sha256:$h}]
                                     ->(c:Covenant {covenant_code:$c})
                               RETURN m.status AS status""",
                            e=r["event"], c=r["covenant"], h=r["evidence_sha256"]).single()
                if cur and cur["status"] != "proposed":
                    skipped += 1
                    continue
                res = s.run(RESTORE, **r).single()
                ok += 1 if res else 0
                if not res:
                    print(f"  ! no matching edge for {r['event'][:38]} / {r['covenant']}",
                          file=sys.stderr)
            print(f"{ok} restored, {skipped} left alone (already decided)", file=sys.stderr)

        else:
            sys.exit("usage: attestations.py [export|restore]")
    drv.close()


if __name__ == "__main__":
    main()
