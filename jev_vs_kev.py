"""Jev vs Kev: the same System One request through Opper, only `model` changes.

Five public tasks, one question type each, N examples per task sampled with a
fixed seed from Hugging Face's datasets-server (no dependencies beyond the
standard library). Every example goes to every model through
POST https://api.opper.ai/v3/compat/v1/systemone.

  OPPER_API_KEY=... SUITE=heldout python3 jev_vs_kev.py [N] [model ...]

SUITE=seen (default): AG News, SST-2, Banking77, Yelp, BoolQ. Kev's training
mixture includes the train splits of these (and SST-5), so it has seen the tasks.
SUITE=fresh: text published after 2026-09-20 (arXiv, Stack Exchange, GitHub) that neither model can have seen.
Build fresh.jsonl with fetch_texts.py (from the published manifest) or build_fresh.py (a new sample).
SUITE=heldout: emotion, tweet_eval offensive, QNLI, PAWS, SciQ, which Kev's
manifest lists as eval-only (never trained on). Jev's training data is unpublished.

Writes results/<model>.jsonl (one line per call) and prints a summary table.
"""
import concurrent.futures as cf
import json
import math
import os
import random
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

URL = "https://api.opper.ai/v3/compat/v1/systemone"
KEY = os.environ["OPPER_API_KEY"]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 100
MODELS = sys.argv[2:] or ["typesafe/jev-latest", "opper/kev-4b"]
SEED = 7
SUITE = os.environ.get("SUITE", "seen")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results-" + SUITE)


def rows(dataset, split, config="default", n=N, pages=10):
    """n rows at random offsets (pages of n/pages), so label-sorted splits are not a problem."""
    q = lambda p: "https://datasets-server.huggingface.co/" + p
    size = json.load(urllib.request.urlopen(q("size?" + urllib.parse.urlencode({"dataset": dataset}))))
    total = next(s["num_rows"] for s in size["size"]["splits"] if s["split"] == split and s["config"] == config)
    rnd = random.Random(f"{SEED}:{dataset}")
    per = max(1, n // pages)
    out = []
    for off in sorted(rnd.sample(range(0, total - per), pages)):
        url = q("rows?" + urllib.parse.urlencode({"dataset": dataset, "config": config, "split": split, "offset": off, "length": per}))
        for attempt in range(5):
            try:
                out += [r["row"] for r in json.load(urllib.request.urlopen(url, timeout=60))["rows"]]
                break
            except urllib.error.HTTPError:
                time.sleep(2 * (attempt + 1))
    return out[:n]


def label_names(dataset, config=None):
    params = {"dataset": dataset, **({"config": config} if config else {})}
    info = json.load(urllib.request.urlopen("https://datasets-server.huggingface.co/info?" + urllib.parse.urlencode(params)))
    if config:
        return info["dataset_info"]["features"]["label"]["names"]
    feats = next(iter(info["dataset_info"].values()))["features"]
    return feats["label"]["names"]


def heldout_tasks():
    items = []
    emo = label_names("dair-ai/emotion", "split")
    for r in rows("dair-ai/emotion", "test", config="split"):
        items.append(("emotion (choice, 6)", r["text"],
                      {"type": "choice", "instructions": "Which emotion does the writer express?", "criteria": {e: None for e in emo}}, emo[r["label"]]))
    for r in rows("cardiffnlp/tweet_eval", "test", config="offensive"):
        items.append(("tweet offensive (noul)", r["text"], {"type": "noul", "instructions": "Is this tweet offensive?"}, r["label"] == 1))
    for r in rows("nyu-mll/glue", "validation", config="qnli"):
        items.append(("qnli (noul)", {"question": r["question"], "sentence": r["sentence"]},
                      {"type": "noul", "instructions": "Does the sentence contain the answer to the question?"}, r["label"] == 0))
    for r in rows("google-research-datasets/paws", "test", config="labeled_final"):
        items.append(("paws (noul)", {"sentence1": r["sentence1"], "sentence2": r["sentence2"]},
                      {"type": "noul", "instructions": "Do the two sentences mean the same thing?"}, r["label"] == 1))
    rnd = random.Random(SEED)
    for r in rows("allenai/sciq", "test"):
        opts = [r["correct_answer"], r["distractor1"], r["distractor2"], r["distractor3"]]
        rnd.shuffle(opts)
        keys = "abcd"
        items.append(("sciq (choice, 4)", {"passage": r["support"] or "(no passage)"},
                      {"type": "choice", "instructions": r["question"], "criteria": {keys[i]: o for i, o in enumerate(opts)}},
                      keys[opts.index(r["correct_answer"])]))
    return items


def fresh_tasks():
    """Built by fetch_texts.py or build_fresh.py: text published after 2026-09-20, labels from the source (arXiv, Stack Exchange, GitHub)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fresh.jsonl")
    return [(r["task"], r["state"], r["question"], r["gold"]) for r in map(json.loads, open(path))]


def tasks():
    if SUITE == "fresh":
        return fresh_tasks()
    if SUITE == "heldout":
        return heldout_tasks()
    """Each item: (task, state, question, gold). gold is a bool (noul), a key (choice) or a level index (score)."""
    items = []
    for r in rows("fancyzhx/ag_news", "test"):
        items.append(("ag_news (choice, 4)", r["text"],
                      {"type": "choice", "instructions": "What is the topic of this news article?",
                       "criteria": {"world": "World news and politics", "sports": "Sports", "business": "Business and economy", "scitech": "Science and technology"}},
                      ["world", "sports", "business", "scitech"][r["label"]]))
    for r in rows("stanfordnlp/sst2", "validation"):
        items.append(("sst2 (noul)", r["sentence"], {"type": "noul", "instructions": "Is the sentiment of this movie review positive?"}, r["label"] == 1))
    b77 = label_names("legacy-datasets/banking77")
    for r in rows("legacy-datasets/banking77", "test"):
        items.append(("banking77 (choice, 77)", r["text"],
                      {"type": "choice", "instructions": "Which banking intent does this customer message express?",
                       "criteria": {name: name.replace("_", " ") for name in b77}},
                      b77[r["label"]]))
    for r in rows("Yelp/yelp_review_full", "test", config="yelp_review_full"):
        items.append(("yelp (score, 5)", r["text"],
                      {"type": "score", "instructions": "How many stars did the reviewer give?", "criteria": ["1 star", "2 stars", "3 stars", "4 stars", "5 stars"]},
                      r["label"]))
    for r in rows("google/boolq", "validation"):
        items.append(("boolq (noul)", r["passage"], {"type": "noul", "instructions": r["question"].rstrip("?") + "?"}, bool(r["answer"])))
    return items


def call(model, state, question):
    body = json.dumps({"model": model, "state": state, "questions": {"q": question}}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    for attempt in range(4):
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                out = json.loads(r.read())
                return {"ok": True, "latency": time.time() - t, "cost": float(r.headers.get("X-Opper-Cost") or 0),
                        "answer": out["answers"]["q"], "input_tokens": out["usage"]["input_tokens"]}
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 529, 504) and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return {"ok": False, "latency": time.time() - t, "error": f"{e.code} {e.read().decode()[:120]}"}
        except Exception as e:  # network
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            return {"ok": False, "latency": time.time() - t, "error": str(e)[:120]}


def grade(question, gold, answer):
    """(correct, confidence in the chosen answer, probability given to the gold answer, abs level error)."""
    if question["type"] == "noul":
        p = answer["noul"]
        pred = p >= 0.5
        return pred == gold, max(p, 1 - p), p if gold else 1 - p, None
    if question["type"] == "choice":
        probs = answer["probabilities"]
        pred = max(probs, key=probs.get)
        return pred == gold, probs[pred], probs.get(gold, 0.0), None
    probs = {int(k): v for k, v in answer["probabilities"].items()}
    pred = max(probs, key=probs.get)
    return pred == gold, probs[pred], probs.get(gold, 0.0), abs(answer["score"] - gold)


def ece(conf, correct, bins=10):
    total, err = len(conf), 0.0
    for b in range(bins):
        idx = [i for i, c in enumerate(conf) if b / bins < c <= (b + 1) / bins or (b == 0 and c == 0)]
        if idx:
            err += len(idx) / total * abs(statistics.mean(conf[i] for i in idx) - statistics.mean(correct[i] for i in idx))
    return err


def main():
    os.makedirs(OUT, exist_ok=True)
    items = tasks()
    print(f"{len(items)} examples x {len(MODELS)} models")
    results = {}
    for model in MODELS:
        call(model, "warm-up", {"type": "noul", "instructions": "Is this a warm-up?"})  # absorb a cold start
        with cf.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(lambda it: call(model, it[1], it[2]), items))
        results[model] = res
        with open(os.path.join(OUT, model.replace("/", "_") + ".jsonl"), "w") as f:
            for it, r in zip(items, res):
                f.write(json.dumps({"task": it[0], "gold": it[3], **r}) + "\n")

    header = f"{'task':24} {'model':22} {'n':>4} {'acc':>6} {'ECE':>6} {'Brier*':>7} {'MAE':>5} {'p50 ms':>7} {'p95 ms':>7} {'$/1k calls':>10}"
    print("\n" + header + "\n" + "-" * len(header))
    for task in dict.fromkeys(t for t, *_ in items):
        for model in MODELS:
            sel = [(it, r) for it, r in zip(items, results[model]) if it[0] == task]
            ok = [(it, r) for it, r in sel if r["ok"]]
            graded = [grade(it[2], it[3], r["answer"]) for it, r in ok]
            if not graded:
                print(f"{task:24} {model:22} all {len(sel)} failed: {sel[0][1].get('error')}")
                continue
            correct = [int(g[0]) for g in graded]
            conf = [g[1] for g in graded]
            brier = statistics.mean((1 - g[2]) ** 2 for g in graded)
            maes = [g[3] for g in graded if g[3] is not None]
            lat = sorted(r["latency"] for _, r in ok)
            cost = statistics.mean(r["cost"] for _, r in ok) * 1000
            fails = len(sel) - len(ok)
            print(f"{task:24} {model:22} {len(ok):>4} {statistics.mean(correct):>6.3f} {ece(conf, correct):>6.3f} {brier:>7.3f} "
                  f"{(statistics.mean(maes) if maes else float('nan')):>5.2f} {lat[len(lat)//2]*1000:>7.0f} {lat[min(len(lat)-1, math.ceil(len(lat)*.95)-1)]*1000:>7.0f} {cost:>10.4f}"
                  + (f"  ({fails} failed)" if fails else ""))
    print("\nacc: top answer correct (noul at 0.5). ECE: calibration error of the top answer's probability (10 bins).")
    print("Brier*: (1 - p(gold))^2, lower is better. MAE: score tasks, |expected level - gold level|.")
    print("Latency is end to end through Opper from this machine, 8 concurrent requests per model.")


if __name__ == "__main__":
    main()
