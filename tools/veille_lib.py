"""Fonctions partagées par les outils de la veille : configuration, fichiers du jour, Markdown simple, dates."""
import html
import json
import re
from datetime import date as Date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DAYS = ROOT / "data" / "days"
SUFFIX = " – Reefact"          # suffixe des <title> (tiret demi-cadratin, comme reefact.net)
STATUTS = ("publie", "candidat", "ecarte")
MOTIFS = ("deja-publie", "hors-fenetre", "hors-perimetre", "non-verifiable", "doublon", "trop-mineur",
          "plafond-atteint", "exclu-config", "rien-de-neuf", "infirme")
TITRE_MAX = 72                               # longueur maximale d'un titre de sujet (texte affiché, sans Markdown)
VERDICTS = ("vrai", "faux", "indetermine")   # « indetermine » : seulement sur un sujet non publié, à revérifier
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


# ---------- configuration ----------
def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def config():
    """Catégories, tags et sujets (index + fichiers actifs)."""
    cats = load_json(CONFIG / "categories.json")
    tags = load_json(CONFIG / "tags.json")
    index = load_json(CONFIG / "sujets.json")
    sujets = {f["chemin"]: load_json(CONFIG / f["chemin"]) for f in index["fichiers"] if f.get("actif", True)}
    return {"categories": cats, "tags": tags, "index": index, "sujets": sujets}


def projets(cfg):
    """Tes projets (config/sujets/projets.json), par dépôt « Reefact/<nom> »."""
    return {p["depot"]: p for p in (cfg["sujets"].get("sujets/projets.json") or {}).get("projets", [])}


def categories_de(sujet):
    """Catégories d'un sujet : la principale, puis la secondaire éventuelle (2 au plus)."""
    sec = sujet.get("categorie_secondaire")
    return [sujet["categorie"]] + ([sec] if isinstance(sec, str) and sec else [])


def fraicheur_cfg(cfg):
    """Règles de fraîcheur (config/sujets/perimetre.json → rapport.fraicheur)."""
    return ((cfg["sujets"].get("sujets/perimetre.json") or {}).get("rapport") or {}).get("fraicheur") or {}


def profil_fraicheur(sujet, cfg):
    """(clé, profil) de fraîcheur d'un sujet : le premier de « priorite » donné par une de ses catégories
    (config/categories.json → fraicheur) ou un de ses tags (config/tags.json → fraicheur) ; à défaut, « defaut »."""
    fr = fraicheur_cfg(cfg)
    profils = fr.get("profils", {})
    donnes = {(cfg["categories"].get(c) or {}).get("fraicheur") for c in categories_de(sujet) if isinstance(c, str)}
    donnes |= {(cfg["tags"].get(t if isinstance(t, str) else t.get("tag")) or {}).get("fraicheur") for t in sujet.get("tags", [])}
    cle = next((k for k in fr.get("priorite", []) if k in donnes), fr.get("defaut"))
    return cle, profils.get(cle, {})


def froid_apres(sujet, cfg, jour):
    """Seuil (en jours) dépassé par un sujet paru il y a plus de froid_apres_jours de son profil, sinon None."""
    if not sujet.get("date") or not jour:
        return None
    seuil = profil_fraicheur(sujet, cfg)[1].get("froid_apres_jours")
    if seuil is None or (Date.fromisoformat(jour[:10]) - Date.fromisoformat(sujet["date"][:10])).days <= seuil:
        return None
    return seuil


def pourquoi_types(cfg):
    """Types de ligne « pourquoi » (config/sujets/perimetre.json → pourquoi.types) : clé → {emoji, prefixe, definition}."""
    return ((cfg["sujets"].get("sujets/perimetre.json") or {}).get("pourquoi") or {}).get("types", {})


def pourquoi_prefixe(s, cfg):
    """(emoji, préfixe) affichés devant la ligne « pourquoi » d'un sujet, ou None si le type est inconnu."""
    t = pourquoi_types(cfg).get((s.get("pourquoi") or {}).get("type") if isinstance(s.get("pourquoi"), dict) else None)
    if not t:
        return None
    nom = (projets(cfg).get(s.get("depot")) or {}).get("nom") or (s.get("depot") or "").split("/")[-1]
    return t["emoji"], t["prefixe"].replace("{projet}", nom)


def sections_resume(cfg):
    """Sections possibles de « À retenir », dans l'ordre d'affichage : clé → (emoji, titre)."""
    rap = (cfg["sujets"].get("sujets/perimetre.json") or {}).get("rapport", {}).get("a_retenir", {})
    spe = rap.get("sections_speciales", {})
    out = {}
    if "urgent" in spe: out["urgent"] = (spe["urgent"]["emoji"], spe["urgent"]["titre"])
    for k in ordered_categories(cfg["categories"]):
        out[k] = (cfg["categories"][k].get("emoji", ""), cfg["categories"][k]["label"])
    if "aussi" in spe: out["aussi"] = (spe["aussi"]["emoji"], spe["aussi"]["titre"])
    return out


def ordered_categories(cats):
    return sorted(cats, key=lambda k: cats[k]["ordre"])


# ---------- vérification des sources ----------
def verif_config(cfg):
    return (cfg["sujets"].get("sujets/sources.json") or {}).get("verification") or {}


def est_reference(url, cfg):
    """L'URL relève-t-elle d'une source de référence (config/sujets/sources.json → verification.references) ?
    Une entrée « domaine » couvre le domaine et ses sous-domaines ; une entrée « domaine/chemin » couvre ce chemin."""
    m = re.match(r"https?://([^/?#]+)([^?#]*)", url or "")
    if not m:
        return False
    host = m.group(1).lower().split(":")[0].removeprefix("www.")
    path = m.group(2).rstrip("/")
    for groupe in verif_config(cfg).get("references", {}).values():
        for d in groupe.get("domaines", []):
            dom, _, chemin = d.lower().partition("/")
            if host != dom and not host.endswith("." + dom):
                continue
            if not chemin or path == "/" + chemin or path.startswith("/" + chemin + "/"):
                return True
    return False


def verification_requise(sujet, day, cfg):
    """Vrai si la règle automatique impose une vérification : jour postérieur à la mise en place, catégorie à risque,
    aucune source de référence. (L'agent de veille peut en demander une dans d'autres cas : c'est son jugement.)"""
    v = verif_config(cfg)
    if not v or day.get("date", "") < v.get("depuis", "9999"):
        return False
    if not set(categories_de(sujet)) & set(v.get("categories_a_risque", {}).get("categories", [])):
        return False
    return not any(est_reference(s.get("url"), cfg) for s in sujet.get("sources", []))


# ---------- fichiers du jour ----------
def day_files():
    return sorted(DAYS.glob("[0-9][0-9][0-9][0-9]/[0-9]*.json"))


def day_path(iso):
    return DAYS / iso[:4] / (iso.replace("-", "") + ".json")


def write_day(path, day):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(day, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def published(day, key="sujets"):
    return [s for s in day.get(key, []) if s.get("statut") == "publie"]


# ---------- dates ----------
def titre_jour(iso):
    d = Date.fromisoformat(iso)
    jour = "1er" if d.day == 1 else str(d.day)
    return f"Veille technologique du {JOURS[d.weekday()]} {jour} {MOIS[d.month - 1]} {d.year}"


# ---------- Markdown simple (gras, code, liens ; paragraphes et listes) ----------
_TOKEN = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|\[([^\]]+)\]\(([^)\s]+)\)", re.S)


def inline(md):
    """Texte Markdown simple → HTML : **gras**, `code`, [texte](url). Tout le reste est échappé.
    Les liens externes s'ouvrent dans un nouvel onglet."""
    out, pos = [], 0
    for m in _TOKEN.finditer(md):
        out.append(html.escape(md[pos:m.start()], quote=False))
        if m.group(1) is not None:
            out.append(f"<code>{html.escape(m.group(1), quote=False)}</code>")
        elif m.group(2) is not None:
            out.append(f"<strong>{inline(m.group(2))}</strong>")
        else:
            url = m.group(4)
            ext = ' target="_blank" rel="noopener"' if re.match(r"https?://", url) else ""
            out.append(f'<a href="{html.escape(url)}"{ext}>{inline(m.group(3))}</a>')
        pos = m.end()
    out.append(html.escape(md[pos:], quote=False))
    return "".join(out)


def blocks(md, indent="  "):
    """Paragraphes séparés par une ligne vide ; lignes « - » consécutives = liste à puces."""
    res = []
    for chunk in re.split(r"\n\s*\n", (md or "").strip()):
        lines = [l for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        if all(l.lstrip().startswith("- ") for l in lines):
            items = "\n".join(f"{indent}  <li>{inline(l.lstrip()[2:].strip())}</li>" for l in lines)
            res.append(f"{indent}<ul>\n{items}\n{indent}</ul>")
        else:
            res.append(f"{indent}<p>{inline(' '.join(l.strip() for l in lines))}</p>")
    return res


def plain(md):
    """Markdown simple → texte brut (pour le flux, la mémoire, les contrôles)."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md or "")
    t = t.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", re.sub(r"^\s*- ", "", t, flags=re.M)).strip()


def urls(sujet):
    """Toutes les URL d'un sujet (sources + liens dans le texte)."""
    found = [s["url"] for s in sujet.get("sources", [])]
    for field in ("resume", "pourquoi", "texte"):
        v = sujet.get(field)
        v = v.get("texte") if isinstance(v, dict) else v
        found += re.findall(r"\]\((https?://[^)\s]+)\)", v or "")
    for v in (sujet.get("details") or {}).values():
        found += re.findall(r"\]\((https?://[^)\s]+)\)", v)
    return found
