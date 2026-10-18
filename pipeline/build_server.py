"""Prépare les données du serveur : site/supabase/places.csv (référentiel des lieux pour Supabase)."""
import csv, json, math, pathlib
ROOT = pathlib.Path(__file__).parent
D = ROOT / "site" / "data"
pl = json.load(open(D / "places.json")); mp = json.load(open(D / "map.json"))
dec = lambda a, b: (48.8 + a / 1e5, 2.2 + b / 1e5)
def hav(a1, o1, a2, o2):
    r = math.radians
    return 2 * 6371000 * math.asin(math.sqrt(math.sin(r(a2 - a1) / 2) ** 2 + math.cos(r(a1)) * math.cos(r(a2)) * math.sin(r(o2 - o1) / 2) ** 2))
rows = []
for it in pl["items"]:
    kd = pl["kinds"][it["k"]]; x = it.get("x") or {}
    rad = x.get("rad") or (100 if it["k"] == "arbre" and x.get("bois") else kd["rad"])
    pts = []
    if x.get("pts"): pts += [dec(x["pts"][j], x["pts"][j + 1]) for j in range(0, len(x["pts"]), 2)]
    rings = []
    if x.get("poly") is not None and x["poly"] < len(mp["parks"]): rings = mp["parks"][x["poly"]]["r"]
    if x.get("mpoly") is not None and x["mpoly"] < len(mp.get("monde", [])): rings = mp["monde"][x["mpoly"]]
    for r in rings: pts += [dec(r[j], r[j + 1]) for j in range(0, len(r), 2)]
    ext = max((hav(it["a"], it["o"], a, b) for a, b in pts), default=0)
    rows.append([it["i"], it["k"], kd["f"], it["t"], round(it["a"], 6), round(it["o"], 6), round(ext + rad, 1)])
out = ROOT / "site" / "supabase" / "places.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["id", "kind", "family", "tier", "lat", "lon", "reach_m"]); w.writerows(rows)
print(len(rows), "lieux →", out, f"{out.stat().st_size / 1e6:.2f} Mo")

# Arrondissement de chaque lieu, pour le classement par arrondissement (à exécuter après direction_a.sql)
import collections
g = collections.defaultdict(list)
for it in pl["items"]:
    r = it.get("r")
    if r and str(r).isdigit() and 1 <= int(r) <= 20: g[int(r)].append(it["i"])
lines = ["-- Parisquest : arrondissement de chaque lieu (à exécuter après direction_a.sql). Généré par pipeline/build_server.py."]
for a in sorted(g):
    lines.append(f"update public.places set arr = {a} where id = any('{{" + ",".join('"' + i + '"' for i in g[a]) + "}'::text[]);")
lines.append("select arr, count(*) from public.places group by arr order by arr;")
out2 = ROOT / "site" / "supabase" / "places_arr.sql"
out2.write_text("\n".join(lines) + "\n")
print(sum(len(v) for v in g.values()), "lieux avec arrondissement →", out2)
