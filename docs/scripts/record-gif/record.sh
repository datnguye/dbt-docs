#!/usr/bin/env bash
# Record docs/assets/img/dbt-2-info-schema.gif: the terminal (dbt Fusion writes the
# info schema, then `dbdocs generate` / `dbdocs serve` with `info_schema: true`)
# followed by a browser walkthrough of the served site.
#
# Needs: dbt Fusion on PATH (or DBT=/path/to/dbt), vhs (brew install vhs — brings
# ttyd + ffmpeg), the uv env (`task install`) and the Playwright browser
# (`task frontend:install frontend:e2e:install`).
#
# DEMO_DIR shows up in the GIF (dbt and dbdocs print absolute paths), so keep it
# free of anything personal — the default is a shared, user-agnostic location.
set -euo pipefail

REPO=$(cd "$(dirname "$0")/../../.." && pwd)
DEMO=${DEMO_DIR:-/Users/Shared/jaffle_shop}
OUT=${OUT:-$REPO/docs/assets/img/dbt-2-info-schema.gif}
DBT=${DBT:-$(command -v dbt)}
JAFFLE_SHOP_REF=5beb145
PORT=8000
WORK=$(mktemp -d)
DBT_DIR=$(dirname "$DBT")
export REPO DEMO DBT_DIR

if [ ! -d "$DEMO/.git" ]; then
  rm -rf "$DEMO"
  git clone -q https://github.com/dbt-labs/jaffle-shop.git "$DEMO"
fi
git -C "$DEMO" checkout -q --force "$JAFFLE_SHOP_REF"

perl -pi -e "s/^profile: .*/profile: default/; s/var\('load_source_data', false\)/var('load_source_data', true)/" \
  "$DEMO/dbt_project.yml"
perl -pi -e "s/as date\)\"/as timestamp)\"/g" "$DEMO/models/marts/metricflow_time_spine.sql"
cat > "$DEMO/profiles.yml" <<'YAML'
default:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: jaffle_shop.duckdb
      threads: 4
YAML
cat > "$DEMO/dbdocs.yml" <<'YAML'
site_name: Jaffle Shop
target_dir: target
output_dir: site
info_schema: true
YAML
(cd "$DEMO" && DBT_PROFILES_DIR="$DEMO" "$DBT" deps >/dev/null)

(cd "$WORK" && vhs "$REPO/docs/scripts/record-gif/info-schema.tape")

(cd "$DEMO" && exec "$REPO/.venv/bin/dbdocs" serve -p "$PORT") >/dev/null 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT
until curl -sf "http://127.0.0.1:$PORT/" >/dev/null; do sleep 0.3; done

node "$REPO/docs/scripts/record-gif/browse.mjs" "http://127.0.0.1:$PORT" "$WORK/video"
BROWSER_VIDEO=$(ls -t "$WORK"/video/*.webm | head -1)

ffmpeg -loglevel error -y -i "$WORK/terminal.mp4" -i "$BROWSER_VIDEO" -filter_complex \
  "[0:v]fps=6,scale=880:-2:flags=lanczos,setsar=1[t];\
[1:v]fps=6,scale=880:-2:flags=lanczos,setsar=1[b];\
[t][b]concat=n=2:v=1:a=0,split[x][y];\
[x]palettegen=max_colors=64:stats_mode=diff[p];\
[y][p]paletteuse=dither=none:diff_mode=rectangle" \
  "$OUT"

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
