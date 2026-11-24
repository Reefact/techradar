#!/usr/bin/env python3
"""Génère la liste des brouillons pour la page /drafts/ : drafts.json.

Usage : python3 tools/build_drafts.py <fichier_de_sortie.json>
Lit drafts/AAAA/AAAAMMJJ-HHMM.html (date et heure de Paris lues dans le nom de fichier ; le titre vient de <title>).
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})\.html$")
SUFFIX = " – Reefact"

out = []
for p in sorted((ROOT / "drafts").glob("*/*.html")):
    m = NAME.match(p.name)
    if not m or p.parent.name != m.group(1):
        continue
    t = p.read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", t, re.S)
    title = re.sub(r"\s+", " ", title.group(1)).strip().removesuffix(SUFFIX) if title else p.stem
    out.append({
        "date": f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
        "time": f"{m.group(4)}:{m.group(5)}",
        "title": title,
        "href": f"{p.parent.name}/{p.name}",
    })
out.sort(key=lambda d: (d["date"], d["time"]), reverse=True)
dest = Path(sys.argv[1])
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{dest} : {len(out)} brouillon(s)")
