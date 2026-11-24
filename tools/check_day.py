#!/usr/bin/env python3
"""Valide un fichier du jour (data/days/AAAA/AAAAMMJJ.json). Code retour 1 s'il y a des erreurs.

  python3 tools/check_day.py <fichier.json> [--contre REF] [--partiel]

  --contre REF  immuabilité : compare avec la version du fichier au commit REF (ex. HEAD, origin/main) ;
                tout sujet « publie » à REF doit rester publié et identique (hors historique).
  --partiel     exécution qui n'a pas fait de recherche complète (ex. modification par un skill) :
                le nombre minimal de sujets analysés n'est pas exigé.

Contrôles : schéma, clés de catégories et de tags, dépôts des projets (config/sujets/projets.json), minimums et plafonds
(config/categories.json ; les sujets d'un projet ne comptent pas dans le plafond),
« À retenir » (config/sujets/perimetre.json), dates des sujets, un sujet publié par dépôt, vérification des sources
(bloc « verification », config/sujets/sources.json), journal (motifs, éléments
toujours suivis vérifiés, exclusions respectées), puis rendu du rapport et contrôle du HTML produit
(tools/check_report.py : structure et signaux de langue).
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import MOTIFS, ROOT, STATUTS, TITRE_MAX, VERDICTS, config, load_json, plain, published, verification_requise  # noqa: E402
import check_report  # noqa: E402
import render  # noqa: E402


def check_verification(s, where, day, cfg):
    """Bloc « verification » d'un sujet (voir tools/veille-verification.md)."""
    errs, st, v = [], s.get("statut"), s.get("verification")
    E = errs.append
    if v is None:
        if st == "publie" and verification_requise(s, day, cfg) and not s.get("verification_non_requise"):
            E(f"{where} : sujet publié sans source de référence dans une catégorie à risque : il faut une vérification au verdict « vrai » (tools/veille-verification.md), ou « verification_non_requise » avec la raison si le fait est annoncé par son auteur")
        return errs
    verdict = v.get("verdict")
    if verdict not in VERDICTS: return [f"{where} : verdict de vérification inconnu « {verdict} » ({', '.join(VERDICTS)})"]
    if not v.get("date"): E(f"{where} : vérification sans date")
    if not v.get("resume"): E(f"{where} : vérification sans « resume »")
    if st == "publie" and verdict != "vrai": E(f"{where} : seul un sujet vérifié « vrai » peut être publié (verdict : {verdict})")
    if verdict == "faux" and (st != "ecarte" or s.get("motif") != "infirme"): E(f"{where} : un sujet vérifié « faux » doit être écarté avec le motif « infirme »")
    if verdict == "vrai":
        src = v.get("source") or {}
        if not src.get("nom") or not src.get("nature"): E(f"{where} : vérification sans « source » (nom, nature)")
        aff = v.get("affirmations") or []
        if not aff: E(f"{where} : vérification « vrai » sans affirmation vérifiée")
        for a in aff:
            if not a.get("texte"): E(f"{where} : affirmation vérifiée sans texte")
            if not any(re.match(r"https?://", p.get("url", "")) for p in a.get("preuves", [])): E(f"{where} : affirmation « {plain(a.get('texte', ''))[:50]} » sans preuve (URL)")
    for r in v.get("retirees", []):
        if not r.get("texte") or not r.get("raison"): E(f"{where} : affirmation retirée sans « texte » ou sans « raison »")
    for r in v.get("recoupements", []):
        if not re.match(r"https?://", r.get("url", "")) or not r.get("texte"): E(f"{where} : recoupement sans texte ou sans URL http(s)")
    return errs


def check(path, contre=None, partiel=False):
    cfg = config()
    cats, tags = cfg["categories"], cfg["tags"]
    sj = cfg["sujets"]
    per = sj.get("sujets/perimetre.json", {})
    proj = sj.get("sujets/projets.json", {})
    confs = sj.get("sujets/conferences.json", {})
    errs, warns = [], []
    E, W = errs.append, warns.append
    try:
        day = load_json(path)
    except Exception as e:
        return [f"JSON illisible : {e}"], []
    legacy = (day.get("config") or {}).get("commit") is None and "converti" in json.dumps(day.get("config", {}), ensure_ascii=False)

    # ----- schéma
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day.get("date", "")): E("champ « date » absent ou invalide (AAAA-MM-JJ)")
    elif Path(path).stem != day["date"].replace("-", ""): E(f"le nom du fichier ne correspond pas à la date {day['date']}")
    for f in ("sous_titre", "a_retenir", "sujets", "pied", "executions", "journal"):
        if f not in day: E(f"champ « {f} » manquant")
    if "en_bref" in day: E("champ « en_bref » supprimé : chaque brève devient un sujet de sa catégorie")
    ids = set()
    projets = {p["depot"]: p["nom"] for p in proj.get("projets", [])}
    for i, s in enumerate(day.get("sujets", [])):
        where = s.get("id", f"sujet n°{i + 1}")
        for f in ("id", "categorie", "statut", "titre"):
            if not s.get(f): E(f"{where} : champ « {f} » manquant")
        if s.get("id") in ids: E(f"{where} : identifiant en double")
        if len(plain(s.get("titre", ""))) > TITRE_MAX: E(f"{where} : titre de {len(plain(s['titre']))} caractères, {TITRE_MAX} au plus : « {plain(s['titre'])} »")
        ids.add(s.get("id"))
        c = cats.get(s.get("categorie"))
        if not c:
            E(f"{where} : catégorie inconnue « {s.get('categorie')} »"); continue
        if s.get("id") and not re.fullmatch(re.escape(c["prefixe"]) + r"\d+", s["id"]): E(f"{where} : l'identifiant doit être « {c['prefixe']} » suivi d'un numéro (catégorie {s['categorie']})")
        st = s.get("statut")
        if st not in STATUTS: E(f"{where} : statut inconnu « {st} »")
        if s.get("date"):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["date"]): E(f"{where} : « date » invalide (AAAA-MM-JJ)")
            elif s["date"] > day.get("date", "9999"): E(f"{where} : « date » {s['date']} postérieure au jour du rapport")
        elif not legacy and st in ("publie", "candidat") and s.get("categorie") != "conferences":
            E(f"{where} : « date » manquante (date de parution de la source la plus récente, AAAA-MM-JJ)")
        if st == "ecarte" and s.get("motif") not in MOTIFS: E(f"{where} : un sujet écarté doit avoir un motif parmi {', '.join(MOTIFS)}")
        if st != "ecarte" and s.get("motif"): W(f"{where} : motif « {s['motif']} » sur un sujet non écarté")
        for t in s.get("tags", []):
            k = t if isinstance(t, str) else t.get("tag")
            if k not in tags: E(f"{where} : tag inconnu « {k} »")
        for src in s.get("sources", []):
            if not re.match(r"https?://", src.get("url", "")): E(f"{where} : source sans URL http(s)")
            if not src.get("texte"): E(f"{where} : source sans texte")
        if s.get("depot"):
            if not isinstance(s["depot"], str) or s["depot"] not in projets: E(f"{where} : « depot » doit être un seul dépôt de config/sujets/projets.json (reçu : {s['depot']!r})")
            elif s["categorie"] == "conferences": E(f"{where} : une conférence ne se rattache pas à un projet")
        if st == "publie":
            for f in ("resume", "sources") + (() if s["categorie"] == "conferences" else ("meta",)):
                if not s.get(f): E(f"{where} : sujet publié sans « {f} »")
            if s["categorie"] == "conferences" and not s.get("conference"): E(f"{where} : conférence publiée sans bloc « conference » (dates, lieu, cfp)")
        errs.extend(check_verification(s, where, day, cfg))

    # ----- volumes
    pub = published(day)
    for k, c in cats.items():
        n = sum(1 for s in pub if s["categorie"] == k)
        hors_projets = sum(1 for s in pub if s["categorie"] == k and not s.get("depot"))
        if c.get("min") and n < c["min"]: E(f"catégorie « {c['label']} » : {n} sujet(s) publié(s), minimum {c['min']}")
        if c.get("max") is not None and hors_projets > c["max"]: E(f"catégorie « {c['label']} » : {hors_projets} sujet(s) publié(s) hors projets, plafond {c['max']}")
    rap = per.get("rapport", {})
    ar = day.get("a_retenir", [])
    for name, lst, rule in (("À retenir", ar, rap.get("a_retenir", {})),):
        if rule.get("min") and len(lst) < rule["min"]: E(f"« {name} » : {len(lst)} élément(s), minimum {rule['min']}")
        if rule.get("max") and len(lst) > rule["max"]: E(f"« {name} » : {len(lst)} élément(s), maximum {rule['max']}")
    pub_ids = {s["id"] for s in pub}
    for x in ar:
        for ref in x.get("sujets", []):
            if ref not in pub_ids: E(f"« À retenir » référence {ref}, qui n'est pas un sujet publié")

    # ----- journal (pas exigé pour un jour converti depuis l'ancien format)
    j = day.get("journal", {})
    if not legacy:
        if not j.get("recherches"): E("journal : « recherches » (nombre de requêtes par catégorie) manquant")
        if not partiel and len(day.get("sujets", [])) < rap.get("analyses_min", 0):
            E(f"journal : {len(day.get('sujets', []))} sujet(s) analysé(s), minimum {rap['analyses_min']} (tous statuts)")
        if not day.get("executions"): E("aucune exécution consignée")
        verified = {plain(v.get("nom", "")).lower() for v in j.get("verifications", [])} | {plain(s["titre"]).lower() for s in day.get("sujets", [])}
        for item in confs.get("toujours_suivre", []) + [x for f, d in sj.items() if "/recherche/" in f for x in d.get("toujours_suivre", [])]:
            n = item["nom"].lower()
            if not any(n in v for v in verified): E(f"journal : « {item['nom']} » est toujours suivi mais n'a pas été vérifié (ajouter une entrée dans journal.verifications)")
    for item in confs.get("exclure", []) + [x for f, d in sj.items() if "/recherche/" in f for x in d.get("exclure", [])] + proj.get("exclure", []):
        n = item["nom"].lower()
        for s in pub:
            if n in plain(s["titre"]).lower(): E(f"{s['id']} : « {item['nom']} » est exclu par la configuration mais publié")

    # ----- immuabilité des sujets publiés
    if contre:
        rel = Path(path).resolve().relative_to(ROOT).as_posix()
        old = subprocess.run(["git", "-C", str(ROOT), "show", f"{contre}:{rel}"], capture_output=True, text=True)
        if old.returncode == 0:
            strip = lambda s: {k: v for k, v in s.items() if k != "historique"}
            now = {s["id"]: s for s in day.get("sujets", [])}
            for s in json.loads(old.stdout).get("sujets", []):
                if s.get("statut") != "publie":
                    continue
                cur = now.get(s["id"])
                if cur is None: E(f"immuabilité : le sujet publié {s['id']} a disparu")
                elif strip(cur) != strip(s): E(f"immuabilité : le sujet publié {s['id']} a été modifié ou dépublié")

    # ----- rendu et contrôle du HTML produit
    if not errs and pub:
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
            f.write(render.render_report(day, cfg))
        e2, w2 = check_report.check(f.name)
        errs += [f"rendu : {e}" for e in e2]
        warns += [f"langue : {w}" for w in w2]
    return errs, warns


if __name__ == "__main__":
    args = sys.argv[1:]
    contre = args[args.index("--contre") + 1] if "--contre" in args else None
    files = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] != "--contre")]
    bad = 0
    for p in files:
        e, w = check(p, contre, "--partiel" in args)
        print(("OK   " if not e else "ERREURS ") + p)
        for x in e: print("   -", x)
        for x in w: print("   ?", x)
        bad += bool(e)
    sys.exit(1 if bad else 0)
