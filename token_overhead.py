"""Compare the input tokens each model reports for identical requests.

  OPPER_API_KEY=... python3 token_overhead.py
"""
import json, os, urllib.request

URL = "https://api.opper.ai/v3/compat/v1/systemone"
KEY = os.environ["OPPER_API_KEY"]
MODELS = ["typesafe/jev-latest", "opper/kev-4b"]


def tokens(model, state, questions):
    req = urllib.request.Request(URL, data=json.dumps({"model": model, "state": state, "questions": questions}).encode(),
                                 method="POST", headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=150).read())["usage"]["input_tokens"]


def noul(text="Does the customer ask for a refund?"):
    return {"type": "noul", "instructions": text}


short = "Please refund my duplicate invoice payment"
more = " The order number is 1182 and I paid by card on Monday."
five = {f"q{i}": noul(f"Question number {i}: is this about billing?") for i in range(5)}
cases = [
    ("almost empty", "x", {"a": noul("x?")}),
    ("short message, 1 question", short, {"a": noul()}),
    ("short message, 5 questions", short, five),
    ("+10 sentences, 1 question", short + more * 10, {"a": noul()}),
    ("+40 sentences, 1 question", short + more * 40, {"a": noul()}),
    ("+40 sentences, 5 questions", short + more * 40, five),
    ("choice, 12 options", short, {"a": {"type": "choice", "instructions": "Which team?", "criteria": {f"team{i}": f"Team number {i}" for i in range(12)}}}),
]
print(f"{'request':30}" + "".join(f"{m:>22}" for m in MODELS))
for name, state, qs in cases:
    print(f"{name:30}" + "".join(f"{tokens(m, state, qs):>22}" for m in MODELS))
