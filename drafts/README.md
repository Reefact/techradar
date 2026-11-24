# drafts/

Versions alternatives d'un rapport, générées quand le rapport du jour existe déjà
(`drafts/AAAA/AAAAMMJJ-HHMM.html`). L'index et le flux ne les voient pas : seul `reports/` est publié dans la liste.

Pour en choisir une : GitHub > Actions > **Promote a draft report** > Run workflow, avec le chemin du brouillon.
Ou à la main : copier le fichier vers `reports/AAAA/AAAAMMJJ.html` et lancer `python3 tools/build_feed.py`.
