#!/usr/bin/env python3
"""Mémoire de la veille, dérivée des rapports : génère data/memory.json.

Usage :
  python3 tools/build_memory.py                 # (ré)écrit data/memory.json
  python3 tools/build_memory.py --due [AAAA-MM-JJ]   # rappels de CFP à émettre ce jour-là (défaut : aujourd'hui)
  python3 tools/build_memory.py --seen URL      # cette URL a-t-elle déjà été publiée ? (code retour 0 = oui)

La sortie est déterministe (pas d'horodatage) : un rapport inchangé ne produit aucun diff.
Source de vérité = reports/**/*.html ; seules les données NON déductibles vivent dans data/notes.md.
"""
import json, re, sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONTHS = {"janv": 1, "janvier": 1, "févr": 2, "fevr": 2, "février": 2, "mars": 3, "avr": 4, "avril": 4, "mai": 5,
          "juin": 6, "juil": 7, "juillet": 7, "août": 8, "aout": 8, "sept": 9, "septembre": 9, "oct": 10,
          "octobre": 10, "nov": 11, "novembre": 11, "déc": 12, "dec": 12, "décembre": 12}
THRESHOLDS = [30, 14, 7, 3]
norm = lambda s: re.sub(r"\s+", " ", s).strip()


class Report(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = self.date = None
        self.articles, self.rows, self.brief = [], [], []
        self._cat = None            # catégorie courante (badge du <h3> hors article)
        self._art = None            # article en cours
        self._h3 = None             # ("cat"|"title", [textes])
        self._in_title = False
        self._tr = self._td = None  # ligne / cellule de tableau
        self._li = None             # <li> de « En bref »
        self._brief_ul = False
        self._a = None              # lien en cours : [href, [textes]]
        self._badge = None          # badge en cours : [classes, [textes]]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "")
        if tag == "title": self._in_title = True
        elif tag == "meta" and a.get("name") == "date": self.date = a.get("content")
        elif tag == "article" and "card" in cls.split():
            self._art = {"id": a.get("id"), "repo": a.get("data-repo"), "category": self._cat, "title": "", "badges": [], "sources": [], "text": []}
        elif tag == "h3":
            self._h3 = ("title" if self._art else "cat", [])
        elif tag == "span" and "badge" in cls.split():
            self._badge = [[c for c in cls.split() if c.startswith("b-")], []]
        elif tag == "ul" and "brief" in cls.split(): self._brief_ul = True
        elif tag == "li" and self._brief_ul: self._li = {"text": [], "links": []}
        elif tag == "tr": self._tr = []
        elif tag == "td" and self._tr is not None: self._td = {"text": [], "badges": [], "link": None}
        elif tag == "p" and self._art is not None: self._art["text"].append("")
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
            if self._h3 and self._h3[0] == "cat" and classes: self._cat = classes[0]
            elif self._td is not None: self._td["badges"].append(text)
            elif self._art is not None: self._art["badges"].append({"class": classes, "text": text})
        elif tag == "a" and self._a:
            href, parts = self._a; self._a = None
            text = norm("".join(parts))
            if href.startswith("http"):
                link = {"text": text, "url": href}
                if self._art is not None: self._art["sources"].append(link)
                if self._li is not None: self._li["links"].append(link)
            elif self._td is not None and href.startswith("#") and not self._td["link"]:
                self._td["link"] = text
        elif tag == "td" and self._td is not None:
            self._tr.append(self._td); self._td = None
        elif tag == "tr" and self._tr:
            if len(self._tr) >= 4: self.rows.append(self._tr)
            self._tr = None
        elif tag == "li" and self._li is not None:
            self.brief.append({"text": norm("".join(self._li["text"])), "links": self._li["links"]}); self._li = None
        elif tag == "ul": self._brief_ul = False
        elif tag == "article" and self._art is not None:
            art = self._art; art["text"] = norm(" ".join(art["text"])); self.articles.append(art); self._art = None

    def handle_data(self, d):
        if self._in_title: self.title = norm((self.title or "") + d)
        if self._h3: self._h3[1].append(d)
        if self._badge: self._badge[1].append(d)
        if self._a: self._a[1].append(d)
        if self._td is not None: self._td["text"].append(d)
        if self._li is not None: self._li["text"].append(d)
        if self._art is not None and self._h3 is None and self._badge is None: 
            if self._art["text"]: self._art["text"][-1] += d


def parse_dates(text):
    """Dates complètes (jour, mois français, année) trouvées dans un texte → liste ISO."""
    out = []
    for m in re.finditer(r"(\d{1,2})(?:er)?\s+([A-Za-zéûèôî]+)\.?\s+(20\d\d)", text):
        mon = MONTHS.get(m.group(2).lower().rstrip("."))
        if mon:
            try: out.append(date(int(m.group(3)), mon, int(m.group(1))).isoformat())
            except ValueError: pass
    return sorted(set(out))


def build():
    reports = []
    topics, tools, radar, urls = [], [], {}, {}
    confs = {}
    for p in sorted((ROOT / "reports").rglob("*.html")):
        r = Report(); r.feed(p.read_text(encoding="utf-8"))
        if not r.date: continue
        rel = p.relative_to(ROOT).as_posix()
        reports.append({"date": r.date, "path": rel, "title": r.title})
        def note_url(u, kind, ref):
            urls.setdefault(u["url"], {"first_seen": r.date, "report": rel, "kind": kind, "ref": ref})
        for a in r.articles:
            cat = (a["category"] or "").removeprefix("b-")
            if cat == "conf":
                c = confs.setdefault(a["title"], {"name": a["title"], "first_seen": r.date, "last_seen": r.date, "links": [], "rows": [], "reminders_seen": []})
                c["last_seen"] = r.date
                for s in a["sources"]:
                    if s not in c["links"]: c["links"].append(s)
            else:
                entry = {"date": r.date, "id": a["id"], "category": cat, "title": a["title"], "sources": a["sources"]}
                if a["repo"]: entry["repo"] = a["repo"]; radar.setdefault(a["repo"], []).append({"date": r.date, "id": a["id"], "title": a["title"]})
                if cat == "tool": tools.append({"date": r.date, "title": a["title"], "url": a["sources"][0]["url"] if a["sources"] else None})
                topics.append(entry)
            for s in a["sources"]: note_url(s, "article", a["id"])
        for item in r.brief:
            for s in item["links"]: note_url(s, "brief", item["text"][:80])
            topics.append({"date": r.date, "id": None, "category": "brief", "title": item["text"][:120], "sources": item["links"]})
        for tr in r.rows:   # tableau des conférences
            name = tr[0]["link"] or norm("".join(tr[0]["text"]))
            c = next((v for k, v in confs.items() if name.lower() in k.lower() or k.lower() in name.lower()), None)
            if c is None:
                c = confs.setdefault(name, {"name": name, "first_seen": r.date, "last_seen": r.date, "links": [], "rows": [], "reminders_seen": []})
            c["name"] = name; c["last_seen"] = r.date
            c["dates"], c["place"], c["cfp"] = norm("".join(tr[1]["text"])), norm("".join(tr[2]["text"])), norm("".join(tr[3]["text"]))
            c["cfp_deadlines"] = parse_dates(c["cfp"])
            for b in tr[0]["badges"]:
                m = re.search(r"⏰\s*J-(\d+)", b)
                if m: c["reminders_seen"].append({"date": r.date, "label": b, "n": int(m.group(1))})
    for c in confs.values(): c.pop("rows", None)
    return {"reports": reports, "radar": radar, "tools_proposed": tools, "conferences": sorted(confs.values(), key=lambda c: c["name"]),
            "topics": topics, "urls": dict(sorted(urls.items()))}


def due(today):
    """Rappels J-30/14/7/3 à émettre pour `today`, d'après les dates limites et les rappels déjà vus."""
    mem = json.loads((ROOT / "data" / "memory.json").read_text(encoding="utf-8"))
    out = []
    for c in mem["conferences"]:
        for iso in c.get("cfp_deadlines", []):
            days = (date.fromisoformat(iso) - today).days
            if days < 0 or days > THRESHOLDS[0]: continue
            hi = min(t for t in THRESHOLDS if t >= days)                 # seuil courant
            lo = max([t for t in THRESHOLDS if t < hi] + [-1])           # seuil du dessous
            if any(lo < r["n"] <= hi for r in c.get("reminders_seen", [])): continue
            out.append({"conference": c["name"], "deadline": iso, "days_left": days, "threshold": f"J-{hi}"})
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--due"]:
        d = date.fromisoformat(a[1]) if len(a) > 1 else date.today()
        print(json.dumps(due(d), ensure_ascii=False, indent=1)); sys.exit(0)
    if a[:1] == ["--seen"]:
        mem = json.loads((ROOT / "data" / "memory.json").read_text(encoding="utf-8"))
        hit = mem["urls"].get(a[1]); print(json.dumps(hit, ensure_ascii=False) if hit else "non"); sys.exit(0 if hit else 1)
    mem = build()
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "memory.json").write_text(json.dumps(mem, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print(f"data/memory.json : {len(mem['reports'])} rapport(s), {len(mem['topics'])} sujet(s), {len(mem['urls'])} URL(s), {len(mem['conferences'])} conférence(s)")
