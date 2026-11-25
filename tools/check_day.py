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
from datetime import date as Date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from veille_lib import MOTIFS, ROOT, STATUTS, TITRE_MAX, day_files, pourquoi_types, sections_resume, VERDICTS, config, load_json, plain, published, verification_requise  # noqa: E402
import check_front  # noqa: E402
import check_report  # noqa: E402
import render  # noqa: E402


def longueur_resume(ar):
    """Longueur de « À retenir » : texte affiché des paragraphes (sans Markdown ni titres de section, qui viennent de la config)."""
    return sum(len(plain(p)) for x in ar for p in x.get("paragraphes", []) if isinstance(p, str))


def deja_publies(day):
    """URL des sources des sujets publiés les jours précédents : url → date de publication."""
    out = {}
    for p in day_files():
        if p.stem >= day["date"].replace("-", ""):
            continue
        d = load_json(p)
        for s in d.get("sujets", []):
            if s.get("statut") == "publie":
                for u in s.get("sources", []):
                    out.setdefault(u.get("url"), d["date"])
    return out


def rapport_precedent(day):
    """Date du rapport précédent (fichier du jour antérieur le plus récent), sinon la veille : c'est le seuil du repère ☄️."""
    avant = [p.stem for p in day_files() if p.stem < day["date"].replace("-", "")]
    if avant:
        a = max(avant)
        return f"{a[:4]}-{a[4:6]}-{a[6:]}"
    return (Date.fromisoformat(day["date"]) - timedelta(days=1)).isoformat()


CHAMPS_SUJET = {"id", "categorie", "statut", "motif", "tags", "titre", "titre_sommaire", "resume", "pourquoi", "sources", "meta", "date",
                "details", "depot", "conference", "verification", "verification_non_requise", "historique", "note",
                "categorie_secondaire", "hors_fenetre", "choix"}


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
        for f in sorted(set(s) - CHAMPS_SUJET): E(f"{where} : champ « {f} » inconnu (libellés, tags et projets viennent uniquement de config/)")
        if len(plain(s.get("titre", ""))) > TITRE_MAX: E(f"{where} : titre de {len(plain(s['titre']))} caractères, {TITRE_MAX} au plus : « {plain(s['titre'])} »")
        ids.add(s.get("id"))
        c = cats.get(s.get("categorie"))
        if not c:
            E(f"{where} : catégorie inconnue « {s.get('categorie')} »"); continue
        if s.get("id") and not re.fullmatch(re.escape(c["prefixe"]) + r"\d+", s["id"]): E(f"{where} : l'identifiant doit être « {c['prefixe']} » suivi d'un numéro (catégorie {s['categorie']})")
        pq = s.get("pourquoi")
        if pq is not None:
            types = pourquoi_types(cfg)
            if not isinstance(pq, dict) or set(pq) != {"type", "texte"} or not str(pq.get("texte", "")).strip():
                E(f"{where} : « pourquoi » doit être {{\"type\": …, \"texte\": …}} (le préfixe vient de la configuration)")
            elif pq["type"] not in types:
                E(f"{where} : type de « pourquoi » inconnu « {pq['type']} » ({', '.join(types)})")
            else:
                if pq["type"] == "projet" and not s.get("depot"): E(f"{where} : « pourquoi » de type projet sans « depot »")
                if s.get("depot") and pq["type"] != "projet": E(f"{where} : sujet rattaché à un projet : le « pourquoi » est de type projet")
                debut = plain(pq["texte"]).lower()
                for t in types.values():
                    if debut.startswith(t["prefixe"].split("{")[0].strip().lower()): E(f"{where} : le texte du « pourquoi » reprend le préfixe « {t['prefixe']} », que le rendu ajoute déjà")
        if day.get("date", "") >= (per.get("rapport", {}).get("choix") or {}).get("depuis", "9999") and not str(s.get("choix") or "").strip():
            E(f"{where} : « choix » manquant (pourquoi ce sujet est {s.get('statut')}, en s'appuyant sur tes préférences quand c'est le cas)")
        sec = s.get("categorie_secondaire")
        if sec is not None:
            if not isinstance(sec, str) or sec not in cats: E(f"{where} : catégorie secondaire « {sec} » absente de config/categories.json (une seule, 2 catégories au plus)")
            elif sec == s["categorie"]: E(f"{where} : catégorie secondaire identique à la principale")
            elif "conferences" in (sec, s["categorie"]): E(f"{where} : pas de catégorie secondaire avec les conférences")
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
            if s["categorie"] == "conferences" and not s.get("conference"): E(f"{where} : conférence publiée sans bloc « conference » (dates, lieu, cfp, site)")
        if s["categorie"] == "conferences" and st != "ecarte" and not re.match(r"https?://", (s.get("conference") or {}).get("site", "")):
            E(f"{where} : conférence sans « conference.site » (lien vers le site officiel, même si le CFP passe par Sessionize ou un autre service)")
        errs.extend(check_verification(s, where, day, cfg))

    # ----- volumes : 15 publiés au plus hors prioritaires ; les prioritaires (alerte récente, rappel) s'ajoutent, hors plafonds
    pub = published(day)
    rap = per.get("rapport", {})
    seuil = rapport_precedent(day)
    tagset = lambda s: {t if isinstance(t, str) else t.get("tag") for t in s.get("tags", [])}
    prio = [s for s in pub if ("alerte" in tagset(s) and (s.get("date") or "") >= seuil) or "rappel" in tagset(s)]
    autres = [s for s in pub if s not in prio]
    cap = rap.get("max_publies")
    if cap and not legacy and len(autres) > cap:
        E(f"{len(autres)} sujets publiés hors prioritaires (alerte récente, rappel) : {cap} au plus")
    for k, c in cats.items():
        n = sum(1 for s in pub if s["categorie"] == k)
        hors_prio = sum(1 for s in autres if s["categorie"] == k)
        if c.get("min") and n < c["min"]: E(f"catégorie « {c['label']} » : {n} sujet(s) publié(s), minimum {c['min']}")
        if c.get("max") is not None and not legacy and hors_prio > c["max"]: E(f"catégorie « {c['label']} » : {hors_prio} sujet(s) publié(s) hors prioritaires, plafond {c['max']}")
    # ----- découverte : nombre de sujets de découverte publiés, consigné dans le journal (à partir de la date des raisons de choix)
    if not legacy and day.get("date", "") >= (rap.get("choix") or {}).get("depuis", "9999"):
        n_dec = sum(1 for s in pub if str(s.get("choix") or "").startswith("Découverte"))
        if not isinstance(day.get("journal", {}).get("decouverte"), int): E("journal : « decouverte » manquant (nombre de sujets de découverte publiés)")
        elif day["journal"]["decouverte"] != n_dec: E(f"journal : « decouverte » vaut {day['journal']['decouverte']}, mais {n_dec} sujet(s) publié(s) ont un choix « Découverte : … »")
        places = (rap.get("gouts") or {}).get("decouverte_places")
        if places and n_dec > places: E(f"{n_dec} sujets de découverte publiés : {places} places au plus")
    # ----- fraîcheur et anti-doublon (config/sujets/perimetre.json → rapport.fraicheur)
    if not legacy:
        fr = rap.get("fraicheur", {})
        deja = deja_publies(day)
        for s in pub:
            tg = tagset(s)
            if "mise-a-jour" not in tg and "rappel" not in tg:
                vus = [u["url"] for u in s.get("sources", []) if u.get("url") in deja]
                if vus: E(f"{s['id']} : déjà publié le {deja[vus[0]]} ({vus[0]}) : un sujet ne revient qu'avec le tag mise-a-jour")
            if s["categorie"] == "conferences" or s.get("hors_fenetre") or not s.get("date"):
                continue
            cs = {s["categorie"]} | ({s["categorie_secondaire"]} if isinstance(s.get("categorie_secondaire"), str) else set())
            fond = bool(cs & set(fr.get("fond_categories", [])) or tg & set(fr.get("fond_tags", [])))
            if cs & set(fr.get("pas_de_fond_categories", [])) or tg & set(fr.get("pas_de_fond_tags", [])):
                fond = False                                                       # l'IA change trop vite : toujours une actualité
            jours = fr.get("fond_jours", 14) if fond else fr.get("actualites_jours", 7)
            limite = (Date.fromisoformat(day["date"]) - timedelta(days=jours)).isoformat()
            if s["date"] < limite: E(f"{s['id']} : publié mais daté du {s['date']}, au-delà de {jours} jours ({'sujet de fond' if fond else 'actualité'}) : candidat, ou raison dans « hors_fenetre »")
    rap = per.get("rapport", {})
    ar = day.get("a_retenir", [])
    rule = rap.get("a_retenir", {})
    pub_ids = {s["id"] for s in pub}
    if not legacy or ar and "section" in ar[0]:
        ordre = list(sections_resume(cfg))
        if len(ar) < rule.get("min_sections", 1): E(f"« À retenir » : {len(ar)} section(s), minimum {rule.get('min_sections', 1)}")
        vues = []
        for x in ar:
            k = x.get("section")
            if k not in ordre: E(f"« À retenir » : section « {k} » inconnue (urgent, aussi ou une clé de config/categories.json)"); continue
            if k in vues: E(f"« À retenir » : section « {k} » en double")
            vues.append(k)
            if not x.get("paragraphes") or not all(isinstance(p, str) and p.strip() for p in x["paragraphes"]): E(f"« À retenir » : section « {k} » sans paragraphe")
            if set(x) - {"section", "paragraphes", "sujets"}: E(f"« À retenir » : section « {k} » avec un champ inconnu ({', '.join(sorted(set(x) - {'section', 'paragraphes', 'sujets'}))})")
        if vues != sorted(vues, key=ordre.index): E("« À retenir » : sections dans le désordre (urgent, puis l'ordre des catégories, puis aussi)")
        n = longueur_resume(ar)
        if rule.get("max_caracteres") and n > rule["max_caracteres"]:
            E(f"« À retenir » : {n} caractères, {rule['max_caracteres']} au plus (texte des paragraphes, sans le Markdown ni les titres de section)")
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
    # ----- cohérence avec config/ : rien d'affiché qui ne soit déclaré (catégories, tags, projets, filtres)
    if not errs:
        for nom, page in (("rapport", render.render_report(day, cfg)), ("dossier", render.render_dossier(day, cfg))):
            errs += [f"front : {e}" for e in check_front.check(page, cfg, nom)]
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
