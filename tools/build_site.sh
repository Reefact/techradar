#!/usr/bin/env bash
# Assemble le site publiable dans dist/ (seul dist/ est déployé sur Cloudflare).
# Exclus volontairement : drafts/, tools/, .github/, .claude/, README...
# Variable optionnelle SITE_URL : liens absolus dans feed.xml.
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v python3 >/dev/null 2>&1; then
  python3 tools/build_feed.py "${SITE_URL:-}"   # flux toujours cohérent avec reports/
else
  echo "python3 absent : feed.xml du dépôt utilisé tel quel" >&2
fi
rm -rf dist && mkdir -p dist
cp index.html feed.xml dist/
cp -r assets reports dist/
echo "dist/ : $(find dist -type f | wc -l) fichier(s)"
