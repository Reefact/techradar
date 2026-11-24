#!/usr/bin/env bash
# Assemble le site publiable dans dist/ (seul dist/ est déployé sur Cloudflare).
# Publiés : index, flux, assets/, reports/, et la page /drafts/ (index + brouillons + drafts.json).
# Exclus volontairement : tools/, .github/, .claude/, data/, docs/, README...
# Variable optionnelle SITE_URL : liens absolus dans feed.xml.
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v python3 >/dev/null 2>&1; then
  python3 tools/build_feed.py "${SITE_URL:-}"   # flux toujours cohérent avec reports/
else
  echo "python3 absent : feed.xml du dépôt utilisé tel quel" >&2
fi
rm -rf dist && mkdir -p dist/drafts
cp index.html feed.xml dist/
cp -r assets reports dist/
# Page des brouillons : drafts/index.html + les fichiers drafts/AAAA/*.html + drafts.json (généré)
cp drafts/index.html dist/drafts/
for d in drafts/[0-9][0-9][0-9][0-9]; do [ -d "$d" ] && cp -r "$d" dist/drafts/; done
if command -v python3 >/dev/null 2>&1; then
  python3 tools/build_drafts.py dist/drafts/drafts.json
else
  echo "[]" > dist/drafts/drafts.json
fi
# Les brouillons ne doivent pas être indexés par les moteurs de recherche.
cat > dist/_headers <<'H'
/drafts
  X-Robots-Tag: noindex, nofollow
/drafts/*
  X-Robots-Tag: noindex, nofollow
H
echo "dist/ : $(find dist -type f | wc -l) fichier(s)"
