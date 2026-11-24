#!/usr/bin/env python3
"""Valide qu'un rapport rendu (reports/**) respecte le gabarit et les règles de la veille.

Usage : python3 tools/check_report.py <fichier.html> [...]      (code retour 1 s'il y a des erreurs)
Les lignes « ? (langue) » sont des avertissements non bloquants (anglais résiduel, calques, phrases trop longues) :
ils ne prouvent pas un mauvais français, ils désignent ce que la relecture doit regarder.
"""
import re, sys
from pathlib import Path
from html.parser import HTMLParser

norm = lambda s: re.sub(r"\s+", " ", s).strip()


class Report(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = self.date = None
        self.articles = []
        self._art = None            # article en cours
        self._h3 = None             # ("cat"|"title", [textes])
        self._in_title = False
        self._a = None              # lien en cours : [href, [textes]]
        self._badge = None          # badge en cours : [classes, [textes]]
        self._in_text = False       # dans un <p>/<dt>/<dd> d'un article

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "title": self._in_title = True
        elif tag == "meta" and a.get("name") == "date": self.date = a.get("content")
        elif tag == "details" and "card" in cls.split():
            self._art = {"id": a.get("id"), "repo": a.get("data-repo"), "category": a.get("data-classe"), "title": "", "badges": [], "sources": [], "text": []}
        elif tag == "h3" and self._art is not None:
            self._h3 = ("title", [])
        elif tag == "span" and "badge" in cls.split():
            self._badge = [[c for c in cls.split() if c.startswith("b-")], []]
        elif tag in ("p", "dt", "dd") and self._art is not None and "src" not in cls.split():
            self._art["text"].append(""); self._in_text = True
        elif tag == "a":
            self._a = [a.get("href", ""), []]

    def handle_endtag(self, tag):
        if tag == "title": self._in_title = False
        elif tag == "h3" and self._h3:
            kind, parts = self._h3; text = norm("".join(parts)); self._h3 = None
            if kind == "title": self._art["title"] = text
        elif tag == "span" and self._badge:
            classes, parts = self._badge; self._badge = None
            text = norm("".join(parts))
            if self._art is not None: self._art["badges"].append({"class": classes, "text": text})
        elif tag == "a" and self._a:
            href, parts = self._a; self._a = None
            text = norm("".join(parts))
            if href.startswith("http"):
                link = {"text": text, "url": href}
                if self._art is not None: self._art["sources"].append(link)
        elif tag in ("p", "dt", "dd"): self._in_text = False
        elif tag == "details" and self._art is not None:
            art = self._art; art["paras"] = [norm(x) for x in art["text"] if norm(x)]; art["text"] = norm(" ".join(art["paras"])); self.articles.append(art); self._art = None

    def handle_data(self, d):
        if self._in_title: self.title = norm((self.title or "") + d)
        if self._h3: self._h3[1].append(d)
        if self._badge: self._badge[1].append(d)
        if self._a: self._a[1].append(d)
        if self._art is not None and self._in_text and self._h3 is None and self._badge is None and self._art["text"]:
            self._art["text"][-1] += d


DAYS = "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche"
MONTHS = "janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre"
SUFFIX = " \u2013 Reefact"   # tiret demi-cadratin U+2013, comme le titre de reefact.net
TITLE_RE = re.compile(rf"^Veille technologique du ({DAYS}) (\d{{1,2}}|1er) ({MONTHS}) (\d{{4}})$")
FORBIDDEN = re.compile(r"chapter|stime", re.I)
# --- Garde-fous de langue (avertissements, jamais bloquants : ils signalent, la relecture décide) ---
EN_WORDS = set("the and of with for is are that this from was were has have will been which their they you your our into than then when while also not its it's can't".split())
CALQUES = [  # (motif, suggestion)
    (r"\bsupporte(?:nt|r|ra|ront)?\s+(?:le|la|les|l['’]|un|une|des)\b", "« supporter » au sens anglais : préférer « prend en charge »"),
    (r"\badress(?:e|er|ent)\s+(?:le|la|les|l['’]|un|une|ce|cette)\b", "« adresser » au sens anglais : préférer « traiter », « répondre à »"),
    (r"\bimpact(?:e|er|ent|é|és|ée|ées)\b", "« impacter » : préférer « toucher », « avoir un effet sur »"),
    (r"\bopportunités?\b", "« opportunité » au sens de « chance » est un calque : préférer « occasion »"),
    (r"\bdéfinitivement\b", "« définitivement » pour « definitely » : préférer « clairement », « certainement »"),
    (r"\bactuellement\s+en\s+cours\b", "pléonasme"),
]


def prose_warnings(r):
    warns = []
    for a in r.articles:
        text = a.get("text", "")
        for para in a.get("paras", []):
            words = re.findall(r"[A-Za-zÀ-ÿ'’-]+", para)
            if len(words) >= 12:
                en = sum(1 for w in words if w.lower() in EN_WORDS)
                if en / len(words) >= 0.10: warns.append(f"{a['id']} : paragraphe qui ressemble à de l'anglais ({en}/{len(words)} mots outils anglais) : « {para[:60]}… »")
        sentences = [x for para in a.get("paras", []) for x in re.split(r"(?<=[.!?])\s+", para) if len(x.split()) > 1]
        long_ = [x for x in sentences if len(x.split()) > 45]
        if long_: warns.append(f"{a['id']} : phrase très longue ({len(long_[0].split())} mots) : « {long_[0][:70]}… »")
        for pat, hint in CALQUES:
            m = re.search(pat, text, re.I)
            if m: warns.append(f"{a['id']} : « {m.group(0)} » — {hint}")
        if re.search(r"\bTODO\b|\{\{|\}\}|\bAAAA\b|JJ/MM", text): warns.append(f"{a['id']} : reste de gabarit ou ponctuation douteuse")
        if len(text) < 120 and a["category"] not in ("b-conf",): warns.append(f"{a['id']} : résumé très court ({len(text)} caractères)")
    return warns


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
    if not re.search(r'href="\.\./\.\./assets/report\.css(\?v=[0-9a-f]+)?"', raw): add("lien vers ../../assets/report.css manquant")
    if re.search(r"<style|<script(?! src=\"\.\./\.\./assets/report\.js(\?v=[0-9a-f]+)?\" defer></script>)", raw, re.I): add("<style> ou <script> en ligne interdit (seul ../../assets/report.js est chargé)")
    tl = re.search(r'<div class="card tldr">(.*?)</div>', raw, re.S)
    n = len(re.findall(r"<p>", tl.group(1))) if tl else 0
    if not tl: add("bloc card tldr manquant")
    elif not 1 <= n <= 4: add(f"« À retenir » : {n} paragraphe(s), 1 à 4 attendus")
    if FORBIDDEN.search(raw): add("mention interdite (chapter / STIME)")
    # liens
    for tag in re.findall(r"<a\b[^>]*>", raw):
        href = re.search(r'href="([^"]*)"', tag)
        if href and href.group(1).startswith("http") and not ('target="_blank"' in tag and "noopener" in tag): add(f"lien externe sans target=_blank/noopener : {href.group(1)[:70]}")
    ids = [a["id"] for a in r.articles]
    for a in r.articles:
        if not a["id"]: add(f"sujet sans id : {a['title'][:50]}")
        if not a["title"]: add(f"sujet sans <h3> : {a['id']}")
    if len(ids) != len(set(ids)): add("ids de sujets en double")
    for href in set(re.findall(r'href="#([^"]+)"', raw)):
        if href != "top" and href not in ids and f'id="{href}"' not in raw: add(f"ancre #{href} sans cible")
    if 'id="top"' not in raw: add('ancre id="top" manquante')
    # projets : au plus un dépôt par article
    for a in r.articles:
        repo = a["repo"]
        if repo is not None and not re.fullmatch(r"Reefact/[\w.-]+", repo): add(f"data-repo invalide (un seul dépôt Reefact/<nom>) : {a['id']}")
    if not r.articles: add("aucun sujet")
    return errs, prose_warnings(r)


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        errs, warns = check(p)
        print(("OK   " if not errs else "ERREURS ") + p)
        for e in errs: print("   -", e)
        for w in warns: print("   ? (langue)", w)
        bad += bool(errs)
    sys.exit(1 if bad else 0)
