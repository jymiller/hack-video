"""The demo's voice. Local, offline, no key, no vendor.

Novita's OpenAI-compatible endpoint carries 143 models and none of them do
audio, so the voice cannot come from there. macOS `say` is better for this
anyway: it needs no network, which is the desk's standing requirement that the
moment must play with no wifi.

THE TRAP, REPRODUCED: `say -v Serena` exits 0 and writes a perfectly valid
file — of the WRONG VOICE, because Serena is not installed. Byte-identical to
the default. Exactly the failure the desk's notes describe for cloud TTS
("a bad voice id returns HTTP 200 and produces nothing, or the wrong voice"),
and invisible unless you hash the output. So this script refuses to synthesise
with a voice it has not first found in the installed list.

    python graph/voice.py                 # render the demo lines
    python graph/voice.py --voice Daniel  # pick a voice
    python graph/voice.py --list          # what is actually installed
"""
import argparse, hashlib, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "audio"

# The narration. Short lines — the moment lands in the first fifteen seconds,
# and a long sentence cannot be re-cued if the room laughs or a demo stalls.
LINES = {
    "01-open": "Gatwick is building a second runway. Two point two billion pounds, "
               "privately financed. Every broadcaster ran it.",
    "02-corroborate": "Five broadcasters. Three of them, independently, say fourteen "
                      "thousand jobs.",
    "03-the-question": "The bonds are tested on two covenants. Senior interest cover, "
                       "and senior debt ratio. So: which of this reaches them?",
    "04-the-zero": "Nothing. Ninety-six links between video and concept, across five "
                   "broadcasters. Zero reach a covenant.",
    "05-the-model": "The model was asked whether the water outage threatened interest "
                    "cover. It said yes. A human said no, and the no is what stands.",
    "06-close": "The useful answer was a column of zeros. That is what it looks like "
                "when a system declines to guess.",
}


def installed_voices() -> dict[str, str]:
    out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
    voices = {}
    for line in out.splitlines():
        m = re.match(r"^(\S+)\s+([a-z]{2}_[A-Z]{2})", line)
        if m:
            voices[m.group(1)] = m.group(2)
    return voices


def render(name: str, text: str, voice: str) -> dict:
    OUT.mkdir(exist_ok=True)
    aiff = OUT / f"{name}.aiff"
    subprocess.run(["say", "-v", voice, "-o", str(aiff), text], check=True)
    data = aiff.read_bytes()
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(aiff)], capture_output=True, text=True).stdout.strip()
    return {"file": aiff.name, "bytes": len(data), "seconds": float(dur or 0),
            "sha256": hashlib.sha256(data).hexdigest()[:12]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="Daniel")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    voices = installed_voices()
    if a.list:
        for v, loc in sorted(voices.items()):
            if loc.startswith("en"):
                print(f"  {v:16} {loc}")
        return

    # Refuse before spending anything. `say` will not tell you.
    if a.voice not in voices:
        print(f"VOICE NOT INSTALLED: {a.voice!r}")
        print("`say` would exit 0 and hand you the default voice instead — silently.")
        print("Installed English voices:")
        for v, loc in sorted(voices.items()):
            if loc.startswith("en"):
                print(f"  {v} ({loc})")
        sys.exit(1)

    print(f"voice: {a.voice} ({voices[a.voice]})\n")
    seen, total = {}, 0.0
    for name, text in LINES.items():
        r = render(name, text, a.voice)
        total += r["seconds"]
        dupe = seen.get(r["sha256"])
        seen[r["sha256"]] = name
        flag = f"  !! byte-identical to {dupe} — synthesis is not varying" if dupe else ""
        print(f"  {r['file']:22} {r['seconds']:5.1f}s  {r['bytes']:>7} b  "
              f"{r['sha256']}{flag}")

    print(f"\n{len(LINES)} lines, {total:.1f}s of narration total")
    if len(seen) != len(LINES):
        print("FAIL: duplicate audio detected — something is not rendering")
        sys.exit(1)
    print("PASS: every line rendered, distinct, and plays with no network")


if __name__ == "__main__":
    main()
