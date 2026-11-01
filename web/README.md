# Web UI

Run the complete project using the root README. For a UI-only preview, run `python3 -m http.server 4173` here; community ranking APIs require the FastAPI backend and will be unavailable on a static server.

`scoring.mjs` supplies all 14 bosses and legacy ID aliases. `app.js` builds the dropdown from that registry, renders local cards, submits explicit Reveal actions to the same-origin API, and exports PNGs. Shared links contain self-reported inputs, not verified database IDs. Static social metadata uses `og-image.png`; set the actual deployment domain before publishing.
