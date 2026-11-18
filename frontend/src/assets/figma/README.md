# Figma artwork

Run `bash scripts/download-figma-assets.sh` (from `frontend/`) to download the design's
images into this folder. The app works without them: every image has a fallback.

File names are the contract. `src/assets/index.js` looks images up by name:

| Used for | File name | How it is chosen |
|---|---|---|
| Category icon (home grid, category row) | `icon-<key>.png` | `key` = the category's `icon` field in the admin |
| Category banner (home, top row) | `banner-<key>.png` | same `key` |
| Chrome (search, chevron, megaphone) | `search-icon.svg`, `chevron-down.svg`, `announcement.svg` | fixed |
| Partner banner, Why Joli | `partner-*.png`, `why-*.png` | fixed |

Keys that have artwork: `ac-service`, `bathroom-cleaning`, `electrician`, `renovation`, `plumber`,
`cooking-range`, `painting`, `waste-management`, `mosquito-net`, `deep-cleaning`, `driving`,
`packers-movers` (icons) and `cleaning`, `appliance`, `laundry`, `beauty` (banners).
So a category named "Plumbing" should have `icon = plumber` in the admin.
