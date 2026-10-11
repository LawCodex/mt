#!/usr/bin/env python3
"""Download ELI metadata and the official PDFs (English + Maltese) for every item of the
catalogue built by mt_catalog.py.

  _raw/mt/meta/<key>.json    ELI RDFa metadata scraped from https://legislation.mt/eli/<path>/eng/portalpdf
  _raw/mt/pdf/<key>_<lang>.pdf

Re-runnable: existing files are skipped. Usage: mt_fetch.py [--only-chapters] [--langs eng,mlt]
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = "https://legislation.mt/"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
RAW = os.environ.get("MT_RAW", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_raw", "mt"))
_tl = threading.local()


def sess():
    s = getattr(_tl, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        s.headers["Accept-Encoding"] = "gzip, deflate"
        _tl.s = s
    return s


def get(url, binary=False):
    for i in range(6):
        try:
            r = sess().get(url, timeout=300)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except Exception as e:  # noqa
            print("retry", url, e, file=sys.stderr, flush=True)
            time.sleep(10 * (i + 1))
    return None


def eli_base(url):
    # 'eli/cap/16/eng/portalpdf' -> 'eli/cap/16'
    return re.sub(r"/(eng|mlt)/portalpdf$", "", url.strip("/"))


def key_of(base):
    return base.replace("eli/", "").replace("/", "_")


META_RE = re.compile(r'<meta about="mlt:([^"]+)"\s+property="([^"]+)"\s+(content|resource)="([^"]*)"')


def fetch_meta(base):
    path = os.path.join(RAW, "meta", key_of(base) + ".json")
    if os.path.exists(path):
        return
    r = get(BASE + base + "/eng/portalpdf")
    if r is None:
        print("META FAIL", base, flush=True)
        return
    triples = [list(m) for m in META_RE.findall(r.text)]
    with open(path, "w") as f:
        json.dump({"base": base, "triples": triples}, f, ensure_ascii=False)


def fetch_pdf(base, lang):
    path = os.path.join(RAW, "pdf", f"{key_of(base)}_{lang}.pdf")
    miss = path + ".missing"
    if os.path.exists(path) or os.path.exists(miss):
        return
    r = get(BASE + base + f"/{lang}/pdf")
    if r is None or not r.content.startswith(b"%PDF"):
        open(miss, "w").write(str(r.status_code if r is not None else "fail"))
        print("PDF MISSING", base, lang, flush=True)
        return
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(r.content)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-chapters", action="store_true")
    ap.add_argument("--langs", default="eng,mlt")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(os.path.join(RAW, "meta"), exist_ok=True)
    os.makedirs(os.path.join(RAW, "pdf"), exist_ok=True)
    cat = json.load(open(os.path.join(RAW, "catalog.json")))
    bases = []
    for x in cat:
        bases.append(eli_base(x["url"]))
    if not a.only_chapters:
        for x in cat:
            for c in x["children"]:
                bases.append(eli_base(c["url"]))
    langs = a.langs.split(",")
    jobs = []
    for b in bases:
        jobs.append((fetch_meta, (b,)))
        for l in langs:
            jobs.append((fetch_pdf, (b, l)))
    done = [0]
    lock = threading.Lock()

    def run(j):
        j[0](*j[1])
        with lock:
            done[0] += 1
            if done[0] % 100 == 0:
                print("done", done[0], "/", len(jobs), flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(run, jobs))
    print("finished", len(jobs), flush=True)


if __name__ == "__main__":
    main()
