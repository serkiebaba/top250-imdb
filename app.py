import os, csv
from flask import Flask, jsonify
from flask_cors import CORS  # <- CORS toevoegen

# ===== Config =====
APP_NAME = "TOP 250 FILMS (IMDB)"
CATALOG_ID = "top250films"
CATALOG_TYPE = "movie"

# Gebruik CSV in /data/ als die bestaat, anders die in de root
CSV_PATH = "data/imdb_top250.csv" if os.path.exists("data/imdb_top250.csv") else "imdb_top250.csv"

# ===== App =====
app = Flask(__name__)
CORS(app)  # <- CORS aanzetten (lost “Failed to fetch” op)

# ===== CSV inlezen =====
def load_metas():
    metas = []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("URL", "")
            if "/title/" not in url:
                continue
            imdb_id = url.split("/title/")[1].split("/")[0]
            metas.append({
                "id": imdb_id,
                "type": CATALOG_TYPE,
                "name": row.get("Title", ""),
                "year": int(row["Year"]) if row.get("Year", "").isdigit() else None,
                "poster": row.get("Poster", "") or None,
                "genres": [g.strip() for g in row.get("Genres", "").split(",") if g.strip()],
                "description": (row.get("Description", "") or "")[:500],
            })
    return metas

METAS = load_metas()

manifest = {
    "id": f"imdb-{CATALOG_ID}",
    "version": "1.0.0",
    "name": APP_NAME,
    "description": "IMDb Top 250 Films — rechtstreeks uit CSV.",
    "resources": ["catalog"],
    "types": [CATALOG_TYPE],
    "catalogs": [
        {"type": CATALOG_TYPE, "id": CATALOG_ID, "name": APP_NAME}
    ],
}

@app.route("/manifest.json")
def serve_manifest():
    return jsonify(manifest)

@app.route(f"/catalog/{CATALOG_TYPE}/{CATALOG_ID}.json")
def serve_catalog():
    return jsonify({"metas": METAS})

@app.route("/")
def root():
    return jsonify({
        "ok": True,
        "csv_path": CSV_PATH,
        "tip": "Gebruik /manifest.json in Stremio"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
