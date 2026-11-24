#!/usr/bin/env python3
"""Valide qu'un rapport (reports/** ou drafts/**) respecte le gabarit et les règles de la veille.

Usage : python3 tools/check_report.py <fichier.html> [...]      (code retour 1 s'il y a des erreurs)
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_memory import Report   # même parseur que la mémoire

DAYS = "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
MONTHS = "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
SUFFIX = " \u2013 Reefact"   # tiret demi-cadratin U+2013, comme le titre de reefact.net
TITLE_RE = re.compile(rf"^Veille technologique du ({DAYS}) (\d{{1,2}}|1er) ({MONTHS}) (\d{{4}})$")
FORBIDDEN = re.compile(r"chapter|stime", re.I)


def check(path):
    raw = Path(path).read_text(encoding="utf-8")
    r = Report(); r.feed(raw)
    errs = []
    add = errs.append
    # titre, date
    base = r.title[:-len(SUFFIX)] if r.title and r.title.endswith(SUFFIX) else None
    if base is None or not TITLE_RE.match(base): add(f"<title> invalide : {r.title!r} (attendu « Veille technologique du mardi 24 novembre 2026 \u2013 Reefact », tiret demi-cadratin U+2013)")
    h1 = re.search(r"<h1>(.*?)</h1>", raw, re.S)
    if not h1 or re.sub(r"\s+", " ", h1.group(1)).strip() != base: add("<h1> absent ou différent du <title> sans le suffixe « \u2013 Reefact »")
    if not r.date or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.date): add("<meta name=\"date\"> absente ou invalide")
    m = TITLE_RE.match(base or "")
    if m and r.date:
        mois = MONTHS.split("|").index(m.group(3)) + 1; jour = 1 if m.group(2) == "1er" else int(m.group(2))
        if r.date != f"{int(m.group(4)):04d}-{mois:02d}-{jour:02d}": add(f"date meta {r.date} incohérente avec le titre")
    # structure
    if 'href="../../assets/report.css"' not in raw: add("lien vers ../../assets/report.css manquant")
    if re.search(r"<style|<script", raw, re.I): add("<style> ou <script> interdit")
    tl = re.search(r'<div class="card tldr">(.*?)</div>', raw, re.S)
    n = len(re.findall(r"<li>", tl.group(1))) if tl else 0
    if not tl: add("bloc card tldr manquant")
    elif not 3 <= n <= 5: add(f"tldr : {n} puce(s), 3 à 5 attendues")
    if FORBIDDEN.search(raw): add("mention interdite (chapter / STIME)")
    # liens
    for tag in re.findall(r"<a\b[^>]*>", raw):
        href = re.search(r'href="([^"]*)"', tag)
        if href and href.group(1).startswith("http") and not ('target="_blank"' in tag and "noopener" in tag): add(f"lien externe sans target=_blank/noopener : {href.group(1)[:70]}")
    ids = [a["id"] for a in r.articles]
    for a in r.articles:
        if not a["id"]: add(f"article sans id : {a['title'][:50]}")
        if not a["title"]: add(f"article sans <h3> : {a['id']}")
    if len(ids) != len(set(ids)): add("ids d'articles en double")
    for href in set(re.findall(r'href="#([^"]+)"', raw)):
        if href != "top" and href not in ids and f'id="{href}"' not in raw: add(f"ancre #{href} sans cible")
    if 'id="top"' not in raw: add('ancre id="top" manquante')
    # radar : un dépôt par article, uniquement sur le radar
    for a in r.articles:
        radar = a["category"] == "b-radar"
        repo = a["repo"]
        if radar and not (repo and re.fullmatch(r"Reefact/[\w.-]+", repo)): add(f"radar sans data-repo unique valide : {a['id']}")
        if radar and repo and "," in repo: add(f"radar avec plusieurs dépôts (un article par dépôt) : {a['id']}")
        if not radar and repo: add(f"data-repo sur un article hors radar : {a['id']}")
    if not r.articles: add("aucun article de résumé")
    return errs


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        errs = check(p)
        print(("OK   " if not errs else "ERREURS ") + p)
        for e in errs: print("   -", e)
        bad += bool(errs)
    sys.exit(1 if bad else 0)
