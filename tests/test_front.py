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
    """Un jour de test : le plus récent, avec au moins un sujet à tag emoji, à tag texte et à projet."""
    return load_json(day_files()[-1])


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

    def test_projet_inconnu_refuse(self):
        day = jour()
        day["sujets"][0]["depot"] = "Reefact/inconnu"
        self.assertTrue(any("projets.json" in e for e in self.valider(day)))


if __name__ == "__main__":
    unittest.main()
