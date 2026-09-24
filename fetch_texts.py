"""Rebuild fresh.jsonl (with texts) from fresh_manifest.jsonl.

The manifest ships only source URLs, questions and answers. This fetches each
item's text from its public source: the arXiv API, the Stack Exchange API and
the GitHub API (set GITHUB_TOKEN to avoid the 60 requests/hour anonymous limit).

  python3 fetch_texts.py            -> fresh.jsonl, ready for jev_vs_kev.py
"""
import html, json, os, re, time, urllib.request, xml.etree.ElementTree as ET


def strip(text, limit=1500):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def get(url, headers=None):
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=60).read()


def arxiv(url):
    aid = url.rsplit("/abs/", 1)[1]
    ns = {"a": "http://www.w3.org/2005/Atom"}
    e = ET.fromstring(get(f"https://export.arxiv.org/api/query?id_list={aid}")).find("a:entry", ns)
    time.sleep(3)
    return {"title": strip(e.find("a:title", ns).text), "abstract": strip(e.find("a:summary", ns).text)}


def stackexchange(url):
    site = url.split("//")[1].split(".stackexchange.com")[0].split(".com")[0]
    qid = url.split("/questions/")[1].split("/")[0]
    d = json.loads(get(f"https://api.stackexchange.com/2.3/questions/{qid}?site={site}&filter=withbody", {"Accept-Encoding": "identity"}))
    q = d["items"][0]
    time.sleep(1)
    return {"title": strip(q["title"]), "body": strip(q["body"])}


def github(url):
    owner, repo, _, num = url.split("github.com/")[1].split("/")[:4]
    h = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    i = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}/issues/{num}", h))
    return {"title": strip(i["title"]), "body": strip(i["body"])}


def main():
    fetch = {"arxiv": arxiv, "stackexchange": stackexchange, "github": github}
    with open("fresh.jsonl", "w") as out:
        for line in open("fresh_manifest.jsonl"):
            item = json.loads(line)
            try:
                state = fetch[item["source"]](item["source_url"])
            except Exception as e:
                print(f"skip {item['source_url']}: {e}")
                continue
            out.write(json.dumps({**item, "state": state}) + "\n")
    print("wrote fresh.jsonl")


if __name__ == "__main__":
    main()
