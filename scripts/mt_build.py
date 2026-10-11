#!/usr/bin/env python3
"""Convert the downloaded legislation.mt PDFs into the LawCodex Markdown tree.

  en/constitution/constitution-of-malta.md
  en/chapters/cap-016-civil-code.md
  en/subsidiary/cap-016/sl-016-01-<slug>.md
  mt/... (same layout, Maltese text, Maltese slugs)

Usage: mt_build.py [--repo PATH] [--langs en,mt] [--kinds const,cap,sl,other] [--workers 4]
"""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pdf2md  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
RAW = os.environ.get("MT_RAW", os.path.join(REPO, "..", "_raw", "mt"))
LANGS = {"en": "eng", "mt": "mlt"}
TODAY = os.environ.get("MT_RETRIEVED", datetime.date.today().isoformat())


def slugify(t, maxlen=70):
    t = t.replace("ħ", "h").replace("Ħ", "h").replace("ġ", "g").replace("Ġ", "g").replace("ż", "z").replace("Ż", "z") \
        .replace("ċ", "c").replace("Ċ", "c").replace("&", " and ")
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t.lower()).strip("-")
    if len(t) > maxlen:
        t = t[:maxlen].rsplit("-", 1)[0]
    return t or "untitled"


def eli_base(url):
    return re.sub(r"/(eng|mlt)/portalpdf$", "", url.strip("/"))


def key_of(base):
    return base.replace("eli/", "").replace("/", "_")


def load_meta(base):
    p = os.path.join(RAW, "meta", key_of(base) + ".json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p))
    out = {"titles": {}}
    b = "eli/" + base.split("eli/", 1)[1]
    for about, prop, _, val in d["triples"]:
        if about == b and prop == "eli:first_date_entry_in_force":
            out["first"] = val
        elif about == b and prop == "eli:date_publication":
            out["pub"] = val
        elif about == b and prop == "eli:has_member":
            out["version"] = val.replace("mlt:", "")
        elif prop == "eli:title":
            lang = about.rsplit("/", 1)[-1]
            out["titles"][lang] = val
    return out


def yq(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def num_pad(n):
    # '16' -> '016', '3A' -> '003a', '16.1' -> '016-01', 'Const.1' -> 'const-01'
    m = re.match(r"^(\d+)([A-Za-z]*)$", n)
    if m:
        return f"{int(m.group(1)):03d}{m.group(2).lower()}"
    m = re.match(r"^([A-Za-z]*\.?)(\d*)([A-Za-z]*)\.(\d+)([A-Za-z]*)$", n)
    if m:
        pre = m.group(1).rstrip(".").lower()
        mid = f"{int(m.group(2)):03d}" if m.group(2) else ""
        head = "-".join(x for x in (pre, mid + m.group(3).lower()) if x)
        return f"{head}-{int(m.group(4)):02d}{m.group(5).lower()}"
    return slugify(n)


def plan():
    cat = json.load(open(os.path.join(RAW, "catalog.json")))
    docs = []
    for x in cat:
        base = eli_base(x["url"])
        label = x["label"]
        repealed = "(R)" in label or bool(re.search(r"\b(Repealed|Imħassar|Imħassra|Revoked)\b", x.get("note", "")))
        kind = base.split("/")[1]
        num = base.split("/")[2] if kind == "cap" else ""
        if kind == "const":
            parent_dir = "constitution"
            d = {"kind": "const", "type": "constitution", "dir": "constitution", "fname": {"en": "constitution-of-malta", "mt": "kostituzzjoni-ta-malta"},
                 "identifier": "Constitution of Malta"}
        elif kind == "cap":
            parent_dir = f"cap-{num_pad(num)}"
            typ = "code" if re.search(r"\bCode\b", x["title"]) else "act"
            d = {"kind": "cap", "type": typ, "dir": "chapters",
                 "fname": {"en": f"cap-{num_pad(num)}-{slugify(x['title'])}", "mt": f"kap-{num_pad(num)}-{slugify(x.get('title_mt') or x['title'])}"},
                 "identifier": re.sub(r"\s*\(R\)\s*$", "", label).strip()}
        else:
            parent_dir = "other"
            d = {"kind": "other", "type": "act", "dir": "other",
                 "fname": {"en": slugify(x["title"]), "mt": slugify(x.get("title_mt") or x["title"])},
                 "identifier": label}
        d.update({"base": base, "label": label, "title": {"en": x["title"], "mt": x.get("title_mt") or ""},
                  "note": {"en": x.get("note", ""), "mt": x.get("note_mt", "")}, "repealed": repealed})
        docs.append(d)
        for c in x["children"]:
            cb = eli_base(c["url"])
            n = cb.split("/", 2)[2]
            crep = "(R)" in c["label"] or bool(re.search(r"\b(Repealed|Imħassar|Imħassrin|Imħassra|Revoked|Revokati)\b", c.get("note", "")))
            docs.append({"kind": "sl", "type": "subsidiary_legislation", "dir": f"subsidiary/{parent_dir}",
                         "fname": {"en": f"sl-{num_pad(n)}-{slugify(c['title'])}", "mt": f"ls-{num_pad(n)}-{slugify(c.get('title_mt') or c['title'])}"},
                         "identifier": re.sub(r"\s*\(R\)\s*$", "", c["label"]).strip() or f"S.L. {n}", "base": cb, "label": c["label"],
                         "title": {"en": c["title"], "mt": c.get("title_mt") or ""},
                         "note": {"en": c.get("note", ""), "mt": c.get("note_mt", "")}, "repealed": crep,
                         "parent": d["identifier"]})
    return docs


def build_one(args):
    d, lang, repo = args
    pdf = os.path.join(RAW, "pdf", f"{key_of(d['base'])}_{LANGS[lang]}.pdf")
    if not os.path.exists(pdf):
        return (d["base"], lang, "missing")
    out_dir = os.path.join(repo, lang, d["dir"])
    out = os.path.join(out_dir, d["fname"][lang] + ".md")
    meta = load_meta(d["base"])
    title = d["title"][lang] or meta.get("titles", {}).get(LANGS[lang], "") or d["title"]["en"]
    try:
        body = pdf2md.convert(pdf)
    except Exception as e:  # noqa
        return (d["base"], lang, f"error {e}")
    if len(body.strip()) < 20:
        return (d["base"], lang, "empty")
    version = meta.get("version", "")
    vdate = ""
    m = re.search(r"/(\d{8})$", version)
    if m:
        vdate = f"{m.group(1)[:4]}-{m.group(1)[4:6]}-{m.group(1)[6:]}"
    fm = ["---", f"title: {yq(title)}", f"identifier: {yq(d['identifier'])}",
          f"eli: {yq('https://legislation.mt/' + d['base'])}", f"type: {d['type']}", "jurisdiction: mt",
          f"language: {lang}"]
    if d.get("parent"):
        fm.append(f"parent: {yq(d['parent'])}")
    if meta.get("first"):
        fm.append(f"date: {meta['first']}")
    if vdate or meta.get("pub"):
        fm.append(f"last_amended: {vdate or meta['pub']}")
    fm.append(f"status: {'repealed' if d['repealed'] else 'in_force'}")
    if d["note"][lang]:
        fm.append(f"status_note: {yq(d['note'][lang])}")
    fm.append(f"source: {yq('https://legislation.mt/' + d['base'] + '/' + LANGS[lang] + '/pdf')}")
    if version:
        fm.append(f"version: {yq('https://legislation.mt/' + version + '/' + LANGS[lang])}")
    fm.append(f"retrieved: {TODAY}")
    fm.append("---")
    h1 = f"# {title}" if d["kind"] in ("const", "other") else f"# {title} ({d['identifier']})"
    text = "\n".join(fm) + "\n\n" + h1 + "\n\n" + body
    os.makedirs(out_dir, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return (d["base"], lang, "ok", os.path.relpath(out, repo), len(text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--langs", default="en,mt")
    ap.add_argument("--kinds", default="const,cap,sl,other")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    docs = [d for d in plan() if d["kind"] in a.kinds.split(",")]
    # disambiguate duplicate filenames
    seen = {}
    for d in docs:
        for lang in ("en", "mt"):
            k = (lang, d["dir"], d["fname"][lang])
            if k in seen:
                d["fname"][lang] += "-" + slugify(d["base"].split("/", 2)[2])
            seen[k] = 1
    jobs = [(d, l, a.repo) for d in docs for l in a.langs.split(",")]
    results = []
    with ProcessPoolExecutor(a.workers) as ex:
        for i, r in enumerate(ex.map(build_one, jobs, chunksize=4)):
            results.append(r)
            if r[2] != "ok":
                print(r, flush=True)
            if (i + 1) % 200 == 0:
                print("built", i + 1, "/", len(jobs), flush=True)
    log = os.path.join(RAW, f"build-{'-'.join(a.kinds.split(','))}-{'-'.join(a.langs.split(','))}.json")
    json.dump(results, open(log, "w"), ensure_ascii=False, indent=0)
    ok = sum(1 for r in results if r[2] == "ok")
    print("ok", ok, "of", len(results))


if __name__ == "__main__":
    main()
