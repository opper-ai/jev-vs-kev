# Jev vs Kev

Code and data for the Opper blog post [Is there an open-source alternative to Jev? We tested Kev](https://opper.ai/blog/jev-vs-kev-open-decision-model)

We asked TypeSafe's [Jev](https://docs.typesafe.ai/models) and [Kev 4B](https://huggingface.co/jaredpalmer/kev-4b), an open reproduction, the same typed questions through the same API endpoint. The headline test set is 362 items published after both models were released, with answers taken from the source itself.

## Files

| File | What it is |
|---|---|
| `fresh_manifest.jsonl` | The 362 test items: source URL, date, the question asked and the correct answer. Texts are not included; fetch them with `fetch_texts.py`. |
| `fetch_texts.py` | Downloads each item's text from arXiv, Stack Exchange and GitHub into `fresh.jsonl`. |
| `build_fresh.py` | Builds a new sample the same way (newest items after a cutoff date), if you want your own set. |
| `jev_vs_kev.py` | The benchmark. Sends every item to each model and prints accuracy, calibration, Brier, latency and cost. |
| `token_overhead.py` | Compares the input tokens each model reports for identical requests. |
| `results.md` | Our results. |

## Run it

You need an [Opper](https://opper.ai) API key. Standard library Python 3.10+ only.

```bash
export OPPER_API_KEY=...
python3 fetch_texts.py                     # builds fresh.jsonl from the manifest
SUITE=fresh python3 jev_vs_kev.py          # both models on the fresh set
SUITE=heldout python3 jev_vs_kev.py 200    # older public datasets (secondary)
python3 token_overhead.py
```

`build_fresh.py` uses the GitHub CLI (`gh`) for issue search. Items can change or disappear at the source, so a rebuilt set may differ slightly from ours.

## Caveats

- One run per suite, a few hundred items. Differences under about 5 points are within noise.
- The fresh tasks are fairly easy for both models, which compresses the differences.
- Kev has trained on similar kinds of tasks, even though it never saw these items. Jev's training data is not published.
- Latency depends on where you call from.

## License

Code: Apache-2.0. The manifest lists public URLs and labels; the texts belong to their authors and are not redistributed here.
