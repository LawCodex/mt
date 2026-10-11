# LawCodex — Malta (`mt`)

The **Constitution of Malta** and the **Laws of Malta** — every consolidated Chapter (Cap. 1 – Cap. 6xx)
and the **Subsidiary Legislation** made under them — as plain Markdown, one file per text, in **English**
(`en/`) and **Maltese** (`mt/`).

Part of [LawCodex](https://github.com/LawCodex) — the laws of every country as Markdown in git.

Retrieved: 2026-10-12. **10,152 files.**

## Contents

| Category | English `en/` | Maltese `mt/` | of which repealed (each language) |
|---|---:|---:|---:|
| Constitution of Malta (`constitution/`) | 1 | 1 | 0 |
| Chapters — consolidated Acts, Codes, Ordinances (`chapters/`) | 562 | 562 | 99 |
| Subsidiary Legislation (`subsidiary/<parent>/`) | 4,512 | 4,512 | 922 |
| Statute Law Revision Act, 2021 (`other/`) | 1 | 1 | 0 |
| **Total** | **5,076** | **5,076** | |

The corpus is the complete "Laws of Malta" listing of legislation.mt (565 entries: the Constitution,
563 Chapters, the SLRA) and every Subsidiary Legislation item listed under them (4,516 items).
Chapters and S.L. that have been **repealed** are kept (the official site still publishes their final
consolidated text, often reduced to a "Repealed by ..." note) and are marked `status: repealed`.

### Language

Malta has two official languages. Under article 74 of the Constitution, laws are enacted in both Maltese and
English and, in case of conflict, **the Maltese text prevails** (save where a law provides otherwise; some
older Chapters exist authoritatively only in English). Both texts are given as published by the Legislation
Unit; `mt/` mirrors `en/` with Maltese file names (`kap-…`, `ls-…` instead of `cap-…`, `sl-…`).

## Structure

```
en/  (and mt/)
  constitution/constitution-of-malta.md            (mt: kostituzzjoni-ta-malta.md)
  chapters/cap-016-civil-code.md                   Cap. 16 (mt: kap-016-kodici-civili.md)
  subsidiary/cap-016/sl-016-14-<slug>.md           S.L. 16.14, made under Cap. 16
  subsidiary/constitution/sl-const-01-<slug>.md    S.L. Const.01, made under the Constitution
  other/statute-law-revision-act-2021.md
```

Chapter numbers are zero-padded to 3 digits (`cap-009`, `cap-123`); S.L. numbers are
`<chapter>-<item>` (`sl-016-14` = S.L. 16.14). File names are stable and derived from the official number
plus the title.

Each file starts with YAML front matter:

```yaml
title: "Civil Code"
identifier: "Cap. 16"                               # or "S.L. 16.14", "Constitution of Malta"
eli: "https://legislation.mt/eli/cap/16"            # ELI work URI
type: code                                          # constitution | code | act | subsidiary_legislation
jurisdiction: mt
language: en                                        # en | mt
parent: "Cap. 16"                                   # S.L. only: enabling Chapter
date: 1870-02-11                                    # first entry into force (ELI metadata)
last_amended: 2026-10-01                            # date of the consolidated version (ELI version date)
status: in_force                                    # in_force | repealed
status_note: "Repealed by Act II of 2015"           # when given by the listing
source: "https://legislation.mt/eli/cap/16/eng/pdf" # official PDF converted
version: "https://legislation.mt/eli/cap/16/20261001/eng"
retrieved: 2026-10-12
```

followed by `# Title (Cap. N)` and the text. Conversion conventions:

- Structural headings (BOOK / PART / TITLE / Sub-title / CHAPTER / § / SCHEDULE, and the Maltese
  KTIEB / TAQSIMA / TITOLU / SUB-TITOLU / KAPITOLU / SKEDA) become `##`…`#####` headings, nested in the order
  they first appear; schedules are always `##`.
- Articles / regulations become the deepest heading: `###### 12A. <marginal note>`. The **marginal note**
  (the official side-heading printed in the margin) is used as the heading text.
- The amendment history printed in the margin ("*Amended by: XXI.1993.3; L.N. 46 of 1965.*",
  "*Substituted by: …*", cross references such as "*Cap. 12.*") is kept as an italic line under the
  heading or next to the paragraph it annotates.
- The front matter of each PDF (chapter number, long title, enactment date, consolidation history) and the
  *Arrangement* (table of contents) are kept as plain text (one line per TOC row).
- Footnotes are kept as paragraphs after the paragraph they interrupt.

## Source

- **[legislation.mt](https://legislation.mt)** — the official legislation portal of the Government of Malta,
  maintained by the Legislation Unit of the Office of the State Advocate / Ministry for Justice. Each item has
  an ELI URI (`https://legislation.mt/eli/cap/16`) and an official PDF per language
  (`…/eng/pdf`, `…/mlt/pdf`); the PDFs are marked `eli:legal_value = official`. legislation.mt publishes
  **PDF only** (no HTML/XML text format is exposed: `…/eng/html` returns an error page).
- Catalogue: the "Laws of Malta" listing (`/Legislation`), via the same AJAX endpoints its web UI uses
  (`/Legislations/LegislationPartial`, `/Legislations/GetChapterChild`), in English and Maltese.
- Metadata: the ELI RDFa `<meta>` tags of each item's page (`/eli/<…>/eng/portalpdf`).
- robots.txt only disallows one specific crawler and sets no Crawl-delay; downloads used a descriptive
  User-Agent and at most 3 parallel connections.

### Copyright / licence

Maltese legislation is published by the Government of Malta on legislation.mt for free public access; the
site states no specific open licence. Statutory texts are official public documents and are reproduced here
for public information. Only the official PDF (and the Government Gazette) is authoritative — this
Markdown conversion is **not** an official version.

## Not covered / known limitations

- **Acts as enacted** (`/eli/act/<year>/<n>`, ~2,000), **Legal Notices** as published in the Gazette
  (`/eli/ln/…`, ~14,000) and **Local Council bye-laws** (`/eli/lcbl/…`): the consolidated Chapters and
  Subsidiary Legislation already incorporate their amendments; the amending instruments themselves are not
  included.
- Bills, EU law, court judgments.
- Items listed but not converted (each in both languages): **Cap. 475** (Budget Measures Implementation (2005)
  Act, repealed) and **S.L. 514.07** (repealed) — the site returns no PDF; **S.L. 16** ("Civil Code as at 31st
  December 2010", a historical snapshot) — no PDF; **S.L. 528.10** (Processing of Personal Data (Secondary
  Processing) (Health Sector) Regulations) and **S.L. 623.02** (repealed) — scanned PDFs without a text layer
  (no OCR was attempted).
- **PDF conversion is heuristic.** Text comes from the PDF text layer (poppler `pdftotext -bbox-layout`) with
  layout analysis for the margin-note column, running headers and paragraphs. Expect occasional artefacts:
  tables (tariffs, forms, schedules of fees) are flattened to text lines; a few headings or paragraph
  breaks may be misplaced; some marginal notes may be attached to the neighbouring paragraph; letter-spaced
  or small-caps words in old PDFs may be split or joined incorrectly; hyphenation at line ends is kept as
  printed. Article text itself is otherwise verbatim.

## Regenerate

Requirements: Python 3 with `requests`, `beautifulsoup4`, `lxml` (`scripts/requirements.txt`) and poppler's
`pdftotext` on `PATH`.

```sh
python scripts/mt_catalog.py          # -> ../_raw/mt/catalog.json   (listing, EN + MT titles)
python scripts/mt_fetch.py            # -> ../_raw/mt/meta/*.json, ../_raw/mt/pdf/*.pdf  (cached, re-runnable)
python scripts/mt_build.py            # -> en/, mt/   (options: --kinds const,cap,sl,other --langs en,mt)
```

`scripts/pdf2md.py <file.pdf>` converts a single PDF to Markdown on stdout. Set `MT_RAW` to change the
scratch directory.
