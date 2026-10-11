#!/usr/bin/env python3
"""Convert a legislation.mt consolidated-law PDF (Laws of Malta layout) into Markdown body text.

The PDFs are typeset with a main text column and a marginal-note column (on the outer margin,
alternating sides between odd and even pages). Marginal notes carry the article headings
("Title.", "Interpretation.") and amendment history ("Amended by: ..."). We use poppler's
`pdftotext -bbox-layout` word geometry to:

  * drop running headers ("CIVIL CODE  [CAP. 16.  9");
  * separate the main column from marginal notes;
  * rebuild paragraphs from justified lines;
  * detect structural headings (BOOK / PART / TITLE / CHAPTER / SCHEDULE ... and the Maltese
    equivalents) and articles ("12A. (1) ...");
  * attach marginal notes to the paragraph they sit next to (article title -> heading text,
    amendment notes -> italic line).

Tables and complex layouts are flattened to text lines.
"""
import html
import re
import statistics
import subprocess

LINE_RE = re.compile(r'<line xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</line>', re.S)
WORD_RE = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', re.S)
PAGE_RE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)

HDR_BRACKET = re.compile(r'\[\s*(CAP|KAP|S\s*\.\s*L|L\s*\.\s*S|SL|LS)\b|\[\s*(CAP|KAP)\.', re.I)
TOC_START = re.compile(r'^(ARRANGEMENT\b|ARRANĠAMENT\b|TAQSIM TA|TABLE OF CONTENTS|WERREJ\b|INDIĊI\b|INDEX\b)', re.I)

KEYWORDS = [
    ("schedule", re.compile(r'^((FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH|[A-Z]+TH)\s+)?SCHEDULE\b|^SCHEDULE\b|^(L-|IS-|IT-|ID-|IR-|IN-|IĊ-|IX-|IŻ-|IL-)?(EWWEL|TIENI|TIELET|RABA|ĦAMES|SITT|SEBA|TMIEN|DISA|GĦAXAR)?\s*SKEDA\b|^SKEDA\b|^(ANNEX|ANNESS|APPENDIX|APPENDIĊI)\b', re.I)),
    ("book", re.compile(r'^(BOOK|KTIEB|IL-KTIEB)\b|^\S+\s+KTIEB\b', re.I)),
    ("part", re.compile(r'^(PART|PARTI|TAQSIMA|IT-TAQSIMA)\b|^\S+\s+(PART|PARTI|TAQSIMA)$', re.I)),
    ("title", re.compile(r'^(TITLE|TITOLU|IT-TITOLU)\b', re.I)),
    ("subtitle", re.compile(r'^(SUB-?\s?TITLE|SUB-?\s?TITOLU)\b', re.I)),
    ("chapter", re.compile(r'^(CHAPTER|KAPITOLU|IL-KAPITOLU)\b(?!\s+\d+\s*$)', re.I)),
    ("section", re.compile(r'^(§|SECTION|SUB-?PART|SUBPART|SUB-?TAQSIMA)', re.I)),
]

ARTICLE_RE = re.compile(r'^(?:[*†]+\s*)?(\d{1,4}[A-Z]{0,3}(?:\.\d+)?)\.(\s+(?![a-z])|(?=\())(.*)$', re.S)
NOTE_SPLIT = re.compile(r'^(Amended|Substituted|Added|Renumbered|Repealed|Deleted|Inserted|Revoked|Replaced|'
                        r'Emendat|Emendati|Emendata|Sostitwit|Sostitwita|Sostitwiti|Miżjud|Miżjuda|Miżjudin|Mżid|'
                        r'Imħassar|Imħassra|Imħassrin|Rinumerat|Rinumerata|Ħassar|Cap\.|Kap\.|S\.L\.|L\.S\.|See |Ara )')


def _f(x):
    return float(x)


def _norm(t):
    return re.sub(r'[^a-zà-žħġċż]', '', t.lower())


def _fix_spaced(words):
    """Join letter-spaced words ("P U B L I C") using geometric gaps."""
    toks = [w[4] for w in words]
    singles = sum(1 for t in toks if len(t) == 1)
    if len(toks) < 6 or singles < 0.6 * len(toks):
        out = toks[0]
        for i in range(len(words) - 1):
            g = words[i + 1][0] - words[i][2]
            h = max(words[i][3] - words[i][1], 4)
            out += ('' if g < 0.115 * h else ' ') + toks[i + 1]
        return out
    gaps = [words[i + 1][0] - words[i][2] for i in range(len(words) - 1)]
    if not gaps:
        return ' '.join(toks)
    med = statistics.median(gaps)
    out = toks[0]
    for i, g in enumerate(gaps):
        out += (' ' if g > med * 1.8 + 0.6 else '') + toks[i + 1]
    return out


SMALLCAPS = re.compile(r'\b([A-ZĦĠĊŻ]) (?=[A-ZĦĠĊŻ][A-ZĦĠĊŻ\'’-]+\b)')


def _fix_smallcaps(t):
    # "O F THE R IGHTS AND D UTIES" -> "OF THE RIGHTS AND DUTIES"
    if t.upper() == t and len(SMALLCAPS.findall(t)) >= 2:
        return SMALLCAPS.sub(r'\1', t)
    return t


def load_pages(pdf):
    out = subprocess.run(['pdftotext', '-bbox-layout', '-enc', 'UTF-8', pdf, '-'],
                         capture_output=True, text=True, errors='replace').stdout
    pages = []
    for pw, ph, body in PAGE_RE.findall(out):
        lines = []
        for x0, y0, x1, y1, inner in LINE_RE.findall(body):
            words = [(_f(a), _f(b), _f(c), _f(d), html.unescape(w)) for a, b, c, d, w in WORD_RE.findall(inner)]
            if not words:
                continue
            text = _fix_spaced(words).strip()
            if not text:
                continue
            lines.append({'x0': _f(x0), 'y0': _f(y0), 'x1': _f(x1), 'y1': _f(y1), 't': text})
        pages.append({'w': _f(pw), 'h': _f(ph), 'lines': lines})
    return pages


def strip_headers(pages):
    top_norms = {}
    for p in pages:
        if not p['lines']:
            p['band'] = []
            continue
        ymin = min(l['y0'] for l in p['lines'])
        band = [l for l in p['lines'] if l['y0'] < ymin + 7 and l['y0'] < p['h'] * 0.25]
        p['band'] = band
        for l in band:
            n = _norm(l['t'])
            if n:
                top_norms[n] = top_norms.get(n, 0) + 1
    multi = len(pages) >= 2
    for p in pages:
        band = p['band']
        has_bracket = any(HDR_BRACKET.search(l['t']) for l in band)
        drop = set()
        for l in band:
            n = _norm(l['t'])
            if has_bracket or re.fullmatch(r'\d{1,4}', l['t'].strip()) or (multi and n and top_norms.get(n, 0) >= 2):
                drop.add(id(l))
        p['lines'] = [l for l in p['lines'] if id(l) not in drop]


def column_bounds(pages):
    """Main column [left, right] per page; fallback per parity."""
    par = {0: [], 1: []}
    for i, p in enumerate(pages):
        wide = [l for l in p['lines'] if l['x1'] - l['x0'] > p['w'] * 0.38]
        p['wide'] = wide
        if len(wide) >= 3:
            left = sorted(l['x0'] for l in wide)[len(wide) // 10]
            right = sorted(l['x1'] for l in wide)[(len(wide) * 9) // 10]
            p['col'] = (left, right)
            par[i % 2].append(p['col'])
        else:
            p['col'] = None
    defaults = {}
    for k in (0, 1):
        if par[k]:
            defaults[k] = (statistics.median(c[0] for c in par[k]), statistics.median(c[1] for c in par[k]))
    for i, p in enumerate(pages):
        if p['col'] is None:
            p['col'] = defaults.get(i % 2) or defaults.get(1 - i % 2) or (p['w'] * 0.18, p['w'] * 0.78)


def merge_rows(lines, tol=2.5):
    """Merge fragments sharing a baseline into single rows (sorted by y then x)."""
    lines = sorted(lines, key=lambda l: (round(l['y1'], 0), l['x0']))
    rows = []
    for l in sorted(lines, key=lambda l: l['y1']):
        if rows and abs(rows[-1]['y1'] - l['y1']) <= tol and abs(rows[-1]['y0'] - l['y0']) <= tol + 3:
            r = rows[-1]
            r['parts'].append(l)
        else:
            rows.append({'y0': l['y0'], 'y1': l['y1'], 'parts': [l]})
    for r in rows:
        r['parts'].sort(key=lambda l: l['x0'])
        r['x0'] = r['parts'][0]['x0']
        r['x1'] = max(p['x1'] for p in r['parts'])
        r['y0'] = min(p['y0'] for p in r['parts'])
        r['y1'] = max(p['y1'] for p in r['parts'])
        r['t'] = ' '.join(p['t'] for p in r['parts'])
    return rows


def group_margin(lines):
    lines = sorted(lines, key=lambda l: l['y0'])
    groups = []
    for l in lines:
        if groups and l['y0'] - groups[-1]['y1'] < 5.5:
            g = groups[-1]
            g['lines'].append(l)
            g['y1'] = max(g['y1'], l['y1'])
        else:
            groups.append({'y0': l['y0'], 'y1': l['y1'], 'lines': [l]})
    for g in groups:
        g['t'] = join_lines([l['t'] for l in g['lines']])
    return groups


def join_lines(ts):
    out = ''
    for t in ts:
        t = t.strip()
        if not out:
            out = t
        elif out.endswith('-') and t[:1].islower():
            out += t
        else:
            out += ' ' + t
    return out


TOC_COLHDR = re.compile(r'^(Articles?|Artikoli|Artikolu|Regulations?|Regolamenti|Regolament|Rules?|Regoli|Paragraphs?|Paragrafi|Sections?|Taqsimiet|Page|Paġna)$', re.I)
TOC_REF = re.compile(r'(\d+[A-Z]{0,3}(\s*[-–]\s*\d+[A-Z]{0,3})?|[IVXL]+)\.?$')


def is_toc_page(p):
    rows = p['all_rows']
    n = len(rows)
    if n < 3:
        return False
    if any(TOC_COLHDR.match(r['t'].strip()) for r in rows):
        return True
    a = sum(1 for r in rows if TOC_REF.search(r['t']) and len(r['t']) < 140)
    b = sum(1 for r in rows if re.match(r'^\d+[A-Z]{0,3}\.\s', r['t']) and len(r['t']) < 120
            and not re.search(r'[;:,]$', r['t']))
    left, right = p['col']
    full = sum(1 for r in p['rows'] if r['x1'] >= right - 4 and (r['x1'] - r['x0']) > 0.8 * (right - left)
               and not TOC_REF.search(r['t']))
    return (a + b) / n >= 0.45 and full < 4


def heading_kind(t):
    for k, rx in KEYWORDS:
        if rx.search(t):
            return k
    return None


def md_escape(t):
    t = t.replace('\\', '\\\\').replace('*', '\\*').replace('_', '\\_')
    t = re.sub(r'^(\s*)(#|>|\+|-(?=\s)|=+|\d+\.(?=\s|$)|\d+\)(?=\s))', lambda m: m.group(1) + '\\' + m.group(2), t)
    t = t.replace('<', '&lt;')
    return t


def convert(pdf):
    pages = load_pages(pdf)
    strip_headers(pages)
    column_bounds(pages)

    # classify main vs margin
    for p in pages:
        left, right = p['col']
        main, margin = [], []
        for l in p['lines']:
            if l['x0'] >= right + 3 or l['x1'] <= left - 3:
                margin.append(l)
            else:
                main.append(l)
        rows = merge_rows(main)
        hs = [r['y1'] - r['y0'] for r in rows]
        mh = statistics.median(hs) if hs else 10
        foot = []
        if rows:
            # footnotes: trailing small-type rows at the bottom of the page starting with a marker
            k = len(rows)
            while k > 0 and (rows[k - 1]['y1'] - rows[k - 1]['y0']) < mh * 0.88:
                k -= 1
            cand = rows[k:]
            if cand and re.match(r'^(\*|†|‡|\d{1,2}\s|\(\d+\)\s?[A-Z])', cand[0]['t']) and k > 0:
                foot = cand
                rows = rows[:k]
        p['rows'] = rows
        p['foot'] = group_margin(foot) if foot else []
        p['margin'] = group_margin(margin)
        p['all_rows'] = merge_rows(p['lines'])

    # TOC detection
    toc_pages = set()
    for i, p in enumerate(pages[: max(3, len(pages) // 4 + 1)]):
        if any(TOC_START.search(r['t']) for r in p['rows'] + p['all_rows']):
            j = i
            while j < len(pages) and (j == i or is_toc_page(pages[j])):
                toc_pages.add(j)
                j += 1
            break

    # Build paragraph stream
    items = []  # dicts: kind in (para, toc, note), text, margin, centered
    cur = None
    for pi, p in enumerate(pages):
        left, right = p['col']
        center = (left + right) / 2
        if pi in toc_pages:
            # the part of the page before the TOC marker is handled as normal text
            rows = p['all_rows']
            started = False
            pre = []
            toc_rows = []
            for r in rows:
                if not started and TOC_START.search(r['t']):
                    started = True
                (toc_rows if started else pre).append(r)
            if any(TOC_START.search(r['t']) for r in rows):
                if pre:
                    p2 = dict(p)
                    p2['rows'] = [r for r in p['rows'] if r['y0'] < toc_rows[0]['y0'] - 1]
                    p2['margin'] = [g for g in p['margin'] if g['y1'] < toc_rows[0]['y0'] - 1]
                    p2['foot'] = []
                    cur = _emit_rows(p2, items, cur, pages)
            else:
                toc_rows = rows
            cur = None
            for r in toc_rows:
                items.append({'kind': 'toc', 'text': '  '.join(x['t'] for x in r['parts'])})
            continue
        cur = _emit_rows(p, items, cur, pages)
    return render(items)


def _emit_rows(p, items, cur, pages):
    left, right = p['col']
    center = (left + right) / 2
    width = right - left
    rows = p['rows']
    paras_here = []
    prev = cur['last'] if cur else None
    for r in rows:
        t = _fix_smallcaps(r['t'])
        r['t'] = t
        lg, rg = r['x0'] - left, right - r['x1']
        centered = (lg > 15 and rg > 8 and abs(lg - rg) < 12 and (r['x1'] - r['x0']) < width * 0.93)
        if centered and cur is not None and cur['kind'] == 'para' and not cur.get('centered'):
            pl = cur['last']
            if pl['x1'] >= cur['right'] - 4 and not re.search(r'[.:;]$', pl['t']) and r['y0'] - pl['y1'] < 8:
                centered = False
        new = False
        if cur is None or cur['kind'] != 'para':
            new = True
        elif centered or cur.get('centered'):
            new = True
        else:
            pl = cur['last']
            h = max(pl['y1'] - pl['y0'], 6)
            same_page = cur.get('page') is p
            if same_page and r['y0'] - pl['y1'] > h * 0.9:
                new = True
            elif pl['x1'] < cur['right'] - 18:
                new = True
            elif re.search(r'[:;]$', pl['t']) and re.match(r'^(\(|["“”\'‘’]|\d|[A-Z]|Provided|Iżda)', t):
                new = True
            elif re.search(r'\.$', pl['t']) and re.match(r'^(\(|\d+[A-Z]*\.)', t) and r['x0'] > cur['contx'] + 4:
                new = True
        if new:
            cur = {'kind': 'para', 'lines': [t], 'y0': r['y0'], 'page': p, 'right': right,
                   'centered': centered, 'x0': r['x0'], 'contx': r['x0'], 'margin': []}
            items.append(cur)
            paras_here.append(cur)
        else:
            cur['lines'].append(t)
            if cur.get('page') is p:
                cur['contx'] = min(cur['contx'], r['x0'])
            else:
                cur['page'] = p
                cur['right'] = right
                cur['contx'] = r['x0']
        cur['last'] = r
    # footnotes go after the last paragraph of the page
    if p.get('foot') and cur is not None:
        cur.setdefault('foot', []).extend(p['foot'])
    # re-split margin groups where a new paragraph starts next to them
    starts = [pp['y0'] for pp in paras_here]
    mlines = sorted([l for g in p['margin'] for l in g['lines']], key=lambda l: l['y0'])
    groups = []
    for l in mlines:
        newg = not groups or l['y0'] - groups[-1]['y1'] >= 5.5
        if not newg and re.search(r'[.;:]$', groups[-1]['lines'][-1]['t']) and \
                any(abs(l['y0'] - sy) < 3.2 for sy in starts):
            newg = True
        if newg:
            groups.append({'y0': l['y0'], 'y1': l['y1'], 'lines': [l]})
        else:
            groups[-1]['lines'].append(l)
            groups[-1]['y1'] = max(groups[-1]['y1'], l['y1'])
    for g in groups:
        g['t'] = join_lines([l['t'] for l in g['lines']])
    # attach margin notes
    for g in groups:
        best, bd = None, 1e9
        for para in paras_here:
            d = abs(para['y0'] - g['y0'])
            if d < bd:
                best, bd = para, d
        if best is not None and bd <= 14:
            best['margin'].append(g)
        else:
            # attach to the paragraph whose span covers the note (latest starting before it)
            cand = [pp for pp in paras_here if pp['y0'] <= g['y0'] + 2]
            if cand:
                cand[-1].setdefault('margin_tail', []).append(g)
            elif cur is not None and items:
                # note at top of page belonging to a paragraph continued from previous page
                tgt = paras_here[0] if paras_here else cur
                tgt.setdefault('margin_tail', []).append(g)
            else:
                items.append({'kind': 'note', 'text': g['t']})
    return cur


def split_note(t):
    """Split marginal note into (title, rest)."""
    m = NOTE_SPLIT.search(t)
    if m:
        return t[:m.start()].strip(), t[m.start():].strip()
    parts = re.split(r'\s(?=(?:Amended|Substituted|Added|Renumbered|Repealed|Deleted|Emendat|Sostitwit|Miżjud|Imħassar|Cap\.|Kap\.|S\.L\.|L\.S\.)\b)', t, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return t.strip(), ''


def render(items):
    ex = []
    for it in items:
        ex.append(it)
        for g in it.get('foot', []):
            for ft in re.split(r'\s(?=\*{1,3}[A-Z])', g['t']):
                ex.append({'kind': 'foot', 'text': ft})
    items = ex
    # First pass: decide headings
    kinds_order = []
    out_items = []
    last_art = None
    seen_body = False
    i = 0
    n = len(items)
    while i < n:
        it = items[i]
        if it['kind'] == 'toc':
            out_items.append(('toc', it['text']))
            i += 1
            continue
        if it['kind'] == 'note':
            out_items.append(('note', it['text']))
            i += 1
            continue
        if it['kind'] == 'foot':
            out_items.append(('foot', it['text']))
            i += 1
            continue
        text = join_lines(it['lines'])
        notes = [g['t'] for g in it.get('margin', [])]
        tail = [g['t'] for g in it.get('margin_tail', [])]
        k = heading_kind(text) if (it['centered'] and len(text) < 160) else None
        if k and seen_body is False and k == 'chapter' and re.match(r'^(CHAPTER|KAPITOLU)\s+\d+\s*$', text, re.I):
            k = None
        if k:
            # absorb following centered non-keyword lines as heading subtitle
            title = text
            j = i + 1
            while j < n and items[j]['kind'] == 'para' and j - i <= 2:
                nt_ = join_lines(items[j]['lines'])
                if heading_kind(nt_) is not None or ARTICLE_RE.match(nt_):
                    break
                ok = items[j]['centered'] and len(nt_) < 200
                ok = ok or (len(items[j]['lines']) == 1 and len(nt_) < 120 and not re.search(r'[.;:,]$', nt_)
                            and not re.match(r'^[\d(*"“]', nt_) and nt_[:1].isupper())
                if not ok:
                    break
                if title.upper() == title and nt_.upper() == nt_ and (title.endswith(',') or
                                                                     re.search(r'\b(AND|OF|THE|U|TA|TAL|FUQ|LI)$', title)):
                    title += ' ' + nt_
                else:
                    title += ' — ' + nt_
                notes = notes + [g['t'] for g in items[j].get('margin', [])]
                tail = tail + [g['t'] for g in items[j].get('margin_tail', [])]
                j += 1
            if k != 'schedule' and k not in kinds_order:
                kinds_order.append(k)
            out_items.append(('heading', k, title))
            for nt in notes + tail:
                out_items.append(('note', nt))
            if k == 'schedule':
                last_art = None
            i = j
            continue
        m = ARTICLE_RE.match(text)
        is_art = False
        if m and not it['centered']:
            num = m.group(1)
            base = int(re.match(r'\d+', num).group(0))
            if notes:
                is_art = True
            elif last_art is not None and last_art <= base <= last_art + 25:
                is_art = True
            elif last_art is None and base <= 3:
                is_art = True
            if is_art:
                last_art = base
                seen_body = True
        if is_art:
            title, rest = ('', '')
            if notes:
                title, rest = split_note(' '.join(notes))
            out_items.append(('article', m.group(1), title, rest, m.group(3).strip(), tail))
        else:
            if it['centered']:
                out_items.append(('centered', text, notes + tail))
            else:
                out_items.append(('para', text, notes, tail))
        i += 1

    # levels
    level = {}
    for idx, k in enumerate(kinds_order):
        level[k] = min(2 + idx, 5)
    level['schedule'] = 2
    art_level = min(6, (max(level.values()) + 1) if kinds_order else 2)
    if not kinds_order:
        art_level = 2

    md = []
    toc_buf = []

    def flush_toc():
        if toc_buf:
            md.append('  \n'.join(md_escape(x) for x in toc_buf))
            md.append('')
            toc_buf.clear()

    for o in out_items:
        if o[0] == 'toc':
            toc_buf.append(o[1])
            continue
        flush_toc()
        if o[0] == 'heading':
            md.append('#' * level[o[1]] + ' ' + md_escape(o[2]).lstrip('\\'))
            md.append('')
        elif o[0] == 'foot':
            md.append(md_escape(o[1]))
            md.append('')
        elif o[0] == 'note':
            md.append('*' + md_escape(o[1]) + '*')
            md.append('')
        elif o[0] == 'article':
            _, num, title, rest, body, tail = o
            h = f'{num}.' + (f' {title}' if title else '')
            md.append('#' * art_level + ' ' + md_escape(h).lstrip('\\'))
            md.append('')
            if rest:
                md.append('*' + md_escape(rest) + '*')
                md.append('')
            if body:
                md.append(md_escape(body))
                md.append('')
            for nt in tail:
                md.append('*' + md_escape(nt) + '*')
                md.append('')
        elif o[0] == 'centered':
            md.append('**' + md_escape(o[1]) + '**')
            md.append('')
            for nt in o[2]:
                md.append('*' + md_escape(nt) + '*')
                md.append('')
        elif o[0] == 'para':
            _, text, notes, tail = o
            for nt in notes:
                md.append('*' + md_escape(nt) + '*')
                md.append('')
            md.append(md_escape(text))
            md.append('')
            for nt in tail:
                md.append('*' + md_escape(nt) + '*')
                md.append('')
    flush_toc()
    s = '\n'.join(md)
    s = re.sub(r'\n{3,}', '\n\n', s).strip() + '\n'
    return s


if __name__ == '__main__':
    import sys
    sys.stdout.write(convert(sys.argv[1]))
