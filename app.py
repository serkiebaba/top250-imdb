import csv, os
from flask import Flask, jsonify

APP_NAME = "TOP 250 FILMS (IMDB)"
CATALOG_ID = "top250films"
CATALOG_TYPE = "movie"
CSV_PATH = os.path.join("data", "imdb_top250.csv")

def load_metas():
    metas = []
    with open("imdb_top250.csv", encoding="utf-8-sig") as f:
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
                "year": int(row["Year"]) if row.get("Year","").isdigit() else None,
                "poster": row.get("Poster", "") or None,
                "genres": [g.strip() for g in row.get("Genres","").split(",") if g.strip()],
                "description": row.get("Description","")[:500]
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
    ]
}

app = Flask(__name__)

@app.route("/manifest.json")
def serve_manifest():
    return jsonify(manifest)

@app.route(f"/catalog/{CATALOG_TYPE}/{CATALOG_ID}.json")
def serve_catalog():
    return jsonify({"metas": METAS})

@app.route("/")
def root():
    return jsonify({"ok": True, "tip": "Gebruik /manifest.json in Stremio"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
