import asyncio
import json
import os
import sys
from pathlib import Path

import httpx2
from dotenv import load_dotenv
from pydantic import BaseModel

from agent import make_llm

load_dotenv()

REPO = "encode/httpx"
LABELS = ["bug", "enhancement", "question"]
DATA = Path(__file__).with_name("eval_data.json")
PER_LABEL = 18


class Label(BaseModel):
    label: str


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


PROMPT = (
    "You label GitHub issues. Reply with exactly one of: bug, enhancement, question.\n"
    "bug = something is broken. enhancement = a new feature or improvement. question = asking for help or clarification."
)


async def score(model: str):
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    llm = make_llm(model).with_structured_output(Label)
    correct, confusion = 0, {}
    for r in rows:
        try:
            pred = (await llm.ainvoke([("system", PROMPT), ("user", f"Title: {r['title']}\n\n{r['body']}")])).label.lower()
        except Exception as e:
            pred = f"error:{str(e)[:30]}"
        hit = pred == r["gold"]
        correct += hit
        confusion[(r["gold"], pred)] = confusion.get((r["gold"], pred), 0) + 1
    print(f"model={model}  accuracy={correct}/{len(rows)} = {correct / len(rows):.0%}")
    per_label = {}
    for lab in LABELS:
        tot = sum(r["gold"] == lab for r in rows)
        right = confusion.get((lab, lab), 0)
        per_label[lab] = [right, tot]
        print(f"  {lab}: {right}/{tot}")
    out = Path(__file__).parent / "results" / "eval.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "model": model, "repo": REPO, "total": len(rows), "correct": correct,
        "accuracy": round(correct / len(rows), 2), "per_label": per_label,
    }, indent=1), encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch()
    else:
        asyncio.run(score(sys.argv[1] if len(sys.argv) > 1 else "llama3.2"))
