#!/usr/bin/env python3
"""Build the catalogue of Maltese legislation (Constitution, Chapters, Subsidiary Legislation)
from legislation.mt's "Laws of Malta" listing (the same AJAX endpoints its web UI uses).

Output: _raw/mt/catalog.json
"""
import json, os, re, sys, time
import requests
from bs4 import BeautifulSoup

BASE = "https://legislation.mt"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
RAW = os.environ.get("MT_RAW", os.path.join(os.path.dirname(__file__), "..", "..", "_raw", "mt"))


def session(culture):
    s = requests.Session()
    s.headers["User-Agent"] = UA
    r = s.post(BASE + "/Multilingual/SetCulture", data={"culture": culture}, timeout=60)
    r.raise_for_status()
    return s


def post(s, path, data):
    for i in range(6):
        try:
            r = s.post(BASE + path, data=data, timeout=400)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa
            print("retry", path, e, file=sys.stderr)
            time.sleep(5 * (i + 1))
    raise RuntimeError(path)


def clean(t):
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    parts = [re.sub(r"\s+", " ", p).strip() for p in t.split("\n")]
    return [p for p in parts if p]


def listing(culture):
    s = session(culture)
    rows, start, total = [], 0, None
    while total is None or start < total:
        d = post(s, "/Legislations/LegislationPartial", {
            "draw": 1, "start": start, "length": 50, "order[0][column]": 1, "order[0][dir]": "asc",
            "search[value]": "", "search[regex]": "false", "search[ChapterString]": "", "search[TitleString]": ""})
        total = d["recordsFiltered"]
        rows += d["data"]
        start += 50
        print(culture, len(rows), "/", total, file=sys.stderr)
    out = []
    for row in rows:
        title = clean(row["ChapterTitle"])
        item = {"id": row["ID"], "label": row["ChapterText"].strip(), "title": title[0] if title else "",
                "note": " ".join(title[1:]), "url": row["URL"], "children": []}
        if row["HasChildren"]:
            c = post(s, "/Legislations/GetChapterChild", {"chapterPK": row["ID"]})
            soup = BeautifulSoup(c["data"], "lxml")
            for tr in soup.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                t = clean(tds[1].decode_contents())
                item["children"].append({"label": tds[0].get_text(" ", strip=True), "title": t[0] if t else "",
                                         "note": " ".join(t[1:]), "url": tr.get("pdflink")})
            time.sleep(0.3)
            print(culture, "children", row["ChapterText"], len(item["children"]), file=sys.stderr)
        out.append(item)
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    en = listing("en-GB")
    mt = listing("mt-MT")
    mt_by_id = {x["id"]: x for x in mt}
    for x in en:
        m = mt_by_id.get(x["id"])
        x["title_mt"] = m["title"] if m else ""
        x["note_mt"] = m["note"] if m else ""
        mc = {re.sub(r"/(eng|mlt)/", "/", c["url"]): c for c in (m["children"] if m else [])}
        for c in x["children"]:
            mm = mc.get(re.sub(r"/(eng|mlt)/", "/", c["url"]))
            c["title_mt"] = mm["title"] if mm else ""
            c["note_mt"] = mm["note"] if mm else ""
    with open(os.path.join(RAW, "catalog.json"), "w") as f:
        json.dump(en, f, ensure_ascii=False, indent=1)
    print(len(en), "chapters,", sum(len(x["children"]) for x in en), "subsidiary")


if __name__ == "__main__":
    main()
