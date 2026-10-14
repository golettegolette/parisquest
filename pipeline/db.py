"""Base de données Parisquest (SQLite) : schéma, écriture et export JSON pour le jeu.

La base est la source de vérité. Le jeu ne lit jamais la base directement :
il reçoit l'export JSON produit par export().
"""
import json
import math
import re
import sqlite3
from datetime import date
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys = ON;

-- Paliers de rareté (0 = Commune ... 4 = Légendaire) et gain en écus à la capture
CREATE TABLE rarity_levels (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    reward_ecus   INTEGER NOT NULL
);

-- Grandes familles de cartes (Nature, Eau, Rues...)
CREATE TABLE families (
    id     TEXT PRIMARY KEY,
    name   TEXT NOT NULL,
    color  TEXT NOT NULL            -- couleur d'émail utilisée sur la carte et le plan
);

-- Jeux de données d'origine
CREATE TABLE sources (
    id             TEXT PRIMARY KEY, -- identifiant du jeu de données sur le portail
    title          TEXT NOT NULL,
    publisher      TEXT,
    licence        TEXT,
    portal_url     TEXT,
    downloaded_on  TEXT              -- date du téléchargement (AAAA-MM-JJ)
);

-- Types de cartes (Arbre remarquable, Fontaine, Voie...), rattachés à une famille
CREATE TABLE kinds (
    id                  TEXT PRIMARY KEY,
    family_id           TEXT NOT NULL REFERENCES families(id),
    label               TEXT NOT NULL,
    illustration        TEXT NOT NULL,   -- nom de l'illustration dessinée par le jeu
    capture_radius_m    INTEGER NOT NULL -- rayon de capture par défaut
);

-- Une ligne = une carte à collectionner = un lieu réel
CREATE TABLE places (
    id                TEXT PRIMARY KEY,           -- "type:identifiant source", ex. "fontaine:450024987"
    kind_id           TEXT NOT NULL REFERENCES kinds(id),
    source_id         TEXT NOT NULL REFERENCES sources(id),
    name              TEXT NOT NULL,
    subtitle          TEXT,                       -- nom latin, modèle, catégorie...
    arrondissement    INTEGER CHECK (arrondissement BETWEEN 1 AND 20),
    address           TEXT,
    lat               REAL NOT NULL,
    lon               REAL NOT NULL,
    rarity            INTEGER NOT NULL REFERENCES rarity_levels(id),
    capture_radius_m  INTEGER NOT NULL,
    highlight         TEXT,                       -- phrase mise en avant au dos de la carte
    description       TEXT,
    url               TEXT,
    photo_url         TEXT,
    photo_credit      TEXT,
    ephemeral         INTEGER NOT NULL DEFAULT 0, -- 1 = lieu appelé à disparaître (arbre à abattre)
    wikidata_id       TEXT,                       -- ex. "Q243" ; lien vers la fiche Wikidata
    wikipedia_url     TEXT,                       -- article Wikipédia en français
    notoriety         INTEGER,                    -- nombre de langues dans lesquelles l'article existe
    attributes        TEXT                        -- JSON des champs propres au type (genre, hauteur, type de fontaine...)
);
CREATE INDEX idx_places_wikidata ON places(wikidata_id);
CREATE INDEX idx_places_kind   ON places(kind_id);
CREATE INDEX idx_places_rarity ON places(rarity);
CREATE INDEX idx_places_arr    ON places(arrondissement);
CREATE INDEX idx_places_geo    ON places(lat, lon);

-- Caractéristiques affichées sur la carte (jusqu'à 3 par lieu)
CREATE TABLE place_facts (
    place_id  TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    label     TEXT NOT NULL,
    value     TEXT NOT NULL,
    PRIMARY KEY (place_id, position)
);

-- Points de capture le long des objets étendus (rues, marchés)
CREATE TABLE place_points (
    place_id  TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    seq       INTEGER NOT NULL,
    lat       REAL NOT NULL,
    lon       REAL NOT NULL,
    PRIMARY KEY (place_id, seq)
);

-- Contours (GeoJSON) : fond de plan (arrondissements, eau, emprises des rues, parcs)
-- et zones de capture des parcs et biens UNESCO
CREATE TABLE shapes (
    id        INTEGER PRIMARY KEY,
    place_id  TEXT REFERENCES places(id) ON DELETE CASCADE, -- NULL si dessin seul (ex. cimetière)
    layer     TEXT NOT NULL CHECK (layer IN ('park', 'bois', 'cim', 'monde', 'arr', 'water', 'street')),
    label     TEXT,                                          -- numéro d'arrondissement pour le calque 'arr'
    geojson   TEXT NOT NULL
);
CREATE INDEX idx_shapes_place ON shapes(place_id);

-- Horaires des marchés (day : 0 = lundi ... 6 = dimanche)
CREATE TABLE market_hours (
    place_id  TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    day       INTEGER NOT NULL CHECK (day BETWEEN 0 AND 6),
    opens     TEXT,
    closes    TEXT,
    PRIMARY KEY (place_id, day)
);

-- Collections à compléter
CREATE TABLE collections (
    id           INTEGER PRIMARY KEY,
    family_id    TEXT NOT NULL REFERENCES families(id),
    name         TEXT NOT NULL,
    description  TEXT,
    bonus_ecus   INTEGER NOT NULL DEFAULT 50
);
CREATE TABLE collection_places (
    collection_id  INTEGER NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    place_id       TEXT NOT NULL REFERENCES places(id) ON DELETE CASCADE,
    PRIMARY KEY (collection_id, place_id)
);

-- Vue de lecture : un lieu avec sa famille, son type et sa rareté en clair
CREATE VIEW v_places AS
SELECT p.id, f.name AS family, k.label AS kind, p.name, p.subtitle, p.arrondissement, p.address,
       r.name AS rarity, p.rarity AS rarity_level, p.lat, p.lon, p.capture_radius_m, p.source_id
FROM places p
JOIN kinds k ON k.id = p.kind_id
JOIN families f ON f.id = k.family_id
JOIN rarity_levels r ON r.id = p.rarity;

-- Vue de contrôle : les lieux les plus connus (nombre de langues Wikipédia)
CREATE VIEW v_most_famous AS
SELECT name, kind_id, arrondissement, notoriety, wikipedia_url FROM places
WHERE notoriety IS NOT NULL ORDER BY notoriety DESC;

-- Vue de contrôle : nombre de cartes par famille et par rareté
CREATE VIEW v_rarity_by_family AS
SELECT f.name AS family,
       SUM(p.rarity = 0) AS commune, SUM(p.rarity = 1) AS peu_commune, SUM(p.rarity = 2) AS rare,
       SUM(p.rarity = 3) AS epique, SUM(p.rarity = 4) AS legendaire, COUNT(*) AS total
FROM places p JOIN kinds k ON k.id = p.kind_id JOIN families f ON f.id = k.family_id
GROUP BY f.id ORDER BY total DESC;
"""

RARITY = [(0, "Commune", 10), (1, "Peu commune", 15), (2, "Rare", 25), (3, "Épique", 40), (4, "Légendaire", 60)]

PARIS = "https://opendata.paris.fr/explore/dataset/"
SOURCES = [
    ("arbresremarquablesparis", "Les arbres remarquables", "Ville de Paris (DEVE)", "ODbL", PARIS),
    ("espaces_verts", "Espaces verts et assimilés", "Ville de Paris (DEVE)", "ODbL", PARIS),
    ("jardins-partages", "Jardins partagés", "Ville de Paris (DEVE)", "ODbL", PARIS),
    ("jardins-relais", "Jardins relais", "Ville de Paris (DEVE)", "ODbL", PARIS),
    ("arbres-a-abattre-pour-raison-sanitaires-et-essence-de-remplacement", "Arbres à abattre pour raisons sanitaires", "Ville de Paris (DEVE)", "ODbL", PARIS),
    ("fontaines-a-boire", "Fontaines à boire", "Eau de Paris", "ODbL", PARIS),
    ("denominations-emprises-voies-actuelles", "Dénominations des emprises des voies actuelles", "Ville de Paris (Urbanisme)", "ODbL", PARIS),
    ("plan-de-voirie-voies-en-escalier", "Plan de voirie : voies en escalier", "Ville de Paris (Voirie)", "ODbL", PARIS),
    ("plaques_commemoratives", "Plaques commémoratives", "Ville de Paris (Affaires culturelles)", "ODbL", PARIS),
    ("femmes-illustres-a-paris-portraits", "Femmes illustres à Paris : portraits", "Ville de Paris (Attractivité)", "ODbL", PARIS),
    ("referentiel-archeologique-de-paris", "Référentiel archéologique de Paris", "Ville de Paris (Affaires culturelles)", "ODbL", PARIS),
    ("plu-annexes-biens-inscrits-au-patrimoine-mondial", "PLU : biens inscrits au patrimoine mondial", "Ville de Paris (Urbanisme)", "ODbL", PARIS),
    ("lieux-municipaux", "Lieux municipaux", "Ville de Paris (Communication)", "ODbL", PARIS),
    ("marches-decouverts", "Marchés découverts", "Ville de Paris (Attractivité)", "ODbL", PARIS),
    ("kiosques-de-presse", "Kiosques de presse", "Ville de Paris (Attractivité)", "ODbL", PARIS),
    ("paris-autrement-balades-dans-les-arrondissements-peripheriques-poi", "Paris autrement : balades, lieux", "Ville de Paris (Attractivité)", "ODbL", PARIS),
    ("arrets", "Référentiel des arrêts : arrêts", "Île-de-France Mobilités", "Licence Ouverte v2.0", "https://data.iledefrance-mobilites.fr/explore/dataset/"),
    ("validations-reseau-ferre-nombre-validations-par-jour-2eme-trimestre", "Validations sur le réseau ferré (2ᵉ trimestre 2026)", "Île-de-France Mobilités", "Licence Ouverte v2.0", "https://data.iledefrance-mobilites.fr/explore/dataset/"),
    ("wikidata", "Lieux de Paris ayant un article Wikipédia", "Wikidata", "CC0 (photos : licences Wikimedia Commons)", "https://www.wikidata.org/wiki/"),
]
KIND_SOURCE = {
    "arbre": "arbresremarquablesparis", "parc": "espaces_verts", "jpart": "jardins-partages", "jrel": "jardins-relais",
    "sursis": "arbres-a-abattre-pour-raison-sanitaires-et-essence-de-remplacement", "fontaine": "fontaines-a-boire",
    "rue": "denominations-emprises-voies-actuelles", "escalier": "plan-de-voirie-voies-en-escalier",
    "plaque": "plaques_commemoratives", "femme": "femmes-illustres-a-paris-portraits",
    "vestige": "referentiel-archeologique-de-paris", "monde": "plu-annexes-biens-inscrits-au-patrimoine-mondial",
    "marche": "marches-decouverts", "kiosque": "kiosques-de-presse",
    "insolite": "paris-autrement-balades-dans-les-arrondissements-peripheriques-poi", "station": "arrets",
}
COMMONS = "https://commons.wikimedia.org/wiki/Special:FilePath/"
GEOM_KEYS = {"pts", "rad", "poly", "mpoly", "mk", "hr"}


def _dec(a, b):
    return round(48.8 + a / 1e5, 5), round(2.2 + b / 1e5, 5)


def _enc(lat, lon):
    return [round((lat - 48.8) * 1e5), round((lon - 2.2) * 1e5)]


def _rings_geojson(rings):
    """Anneaux encodés (entiers) -> géométrie GeoJSON MultiPolygon (un anneau par polygone)."""
    polys = []
    for r in rings:
        ring = []
        for j in range(0, len(r), 2):
            la, lo = _dec(r[j], r[j + 1])
            ring.append([lo, la])
        polys.append([ring])
    return json.dumps({"type": "MultiPolygon", "coordinates": polys}, separators=(",", ":"))


def _geojson_rings(geojson):
    g = json.loads(geojson)
    out = []
    for poly in g["coordinates"]:
        for ring in poly:
            flat = []
            for lo, la in ring:
                flat += _enc(la, lo)
            out.append(flat)
    return out


def _delta(flat):
    """Anneau encodé -> premier point absolu puis écarts, pour alléger le fichier des rues."""
    out = flat[:2]
    for j in range(2, len(flat)):
        out.append(flat[j] - flat[j - 2])
    return out


LAT0, LON0 = 48.8566, 2.3522
COS0 = math.cos(math.radians(LAT0))


def _axis(rings):
    """Orientation et longueur d'une rue (axe principal de ses contours), pour placer son nom sur le plan."""
    pts = []
    for r in rings:
        for j in range(0, len(r), 2):
            lat, lon = 48.8 + r[j] / 1e5, 2.2 + r[j + 1] / 1e5
            pts.append(((lon - LON0) * COS0 * 1000, -(lat - LAT0) * 1000))
    if len(pts) < 2:
        return {"ang": 0, "len": 0}
    mx = sum(p[0] for p in pts) / len(pts)
    my = sum(p[1] for p in pts) / len(pts)
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ux, uy = math.cos(ang), math.sin(ang)
    proj_ = [(p[0] - mx) * ux + (p[1] - my) * uy for p in pts]
    return {"ang": round(ang, 2), "len": round(max(proj_) - min(proj_), 2)}


def write(path, families, kinds, items, collections, map_parks, monde_polys):
    path = Path(path)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    today = date.today().isoformat()
    con.executemany("INSERT INTO rarity_levels VALUES (?,?,?)", RARITY)
    con.executemany("INSERT INTO families VALUES (?,?,?)", [(k, v["name"], v["color"]) for k, v in families.items()])
    con.executemany("INSERT INTO sources VALUES (?,?,?,?,?,?)", [(i, t, p, l, u + i, today) for i, t, p, l, u in SOURCES])
    con.executemany("INSERT INTO kinds VALUES (?,?,?,?,?)", [(k, v[0], v[1], v[2], v[3]) for k, v in kinds.items()])

    for it in items:
        k = it["k"]
        x = dict(it.get("x") or {})
        radius = x.get("rad") or (100 if k == "arbre" and x.get("bois") else kinds[k][3])
        attrs = {kk: vv for kk, vv in x.items() if kk not in GEOM_KEYS}
        if it.get("q"):
            attrs["qualification"] = it["q"]
        arr = int(it["r"]) if str(it.get("r") or "").isdigit() else None
        source = "wikidata" if re.search(r":Q\d+$", it["i"]) else KIND_SOURCE.get(k, "lieux-municipaux")
        con.execute("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            it["i"], k, source, it["n"], it.get("s"), arr, it.get("site"),
            it["a"], it["o"], it.get("t", 0), radius, it.get("w"), it.get("d"), it.get("u"), it.get("p"), it.get("c"),
            1 if x.get("eph") else 0, it.get("wd"), it.get("wp"), it.get("nt"),
            json.dumps(attrs, ensure_ascii=False) if attrs else None))
        for pos, (label, value) in enumerate(it.get("f") or []):
            if value not in (None, ""):
                con.execute("INSERT INTO place_facts VALUES (?,?,?,?)", (it["i"], pos, label, str(value)))
        pts = x.get("pts") or []
        con.executemany("INSERT INTO place_points VALUES (?,?,?,?)",
                        [(it["i"], j // 2, *_dec(pts[j], pts[j + 1])) for j in range(0, len(pts), 2)])
        if x.get("mk"):
            hr = x.get("hr") or [None] * 6
            for day, on in enumerate(x["mk"]):
                if on:
                    o, c = (hr[0], hr[1]) if day < 5 else (hr[2], hr[3]) if day == 5 else (hr[4], hr[5])
                    con.execute("INSERT INTO market_hours VALUES (?,?,?,?)", (it["i"], day, o, c))
        if x.get("mpoly") is not None and monde_polys[x["mpoly"]]:
            con.execute("INSERT INTO shapes (place_id, layer, geojson) VALUES (?,?,?)", (it["i"], "monde", _rings_geojson(monde_polys[x["mpoly"]])))
    ids = {it["i"] for it in items}

    for p in map_parks:
        if not p["r"]:
            continue
        pid = p.get("i") if p.get("i") in ids else None
        label = json.dumps({"n": p["label"], "at": p["at"]}) if p.get("label") else None
        con.execute("INSERT INTO shapes (place_id, layer, label, geojson) VALUES (?,?,?,?)", (pid, p["c"], label, _rings_geojson(p["r"])))

    for cid, (fam, name, sub, idxs) in enumerate(collections, start=1):
        con.execute("INSERT INTO collections VALUES (?,?,?,?,50)", (cid, fam, name, sub))
        con.executemany("INSERT INTO collection_places VALUES (?,?)", [(cid, items[i]["i"]) for i in idxs])
    con.commit()
    con.execute("VACUUM")
    con.close()


def export(path, out_dir):
    """Base SQLite -> places.json et map.json, au format compact lu par le jeu."""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    out_dir = Path(out_dir)
    families = {r["id"]: {"name": r["name"], "color": r["color"]} for r in con.execute("SELECT * FROM families ORDER BY rowid")}
    kinds = {r["id"]: {"f": r["family_id"], "l": r["label"], "art": r["illustration"], "rad": r["capture_radius_m"]}
             for r in con.execute("SELECT * FROM kinds ORDER BY rowid")}

    facts, points, hours = {}, {}, {}
    for r in con.execute("SELECT * FROM place_facts ORDER BY place_id, position"):
        facts.setdefault(r["place_id"], []).append((r["label"], r["value"]))
    for r in con.execute("SELECT * FROM place_points ORDER BY place_id, seq"):
        points.setdefault(r["place_id"], []).extend(_enc(r["lat"], r["lon"]))
    for r in con.execute("SELECT * FROM market_hours"):
        hours.setdefault(r["place_id"], {})[r["day"]] = (r["opens"], r["closes"])

    parks, monde, poly_of, mpoly_of, streets, arrs, water = [], [], {}, {}, [], [], []
    for r in con.execute("SELECT * FROM shapes ORDER BY id"):
        rings = _geojson_rings(r["geojson"])
        if r["layer"] == "street":
            streets.append({"i": r["place_id"], "r": [_delta(x) for x in rings], **_axis(rings)})
            continue
        if r["layer"] == "arr":
            lab = json.loads(r["label"]) if r["label"] else {}
            arrs.append({"n": lab.get("n"), "at": lab.get("at"), "r": rings})
            continue
        if r["layer"] == "water":
            water.append(rings)
            continue
        if r["layer"] == "monde":
            mpoly_of[r["place_id"]] = len(monde)
            monde.append(rings)
        else:
            entry = {"c": r["layer"], "r": rings}
            if r["place_id"]:
                entry["i"] = r["place_id"]
                poly_of[r["place_id"]] = len(parks)
            parks.append(entry)

    items, index = [], {}
    for r in con.execute("SELECT * FROM places ORDER BY rowid"):
        pid, k = r["id"], r["kind_id"]
        x = json.loads(r["attributes"]) if r["attributes"] else {}
        x.pop("qualification", None)
        x.pop("wdt", None)
        if pid in points:
            x["pts"] = points[pid]
        if r["capture_radius_m"] != kinds[k]["rad"] and not (k == "arbre" and x.get("bois")):
            x["rad"] = r["capture_radius_m"]
        if pid in poly_of:
            x["poly"] = poly_of[pid]
        if pid in mpoly_of:
            x["mpoly"] = mpoly_of[pid]
        if pid in hours:
            h = hours[pid]
            x["mk"] = [1 if d in h else 0 for d in range(7)]
            wk = next((h[d] for d in range(5) if d in h), (None, None))
            x["hr"] = [wk[0], wk[1], *(h.get(5, (None, None))), *(h.get(6, (None, None)))]
        f = facts.get(pid, [])
        kd = kinds[k]
        labels = [l for l, _ in f]
        kd.setdefault("fl", labels)
        it = {"i": pid, "k": k, "n": r["name"], "a": r["lat"], "o": r["lon"], "t": r["rarity"]}
        for key, col in (("s", "subtitle"), ("site", "address"), ("w", "highlight"), ("d", "description"), ("u", "url"), ("p", "photo_url"), ("c", "photo_credit")):
            if r[col]:
                it[key] = r[col]
        if r["arrondissement"]:
            it["r"] = str(r["arrondissement"])
        if r["wikipedia_url"]:
            it["wp"] = r["wikipedia_url"].replace("https://fr.wikipedia.org/wiki/", "")
        if it.get("p", "").startswith(COMMONS):
            it["p"] = "c:" + it["p"][len(COMMONS):]
        if f:
            it["f"] = [v for _, v in f] if labels == kd["fl"] else [list(p) for p in f]
        if x:
            it["x"] = x
        index[pid] = len(items)
        items.append(it)

    cols = []
    for c in con.execute("SELECT * FROM collections ORDER BY id"):
        ids = [row[0] for row in con.execute("SELECT place_id FROM collection_places WHERE collection_id = ?", (c["id"],))]
        cols.append([c["family_id"], c["name"], c["description"], sorted(index[i] for i in ids)])
    con.close()

    places = {"families": families, "kinds": kinds, "items": items, "collections": cols}
    (out_dir / "places.json").write_text(json.dumps(places, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (out_dir / "map.json").write_text(json.dumps({"parks": parks, "monde": monde, "arr": arrs, "water": water}, separators=(",", ":")), encoding="utf-8")
    (out_dir / "streets.json").write_text(json.dumps({"streets": streets}, separators=(",", ":")), encoding="utf-8")
