"""Model bake-off on a task where we know the right answer.

Four events, four covenant judgements each. The ground truth:
  - DCO granted            -> no covenant effect (consent changes no cash or debt)
  - Court ruling           -> no covenant effect (removes a risk, moves no number)
  - Bond supplement        -> AFFECTS both (more senior debt: ICR down, RAR up)
  - Water supply failure   -> no covenant effect (cost is immaterial)

The water outage is the trap. deepseek-v4-flash fell for it.
"""
import os, json, time, pathlib, sys
import httpx
from dotenv import load_dotenv

root = pathlib.Path(__file__).resolve().parent.parent
load_dotenv(root / ".env")
load_dotenv(pathlib.Path.home() / "Downloads/source/hack-you/.env")
KEY = os.environ["NOVITA_API_KEY"]
URL = "https://api.novita.ai/v3/openai/chat/completions"
http = httpx.Client(timeout=240.0)

MODELS = ["deepseek/deepseek-v4-flash", "zai-org/glm-5.2", "moonshotai/kimi-k3",
          "minimax/minimax-m3", "deepseek/deepseek-v4-pro"]

TRUTH = {
    ("dco", "senior_icr"): False, ("dco", "senior_rar"): False,
    ("court", "senior_icr"): False, ("court", "senior_rar"): False,
    ("bond", "senior_icr"): True,  ("bond", "senior_rar"): True,
    ("water", "senior_icr"): False, ("water", "senior_rar"): False,
}
EVENTS = [
    ("dco",   "Northern Runway development consent granted", "regulatory_approval", "2025-09-21"),
    ("court", "High Court dismisses runway challenge",       "legal_challenge",     "2026-06-23"),
    ("bond",  "Bond programme supplementary prospectus",     "financing_event",     "2026-02-10"),
    ("water", "Airport water supply failure",                "operational_incident","2026-07-26"),
]
PROMPT = """You are assessing whether a news event could affect a debt covenant.

EVENT: {ev} (kind: {kind}, date: {date})

COVENANTS:
- senior_icr (Senior interest cover ratio, must stay above a floor)
- senior_rar (Senior debt ratio, must stay below a ceiling)

For EACH covenant decide whether this event could plausibly affect it.
Be sceptical. Most news events affect no covenant at all. An event only affects
a covenant if it moves the actual numbers the ratio is computed from.

JSON only:
{{"assessments":[{{"covenant_code":"senior_icr","could_affect":true|false,"rationale":"one sentence"}},
                 {{"covenant_code":"senior_rar","could_affect":true|false,"rationale":"one sentence"}}]}}"""

SCHEMA = {"type":"object","additionalProperties":False,"properties":{"assessments":{"type":"array","items":{
    "type":"object","additionalProperties":False,
    "properties":{"covenant_code":{"type":"string"},"could_affect":{"type":"boolean"},
                  "rationale":{"type":"string"}},
    "required":["covenant_code","could_affect","rationale"]}}},"required":["assessments"]}


def parse(text):
    """Models wrap JSON in markdown fences, or prose. Dig it out."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```")[1]
        if t.lstrip().lower().startswith("json"):
            t = t.lstrip()[4:]
    t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        i, j = t.find("{"), t.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(t[i:j + 1])
            except json.JSONDecodeError:
                pass
    return None


def call(model, prompt, use_schema):
    body = {"model": model, "messages":[{"role":"user","content":prompt}],
            "max_tokens": 3000, "temperature": 0.1}
    body["response_format"] = ({"type":"json_schema",
                                "json_schema":{"name":"a","strict":True,"schema":SCHEMA}}
                               if use_schema else {"type":"json_object"})
    t0 = time.time()
    r = http.post(URL, headers={"Authorization": f"Bearer {KEY}"}, json=body)
    dt = time.time() - t0
    if r.status_code != 200:
        return None, dt, f"HTTP {r.status_code}"
    m = r.json()["choices"][0]["message"]
    # some models return nothing in `content` and put it all in `reasoning_content`
    c = (m.get("content") or "").strip() or (m.get("reasoning_content") or "").strip()
    if not c:
        return None, dt, "empty content"
    d = parse(c)
    if d is None:
        return None, dt, "unparseable"
    return d.get("assessments", []), dt, None


print(f"{'model':30} {'schema':7} {'score':7} {'water trap':11} {'secs':6}")
print("-" * 68)
results = []
for model in MODELS:
    # does it support strict json_schema?
    probe = http.post(URL, headers={"Authorization": f"Bearer {KEY}"},
        json={"model":model,"messages":[{"role":"user","content":"x"}],"max_tokens":20,
              "response_format":{"type":"json_schema",
                                 "json_schema":{"name":"a","strict":True,
                                                "schema":{"type":"object","properties":{"a":{"type":"string"}},
                                                          "required":["a"],"additionalProperties":False}}}})
    # trust the status code — providers word the rejection differently
    # ("does not support" vs "is not supported"), so never string-match it
    has_schema = probe.status_code == 200

    right = total = 0
    water_ok = "—"
    secs = 0.0
    for key, name, kind, date in EVENTS:
        out, dt, err = call(model, PROMPT.format(ev=name, kind=kind, date=date), has_schema)
        secs += dt
        if out is None:
            total += 2
            continue
        for a in out:
            cc = a.get("covenant_code")
            if (key, cc) not in TRUTH:
                continue
            total += 1
            got = bool(a.get("could_affect"))
            if got == TRUTH[(key, cc)]:
                right += 1
            if key == "water" and cc == "senior_icr":
                water_ok = "PASS" if not got else "fell for it"
    pct = f"{right}/{total}"
    print(f"{model:30} {'yes' if has_schema else 'no':7} {pct:7} {water_ok:11} {secs:5.1f}")
    results.append((model, right, total, water_ok, secs, has_schema))

print()
best = max(results, key=lambda r: (r[1]/max(r[2],1), -r[4]))
print(f"best: {best[0]}  ({best[1]}/{best[2]} correct, {best[4]:.1f}s, "
      f"json_schema={'yes' if best[5] else 'no'})")
