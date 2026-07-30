# Neo4j Aura: local graph → a database Render can reach

Render cannot see `bolt://localhost:7687`. This is the path from the local `hackgraph`
container to a managed instance the deployed app talks to, and the checks that prove the
graph arrived intact — the embeddings especially, because those fail quietly.

Researched against Neo4j's live docs on 30 July 2026. Sources at the bottom.

---

## The make-or-break question: vector indexes on the free tier

**Yes. AuraDB Free runs vector indexes.** `search_moments` keeps working.

Vector indexing is not an edition-gated feature at all: "Vector indexes are available in both
Neo4j Enterprise Edition and Community Edition" ([Cypher Manual → Vector
indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)),
and Neo4j's own pricing comparison lists **Vector indexing: Included** for self-managed
Community. Aura Free runs the same database. The June 2026 Aura database release, which shipped
new vector index options, is tagged for AuraDB Free alongside the paid tiers on the
[Aura changelog](https://neo4j-aura.canny.io/changelog).

Do not confuse this with **Vector Optimization**, which the pricing page marks *Not Included*
for Free. That is a memory-reservation toggle that carves page cache out for the vector index,
[available only on instances larger than
4GB](https://neo4j.com/docs/aura/managing-instances/vector-optimization/) — i.e. paid tiers.
It is a throughput setting for millions of vectors. We have 58 vectors of 512 dimensions,
about a quarter of a megabyte. It buys us nothing.

If it were ever needed, the cheapest tier that has it is **AuraDB Professional at $65/GB/month,
minimum 1GB, so $65.70/month for a 2GB instance** — and vector optimization only switches on
above 4GB, i.e. $131.40/month. We do not need to spend that.

`CREATE VECTOR INDEX` and `db.create.setNodeVectorProperty` are both available and both
exercised by `graph/aura.py push`. `db.index.vector.queryNodes` — what `search_moments` calls —
still works, but is **deprecated as of Neo4j 2026.04** in favour of the Cypher `SEARCH` clause.
Aura runs 2026.x, so expect a deprecation warning in the logs. It is a warning, not an error;
verified returning identical rows and identical scores on a 2026.06 server.

## Free tier limits, and the one that can ruin a demo

| | AuraDB Free |
|---|---|
| Graph size | **50,000 nodes / 175,000 relationships** |
| Our graph | ~171 nodes / ~399 relationships — 0.3% of the cap |
| Instances | one per account, GCP only |
| Backups | **none** |
| Auto-pause | **after 72 hours of inactivity**, automatic, cannot be triggered manually |
| Resume | one click in the console; takes minutes |
| If left paused | Free instances do **not** auto-resume; after **30 days paused, Aura deletes the instance and the data** |

Two things follow.

**The demo risk is the pause, not the size.** A paused instance refuses connections outright —
"any applications or users trying to connect won't be able to run queries." If the instance
naps overnight before a demo, the app comes up and every graph call fails. Resume takes minutes,
not seconds. So: **touch the database within 72 hours of the demo, and check the console is
green before you present.** `python -m graph.aura verify` is the cheapest possible touch — it
reads counts and runs one vector query, which resets the inactivity clock.

**There are no backups on Free, so the local graph is the backup.** `push` is idempotent, so
recovery from a deleted or reset instance is just running it again. The one thing that is not
rebuildable is the human attestations — `status`, `validated_by`, `validated_at` on `MAY_AFFECT`
— and `push` carries those verbatim, byte for byte. `plan` prints every one of them before
writing so you can see what is about to move.

---

## Signup to connected

1. **Create the account.** <https://console.neo4j.io> → sign up. No credit card.
2. **Create the instance.** *New Instance* → **AuraDB Free**. Name it `hackvideo`.
   Leave Graph Analytics on the default. The Vector optimization toggle is not offered on
   Free — that is expected, see above.
3. **Save the credentials.** A panel shows the generated password exactly once and offers a
   `.txt` download. **Download it.** It is not recoverable; losing it means cloning the
   instance to get new credentials. The file contains:

   ```
   NEO4J_URI=neo4j+s://a1b2c3d4.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=<generated>
   ```

   `neo4j+s://` is TLS Bolt with full certificate validation — Aura's default and what you
   want. (Aura also serves `https://` for the Query API if a firewall blocks the Bolt port;
   the Python driver does not need it.)
4. **Wait for the instance to go green** — a minute or two.
5. **Dry run, locally, changing nothing:**

   ```sh
   .venv/bin/python -m graph.aura plan
   ```

   This needs no Aura credentials at all. It reads the live local graph and prints every
   statement it would run, the per-label node counts, which properties are temporal, and every
   human-signed edge.
6. **Push.** Paste the three values from the downloaded file into `AURA_*` — deliberately
   *not* `NEO4J_*`, so a push can never be aimed at the wrong database by an env var the app
   already set:

   ```sh
   AURA_URI=neo4j+s://a1b2c3d4.databases.neo4j.io \
   AURA_USER=neo4j \
   AURA_PASSWORD=<generated> \
     .venv/bin/python -m graph.aura push
   ```

   Constraints and indexes first, then nodes, then the embeddings through
   `db.create.setNodeVectorProperty`, then relationships, then the vector index, then
   `db.awaitIndexes`. It ends by running `verify` itself.
7. **Read the verify table.** Every line must say `ok`. It exits non-zero if any does not:

   ```
   ok  nodes                  local 171          remote 171
   ok  relationships          local 399          remote 399
   ok  embedded segments      local 58           remote 58
   ok  attestation edges      local 5            remote 5
   ok  Event.date type        local ['DATE NOT NULL']  remote ['DATE NOT NULL']
   ok  vector index           segment_embedding ONLINE 100.0
   ok  queryNodes reach       local 58/58        remote 58/58
   ```

   The last line is the one that matters most. See below.
8. **Sanity check in the console.** Aura → *Query*, and run:

   ```cypher
   MATCH (e:Event)-[m:MAY_AFFECT]->(c:Covenant) WHERE m.validated_by IS NOT NULL
   RETURN e.name, c.covenant_code, m.status, m.validated_by, m.validated_at
   ```

   Those five rows are the signed human decisions. If they are there, the migration kept the
   only thing in the graph that could not be rebuilt.

## Render environment variables

`render.yaml` already declares these three with `sync: false`, so the Blueprint prompts for them
at creation and the values live in the dashboard, never in git. See `DEPLOY.md` for the deploy
itself. To set them by hand: Render dashboard → the service → **Environment** → *Add
Environment Variable*. The app reads `NEO4J_*` (`server.py:410`, `graph/db.py`):

| Key | Value |
|---|---|
| `NEO4J_URI` | `neo4j+s://a1b2c3d4.databases.neo4j.io` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | the generated password |

Alongside the keys the app already needs: `TWELVELABS_API_KEY`, `OPENAI_API_KEY`, `YDC_API_KEY`.

Save, let Render redeploy, then hit the app and ask something that goes through
`search_moments`. `neo4j+s://` needs no extra TLS configuration and no allow-list — Aura Free
accepts connections from anywhere, so Render's egress IPs are not a problem.

Set `AURA_*` only in your own shell, never in Render. Render never pushes; it only reads.

---

## Why `verify` checks "queryNodes reach"

Counts matching is not proof the search works.

A vector whose length does not match the index dimensionality is **accepted on write and then
dropped from the index with no error**. Measured on both Neo4j 5.26 and 2026.06: a 511-element
vector is accepted by a plain `SET` *and* by `db.create.setNodeVectorProperty` (the procedure
rejects non-finite components, but does not check length against the index). The property is
there. `SHOW VECTOR INDEXES` says `ONLINE`, `100.0`. The node count is right. And
`search_moments` silently never returns that segment again.

So `verify` asks the index what it can actually reach: it queries for as many neighbours as
there are stored vectors and counts what comes back. `58/58` is the assertion. Anything less
prints:

```
BAD queryNodes reach       local 58/58    remote 57/58
    ! silent exclusion — vectors are stored but not indexed, search under-returns
```

This was tested by deliberately corrupting one vector on a target: every other check still said
`ok`, and only this one caught it. Re-running `push` repaired it.

## Rehearsing without touching Aura

`push` was developed and proved against a throwaway container running **the same Neo4j
generation Aura runs (2026.06)**, not the local 5.26:

```sh
docker run -d --name aura-scratch -p 7690:7687 -e NEO4J_AUTH=neo4j/scratchpass2026 neo4j:2026.06
AURA_URI=bolt://localhost:7690 AURA_USER=neo4j AURA_PASSWORD=scratchpass2026 \
  .venv/bin/python -m graph.aura push
docker rm -f aura-scratch
```

**Check `docker info | grep "Total Memory"` before you do this.** The Docker VM on this machine
is 1.9 GiB, and a second Neo4j alongside the ones already running was enough for the kernel to
OOM-kill `hackgraph` mid-test (`docker inspect hackgraph --format '{{.State.OOMKilled}}'` →
`true`). It restarted clean with nothing lost, but stop the other containers first, or raise the
VM's memory in Docker Desktop, or just skip the rehearsal and push straight to a real Free
instance — that is what `plan` and `verify` are for.

The only untested difference against real Aura is the transport — `neo4j+s://` and TLS instead
of plain `bolt://`.

## Notes

- **Dates never become strings.** `push` goes driver to driver; `Event.date` crosses Bolt as a
  `neo4j.time.Date` and lands as a `DATE`. `verify` asserts `valueType(e.date)` matches on both
  sides, so a regression to `STRING` — which would make every date comparison quietly stop
  matching — fails the check rather than surviving to the demo.
- **`push` is re-runnable.** Node identity is a hash of the natural key the schema constraints
  already name (`Source.id`, `Segment.(video_id, start)`, …), not an `elementId`, so a push
  after the local graph is rebuilt updates the same remote nodes instead of doubling them.
  Relationship identity includes `evidence_sha256`, because there really are several distinct
  `MAY_AFFECT` edges between the same Event and Covenant, one per piece of evidence, and
  collapsing them would destroy separate human decisions.
- **The `_mig` property is left behind on purpose.** It is the join key that makes a re-push an
  update rather than a duplicate. Same for the `Migrated` label and its index.
- **`push` expects an empty instance, or one it pushed before.** If the target already holds
  nodes loaded some other way (`graph/migrate.py`, an import), the merge finds no `_mig` to
  match and the unique constraints reject the second copy. That is the loud failure, and it is
  the one you want; *Reset to blank* in the Aura console and push again.
- **`Observation` and `Fact` have no unique constraint**, so they are keyed on their whole
  property map. If their text changes locally, a re-push adds the new version and leaves the
  old one behind. Everything else keys on a real natural key and updates in place.
- **The vector index is rebuilt, not replayed.** The local `createStatement` carries
  `vector.quantization.enabled`, which Neo4j deprecated in 2026.06 and which has a known bug
  there. `push` emits a clean `CREATE VECTOR INDEX` with only `vector.dimensions` and
  `vector.similarity_function` and lets the server pick current defaults.
- **Aura Free defaults to a newer Cypher.** Aura's per-instance default is Cypher 5; a fresh
  2026.06 database defaults to Cypher 25. Everything here was verified working under Cypher 25,
  including the deprecated `db.index.vector.queryNodes` the agent still calls.

## Sources

- [AuraDB Free FAQ — 50,000 nodes / 175,000 relationships, no backups, 3-day pause](https://neo4j.com/free-graph-database/)
- [Aura → Instance actions — 72-hour auto-pause, no manual pause on Free, deleted after 30 days paused](https://neo4j.com/docs/aura/managing-instances/instance-actions/)
- [Aura → Connect to an instance — `neo4j+s://` default, `https://` fallback, credentials file](https://neo4j.com/docs/aura/getting-started/connect-instance/)
- [Aura → Create an instance — one Free instance per account](https://neo4j.com/docs/aura/getting-started/create-instance/)
- [Aura → Vector optimization — >4GB instances only](https://neo4j.com/docs/aura/managing-instances/vector-optimization/)
- [Cypher Manual → Vector indexes — Enterprise *and* Community; `queryNodes` deprecated 2026.04](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)
- [Neo4j pricing — Free $0 with Vector Optimization not included; Professional $65/GB/month](https://neo4j.com/pricing/)
- [Aura changelog — June 2026 database release incl. vector features, tagged AuraDB Free](https://neo4j-aura.canny.io/changelog)
