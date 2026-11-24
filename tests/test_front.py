"""Tests du contrôle de cohérence config ↔ front (tools/check_front.py) : il doit accepter le rendu réel et refuser
tout libellé, tag, catégorie ou projet qui ne vient pas de config/.

  python3 -m unittest discover -s tests
"""
import copy
import html
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import check_day  # noqa: E402
import check_front  # noqa: E402
import render  # noqa: E402
from veille_lib import config, day_files, load_json  # noqa: E402


def jour():
    """Un jour de test : de préférence avec un sujet de projet publié, et le plus de sujets publiés (catégories, tags variés)."""
    return max((load_json(p) for p in day_files()),
               key=lambda d: (any(s.get("depot") and s["statut"] == "publie" for s in d["sujets"]), sum(s["statut"] == "publie" for s in d["sujets"])))


def avec_publies(day, n_autres, n_prio=0):
    """Remplace les sujets publiés du jour par n_autres sujets ordinaires et n_prio alertes récentes (clones numérotés)."""
    import copy as cp
    modele = next(s for s in day["sujets"] if s["statut"] == "publie" and s["categorie"] not in ("conferences",) and not s.get("depot"))
    cat = day["sujets"]
    day["sujets"] = [s for s in cat if s["statut"] != "publie"]
    prefixes = {"dotnet": "n", "ia": "i", "craftsmanship": "cr", "architecture": "p", "securite": "s"}
    repartition = ["dotnet"] * 4 + ["ia"] * 4 + ["craftsmanship"] * 4 + ["architecture"] * 3 + ["securite"] * 2
    for k in range(n_autres + n_prio):
        s = cp.deepcopy(modele)
        c = "securite" if k >= n_autres else repartition[k % len(repartition)]
        s.update({"id": f"{prefixes[c]}{900 + k}", "categorie": c, "date": day["date"], "tags": ["alerte"] if k >= n_autres else []})
        s.pop("categorie_secondaire", None); s.pop("verification", None); s.pop("verification_non_requise", None)
        day["sujets"].append(s)
    day["a_retenir"] = [{"section": "urgent", "paragraphes": ["x"], "sujets": []}]
    return day


class Front(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config()
        cls.day = jour()

    def rendu(self, day=None, cfg=None):
        day, cfg = day or self.day, cfg or self.cfg
        return render.render_report(day, cfg), render.render_dossier(day, cfg)

    def erreurs(self, pages, cfg=None):
        return [e for p in pages for e in check_front.check(p, cfg or self.cfg)]

    def test_rendu_reel_conforme(self):
        rapport, dossier = self.rendu()
        self.assertEqual(self.erreurs([rapport, dossier]), [])
        self.assertGreater(rapport.count('<details class="card"'), 0)

    def test_tous_les_blocs_sont_controles(self):
        rapport, _ = self.rendu()
        n = rapport.count('<details class="card"')
        faux = rapport.replace('<span class="badges">', '<span class="badges"><span class="badge b-new" title="x">Inventé</span>')
        blocs = {e.split(" : ")[1] for e in self.erreurs([faux]) if "badge de catégorie" in e}
        self.assertEqual(len(blocs), n)

    def test_libelle_de_categorie_different(self):
        rapport, _ = self.rendu()
        c = next(iter(self.cfg["categories"].values()))
        avant = f'>{html.escape(c["label"], quote=False)}</span>'
        self.assertIn(avant, rapport)
        faux = rapport.replace(avant, '>Autre chose</span>', 1)
        self.assertTrue(any("badge de catégorie" in e for e in self.erreurs([faux])))

    def test_categorie_non_declaree(self):
        cfg = copy.deepcopy(self.cfg)
        k = next(iter(cfg["categories"]))
        cfg["categories"]["renommee"] = cfg["categories"].pop(k)
        rapport, _ = self.rendu()
        self.assertTrue(any("absente de config/categories.json" in e for e in self.erreurs([rapport], cfg)))

    def test_categorie_secondaire_affichee_et_filtrable(self):
        day = copy.deepcopy(self.day)
        s = next(s for s in day["sujets"] if s["statut"] == "publie" and not s.get("categorie_secondaire") and s["categorie"] != "conferences")
        autre = next(k for k in self.cfg["categories"] if k not in (s["categorie"], "conferences"))
        s["categorie_secondaire"] = autre
        rapport, _ = self.rendu(day)
        self.assertEqual(self.erreurs([rapport]), [])
        self.assertIn(f'data-cat="{s["categorie"]} {autre}"', rapport)
        faux = rapport.replace(f'data-cat="{s["categorie"]} {autre}"', f'data-cat="{s["categorie"]} {autre} ia"', 1)
        self.assertTrue(any("1 ou 2 attendues" in e for e in self.erreurs([faux])))

    def test_titre_de_section_invente(self):
        rapport, _ = self.rendu()
        self.assertIn('class="tl-h"', rapport)
        faux = rapport.replace("À ne pas manquer</h3>", "Urgentissime</h3>", 1)
        self.assertTrue(any("titrée" in e for e in self.erreurs([faux])))

    def test_prefixe_de_pourquoi_invente(self):
        rapport, _ = self.rendu()
        self.assertIn('class="why" data-type="compte"', rapport)
        faux = rapport.replace("Pourquoi ça compte pour toi :", "Ça te parle :", 1)
        self.assertTrue(any("ne commence pas par" in e for e in self.erreurs([faux])))

    def test_tag_non_declare(self):
        rapport, _ = self.rendu()
        faux = rapport.replace('data-tags="', 'data-tags="invente ', 1)
        self.assertTrue(any("tag « invente » absent" in e for e in self.erreurs([faux])))

    def test_tag_affiche_avec_un_autre_libelle(self):
        day = copy.deepcopy(self.day)
        s = next(s for s in day["sujets"] if s["statut"] == "publie")
        s["tags"] = s.get("tags", []) + ["nouveau"]
        rapport, _ = self.rendu(day)
        self.assertIn(">#nouveau</span>", rapport)
        faux = rapport.replace(">#nouveau</span>", ">#tout-neuf</span>")
        self.assertTrue(any("tag « nouveau »" in e for e in self.erreurs([faux])))

    def test_infobulle_de_tag_emoji_dependant_du_sujet(self):
        day = copy.deepcopy(self.day)
        s = next(s for s in day["sujets"] if s["statut"] == "publie")
        s["tags"] = s.get("tags", []) + ["pepite"]
        rapport, _ = self.rendu(day)
        faux = rapport.replace('title="Pépite : ', 'title="Pépite propre au sujet : ', 1)
        self.assertTrue(any("tag « pepite »" in e for e in self.erreurs([faux])))

    def test_projet_non_declare(self):
        rapport, _ = self.rendu()
        faux = rapport.replace('data-repo="Reefact/', 'data-repo="Reefact/inconnu-', 1)
        self.assertTrue(any("absent de config/sujets/projets.json" in e for e in self.erreurs([faux])))

    def test_puce_de_filtre_inventee(self):
        rapport, _ = self.rendu()
        faux = rapport.replace('<span class="chips"><button type="button" class="chip',
                               '<span class="chips"><button type="button" class="chip b-new" data-v="fantome" aria-pressed="false">Fantôme <span class="n">1</span></button><button type="button" class="chip', 1)
        self.assertTrue(any("« fantome » non déclarée" in e for e in self.erreurs([faux])))

    def test_libelle_de_filtre_different(self):
        rapport, _ = self.rendu()
        k, c = next(iter(self.cfg["categories"].items()))
        if f'data-v="{k}"' not in rapport:
            self.skipTest("catégorie absente du jour")
        avant = f'{html.escape(c["label"], quote=False)} <span class="n">'
        self.assertIn(avant, rapport)
        faux = rapport.replace(avant, 'Libellé maison <span class="n">', 1)
        self.assertTrue(any("au lieu du libellé déclaré" in e for e in self.erreurs([faux])))


class Donnees(unittest.TestCase):
    """Le validateur du fichier du jour refuse ce qui n'est pas déclaré."""

    def valider(self, day):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / day["date"][:4] / (day["date"].replace("-", "") + ".json")
            p.parent.mkdir()
            p.write_text(json.dumps(day, ensure_ascii=False), encoding="utf-8")
            return check_day.check(p, None, partiel=True)[0]

    def test_libelle_de_carte_propre_refuse(self):
        day = jour()
        day["sujets"][0]["etiquette"] = "Autre"
        self.assertTrue(any("« etiquette » inconnu" in e for e in self.valider(day)))

    def test_tag_inconnu_refuse(self):
        day = jour()
        day["sujets"][0]["tags"] = ["invente"]
        self.assertTrue(any("tag inconnu" in e for e in self.valider(day)))

    def test_categorie_inconnue_refusee(self):
        day = jour()
        day["sujets"][0]["categorie"] = "api"
        self.assertTrue(any("catégorie inconnue" in e for e in self.valider(day)))

    def test_categorie_secondaire_inconnue_refusee(self):
        day = jour()
        day["sujets"][0]["categorie_secondaire"] = "inventee"
        self.assertTrue(any("catégorie secondaire" in e for e in self.valider(day)))

    def test_trois_categories_impossible(self):
        day = jour()
        day["sujets"][0]["categorie_secondaire"] = ["ia", "dotnet"]
        self.assertTrue(any("catégorie secondaire" in e for e in self.valider(day)))

    def test_section_de_resume_inconnue_refusee(self):
        day = jour()
        day["a_retenir"] = [{"section": "divers", "paragraphes": ["x"], "sujets": []}]
        self.assertTrue(any("section « divers » inconnue" in e for e in self.valider(day)))

    def test_sections_de_resume_dans_le_desordre(self):
        day = jour()
        day["a_retenir"] = [{"section": "ia", "paragraphes": ["x"], "sujets": []}, {"section": "urgent", "paragraphes": ["y"], "sujets": []}]
        self.assertTrue(any("désordre" in e for e in self.valider(day)))

    def test_resume_trop_long_refuse(self):
        day = jour()
        day["a_retenir"] = [{"section": "urgent", "paragraphes": ["x" * 1901], "sujets": []}]
        self.assertTrue(any("1900 au plus" in e for e in self.valider(day)))

    def test_resume_a_la_limite_accepte(self):
        day = jour()
        day["a_retenir"] = [{"section": "urgent", "paragraphes": ["**" + "x" * 1900 + "**"], "sujets": []}]
        self.assertFalse(any("caractères" in e for e in self.valider(day)))

    def test_pourquoi_sans_type_refuse(self):
        day = jour()
        s = next(x for x in day["sujets"] if x.get("pourquoi"))
        s["pourquoi"] = "Pourquoi ça compte pour toi : texte libre"
        self.assertTrue(any("« pourquoi » doit être" in e for e in self.valider(day)))

    def test_pourquoi_type_inconnu_refuse(self):
        day = jour()
        s = next(x for x in day["sujets"] if x.get("pourquoi"))
        s["pourquoi"] = {"type": "important", "texte": "x"}
        self.assertTrue(any("type de « pourquoi » inconnu" in e for e in self.valider(day)))

    def test_pourquoi_qui_repete_le_prefixe_refuse(self):
        day = jour()
        s = next(x for x in day["sujets"] if x.get("pourquoi") and not x.get("depot"))
        s["pourquoi"] = {"type": "compte", "texte": "Pourquoi ça compte pour toi : x"}
        self.assertTrue(any("reprend le préfixe" in e for e in self.valider(day)))

    def test_pourquoi_projet_sans_depot_refuse(self):
        day = jour()
        s = next(x for x in day["sujets"] if x.get("pourquoi") and not x.get("depot"))
        s["pourquoi"] = {"type": "projet", "texte": "x"}
        self.assertTrue(any("type projet sans « depot »" in e for e in self.valider(day)))

    def jour_recent(self):
        """Le jour de test, traité comme un jour ordinaire (pas un jour converti de l'ancien format)."""
        day = jour()
        day["config"] = {"commit": "test"}
        return day

    def test_plus_de_15_publies_hors_prioritaires_refuse(self):
        day = avec_publies(self.jour_recent(), 16)
        self.assertTrue(any("15 au plus" in e for e in self.valider(day)))

    def test_prioritaires_en_plus_des_15(self):
        day = avec_publies(self.jour_recent(), 15, n_prio=5)                  # 15 autres + 5 alertes récentes = 20 publiés
        self.assertFalse(any("15 au plus" in e or "plafond" in e for e in self.valider(day)))
        day = avec_publies(self.jour_recent(), 16, n_prio=5)                  # 16 autres : refusé
        self.assertTrue(any("15 au plus" in e for e in self.valider(day)))

    def test_sujet_ancien_publie_refuse(self):
        day = self.jour_recent()
        s = next(x for x in day["sujets"] if x["statut"] == "publie" and x["categorie"] not in ("conferences", "distribution") and x.get("date"))
        s["date"] = "2026-01-01"
        self.assertTrue(any(f"{s['id']} : publié mais daté" in e for e in self.valider(day)))

    def test_sujet_deja_publie_un_jour_precedent_refuse(self):
        days = [load_json(p) for p in day_files()]
        if len(days) < 2: self.skipTest("un seul jour")
        avant, apres = days[-2], copy.deepcopy(days[-1])
        apres["config"] = {"commit": "test"}
        ancien = next(s for s in avant["sujets"] if s["statut"] == "publie" and s["categorie"] != "conferences")
        s = next(x for x in apres["sujets"] if x["statut"] == "publie" and x["categorie"] != "conferences")
        s["sources"] = ancien["sources"]
        s["tags"] = [t for t in s.get("tags", []) if (t if isinstance(t, str) else t["tag"]) not in ("mise-a-jour", "rappel")]
        self.assertTrue(any("déjà publié" in e for e in self.valider(apres)))

    def test_fenetres_de_fraicheur(self):
        day = self.jour_recent()
        s = next(x for x in day["sujets"] if x["statut"] == "publie" and x["categorie"] not in ("conferences", "distribution"))
        s.pop("categorie_secondaire", None); s["tags"] = []; s.pop("depot", None)
        s["pourquoi"] = {"type": "compte", "texte": "x"} if s.get("pourquoi") else s.get("pourquoi")
        il_y_a = lambda j: (__import__("datetime").date.fromisoformat(day["date"]) - __import__("datetime").timedelta(days=j)).isoformat()
        perime = lambda: any(f"{s['id']} : publié mais daté" in e for e in self.valider(day))
        s["categorie"], s["date"] = "craftsmanship", il_y_a(60)          # fond : 3 mois
        self.assertFalse(perime())
        s["date"] = il_y_a(100)
        self.assertTrue(perime())
        s["date"], s["tags"] = il_y_a(60), ["agents"]                    # agents : jamais de fond
        self.assertTrue(perime())

    def test_projet_inconnu_refuse(self):
        day = jour()
        day["sujets"][0]["depot"] = "Reefact/inconnu"
        self.assertTrue(any("projets.json" in e for e in self.valider(day)))


if __name__ == "__main__":
    unittest.main()
