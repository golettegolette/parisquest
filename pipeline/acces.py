"""Distances de capture selon l'accès public (décision de Timothée, 18/10/2026 : éviter les intrusions et la mise en danger).

On dessine l'espace public sur une grille de 2 m : emprises des voies publiques (et privées ouvertes à la circulation),
parcs, jardins, bois et cimetières de la Ville. Pour chaque lieu on mesure la distance entre son point (ou les points
de son tracé) et cet espace public, puis :
  * voies privées fermées au public (villas, cours, cités, squares « non inscrits à la liste des voies privées ouvertes
    à la circulation publique ») : le lieu est déplacé à son entrée, là où il touche l'espace public, et se capture
    depuis l'entrée (40 m), sans jamais avoir à y entrer ;
  * autres lieux trop loin de l'espace public pour leur rayon (gares, lieux en fond de cour, œuvres dans des enceintes) :
    le rayon de capture est allongé jusqu'à atteindre l'espace public (distance + 20 m, 150 m au plus).
Les lieux qui sont eux-mêmes un espace (parcs, cimetières, sites du patrimoine mondial) ne changent pas.
build_server.py écrit ensuite site/supabase/acces.sql pour reporter positions et rayons sur le serveur.
À lancer après ponts.py, avant lines.py. Peut être relancé : les valeurs d'origine sont gardées (x.rad0)."""
import json, math, pathlib
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = pathlib.Path(__file__).parent
PL = ROOT / "site" / "data" / "places.json"
pl = json.load(open(PL)); K = pl["kinds"]
mp = json.load(open(ROOT / "site" / "data" / "map.json"))
V = json.load(open(ROOT / "data" / "src" / "denominations-emprises-voies-actuelles.json"))

RES = 2.0                      # mètres par case
LAT0, LON0 = 48.80, 2.20
KX = math.cos(math.radians(48.86)) * 111320; KY = 110574
W, H = int(0.28 * KX / RES), int(0.13 * KY / RES)
px = lambda lat, lon: ((lon - LON0) * KX / RES, (0.13 - (lat - LAT0)) * KY / RES)
dec = lambda a, b: (48.8 + a / 1e5, 2.2 + b / 1e5)
enc = lambda lat, lon: [round((lat - 48.8) * 1e5), round((lon - 2.2) * 1e5)]
FERMEE = "Voie privée non inscrite"
EXTRA, CAP, PRIV_RAD = 20, 150, 40

# ---------- espace public ----------
img = Image.new("1", (W, H), 0); dr = ImageDraw.Draw(img)
statut = {}; trous = []
for v in V:
    statut["rue:" + v["id"]] = v["statut"] or ""
    if not v["geo_shape"] or (v["statut"] or "").startswith(FERMEE): continue
    g = v["geo_shape"]["geometry"]
    for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []):
        if len(poly) == 1: dr.polygon([px(b, a) for a, b in poly[0]], fill=1); continue
        # polygone à trous (îlot au milieu d'une place) : dessiné à part pour ne pas effacer les voies voisines
        rings = [[px(b, a) for a, b in r] for r in poly]
        x0 = int(min(q[0] for q in rings[0])); y0 = int(min(q[1] for q in rings[0]))
        x1 = int(max(q[0] for q in rings[0])) + 2; y1 = int(max(q[1] for q in rings[0])) + 2
        loc = Image.new("1", (x1 - x0, y1 - y0), 0); ld = ImageDraw.Draw(loc)
        ld.polygon([(q[0] - x0, q[1] - y0) for q in rings[0]], fill=1)
        for r in rings[1:]: ld.polygon([(q[0] - x0, q[1] - y0) for q in r], fill=0)
        trous.append((x0, y0, np.array(loc, dtype=bool)))
for p in mp["parks"]:
    for r in p["r"]:
        pts = [px(*dec(r[j], r[j + 1])) for j in range(0, len(r), 2)]
        if len(pts) >= 3: dr.polygon(pts, fill=1)
pub = np.array(img, dtype=bool)
for x0, y0, m in trous:
    sy, sx = slice(max(0, y0), min(H, y0 + m.shape[0])), slice(max(0, x0), min(W, x0 + m.shape[1]))
    pub[sy, sx] |= m[sy.start - y0:sy.stop - y0, sx.start - x0:sx.stop - x0]
dist = ndimage.distance_transform_edt(~pub).astype(np.float32) * RES
def D(lat, lon):
    x, y = px(lat, lon); x, y = int(x), int(y)
    return float(dist[y, x]) if 0 <= y < H and 0 <= x < W else 0.0
hav = lambda a1, o1, a2, o2: 2 * 6371000 * math.asin(math.sqrt(math.sin(math.radians(a2 - a1) / 2) ** 2 + math.cos(math.radians(a1)) * math.cos(math.radians(a2)) * math.sin(math.radians(o2 - o1) / 2) ** 2))

# ---------- lieux ----------
n_priv = n_ext = 0; loin = []
for it in pl["items"]:
    x = it.get("x") or {}
    if x.get("poly") is not None or x.get("mpoly") is not None: continue
    base = x.get("rad0") or x.get("rad") or (100 if it["k"] == "arbre" and x.get("bois") else K[it["k"]]["rad"])
    if it["k"] == "rue" and statut.get(it["i"], "").startswith(FERMEE):
        if not x.get("priv"):
            pts = [dec(x["pts"][j], x["pts"][j + 1]) for j in range(0, len(x.get("pts") or []), 2)] or [(it["a"], it["o"])]
            ds = [(D(a, b), a, b) for a, b in pts]
            dmin = min(d for d, _, _ in ds)
            ent = []                                    # entrées : points du tracé au bord de l'espace public
            for d, a, b in sorted(ds):
                if d <= max(12, dmin + 2) and all(hav(a, b, e[1], e[2]) > 40 for e in ent): ent.append((d, a, b))
            it["a"], it["o"] = round(ent[0][1], 6), round(ent[0][2], 6)
            x["pts"] = [v for _, a, b in ent for v in enc(a, b)]
            x["priv"] = 1; x["rad0"] = base
            x["rad"] = min(CAP, max(PRIV_RAD, math.ceil(max(d for d, _, _ in ent) + EXTRA)))
            it["x"] = x
        n_priv += 1
        continue
    pts = [(it["a"], it["o"])] + [dec(x["pts"][j], x["pts"][j + 1]) for j in range(0, len(x.get("pts") or []), 2)]
    d = min(D(a, b) for a, b in pts)
    if d > base - 10:
        x["rad0"] = base; x["rad"] = min(CAP, max(base, math.ceil(d + EXTRA))); x["acc"] = round(d)
        it["x"] = x; n_ext += 1
        if d + EXTRA > CAP: loin.append((round(d), it["k"], it["n"]))
    elif x.get("rad0"):                                  # relance : revenir au rayon d'origine si plus nécessaire
        x["rad"] = x.pop("rad0"); x.pop("acc", None)
        if x["rad"] == K[it["k"]]["rad"]: x.pop("rad")

json.dump(pl, open(PL, "w"), ensure_ascii=False, separators=(",", ":"))
print(f"{n_priv} voies privées fermées : capture depuis l'entrée ; {n_ext} lieux au rayon allongé ; "
      f"{len(loin)} lieux à plus de {CAP - EXTRA} m de l'espace public (gares, grands jardins d'État : accessibles par l'intérieur)")
for l in sorted(loin, reverse=True)[:12]: print("  ", l)

# ---------- Arrondissement d'après la position (les fiches Wikidata se trompent parfois : Café de Flore noté dans le 5e) ----------
from matplotlib.path import Path
G = json.load(open(ROOT / "data" / "src" / "arrondissements.geojson"))
ARRS = [(int(f["properties"]["c_ar"]), Path(poly[0])) for f in G["features"]
        for poly in ([f["geometry"]["coordinates"]] if f["geometry"]["type"] == "Polygon" else f["geometry"]["coordinates"])]
def arr_of(lat, lon): return next((a for a, p in ARRS if p.contains_point((lon, lat))), None)
fix = 0
for it in pl["items"]:
    if it["k"] == "rue": continue                     # une voie peut traverser plusieurs arrondissements : on garde le sien
    a = arr_of(it["a"], it["o"])
    if not a or str(it.get("r")) == str(a): continue
    # près d'une limite (Arc de triomphe, colonne de Juillet), on garde l'arrondissement de la fiche
    near = {arr_of(it["a"] + 40 / KY * math.sin(t), it["o"] + 40 / KX * math.cos(t)) for t in [k * math.pi / 4 for k in range(8)]}
    if str(it.get("r")).isdigit() and int(it["r"]) in near: continue
    it["r"] = str(a); fix += 1
json.dump(pl, open(PL, "w"), ensure_ascii=False, separators=(",", ":"))
print(fix, "arrondissements corrigés d'après la position")
