"""Parisquest v2 : unifie les jeux de données de opendata.paris.fr en cartes à collectionner.

Entrée  : data/src/*.json (+ espaces_verts.geojson), tels que téléchargés sur opendata.paris.fr
Sortie  : site/data/places.json (cartes + collections), site/data/map.json (parcs dessinés sur la carte)
Usage   : python3 build2.py
"""
import collections
import hashlib
import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "data" / "src"
OUT = ROOT / "site" / "data"
OUT.mkdir(parents=True, exist_ok=True)

LAT0, LON0 = 48.8566, 2.3522
COS0 = math.cos(math.radians(LAT0))
M = 111195.0
THIS_YEAR = 2026


def load(name):
    return json.loads((SRC / name).read_text(encoding="utf-8"))


# ---------- géométrie ----------
def to_m(lon, lat):
    return ((lon - LON0) * COS0 * M, (lat - LAT0) * M)


def from_m(x, y):
    return (LON0 + x / (COS0 * M), LAT0 + y / M)


def dp(pts, tol):
    """Douglas-Peucker sur une liste de (x, y) en mètres."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, bi = -1, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / L if L > 1e-6 else math.hypot(px - ax, py - ay)
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def rings_of(geom):
    if not geom:
        return []
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return c
    if t == "MultiPolygon":
        return [r for poly in c for r in poly]
    return []


def outer_rings(geom):
    if not geom:
        return []
    t, c = geom.get("type"), geom.get("coordinates")
    if t == "Polygon":
        return [c[0]]
    if t == "MultiPolygon":
        return [poly[0] for poly in c]
    return []


def geom_of(rec, key="geo_shape"):
    g = rec.get(key)
    if isinstance(g, dict) and "geometry" in g:
        return g["geometry"]
    return g if isinstance(g, dict) else None


def enc(lon, lat):
    return [round((lat - 48.8) * 1e5), round((lon - 2.2) * 1e5)]


def sample_boundary(geom, step=55.0, cap=40):
    """Points régulièrement espacés le long des contours, pour tester la proximité d'un objet étendu."""
    out = []
    rings = outer_rings(geom)
    if not rings:
        return out
    per = 0.0
    mrings = []
    for r in rings:
        m = [to_m(*p[:2]) for p in r]
        mrings.append(m)
        per += sum(math.hypot(m[i + 1][0] - m[i][0], m[i + 1][1] - m[i][1]) for i in range(len(m) - 1))
    step = max(step, per / cap) if per else step
    for m in mrings:
        acc = step
        for i in range(len(m) - 1):
            (x0, y0), (x1, y1) = m[i], m[i + 1]
            seg = math.hypot(x1 - x0, y1 - y0)
            while acc <= seg and seg > 0:
                f = acc / seg
                out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f))
                acc += step
            acc -= seg
    if not out and mrings:
        out = [mrings[0][0]]
    flat = []
    for x, y in out[:cap]:
        lon, lat = from_m(x, y)
        flat += enc(lon, lat)
    return flat, step


def encode_rings(geom, tol=3.5, min_area=0.0):
    rings = []
    for r in rings_of(geom):
        m = [to_m(*p[:2]) for p in r]
        s = dp(m, tol)
        if len(s) < 4:
            continue
        flat = []
        for x, y in s:
            lon, lat = from_m(x, y)
            flat += enc(lon, lat)
        rings.append(flat)
    return rings


# ---------- texte ----------
SMALL = {"de", "du", "des", "la", "le", "les", "et", "aux", "au", "en", "sur", "à", "sous", "dit", "dite"}


def title(s):
    if not s:
        return ""
    s = re.sub(r"\s+", " ", str(s).strip().lower())
    words = s.split(" ")
    out = []
    for i, w in enumerate(words):
        if i > 0 and w in SMALL:
            out.append(w)
        elif w.startswith(("l'", "d'")) and len(w) > 2:
            out.append(w[:2] + w[2:3].upper() + w[3:])
        else:
            out.append(w[:1].upper() + w[1:])
    return " ".join(out)


def cap1(s):
    s = (s or "").strip()
    return s[:1].upper() + s[1:]


def clip(s, n):
    s = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(s or ""))).strip()
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def arr_of(*vals):
    for v in vals:
        if v is None:
            continue
        if isinstance(v, list):
            v = v[0] if v else ""
        s = str(v)
        m = re.search(r"750(\d\d)", s)
        if m and 1 <= int(m.group(1)) <= 20:
            return str(int(m.group(1)))
        m = re.search(r"(\d{1,2})\s*(e|E|er|ème|EME|EME ARR|E ARR)", s)
        if m and 1 <= int(m.group(1)) <= 20:
            return str(int(m.group(1)))
        if re.fullmatch(r"\d{1,2}(\.0)?", s) and 1 <= int(float(s)) <= 20:
            return str(int(float(s)))
    return ""


def h(s):
    return int(hashlib.md5(str(s).encode()).hexdigest()[:8], 16)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def fmt_int(v):
    return f"{int(round(v)):,}".replace(",", " ")


# ---------- types de cartes ----------
FAMILIES = {
    "nature": {"name": "Nature", "color": "#3F7D4F"},
    "eau": {"name": "Eau", "color": "#2C7FA8"},
    "rues": {"name": "Rues", "color": "#1F3B6E"},
    "memoire": {"name": "Mémoire", "color": "#8C2F3A"},
    "patrimoine": {"name": "Patrimoine", "color": "#A8742A"},
    "culture": {"name": "Culture", "color": "#6B3F8F"},
    "quartier": {"name": "Quartier", "color": "#C2582B"},
    "transport": {"name": "Transports", "color": "#4D5B6E"},
}
KINDS = {
    "arbre": ("nature", "Arbre remarquable", "tree", 50),
    "parc": ("nature", "Parc et jardin", "park", 25),
    "jpart": ("nature", "Jardin partagé", "sprout", 40),
    "jrel": ("nature", "Jardin relais", "sprout", 40),
    "sursis": ("nature", "Arbre en sursis", "tree", 35),
    "fontaine": ("eau", "Fontaine", "fountain", 30),
    "piscine": ("eau", "Piscine", "pool", 60),
    "baignade": ("eau", "Baignade", "pool", 80),
    "bains": ("eau", "Bains-douches", "pool", 40),
    "rue": ("rues", "Voie", "plaque", 35),
    "plaque": ("memoire", "Plaque", "memorial", 25),
    "femme": ("memoire", "Femme illustre", "cameo", 40),
    "vestige": ("patrimoine", "Vestige", "amphora", 40),
    "monde": ("patrimoine", "Patrimoine mondial", "laurel", 60),
    "culte": ("patrimoine", "Lieu de culte", "church", 50),
    "mairie": ("patrimoine", "Mairie", "townhall", 50),
    "cimetiere": ("patrimoine", "Cimetière", "stele", 120),
    "musee": ("culture", "Musée", "museum", 60),
    "biblio": ("culture", "Bibliothèque", "books", 50),
    "theatre": ("culture", "Théâtre", "curtain", 50),
    "conserv": ("culture", "Conservatoire", "lyre", 50),
    "atelier": ("culture", "Atelier", "palette", 50),
    "decouverte": ("culture", "Découverte", "compass", 60),
    "marche": ("quartier", "Marché", "awning", 40),
    "marchesp": ("quartier", "Marché spécialisé", "awning", 60),
    "kiosque": ("quartier", "Kiosque", "kiosk", 25),
    "insolite": ("quartier", "Insolite", "eye", 40),
    "sport": ("quartier", "Sport", "ball", 60),
    "station": ("transport", "Station", "station", 60),
}

items = []
ids = set()


def add(kind, uid, name, lat, lon, **kw):
    if lat is None or lon is None:
        return None
    if not (48.80 < lat < 48.91 and 2.22 < lon < 2.48):
        return None
    iid = f"{kind}:{uid}"
    if iid in ids:
        return None
    ids.add(iid)
    it = {"i": iid, "k": kind, "n": name, "a": round(lat, 5), "o": round(lon, 5)}
    it.update({k: v for k, v in kw.items() if v not in (None, "", [], {}, 0) or k == "t"})
    items.append(it)
    return it


def pt(rec, key="geo_point_2d"):
    g = rec.get(key) or {}
    return g.get("lat"), g.get("lon")


def percentile_tiers(group, score):
    """Rang par score ; les ex aequo partagent le même palier."""
    if not group:
        return
    group = sorted(group, key=lambda it: (score(it), h(it["i"]) % 1000 / 1e6))
    n = len(group)
    scores = [score(it) for it in group]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and scores[j + 1] == scores[i]:
            j += 1
        mid = (i + j) / 2 / max(1, n - 1)
        tier = 0 if mid < .35 else 1 if mid < .6 else 2 if mid < .8 else 3 if mid < .93 else 4
        for it in group[i:j + 1]:
            it["t"] = tier
        i = j + 1


# ---------- 1. Arbres remarquables ----------
arbres = []
gc = collections.Counter(r.get("arbres_genre") for r in load("arbresremarquablesparis.json"))
for r in load("arbresremarquablesparis.json"):
    g = r.get("geom_x_y") or {}
    y = None
    for key in ("com_annee_plantation", "arbres_dateplantation"):
        m = re.match(r"^(\d{4})", str(r.get(key) or ""))
        if m and int(m.group(1)) > 1700:
            y = int(m.group(1))
            break
    hgt, circ = num(r.get("arbres_hauteurenm")), num(r.get("arbres_circonferenceencm"))
    dom = r.get("com_domanialite") or ""
    age = THIS_YEAR - y if y else None
    it = add("arbre", int(num(r.get("arbres_idbase"))), r.get("com_nom_usuel") or r.get("arbres_libellefrancais") or "Arbre remarquable",
             g.get("lat"), g.get("lon"),
             s=r.get("com_nom_latin"), r=arr_of(r.get("com_arrondissement")),
             site=r.get("com_site"),
             f=[["Hauteur", f"{fmt_int(hgt)} m"], ["Circonf.", f"{fmt_int(circ)} cm"], ["Âge", f"{age} ans" if age else "inconnu"]],
             w=r.get("com_resume"), d=clip(r.get("com_descriptif"), 700),
             u=r.get("com_url_pdf"), p=r.get("com_url_photo1"), c=r.get("com_copyright1"),
             q=r.get("com_qualification_rem"),
             x={"h": hgt, "c": circ, "g": r.get("arbres_genre"), "y": y, "bois": 1 if dom.startswith("Bois") else 0, "lab": 1 if r.get("com_label_arbres") else 0})
    if it:
        score = (0 if age is None else 3 if age >= 200 else 2 if age >= 140 else 1 if age >= 80 else 0) if age else 1
        score += 2 if gc[r.get("arbres_genre")] == 1 else 1 if gc[r.get("arbres_genre")] == 2 else 0
        score += {"Historique": 2, "Symbolique": 1, "Botanique": 1}.get(r.get("com_qualification_rem"), 0)
        score += 1 if r.get("com_label_arbres") else 0
        it["_s"] = score
        arbres.append(it)
percentile_tiers(arbres, lambda it: it["_s"])

# ---------- 2. Parcs et jardins (espaces verts) ----------
ev = load("espaces_verts.geojson")["features"]
PARK_CATS = {"Square", "Jardin", "Parc", "Promenade", "Bois", "Arboretum", "Ile", "Archipel", "Foret urbaine", "Esplanade", "Mail"}
BIG_CATS = {"Parc", "Bois", "Arboretum", "Ile", "Archipel", "Foret urbaine"}
map_parks, parcs = [], []
for f in ev:
    p = f.get("properties") or {}
    cat = p.get("categorie")
    geom = f.get("geometry")
    if cat not in PARK_CATS and cat != "Cimetière":
        continue
    rings = encode_rings(geom, tol=4.0 if cat not in BIG_CATS else 6.0)
    if not rings:
        continue
    entry = {"c": "cim" if cat == "Cimetière" else "bois" if cat in ("Bois", "Foret urbaine") else "park", "r": rings}
    if cat in PARK_CATS:
        g = p.get("geom_x_y") or {}
        surf = num(p.get("surface_totale_reelle"))
        yr = p.get("annee_ouverture")
        it = add("parc", p.get("nsq_espace_vert"), title(p.get("nom_ev")) or cat, g.get("lat"), g.get("lon"),
                 s=cat.replace("Foret", "Forêt").replace("Ile", "Île"), r=arr_of(p.get("adresse_codepostal")),
                 site=title(" ".join(str(v) for v in (p.get("adresse_numero"), p.get("adresse_typevoie"), p.get("adresse_libellevoie")) if v)),
                 f=[["Surface", f"{surf / 10000:.1f} ha".replace(".", ",") if surf >= 10000 else f"{fmt_int(surf)} m²"],
                    ["Ouverture", str(yr) if yr else "?"], ["Type", cat.replace("Foret", "Forêt").replace("Ile", "Île")]],
                 w=f"Ancien nom : {title(p.get('ancien_nom_ev'))}" if p.get("ancien_nom_ev") else "",
                 x={"poly": len(map_parks)})
        if it:
            it["_s"] = (3 if cat in BIG_CATS else 0) + math.log10(1 + surf) + (1 if yr and int(num(yr)) < 1900 else 0)
            entry["i"] = it["i"]
            parcs.append(it)
    map_parks.append(entry)
percentile_tiers(parcs, lambda it: it["_s"])

# ---------- 3. Jardins partagés / relais / arbres en sursis ----------
for r in load("jardins-partages.json"):
    la, lo = pt(r)
    add("jpart", h(str(r.get("nom_ev")) + str(la)), r.get("nom_ev") or "Jardin partagé", la, lo, t=1,
        s="Jardin partagé", r=arr_of(r.get("arrondissement")), site=r.get("adresse"),
        f=[["Géré par", clip(r.get("nom_gerant"), 28)], ["Terrain", r.get("domaine") or "?"]],
        u=r.get("internet_1"))
for r in load("jardins-relais.json"):
    la, lo = pt(r)
    add("jrel", r.get("idt"), r.get("nom_de_la_structure") or "Jardin relais", la, lo, t=2,
        s=r.get("association"), r=arr_of(r.get("code_postal")), site=r.get("adresse"),
        f=[["Réseau", "Jardins relais"], ["Code", r.get("idt")]],
        w="Point relais pour végétaliser son quartier : graines, outils, conseils.",
        d=clip(r.get("projet"), 500), u=r.get("site_internet") if str(r.get("site_internet", "")).startswith("http") else "")
for r in load("arbres-a-abattre-pour-raison-sanitaires-et-essence-de-remplacement.json"):
    la, lo = pt(r)
    add("sursis", r.get("idbase"), r.get("libellefrancais") or "Arbre", la, lo, t=1,
        s="Arbre en sursis", r=arr_of(r.get("arrondissement")), site=title(r.get("adresse")),
        f=[["Essence", r.get("genre") or "?"], ["Remplacé par", r.get("genrefutur") or "?"], ["Lieu", r.get("domanialite") or "?"]],
        w="Cet arbre doit être abattu pour raison sanitaire. Sa carte ne sera bientôt plus capturable.",
        d=clip(r.get("motifabattage"), 400), x={"g": r.get("genre"), "h": 14, "c": 120, "eph": 1})

# ---------- 4. Fontaines ----------
FT = {
    "FONTNE_WALLACE": ("Fontaine Wallace", 3), "FTNE_PETILLANTE": ("Fontaine pétillante", 3),
    "FONTAINE_ALBIEN": ("Fontaine à l'albien", 4), "FTNE_MILLENAIRE": ("Fontaine du Millénaire", 4),
    "FONTAINE_ARCEAU": ("Fontaine Arceau", 1), "FONTAINE_2EN1": ("Fontaine 2 en 1", 1),
    "FONTAINE_TOTEM": ("Fontaine Totem", 2), "FTNE_POING_EAU": ("Fontaine Poing d'eau", 2),
    "BORNE_FONTAINE": ("Borne-fontaine", 0), "FONTAINE_BOIS": ("Fontaine des parcs", 0),
}
for r in load("fontaines-a-boire.json"):
    la, lo = pt(r)
    typ = r.get("type_objet") or ""
    nm, tier = FT.get(typ, ("Fontaine", 0))
    num_ = r.get("no_voirie_pair") or r.get("no_voirie_impair") or ""
    voie = title(r.get("voie"))
    add("fontaine", r.get("gid"), nm, la, lo, t=tier, s=r.get("modele") or "", r=arr_of(r.get("commune")),
        site=f"{num_} {voie}".strip(),
        f=[["Modèle", clip(r.get("modele") or "?", 22)], ["État", "En service" if r.get("dispo") == "OUI" else "En panne"]],
        w={"FONTNE_WALLACE": "Offertes à Paris par Richard Wallace en 1872, ces fontaines vert sombre sont devenues un symbole de la ville.",
           "FTNE_PETILLANTE": "Une fontaine qui sert de l'eau gazeuse, gratuitement.",
           "FONTAINE_ALBIEN": "Eau puisée dans la nappe de l'albien, à plus de 500 mètres de profondeur.",
           "FTNE_MILLENAIRE": "Fontaine installée pour le passage à l'an 2000."}.get(typ, ""),
        x={"ft": typ})

# ---------- 5. Rues ----------
rues_raw = load("denominations-emprises-voies-actuelles.json")
tv = collections.Counter(r.get("typvoie") for r in rues_raw)
rues, street_pts, street_rings = [], [], []
for r in rues_raw:
    la, lo = pt(r)
    geom = geom_of(r)
    sp = sample_boundary(geom, step=70, cap=24)
    flat, step = sp if sp else ([], 55)
    sie = r.get("siecle")
    sien = int(sie) if sie and str(sie).isdigit() else None
    L = num(r.get("longueur"))
    nm = cap1(r.get("typo_min") or title(r.get("typo")))
    hist = " ".join(clip(r.get(k), 200) for k in ("historique", "ouverture") if r.get(k))
    it = add("rue", r.get("id"), nm, la, lo, s=cap1(r.get("typvoie") or "voie"), r=arr_of(r.get("arrdt")),
             site=", ".join(r.get("quartier") or []),
             f=[["Longueur", f"{fmt_int(L)} m" if L else "?"], ["Largeur", f"{num(r.get('largeur')):g} m".replace(".", ",") if r.get("largeur") else "?"],
                ["Nommée", f"{sien}ᵉ s." if sien else "?"]],
             w=clip(r.get("orig"), 200), d=clip(hist, 360),
             x={"pts": flat, "rad": max(35, round(step / 2))})
    if it:
        s = (4 if sien and sien <= 15 else 3 if sien and sien <= 17 else 2 if sien == 18 else 1 if sien == 19 else 0)
        n = tv[r.get("typvoie")]
        s += 3 if n <= 10 else 2 if n <= 60 else 1 if n <= 250 else 0
        s += 0.5 if L and L < 60 else 0
        it["_s"] = s
        it["_ty"] = r.get("typvoie")
        it["_si"] = sien
        rues.append(it)
        street_rings.append({"i": it["i"], "c": "street", "r": encode_rings(geom, tol=1.2)})
        for i in range(0, len(flat), 2):
            street_pts.append((flat[i], flat[i + 1], it))
percentile_tiers(rues, lambda it: it["_s"])

# grille pour retrouver la rue la plus proche d'un point
GRID = collections.defaultdict(list)
for la_i, lo_i, it in street_pts:
    GRID[(la_i // 300, lo_i // 300)].append((la_i, lo_i, it))


def nearest_street(lat, lon):
    la_i, lo_i = enc(lon, lat)
    best, bd = None, 1e18
    cx, cy = la_i // 300, lo_i // 300
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for a, b, it in GRID.get((cx + dx, cy + dy), []):
                d = (a - la_i) ** 2 + ((b - lo_i) * COS0) ** 2
                if d < bd:
                    bd, best = d, it
    return best


# ---------- 6. Escaliers (regroupés par proximité) ----------
# Retirés du jeu le 14/10/2026 (décision de Timothée) : les escaliers restaient seuls en points dans la famille Rues.
esc = []
pts_esc = []
for r in esc:
    la, lo = pt(r)
    if la is None:
        continue
    x, y = to_m(lo, la)
    pts_esc.append([x, y, num(r.get("st_area_shape")), r.get("objectid")])
parent = list(range(len(pts_esc)))


def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


for i in range(len(pts_esc)):
    for j in range(i + 1, len(pts_esc)):
        if abs(pts_esc[i][0] - pts_esc[j][0]) < 28 and math.hypot(pts_esc[i][0] - pts_esc[j][0], pts_esc[i][1] - pts_esc[j][1]) < 28:
            parent[find(i)] = find(j)
clusters = collections.defaultdict(list)
for i in range(len(pts_esc)):
    clusters[find(i)].append(pts_esc[i])
escaliers = []
for cl in clusters.values():
    area = sum(c[2] for c in cl)
    x = sum(c[0] * max(c[2], 1) for c in cl) / sum(max(c[2], 1) for c in cl)
    y = sum(c[1] * max(c[2], 1) for c in cl) / sum(max(c[2], 1) for c in cl)
    lon, lat = from_m(x, y)
    st = nearest_street(lat, lon)
    nm = f"Escalier, {st['n'][:1].lower() + st['n'][1:]}" if st else "Escalier"
    it = add("escalier", min(c[3] for c in cl), nm, lat, lon, s="Voie en escalier", r=st.get("r", "") if st else "",
             site=st["n"] if st else "", f=[["Surface", f"{fmt_int(area)} m²"], ["Volées", str(len(cl))]],
             w="Paris compte plusieurs centaines de voies en escalier, surtout sur ses collines.")
    if it:
        it["_s"] = area
        escaliers.append(it)
percentile_tiers(escaliers, lambda it: it["_s"])

# ---------- 7. Plaques commémoratives ----------
pl = load("plaques_commemoratives.json")
oc = collections.Counter(r.get("objet_1") for r in pl)
plaques = []
for r in pl:
    la, lo = r.get("y_4326"), r.get("x_4326")
    sie = str(r.get("siecle") or "")
    first = int(re.match(r"\d+", sie).group()) if re.match(r"\d+", sie) else None
    obj = (r.get("objet_1") or "").replace("les ", "", 1)
    it = add("plaque", r.get("index_plaque"), r.get("titre") or r.get("personnalite") or "Plaque commémorative", la, lo,
             s=cap1(obj), r=arr_of(r.get("ardt")), site=title(r.get("adresse")),
             f=[["Siècle", f"{sie.replace('-', '–')}ᵉ" if sie else "?"], ["Matériau", cap1(r.get("materiau")) or "?"], ["Taille", r.get("taille") or "?"]],
             w=clip(r.get("retranscription"), 260), d=f"Emplacement : {r.get('emplacement')}." if r.get("emplacement") else "",
             x={"obj": r.get("objet_1")})
    if it:
        s = (3 if first and first <= 16 else 2 if first == 17 else 1 if first == 18 else 0)
        n = oc[r.get("objet_1")]
        s += 2 if n < 20 else 1 if n < 100 else 0
        s += 1.5 / math.log2(2 + n)
        it["_s"] = s
        it["_si"] = first
        plaques.append(it)
percentile_tiers(plaques, lambda it: it["_s"])

# ---------- 8. Femmes illustres ----------
seen = {}
for r in load("femmes-illustres-a-paris-portraits.json"):
    nm = r.get("name")
    if nm in seen and r.get("tab_name") == "77 Illustres Parisiennes":
        continue
    seen[nm] = r
for nm, r in seen.items():
    la, lo = pt(r)
    descs = [r.get(f"desc{i}") for i in range(1, 6) if r.get(f"desc{i}")]
    theme = r.get("tab_name") if r.get("tab_name") != "77 Illustres Parisiennes" else "Illustre Parisienne"
    add("femme", h(nm), nm, la, lo, t=2, s=theme, site=r.get("short_desc"),
        f=[["Thème", theme]], w=clip(descs[0] if descs else "", 260), d=clip(" ".join(descs[1:]), 600),
        p=r.get("thumb_url"), x={"th": theme})

# ---------- 9. Vestiges archéologiques ----------
vest = []
PER = [("protohistoire", "gaulois", 3), ("antiquite", "antiques", 2), ("moyen_age", "médiévaux", 1), ("temps_modernes", "modernes", 0.5), ("epoque_contemporaine", "contemporains", 0)]
for r in load("referentiel-archeologique-de-paris.json"):
    la, lo = pt(r)
    per = [p for p in PER if r.get(p[0]) == "Oui"]
    label = f"Vestiges {per[0][1]}" if per else "Site archéologique"
    eps = ", ".join({"protohistoire": "Gaule", "antiquite": "Antiquité", "moyen_age": "Moyen Âge", "temps_modernes": "Temps modernes", "epoque_contemporaine": "Époque contemp."}[p[0]] for p in per)
    it = add("vestige", r.get("id"), label, la, lo, s=r.get("nature_operation") or "Découverte", r=arr_of(r.get("code_postal")),
             site=r.get("adresse"), f=[["Époques", eps or "?"], ["Année", str(r.get("date_operation") or "?")]],
             w=clip(r.get("synthese"), 200), d=clip(r.get("synthese"), 520) if len(str(r.get("synthese") or "")) > 200 else "",
             x={"per": [p[0] for p in per]})
    if it:
        it["_s"] = sum(p[2] for p in per) + (1 if r.get("nature_operation") in ("Fouille", "Sauvetage urgent") else 0)
        vest.append(it)
percentile_tiers(vest, lambda it: it["_s"])

# ---------- 10. Patrimoine mondial ----------
pm = {}
for r in load("plu-annexes-biens-inscrits-au-patrimoine-mondial.json"):
    if r["nom"] not in pm or r["surface"] < pm[r["nom"]]["surface"]:
        pm[r["nom"]] = r
monde_polys = []
for nm, r in pm.items():
    la, lo = pt(r)
    rings = encode_rings(geom_of(r), tol=8.0)
    it = add("monde", h(nm), title(nm).replace("Oeuvre", "Œuvre"), la, lo, t=4, s="Patrimoine mondial de l'UNESCO",
             f=[["Surface", f"{num(r['surface']) / 10000:.1f} ha".replace(".", ",") if r["surface"] > 10000 else f"{fmt_int(r['surface'])} m²"], ["Inscrit", "UNESCO"]],
             w="Bien inscrit sur la liste du patrimoine mondial de l'UNESCO.",
             x={"mpoly": len(monde_polys)})
    if it:
        monde_polys.append(rings)

# ---------- 11. Lieux municipaux (sélection) ----------
LM = {
    "Musées municipaux": ("musee", 3), "Lieux de culte remarquables": ("culte", 2), "Bibliothèques": ("biblio", 1),
    "Théâtres et établissements culturels soutenus": ("theatre", 1), "Conservatoires": ("conserv", 1),
    "Ateliers Beaux-Arts": ("atelier", 1), "Lieux de decouverte et d initiation": ("decouverte", 2),
    "Cimetières": ("cimetiere", 2), "Mairies d'arrondissement": ("mairie", 1), "Bains-douches": ("bains", 2),
    "Piscines": ("piscine", 1), "Baignades estivales": ("baignade", 3), "Marchés spécialisés": ("marchesp", 3),
    "Skate park et aires de glisse": ("sport", 1), "Stades": ("sport", 1), "Terrains de boules": ("sport", 0),
}
for r in load("lieux-municipaux.json"):
    cat = r.get("categorie")
    if cat not in LM:
        continue
    kind, tier = LM[cat]
    add(kind, r.get("id"), r.get("name"), r.get("latitude"), r.get("longitude"), t=tier, s=cat,
        r=arr_of(r.get("address_postcode")), site=r.get("address_street"),
        f=[["Catégorie", clip(cat, 24)]], u=r.get("url"), p=r.get("photo_url"), c=r.get("photo_credit"))

# ---------- 12. Marchés découverts ----------
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
for r in load("marches-decouverts.json"):
    la, lo = pt(r)
    mask = [int(r.get(d) or 0) for d in DAYS]
    nd = sum(mask)
    sp = sample_boundary(geom_of(r), step=50, cap=30)
    flat, step = sp if sp else ([], 50)
    hours = [r.get("h_deb_sem_1"), r.get("h_fin_sem_1"), r.get("h_deb_sam"), r.get("h_fin_sam"), r.get("h_deb_dim"), r.get("h_fin_dim")]
    prod = r.get("produit") or "Alimentaire"
    tier = (3 if nd <= 1 else 2 if nd == 2 else 1) + (1 if prod != "Alimentaire" else 0)
    add("marche", r.get("id_marche"), title(r.get("nom_long")).replace("Marché", "Marché", 1), la, lo, t=min(4, tier),
        s=prod, r=arr_of(r.get("ardt")), site=clip(r.get("localisation"), 90),
        f=[["Jours", ", ".join(d[:3] for d, m in zip(DAYS, mask) if m)], ["Longueur", f"{fmt_int(num(r.get('lineaire')))} m"]],
        w=f"Se tient le {r.get('jours_tenue')}. Capturable uniquement pendant le marché.",
        x={"mk": mask, "hr": hours, "pts": flat, "rad": max(40, round(step / 2))})

# ---------- 13. Kiosques ----------
for r in load("kiosques-de-presse.json"):
    la, lo = pt(r)
    add("kiosque", r.get("code_mobilier"), "Kiosque à journaux", la, lo, t=0, s=r.get("type_activite"),
        r=arr_of(r.get("code_postal")), site=title(r.get("adresse")), f=[["Activité", r.get("type_activite") or "?"]])

# ---------- 14. Paris autrement (insolite) ----------
for r in load("paris-autrement-balades-dans-les-arrondissements-peripheriques-poi.json"):
    la, lo = pt(r)
    cat = r.get("categorie") or ""
    add("insolite", r.get("identifiant"), r.get("nom_poi") or r.get("legende"), la, lo,
        t=3 if cat in ("street-art", "célébrité", "patrimoine religieux") else 2, s=cap1(cat),
        r=arr_of(r.get("code_postal")), site=r.get("adresse"), f=[["Catégorie", cap1(cat)]],
        w=clip(r.get("legende"), 160), d=clip(r.get("texte_description"), 700),
        p=r.get("url_image"), c=r.get("copyright_image"))


# ---------- 15. Stations de métro, RER et tram (référentiel des arrêts IDFM) ----------
MODE = {"metro": ("Métro", 0), "rail": ("RER / Train", 1), "tram": ("Tramway", 0.5), "cableway": ("Câble", 2)}
groups = collections.defaultdict(list)
for r in load("arrets.json"):
    t = r.get("arrtype")
    pr = str(r.get("arrpostalregion") or "")
    if t not in MODE or not pr.startswith("751"):
        continue
    g = r.get("arrgeopoint") or {}
    if g.get("lat") is None:
        continue
    groups[(re.sub(r"\s+", " ", r.get("arrname") or "").strip(), t)].append(r)
stations = []
for (nm, t), rs in groups.items():
    # un même nom peut désigner deux stations éloignées : on sépare les quais à plus de 500 m
    clusters_ = []
    for r in rs:
        x, y = to_m(r["arrgeopoint"]["lon"], r["arrgeopoint"]["lat"])
        for cl in clusters_:
            if math.hypot(cl[0][0] - x, cl[0][1] - y) < 500:
                cl[1].append(r)
                break
        else:
            clusters_.append(((x, y), [r]))
    for _, crs in clusters_:
        la = sum(r["arrgeopoint"]["lat"] for r in crs) / len(crs)
        lo = sum(r["arrgeopoint"]["lon"] for r in crs) / len(crs)
        acc = collections.Counter(r.get("arraccessibility") for r in crs).most_common(1)[0][0]
        zone = crs[0].get("arrfarezone") or "?"
        label, mr = MODE[t]
        it = add("station", f"{t}-{min(int(r['arrid']) for r in crs)}", nm, la, lo, s=label,
                 r=str(int(str(crs[0]["arrpostalregion"])[-2:])), site=crs[0].get("arrtown"),
                 f=[["Mode", label], ["Quais", str(len(crs))], ["Zone", str(zone)],
                    ],
                 w={"true": "Station accessible aux personnes à mobilité réduite.", "partial": "Station partiellement accessible."}.get(acc, ""),
                 x={"mode": t, "quais": len(crs)})
        if it:
            # sans données de fréquentation : les grands pôles sont communs,
            # les stations à sens unique (un seul quai) sont légendaires
            q = len(crs)
            if t == "metro":
                it["t"] = 0 if q >= 4 else 1 if q >= 2 else 4
            elif t == "rail":
                it["t"] = 0 if nm.startswith("Gare") else 2
            else:
                it["t"] = 1
            stations.append(it)

# fréquentation IDFM (validations du trimestre) : plus une station est fréquentée, plus sa carte est prestigieuse
import ridership  # noqa: E402
if (SRC / "validations.json").exists():
    n_match = ridership.attach(stations, SRC / "validations.json")
    freq = [it for it in stations if it["x"].get("valid")]
    percentile_tiers(freq, lambda it: math.log10(1 + it["x"]["valid"]))
    for it in stations:
        if not it["x"].get("valid") and it["x"].get("mode") in ("metro", "rail"):
            it["t"] = 1  # station non rapprochée : Peu commune par défaut
    for it in freq:
        v = it["x"]["valid"]
        if it["x"].get("quais", 9) == 1:  # station à sens unique : un cran de plus
            it["t"] = min(4, it["t"] + 1)
        txt = f"{v / 1e6:.1f} M".replace(".", ",") if v >= 1e6 else f"{round(v / 1000)} k"
        it["f"] = [["Mode", it["s"]], ["Validations", txt], it["f"][2]]
        it["w"] = (it.get("w") or "") + f" {fmt_int(v)} validations au 2ᵉ trimestre 2026 (IDFM)."
        it["w"] = it["w"].strip()
    print("Fréquentation :", n_match, "stations rapprochées")

# ---------- 16. Lieux Wikidata (articles Wikipédia) ----------
import wikidata  # noqa: E402
wd_stats, wd_created = wikidata.integrate(str(SRC), items, add, KINDS, percentile_tiers, clip, cap1)
print("Wikidata :", dict(wd_stats))

# ---------- Fond de carte : arrondissements et voies d'eau ----------
import ast  # noqa: E402
for f in load("arrondissements.geojson")["features"]:
    pr = f["properties"]
    c = pr.get("geom_x_y")
    c = ast.literal_eval(c) if isinstance(c, str) else (c or {})
    map_parks.append({"c": "arr", "r": encode_rings(f["geometry"], tol=3.0), "label": str(pr.get("c_ar")), "at": [c.get("lat"), c.get("lon")]})
for f in load("voies-deau.geojson")["features"]:
    map_parks.append({"c": "water", "r": encode_rings(f["geometry"], tol=2.0)})
map_parks.extend(street_rings)

# arrondissement manquant : celui de la rue la plus proche
for it in items:
    if not it.get("r"):
        st = nearest_street(it["a"], it["o"])
        if st and st.get("r"):
            it["r"] = st["r"]

# ---------- Collections ----------
by_kind = collections.defaultdict(list)
for idx, it in enumerate(items):
    by_kind[it["k"]].append(idx)


def sel(kind, pred=lambda it: True):
    return [i for i in by_kind[kind] if pred(items[i])]


COLS = [
    ("nature", "Plus vieux que le métro", "Arbres plantés avant 1900", sel("arbre", lambda it: (it.get("x", {}).get("y") or 9999) < 1900)),
    ("nature", "Les géants", "Arbres de 25 mètres et plus", sel("arbre", lambda it: it.get("x", {}).get("h", 0) >= 25)),
    ("nature", "Arbres de mémoire", "Plantés en souvenir ou témoins de l'histoire", sel("arbre", lambda it: it.get("q") in ("Symbolique", "Historique"))),
    ("nature", "Les grands parcs", "Parcs, bois, îles et arboretum", sel("parc", lambda it: it.get("s") in ("Parc", "Bois", "Arboretum", "Île", "Archipel", "Forêt urbaine"))),
    ("nature", "Jardins relais", "Le réseau complet", sel("jrel")),
    ("eau", "Fontaines Wallace", "Les fontaines vertes de Richard Wallace", sel("fontaine", lambda it: it["x"].get("ft") == "FONTNE_WALLACE")),
    ("eau", "Fontaines pétillantes", "Eau gazeuse gratuite", sel("fontaine", lambda it: it["x"].get("ft") == "FTNE_PETILLANTE")),
    ("eau", "Fontaines légendaires", "Albien et Millénaire", sel("fontaine", lambda it: it["x"].get("ft") in ("FONTAINE_ALBIEN", "FTNE_MILLENAIRE"))),
    ("eau", "Baignades estivales", "Se baigner à Paris", sel("baignade")),
    ("eau", "Bains-douches", "Les bains-douches municipaux", sel("bains")),
    ("rues", "Rues médiévales", "Voies nommées avant le XVIᵉ siècle", [items.index(it) for it in rues if it.get("_si") and it["_si"] <= 15]),
    ("rues", "Hameaux, sentes et belvédères", "Les types de voies les plus rares", [items.index(it) for it in rues if it.get("_ty") in ("belvédère", "hameau", "sente", "balcon", "péristyle", "terrasse", "placette", "ruelle", "sentier")]),
    ("memoire", "Femmes de sciences", "Scientifiques illustres", sel("femme", lambda it: it["x"].get("th") == "Scientifiques")),
    ("memoire", "Femmes de lettres", "Écrivaines illustres", sel("femme", lambda it: it["x"].get("th") == "Femmes de lettres")),
    ("memoire", "Sportives", "Championnes illustres", sel("femme", lambda it: it["x"].get("th") == "Sportives")),
    ("memoire", "Artistes", "Artistes illustres", sel("femme", lambda it: it["x"].get("th") == "Artistes")),
    ("memoire", "Inventeurs et ingénieurs", "Plaques commémoratives", sel("plaque", lambda it: it["x"].get("obj") == "les inventeurs et ingénieurs")),
    ("memoire", "Aviateurs et explorateurs", "Plaques commémoratives", sel("plaque", lambda it: it["x"].get("obj") in ("les aviateurs", "les explorateurs"))),
    ("memoire", "Plaques d'Ancien Régime", "Plaques du XVIIᵉ siècle et avant", [items.index(it) for it in plaques if it.get("_si") and it["_si"] <= 17]),
    ("patrimoine", "Patrimoine mondial", "Les biens UNESCO de Paris", sel("monde")),
    ("patrimoine", "Vestiges gaulois", "Traces de la Lutèce d'avant Rome", sel("vestige", lambda it: "protohistoire" in it["x"].get("per", []))),
    ("patrimoine", "Mairies d'arrondissement", "Les 17 mairies", sel("mairie")),
    ("patrimoine", "Cimetières parisiens", "Tous les cimetières de la Ville", sel("cimetiere")),
    ("culture", "Musées de la Ville", "Les musées municipaux", sel("musee")),
    ("culture", "Conservatoires", "Musique, danse, théâtre", sel("conserv")),
    ("quartier", "Marchés aux puces et aux fleurs", "Les marchés spécialisés", sel("marchesp")),
    ("quartier", "Marchés bio", "Marchés alimentaires bio", sel("marche", lambda it: it.get("s") == "Alimentaire bio")),
    ("quartier", "Skate parks et stades", "Les lieux de sport", sel("sport", lambda it: "Terrain" not in (it.get("s") or ""))),
    ("patrimoine", "Paris disparu", "Lieux détruits, à retrouver là où ils se dressaient", sel("disparu")),
    ("patrimoine", "Enceintes de Paris", "Portes, bastions et murailles", sel("enceinte")),
    ("patrimoine", "Hôtels particuliers du Marais", "Hôtels particuliers des 3ᵉ et 4ᵉ arrondissements", sel("hotelpart", lambda it: it.get("r") in ("3", "4"))),
    ("eau", "Ponts de Paris", "Tous les ponts et passerelles", sel("pont")),
    ("rues", "Passages couverts", "Les galeries et passages couverts", [i for i, it in enumerate(items) if (it.get("x") or {}).get("couvert")]),
    ("quartier", "Cafés et restaurants historiques", "Les adresses qui ont leur article Wikipédia", sel("cafe")),
    ("transport", "Stations fantômes", "Les stations fermées ou jamais ouvertes", sel("fantome")),
    ("transport", "Les gares parisiennes", "Les grandes gares RER et Transilien", sel("station", lambda it: it["x"].get("mode") == "rail" and it["n"].startswith("Gare"))),
    ("transport", "Tramways de Paris", "Toutes les stations de tram dans Paris", sel("station", lambda it: it["x"].get("mode") == "tram")),
    ("transport", "Petites stations de métro", "Les stations de métro à un seul quai par sens", sel("station", lambda it: it["x"].get("mode") == "metro" and it["x"].get("quais", 9) <= 2)),
]
cols = [[fam, name, sub, idxs] for fam, name, sub, idxs in COLS if len(idxs) >= 2]

# ---------- Sortie : base SQLite puis export JSON pour le jeu ----------
for it in items:
    for k in [k for k in it if k.startswith("_")]:
        del it[k]
    it.setdefault("t", 0)

import db  # noqa: E402

DB_PATH = ROOT / "parisquest.sqlite"
db.write(DB_PATH, FAMILIES, KINDS, items, cols, map_parks, monde_polys)
db.export(DB_PATH, OUT)

cnt = collections.Counter(it["k"] for it in items)
print(len(items), "cartes")
for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
    tiers = collections.Counter(it["t"] for it in items if it["k"] == k)
    print(f"  {k:10} {v:5}  paliers {dict(sorted(tiers.items()))}")
print(len(cols), "collections")
for f in ("places.json", "map.json", "streets.json"):
    print(f, round((OUT / f).stat().st_size / 1e6, 2), "Mo")
print(DB_PATH.name, round(DB_PATH.stat().st_size / 1e6, 1), "Mo")
