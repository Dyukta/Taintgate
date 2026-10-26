import asyncio
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import httpx2
from dotenv import load_dotenv

from agent import triage

load_dotenv()

REPO = "encode/httpx"
# The meaning is shown to the agent; iterating the dict gives just the names.
LABELS = {
    "bug": "something is broken or behaves wrongly",
    "enhancement": "a request for a new feature or a change in behavior",
    "question": "asking how to do something or how it works",
}
DATA = Path(__file__).with_name("eval_data.json")
PER_LABEL = 18


def _headers():
    return {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}", "Accept": "application/vnd.github+json"}


def fetch():
    rows, seen = [], set()
    for lab in LABELS:
        r = httpx2.get(
            "https://api.github.com/search/issues",
            params={"q": f"repo:{REPO} is:issue label:{lab}", "per_page": 30, "sort": "created"},
            headers=_headers(),
        )
        for i in r.json()["items"]:
            gold = [l["name"] for l in i["labels"] if l["name"] in LABELS]
            if len(gold) == 1 and i["number"] not in seen and (i["body"] or "").strip():
                seen.add(i["number"])
                rows.append({"number": i["number"], "title": i["title"], "body": i["body"][:2000], "gold": gold[0]})
    balanced = []
    for lab in LABELS:
        balanced += [r for r in rows if r["gold"] == lab][:PER_LABEL]
    DATA.write_text(json.dumps(balanced, indent=1), encoding="utf-8")
    print(f"froze {len(balanced)} issues to {DATA.name}:", {l: sum(r['gold'] == l for r in balanced) for l in LABELS})


async def predict(r, model: str, taint: bool, defended: bool) -> dict:
    row = {"number": r["number"], "gold": r["gold"]}
    try:
        run = await triage(os.environ["SANDBOX_REPO"], r["number"], model, inject=(r["title"], r["body"]),
                           taint=taint, prompt="realistic", labels=LABELS, defended=defended)
    except Exception as e:
        return row | {"pred": "error", "error": str(e)[:120]}
    picked = [label.lower() for label in run.triage.labels] if run.triage else []
    post_error = next((c.result[:160] for c in run.tool_calls if c.tool == "post_comment" and c.blocked), None)
    return row | {
        "pred": next((label for label in picked if label in LABELS), "none" if run.triage else "no-output"),
        "looped": run.looped,
        "triage_error": run.error,
        "post_failed": post_error is not None,
        "post_error": post_error,
    }


async def score(model: str, taint: bool, defended: bool):
    suffix = ("-taint" if taint else "") + ("" if defended else "-nolock")
    out = Path(__file__).parent / "results" / f"eval-{re.sub(r'[^\w.-]', '_', model)}{suffix}.json"
    done = []
    for r in json.loads(DATA.read_text(encoding="utf-8")):
        done.append(await predict(r, model, taint, defended))
        print(json.dumps(done[-1]), flush=True)
        out.write_text(json.dumps({
            "model": model, "source": REPO, "agent": f"realistic prompt, repo binding {'on' if defended else 'off'}", "taint": taint,
            "date": date.today().isoformat(), "total": len(done),
            "correct": sum(d["pred"] == d["gold"] for d in done),
            "per_label": {lab: [sum(d["pred"] == d["gold"] == lab for d in done), sum(d["gold"] == lab for d in done)]
                          for lab in LABELS},
            "no_output": sum(d["pred"] in ("no-output", "error") for d in done),
            "post_failed": sum(d.get("post_failed", False) for d in done),
            "post_invalid_args": sum("validation error" in (d.get("post_error") or "") for d in done),
            "rows": done,
        }, indent=1), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch()
    else:
        asyncio.run(score(sys.argv[1], "taint" in sys.argv[2:], "nolock" not in sys.argv[2:]))
