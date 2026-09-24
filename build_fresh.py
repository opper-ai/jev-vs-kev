"""Build a frozen 'fresh' eval set from text published after both models were built.

Every item was created on or after CUTOFF (2026-09-20: after Jev 1.13 shipped on
2026-09-15 and after Kev-4B's release), so neither model, nor their base models,
can have trained on it. Ground truth comes from the source itself, not from a
model: arXiv's primary category, the Stack Exchange site a question was asked
on, and the label a GitHub maintainer put on an issue.

  python3 build_fresh.py        -> fresh.jsonl (task, state, question, gold, source_url, created)
"""
import html
import json
import os
import random
import re
import subprocess
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CUTOFF = "2026-09-20"
PER_CLASS = 20
SEED = 11
HERE = os.path.dirname(os.path.abspath(__file__))
rnd = random.Random(SEED)


def strip(text, limit=1500):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def arxiv():
    cats = {"cs.CL": "Computation and language (NLP)", "cs.CV": "Computer vision", "cs.CR": "Cryptography and security",
            "astro-ph.GA": "Astrophysics of galaxies", "cond-mat.mtrl-sci": "Materials science",
            "math.AP": "Analysis of PDEs", "quant-ph": "Quantum physics", "stat.ME": "Statistics methodology"}
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    items = []
    for cat in cats:
        url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": f"cat:{cat}", "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 120})
        root = ET.fromstring(urllib.request.urlopen(url, timeout=60).read())
        got = []
        for e in root.findall("a:entry", ns):
            primary = e.find("x:primary_category", ns).get("term")
            published = e.find("a:published", ns).text[:10]
            if primary != cat or published < CUTOFF:
                continue
            got.append({"task": "arxiv category (choice, 8)",
                        "state": {"title": strip(e.find("a:title", ns).text), "abstract": strip(e.find("a:summary", ns).text)},
                        "question": {"type": "choice", "instructions": "Which arXiv category is this paper's primary subject?", "criteria": cats},
                        "gold": cat, "source_url": e.find("a:id", ns).text, "created": published})
        rnd.shuffle(got)
        items += got[:PER_CLASS]
        print(f"arxiv {cat}: {len(got)} after cutoff, kept {min(len(got), PER_CLASS)}")
        time.sleep(3)  # arXiv asks for 3 s between calls
    return items


def stackexchange():
    # Stack Exchange traffic is thin in 2026; these six had 20+ questions since the cutoff.
    sites = {"math": "Mathematics", "physics": "Physics", "askubuntu": "Ask Ubuntu (Ubuntu Linux)", "superuser": "Super User (general computing)",
             "electronics": "Electrical engineering and electronics", "diy": "Home improvement (DIY)"}
    import calendar
    from_ts = calendar.timegm(time.strptime(CUTOFF, "%Y-%m-%d"))
    items = []
    for site in sites:
        url = "https://api.stackexchange.com/2.3/questions?" + urllib.parse.urlencode(
            {"site": site, "fromdate": from_ts, "pagesize": 100, "order": "desc", "sort": "creation", "filter": "withbody"})
        req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        got = [{"task": "stackexchange site (choice, 6)",
                "state": {"title": strip(q["title"]), "body": strip(q["body"])},
                "question": {"type": "choice", "instructions": "Which Q&A community was this question posted on?", "criteria": sites},
                "gold": site, "source_url": q["link"], "created": time.strftime("%Y-%m-%d", time.gmtime(q["creation_date"]))}
               for q in data.get("items", [])]
        rnd.shuffle(got)
        items += got[:PER_CLASS]
        print(f"stackexchange {site}: {len(got)} after cutoff, kept {min(len(got), PER_CLASS)}")
        time.sleep(1)
    return items


def github():
    """Issues labelled by maintainers as a bug or a feature request, opened after the cutoff, from large repos that
    label consistently. Fresh feature labels are scarce, so bugs are sampled down to the same count."""
    bug = [("microsoft/vscode", "bug"), ("godotengine/godot", "bug"), ("rust-lang/rust", "C-bug"), ("microsoft/terminal", "Issue-Bug"), ("ollama/ollama", "bug")]
    feat = [("microsoft/vscode", "feature-request"), ("godotengine/godot-proposals", None), ("microsoft/terminal", "Issue-Feature"),
            ("ollama/ollama", "feature request"), ("flutter/flutter", "c: new feature")]

    def fetch(pairs, is_bug):
        got = {}
        for repo, label in pairs:
            cmd = ["gh", "search", "issues", "--repo", repo, "--created", f">={CUTOFF}", "--limit", "100", "--json", "title,body,url,createdAt,labels"]
            if label:
                cmd += ["--label", label]
            for i in json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout or "[]"):
                names = {l["name"].lower() for l in i["labels"]}
                mixed = any("bug" in n for n in names) and any("feature" in n or "enhancement" in n for n in names)
                if mixed or len(strip(i["body"], 5000)) < 80:
                    continue
                got[i["url"]] = {"task": "github bug report (noul)",
                                 "state": {"title": strip(i["title"]), "body": strip(i["body"])},
                                 "question": {"type": "noul", "instructions": "Is this issue a bug report (as opposed to a feature request)?"},
                                 "gold": is_bug, "source_url": i["url"], "created": i["createdAt"][:10]}
            time.sleep(2)
        return list(got.values())

    bugs, feats = fetch(bug, True), fetch(feat, False)
    rnd.shuffle(bugs)
    n = min(len(bugs), len(feats))
    print(f"github: {len(bugs)} bugs, {len(feats)} feature requests after cutoff, kept {n} of each")
    return bugs[:n] + feats[:n]


def main():
    items = arxiv() + stackexchange() + github()
    path = os.path.join(HERE, "fresh.jsonl")
    with open(path, "w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    print(f"{len(items)} items -> {path}")


if __name__ == "__main__":
    main()
