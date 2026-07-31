"""Create or update the Render service for the submission artifact. Idempotent.

    python render_deploy.py                      # create/update, no graph
    NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io \
    NEO4J_PASSWORD=... python render_deploy.py   # ...and wire the graph

Two things must be true first, and neither can be automated:

  1. `hack-video` is in Render's GitHub App repository selection.
     https://github.com/settings/installations -> Render -> Repository access.
     The repo is private, which is fine — hackathon-prep and outside-llms are too
     and both deploy. It just is not in the list yet.

  2. A Neo4j Aura instance exists, if you want the graph pages to work.
     https://console.neo4j.io -> free instance. Then populate it FROM THE LAPTOP:
       NEO4J_URI=... NEO4J_USER=neo4j NEO4J_PASSWORD=... make restore
     load.py reads the TwelveLabs cloud index, so this needs no local media and no
     graph importer. Without step 2 the service still deploys: pages, search and
     video work, graph endpoints 500.

Media presigned URLs are regenerated on every run — they are valid for 7 days, which
is the SigV4 maximum, so re-running this is how you renew them.
"""
import json, os, pathlib, sys
import boto3
import httpx
from botocore.config import Config
from dotenv import dotenv_values

ROOT = pathlib.Path(__file__).resolve().parent
OWNER = "tea-d9him5vlk1mc73e2bm3g"          # John's workspace
REPO = "https://github.com/jymiller/hack-video"
BUCKET = "hack-video-gatwick-media"
NAME = "hack-video"

hy = dotenv_values(pathlib.Path.home() / "Downloads/source/hack-you/.env")
tl = dotenv_values(ROOT / ".env")
region = hy.get("AWS_REGION") or "us-west-2"
H = {"Authorization": f"Bearer {hy['RENDER_API_KEY']}", "Accept": "application/json",
     "Content-Type": "application/json"}


def presign() -> str:
    """Fresh 7-day URLs, signed against the REGIONAL endpoint — the global host
    answers with a 307 of its own, which costs a hop and can break the signature."""
    s3 = boto3.client(
        "s3", aws_access_key_id=hy["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=hy["AWS_SECRET_ACCESS_KEY"], region_name=region,
        endpoint_url=f"https://s3.{region}.amazonaws.com",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}))
    out = {}
    for o in s3.list_objects_v2(Bucket=BUCKET).get("Contents", []):
        d = s3.head_object(Bucket=BUCKET, Key=o["Key"]).get("Metadata", {}).get("duration", "")
        out[o["Key"]] = {
            "url": s3.generate_presigned_url("get_object",
                    Params={"Bucket": BUCKET, "Key": o["Key"]}, ExpiresIn=604800),
            "size_mb": round(o["Size"] / 1e6, 1),
            "duration": int(d) if d.isdigit() else None,
        }
    print(f"  media      {len(out)} presigned urls, 7-day expiry")
    return json.dumps(out, separators=(",", ":"))


def env_vars() -> list:
    v = [{"key": "PYTHON_VERSION", "value": "3.12.12"},
         {"key": "PUBLIC_READONLY", "value": "1"},
         {"key": "TWELVELABS_API_KEY", "value": tl["TWELVELABS_API_KEY"]},
         {"key": "YDC_API_KEY", "value": hy["YDC_API_KEY"]},
         {"key": "MEDIA_URLS", "value": presign()}]
    uri = os.environ.get("NEO4J_URI")
    if uri:
        v += [{"key": "NEO4J_URI", "value": uri},
              {"key": "NEO4J_USER", "value": os.environ.get("NEO4J_USER", "neo4j")},
              {"key": "NEO4J_PASSWORD", "value": os.environ["NEO4J_PASSWORD"]}]
        print(f"  graph      {uri}")
    else:
        print("  graph      NOT SET — graph endpoints will 500 until NEO4J_URI is given")
    return v


def find() -> dict | None:
    r = httpx.get("https://api.render.com/v1/services?limit=50", headers=H, timeout=60.0)
    r.raise_for_status()
    for item in r.json():
        s = item.get("service", item)
        if s.get("name") == NAME:
            return s
    return None


def main():
    vars_ = env_vars()
    existing = find()

    if existing:
        sid = existing["id"]
        r = httpx.put(f"https://api.render.com/v1/services/{sid}/env-vars",
                      headers=H, json=vars_, timeout=120.0)
        print(f"  env vars   HTTP {r.status_code} ({len(vars_)} set)")
        r = httpx.post(f"https://api.render.com/v1/services/{sid}/deploys",
                       headers=H, json={"clearCache": "do_not_clear"}, timeout=120.0)
        print(f"  deploy     HTTP {r.status_code}")
        url = existing.get("serviceDetails", {}).get("url")
    else:
        payload = {
            "type": "web_service", "name": NAME, "ownerId": OWNER,
            "repo": REPO, "branch": "main", "autoDeploy": "yes",
            "serviceDetails": {
                "env": "python", "plan": "free", "region": "oregon",
                "healthCheckPath": "/",
                "envSpecificDetails": {
                    "buildCommand": "pip install -r requirements.txt",
                    "startCommand": "uvicorn server:app --host 0.0.0.0 --port $PORT",
                },
            },
            "envVars": vars_,
        }
        r = httpx.post("https://api.render.com/v1/services", headers=H,
                       json=payload, timeout=120.0)
        if r.status_code not in (200, 201):
            msg = r.json().get("message", r.text[:300])
            print(f"  create     HTTP {r.status_code}: {msg}")
            if "unfetchable" in msg:
                print("\n  ^ Render cannot read the repo. Add hack-video at")
                print("    https://github.com/settings/installations -> Render")
            sys.exit(1)
        svc = r.json().get("service", r.json())
        print(f"  created    {svc.get('id')}")
        url = svc.get("serviceDetails", {}).get("url")

    print(f"\n  URL        {url or '(check the dashboard)'}")
    print("  Free-tier instances sleep when idle; first hit after that takes ~50s.")


if __name__ == "__main__":
    main()
