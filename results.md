# Results (2026-09-24)

Both models were called through `POST https://api.opper.ai/v3/compat/v1/systemone` with identical requests, one question per request. Only `model` differed: `typesafe/jev-latest` or `opper/kev-4b`.

## Fresh data (headline)

362 items published after 2026-09-20. See `fresh_manifest.jsonl`.

| Task | n | Jev accuracy | Kev accuracy | Jev calibration error | Kev calibration error | Jev Brier | Kev Brier | Jev $ per 1k calls | Kev $ per 1k calls |
|---|---|---|---|---|---|---|---|---|---|
| arXiv category (8 options) | 160 | 96.9% | 95.0% | 0.032 | 0.043 | 0.025 | 0.045 | 0.030 | 0.015 |
| Stack Exchange site (6 options) | 120 | 97.5% | 98.3% | 0.027 | 0.125 | 0.021 | 0.036 | 0.026 | 0.012 |
| GitHub bug or feature (yes/no) | 82 | 95.1% | 93.9% | 0.049 | 0.138 | 0.037 | 0.051 | 0.025 | 0.013 |

## Older public datasets (secondary)

Kev did not train on these, but its authors used them to choose between training runs.

| Task | n | Jev accuracy | Kev accuracy | Jev calibration error | Kev calibration error |
|---|---|---|---|---|---|
| emotion (6 options) | 160 | 52.5% | 56.2% | 0.319 | 0.099 |
| tweet_eval offensive (yes/no) | 200 | 75.0% | 80.0% | 0.077 | 0.054 |
| QNLI (yes/no) | 200 | 95.5% | 92.0% | 0.042 | 0.055 |
| PAWS paraphrase (yes/no) | 200 | 87.0% | 74.5% | 0.044 | 0.164 |
| SciQ (4 options) | 200 | 100.0% | 98.5% | 0.003 | 0.044 |

## Input tokens reported for identical requests

From `token_overhead.py`. Both models list at USD 0.042 per million input tokens, output free.

| Request | Jev | Kev |
|---|---|---|
| Almost empty | 269 | 12 |
| Short message, 1 question | 280 | 23 |
| Short message, 5 questions | 350 | 97 |
| +10 sentences, 1 question | 450 | 193 |
| +40 sentences, 1 question | 960 | 703 |
| +40 sentences, 5 questions | 1,030 | 777 |
| Choice, 12 options | 481 | 124 |

## Definitions

- Accuracy: top answer matches the ground truth (yes/no at 0.5).
- Calibration error: expected calibration error of the top answer's probability, 10 bins. Lower is better.
- Brier: mean of (1 - probability given to the correct answer)^2. Lower is better.
- $ per 1k calls: mean of the per-call cost Opper returns, times 1,000, at list price.
- With 80 to 200 items per task, differences under about 5 points are within noise.
