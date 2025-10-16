import os, csv, re, json, time
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup

# ===== Config =====
APP_NAME_FILMS = "TOP 250 FILMS (IMDB)"
CATALOG_ID_FILMS = "top250films"
CATALOG_TYPE_FILMS = "movie"
PAGE_SIZE = 50  # aantal items per pagina voor TV-navigatie

APP_NAME_NETFLIX = "NETFLIX TOP 10 (NL) – Series"
CATALOG_ID_NETFLIX = "netflix-top10-nl"
CATALOG_TYPE_NETFLIX = "series"

# CSV voor films (werkt met /data/imdb_top250.csv of met imdb_top250.csv in root)
CSV_PATH = "data/imdb_top250.csv" if os.path.exists("data/imdb_top250.csv") else "imdb_top250.csv"

# Netflix bron (live van Tudum). Cache op 0 zodat elke “wake-up” vers ophaalt.
NETFLIX_TUDUM_URL = "https://www.netflix.com/tudum/top10/netherlands/tv"
NETFLIX_CACHE_SECONDS = 0  # 0 = altijd nieuw bij wakker worden

app = Flask(__name__)
CORS(app)

def _ua():
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# ===== CSV (IMDB Top 250 Films) =====
def load_metas_films():
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
                "type": CATALOG_TYPE_FILMS,
                "name": row.get("Title", ""),
                "year": int(row["Year"]) if row.get("Year", "").isdigit() else None,
                "poster": row.get("Poster", "") or None,
                "genres": [g.strip() for g in row.get("Genres", "").split(",") if g.strip()],
                "description": (row.get("Description", "") or "")[:500],
            })
    return metas

FILM_METAS = load_metas_films()

# ===== Netflix Top 10 NL (live) =====
_netflix_cache = {"ts": 0, "metas": []}

def fetch_netflix_top10_nl_series():
    # Altijd nieuw (cache=0) bij eerste request na “wakker worden”.
    try:
        r = requests.get(NETFLIX_TUDUM_URL, headers=_ua(), timeout=15)
        r.raise_for_status()
        html = r.text
    except Exception:
        return _netflix_cache["metas"]

    soup = BeautifulSoup(html, "html.parser")

    titles = []
    # 1) Probeer __NEXT_DATA__ JSON
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if tag and tag.string:
        try:
            data = json.loads(tag.string)
            text = json.dumps(data).lower()
            raw = re.findall(r'"title"\s*:\s*"([^"]{2,100})"', text)
            for t in raw:
                t = t.strip().title()
                if len(t) > 2 and t not in titles:
                    titles.append(t)
        except Exception:
            pass

    # 2) Fallback: DOM headings/aria-labels
    if not titles:
        for a in soup.find_all(["a", "div"], attrs={"aria-label": True}):
            t = a["aria-label"].strip()
            if len(t) > 2 and t not in titles:
                titles.append(t)
        for h in soup.find_all(["h2", "h3"]):
            t = h.get_text(strip=True)
            if len(t) > 2 and t not in titles:
                titles.append(t)

    # Alleen top-10
    titles = titles[:10]

    metas = []
    for rank, name in enumerate(titles, start=1):
        metas.append({
            "id": f"netflix-nl-{rank}-{re.sub(r'[^a-z0-9]+', '-', name.lower())}",
            "type": CATALOG_TYPE_NETFLIX,
            "name": name,
            "poster": None,  # TMDB metadata addon vult aan
            "description": f"Netflix NL Top 10 – positie #{rank}",
        })

    _netflix_cache["ts"] = time.time()
    _netflix_cache["metas"] = metas
    return metas

# ===== Manifest met twee catalogs =====
manifest = {
    "id": "custom-toplists",
    "version": "1.2.0",
    "name": "Custom Top Lists (IMDB + Netflix)",
    "description": "IMDb Top 250 Films en Netflix Top 10 NL (Series).",
    "resources": ["catalog"],
    "types": [CATALOG_TYPE_FILMS, CATALOG_TYPE_NETFLIX],
    "catalogs": [
        {
            "type": CATALOG_TYPE_FILMS,
            "id": CATALOG_ID_FILMS,
            "name": APP_NAME_FILMS,
            "extraSupported": ["skip"]  # paging voor TV navigatie
        },
        {
            "type": CATALOG_TYPE_NETFLIX,
            "id": CATALOG_ID_NETFLIX,
            "name": APP_NAME_NETFLIX
        }
    ]
}

# ===== Routes =====
@app.route("/manifest.json")
def serve_manifest():
    return jsonify(manifest)

# Dynamisch: films (paged) + netflix
@app.route(f"/catalog/<type>/<id>.json")
def serve_catalog_dynamic(type, id):
    if type == CATALOG_TYPE_FILMS and id == CATALOG_ID_FILMS:
        skip = request.args.get("skip", default=0, type=int)
        slice_ = FILM_METAS[skip: skip + PAGE_SIZE]
        has_more = (skip + PAGE_SIZE) < len(FILM_METAS)
        return jsonify({"metas": slice_, "hasMore": has_more})

    if type == CATALOG_TYPE_NETFLIX and id == CATALOG_ID_NETFLIX:
        metas = fetch_netflix_top10_nl_series()
        return jsonify({"metas": metas})

    return jsonify({"metas": []})

# Backwards compat voor oude films-route
@app.route(f"/catalog/{CATALOG_TYPE_FILMS}/{CATALOG_ID_FILMS}.json")
def serve_catalog_legacy_films():
    return serve_catalog_dynamic(CATALOG_TYPE_FILMS, CATALOG_ID_FILMS)

@app.route("/")
def root():
    return jsonify({
        "ok": True,
        "csv_path": CSV_PATH,
        "endpoints": {
            "manifest": "/manifest.json",
            "films": f"/catalog/{CATALOG_TYPE_FILMS}/{CATALOG_ID_FILMS}.json",
            "netflix_nl_series": f"/catalog/{CATALOG_TYPE_NETFLIX}/{CATALOG_ID_NETFLIX}.json"
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
