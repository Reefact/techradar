#!/usr/bin/env python3
"""Mémoire de la veille, dérivée des fichiers du jour (data/days/AAAA/AAAAMMJJ.json) : écrit data/memory.json.

  python3 tools/build_memory.py                       (ré)écrit data/memory.json
  python3 tools/build_memory.py --seen URL            cette URL a-t-elle déjà été vue ? (code retour 0 = déjà PUBLIÉE)
  python3 tools/build_memory.py --due [AAAA-MM-JJ]    rappels de CFP à émettre ce jour-là (défaut : aujourd'hui)
  python3 tools/build_memory.py --reconsiderer        sujets « mis de côté » ou « candidat » des jours précédents

Sortie déterministe (aucun horodatage). Seuls les sujets PUBLIÉS bloquent l'anti-doublon ; un sujet écarté
ou mis de côté reste reconsidérable (son motif est donné).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import ROOT, day_files, load_json, plain, urls  # noqa: E402

MONTHS = {"janv": 1, "janvier": 1, "févr": 2, "fevr": 2, "février": 2, "mars": 3, "avr": 4, "avril": 4, "mai": 5,
          "juin": 6, "juil": 7, "juillet": 7, "août": 8, "aout": 8, "sept": 9, "septembre": 9, "oct": 10,
          "octobre": 10, "nov": 11, "novembre": 11, "déc": 12, "dec": 12, "décembre": 12}
THRESHOLDS = [30, 14, 7, 3]
OUT = ROOT / "data" / "memory.json"


def parse_dates(text):
    """Dates complètes (jour, mois en français, année) trouvées dans un texte → liste ISO."""
    out = []
    for m in re.finditer(r"(\d{1,2})(?:er)?\s+([A-Za-zéûèôî]+)\.?\s+(20\d\d)", text or ""):
        mon = MONTHS.get(m.group(2).lower().rstrip("."))
        if mon:
            try:
                out.append(date(int(m.group(3)), mon, int(m.group(1))).isoformat())
            except ValueError:
                pass
    return sorted(set(out))


def build():
    days = [load_json(p) for p in day_files()]
    days.sort(key=lambda d: d["date"])
    reports, topics, tools, projets, url_index, confs = [], [], [], {}, {}, {}
    for d in days:
        pub = [s for s in d.get("sujets", []) if s.get("statut") == "publie"]
        if pub:
            reports.append({"date": d["date"], "path": f"reports/{d['date'][:4]}/{d['date'].replace('-', '')}.html", "publies": len(pub)})
        for s in d.get("sujets", []):
            st = s.get("statut")
            entry = {"date": d["date"], "id": s["id"], "categorie": s["categorie"], "statut": st, "titre": plain(s["titre"])}
            if s.get("motif"):
                entry["motif"] = s["motif"]
            if s.get("depot"):
                entry["depot"] = s["depot"]
            topics.append(entry)
            for u in urls(s):
                cur = url_index.get(u)
                # une URL publiée prime sur toute autre trace ; sinon on garde la première vue
                if cur is None or (st == "publie" and cur["statut"] != "publie"):
                    url_index[u] = {"date": d["date"], "id": s["id"], "statut": st, **({"motif": s["motif"]} if s.get("motif") else {})}
            if st != "publie":
                continue
            if s["categorie"] == "outils":
                tools.append({"date": d["date"], "titre": plain(s["titre"]), "url": s["sources"][0]["url"] if s.get("sources") else None})
            if s.get("depot"):
                projets.setdefault(s["depot"], []).append({"date": d["date"], "id": s["id"], "titre": plain(s["titre"])})
            if s["categorie"] == "conferences":
                name = plain(s.get("titre_sommaire") or s["titre"])
                k = s.get("conference", {})
                c = confs.setdefault(name, {"name": name, "first_seen": d["date"], "reminders_seen": []})
                c.update({"last_seen": d["date"], "dates": plain(k.get("dates", "")), "place": plain(k.get("lieu", "")), "cfp": plain(k.get("cfp", ""))})
                c["cfp_deadlines"] = parse_dates(c["cfp"])
                for t in s.get("tags", []):
                    if isinstance(t, dict) and t.get("tag") in ("rappel", "rappel-cfp"):
                        m = re.search(r"J-(\d+)", t.get("texte", ""))
                        if m:
                            c["reminders_seen"].append({"date": d["date"], "label": t["texte"], "n": int(m.group(1))})
    return {"reports": reports, "projets": projets, "tools_proposed": tools, "conferences": sorted(confs.values(), key=lambda c: c["name"]),
            "topics": topics, "urls": dict(sorted(url_index.items()))}


def mem():
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else build()


def due(today):
    out = []
    for c in mem()["conferences"]:
        for iso in c.get("cfp_deadlines", []):
            days = (date.fromisoformat(iso) - today).days
            if days < 0 or days > THRESHOLDS[0]:
                continue
            hi = min(t for t in THRESHOLDS if t >= days)
            lo = max([t for t in THRESHOLDS if t < hi] + [-1])
            if any(lo < r["n"] <= hi for r in c.get("reminders_seen", [])):
                continue
            out.append({"conference": c["name"], "deadline": iso, "days_left": days, "threshold": f"J-{hi}"})
    return out


def reconsider():
    """Derniers sujets « mis de côté » (et candidats non publiés) : à réexaminer par l'exécution suivante."""
    m = mem()
    published_titles = {t["titre"] for t in m["topics"] if t["statut"] == "publie"}
    return [t for t in m["topics"] if t["statut"] in ("mis-de-cote", "candidat") and t["titre"] not in published_titles][-40:]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--due"]:
        print(json.dumps(due(date.fromisoformat(a[1]) if len(a) > 1 else date.today()), ensure_ascii=False, indent=1)); sys.exit(0)
    if a[:1] == ["--seen"]:
        hit = mem()["urls"].get(a[1])
        print(json.dumps(hit, ensure_ascii=False) if hit else "non")
        sys.exit(0 if hit and hit["statut"] == "publie" else 1)
    if a[:1] == ["--reconsiderer"]:
        print(json.dumps(reconsider(), ensure_ascii=False, indent=1)); sys.exit(0)
    m = build()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"data/memory.json : {len(m['reports'])} rapport(s), {len(m['topics'])} sujet(s) analysé(s), {len(m['urls'])} URL(s), {len(m['conferences'])} conférence(s)")
