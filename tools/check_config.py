#!/usr/bin/env python3
"""Vérifie la cohérence de la configuration de la veille (config/). Code retour 1 en cas d'erreur.

  python3 tools/check_config.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import CONFIG, load_json  # noqa: E402


def check():
    errs = []
    add = errs.append
    try:
        cats, tags, index = (load_json(CONFIG / f) for f in ("categories.json", "tags.json", "sujets.json"))
    except Exception as e:  # JSON invalide
        return [f"lecture impossible : {e}"]
    for k, c in cats.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", k): add(f"categories.json : clé invalide « {k} »")
        for f in ("label", "carte", "classe", "prefixe", "ordre", "description"):
            if f not in c: add(f"categories.json : {k} sans « {f} »")
        if c.get("max") is not None and c.get("min", 0) > c["max"]: add(f"categories.json : {k} a min > max")
    if len({c.get("ordre") for c in cats.values()}) != len(cats): add("categories.json : deux catégories ont le même ordre")
    if len({c.get("prefixe") for c in cats.values()}) != len(cats): add("categories.json : deux catégories ont le même préfixe d'identifiant")
    for k, t in tags.items():
        if not re.fullmatch(r"[a-z][a-z0-9-]*", k): add(f"tags.json : clé invalide « {k} »")
        for f in ("label", "classe", "description"):
            if f not in t: add(f"tags.json : {k} sans « {f} »")
    listed = set()
    for f in index.get("fichiers", []):
        p = CONFIG / f["chemin"]
        listed.add(p.resolve())
        if not p.exists():
            add(f"sujets.json : fichier listé introuvable « {f['chemin']} »"); continue
        try:
            d = load_json(p)
        except Exception as e:
            add(f"{f['chemin']} : JSON invalide ({e})"); continue
        if "/recherche/" in f["chemin"]:
            if d.get("categorie") not in cats: add(f"{f['chemin']} : catégorie inconnue « {d.get('categorie')} »")
            for champ in ("consigne", "sources", "toujours_suivre", "exclure"):
                if champ not in d: add(f"{f['chemin']} : champ « {champ} » manquant")
    for p in (CONFIG / "sujets").rglob("*.json"):
        if p.resolve() not in listed: add(f"{p.relative_to(CONFIG)} : présent mais absent de l'index sujets.json")
    per = CONFIG / "sujets" / "perimetre.json"
    src = CONFIG / "sujets" / "sources.json"
    v = load_json(src).get("verification") if src.exists() else None
    if v:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.get("depuis", "")): add("sources.json : verification.depuis doit être une date AAAA-MM-JJ")
        for k in v.get("categories_a_risque", {}).get("categories", []):
            if k not in cats: add(f"sources.json : catégorie à risque inconnue « {k} »")
        for g, d in v.get("references", {}).items():
            for dom in d.get("domaines", []):
                if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}(/[\w./-]+)?", dom): add(f"sources.json : référence « {g} » : domaine invalide « {dom} » (sans https://, ex. lemonde.fr ou github.com/dotnet)")
    proj = CONFIG / "sujets" / "projets.json"
    if proj.exists():
        for pr in load_json(proj).get("projets", []):
            if not re.fullmatch(r"Reefact/[\w.-]+", pr.get("depot", "")): add(f"projets.json : dépôt invalide pour {pr.get('nom')}")
            if pr.get("depot", "").split("/")[-1] != pr.get("nom"): add(f"projets.json : le nom « {pr.get('nom')} » ne correspond pas au dépôt « {pr.get('depot')} »")
            if not pr.get("theme"): add(f"projets.json : {pr.get('nom')} sans « theme »")
    return errs


if __name__ == "__main__":
    e = check()
    print("configuration : OK" if not e else "configuration : ERREURS\n  - " + "\n  - ".join(e))
    sys.exit(1 if e else 0)
