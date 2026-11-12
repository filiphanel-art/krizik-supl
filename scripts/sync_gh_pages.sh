#!/usr/bin/env bash
set -euo pipefail

# Skript pro automatickou synchronizaci statického exportu do větve gh-pages
# Použití: ./scripts/sync_gh_pages.sh [--dry-run]

DRY_RUN=0
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ]; then
    DRY_RUN=1
  fi
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Aktivace virtuálního prostředí
if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Spouštím export-static..."
python -m app export-static --output dist

# Ověření výstupu
INDEX_FILE="$REPO_ROOT/dist/data/index.json"
if [ ! -s "$INDEX_FILE" ]; then
  echo "CHYBA: Soubor $INDEX_FILE neexistuje nebo je prázdný!" >&2
  exit 1
fi

echo "Export úspěšně ověřen ($INDEX_FILE)."

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[DRY RUN] Kontrola a statický export proběhly v pořádku. Git push do gh-pages byl přeskočen."
  exit 0
fi

# Publikace do větve gh-pages
echo "Nasadit do větve gh-pages..."
TEMP_DIR=$(mktemp -d)
cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

cp -a "$REPO_ROOT/dist/." "$TEMP_DIR/"
cd "$TEMP_DIR"
git init -b gh-pages
git config user.name "Krizik Bot"
git config user.email "bot@skolakrizik.cz"
git add -A
git commit -m "Automatický export suplování $(date -u +'%Y-%m-%dT%H:%M:%SZ')"

REMOTE_URL=$(git -C "$REPO_ROOT" config --get remote.origin.url || echo "origin")
git push "$REMOTE_URL" gh-pages:gh-pages --force
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Úspěšně nahráno do větve gh-pages."
