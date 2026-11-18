#!/usr/bin/env bash
# Downloads the 30 images used by the Figma design into src/assets/figma/.
# The links below come from Figma and EXPIRE 7 DAYS after they were generated
# (see the date in the README). If a download fails with 403/404, ask for fresh links.
#
#   cd frontend && bash scripts/download-figma-assets.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=src/assets/figma
mkdir -p "$OUT"

BASE="https://www.figma.com/api/mcp/asset/4ad9f94b-326f-4b11-ae83-386314ab910a"

get() {  # get <file hash with extension> <local name>
  echo "downloading $2"
  curl -fsSL "$BASE/$1" -o "$OUT/$2"
}

# header / chrome
get 5cf99.svg  search-icon.svg
get 530ad.svg  chevron-down.svg
get 1d67b.svg  announcement.svg

# home: "Most Used Services" banners (keys: cleaning, appliance, laundry, beauty)
get 8656f.png  banner-cleaning.png
get aed9b.png  banner-appliance.png
get 8f1bc.png  banner-laundry.png
get 9018f.png  banner-beauty.png

# home: service icon grid (use these names in Category.icon from the admin)
get a8b8e.png  icon-ac-service.png
get be78b.png  icon-bathroom-cleaning.png
get befab.png  icon-electrician.png
get e0c2d.png  icon-renovation.png
get d0acf.png  icon-plumber.png
get 389df.png  icon-cooking-range.png
get d054c.png  icon-painting.png
get 9df21.png  icon-waste-management.png
get b8712.png  icon-mosquito-net.png
get 99d65.png  icon-deep-cleaning.png
get a9a3a.png  icon-driving.png
get b7edb.png  icon-packers-movers.png
get cc0ca.png  icon-more.png

# home: partner banner
get 7218c.png  partner-workers.png
get 39bfc.png  partner-productivity.png
get d46b6.png  partner-earnings.png
get d8cea.png  partner-customers.png

# home: "Why Joli?" strip
get 8d5e1.png  why-ball.png
get b457a.png  why-calendar.png
get aa83b.png  why-card.png
get d665f.png  why-shield.png
get 75b28.png  why-tag.png
get 0b227.png  why-support.png

echo "done: $(ls "$OUT" | wc -l) files in $OUT"
