"""Lignes de métro, RER, tramway et Transilien desservant chaque station du jeu.

Sources (Île-de-France Mobilités, open data) :
  data/src/idfm-arrets-lignes.csv          arrêts desservis par chaque ligne (jeu « arrets-lignes »)
  data/src/idfm-referentiel-des-lignes.csv couleurs officielles des lignes (jeu « referentiel-des-lignes »)
Sortie : site/data/places.json enrichi : champ « ln » (codes de lignes) sur les stations,
         et table « lines » (nom, mode, couleur, couleur du texte). À relancer après build2.py.
Vérifié le 18/10/2026 contre Wikipédia (lignes 1, 4, 11, 14, 3bis ; RER A à E dans Paris)."""
import csv, json, math, re, unicodedata, pathlib, collections
ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "data" / "src"
PL = ROOT / "site" / "data" / "places.json"

MODES = {"Metro": "metro", "Tramway": "tram", "RapidTransit": "rer", "LocalTrain": "train", "RailShuttle": "train", "Funicular": "funi"}
def code(mode, short):
    if mode == "metro": return "M" + short.replace("B", "bis")
    if mode == "rer": return "R" + short
    if mode == "train": return "TN" + short
    if mode == "funi": return "FUN"
    return short                                         # tram : T2, T3a…
LABEL = lambda mode, short: {"metro": short.replace("B", "bis"), "rer": short, "train": short, "funi": "Funi", "tram": short}[mode]
NAME = lambda mode, short: {"metro": f"Métro {short.replace('B', 'bis')}", "rer": f"RER {short}", "train": f"Transilien {short}", "funi": "Funiculaire de Montmartre", "tram": f"Tramway {short}"}[mode]

def norm(s):
    s = unicodedata.normalize("NFD", s.lower()); s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", s.replace("gare de", "").replace("paris", ""))
def hav(a1, o1, a2, o2):
    r = math.radians
    return 2 * 6371000 * math.asin(math.sqrt(math.sin(r(a2 - a1) / 2) ** 2 + math.cos(r(a1)) * math.cos(r(a2)) * math.sin(r(o2 - o1) / 2) ** 2))

ref = {r["ID_Line"]: r for r in csv.DictReader(open(SRC / "idfm-referentiel-des-lignes.csv", encoding="utf-8-sig"), delimiter=";")}
rows = [r for r in csv.DictReader(open(SRC / "idfm-arrets-lignes.csv", encoding="utf-8-sig"), delimiter=";") if r["mode"] in MODES]
lines, by_stop = {}, collections.defaultdict(set)
for r in rows:
    m = MODES[r["mode"]]; c = code(m, r["route_long_name"]); rid = r["route_id"].split(":")[-1]; rf = ref.get(rid, {})
    lines[c] = {"n": NAME(m, r["route_long_name"]), "l": LABEL(m, r["route_long_name"]), "m": m,
                "c": "#" + (rf.get("ColourWeb_hexa") or "888888"), "t": "#" + (rf.get("TextColourWeb_hexa") or "ffffff")}
    r["_c"] = c; by_stop[r["stop_id"].split(":")[-1]].add(c)

pl = json.load(open(PL))
ACCEPT = {"metro": {"metro"}, "tram": {"tram"}, "rail": {"rer", "train"}}
# Corrections vérifiées à la main : la gare de Bercy (grandes lignes) est en correspondance avec le métro Bercy (6 et 14).
MANUAL = {"station:rail-41397": ["M6", "M14"], "station:rail-479034": ["M6", "M14"]}
n = 0
for it in pl["items"]:
    if it["k"] != "station": it.pop("ln", None); continue
    mode = (it.get("x") or {}).get("mode")
    got = set(by_stop.get(it["i"].split("-")[-1], set()))
    for r in rows:
        d = hav(it["a"], it["o"], float(r["stop_lat"]), float(r["stop_lon"]))
        if d >= 350 or MODES[r["mode"]] not in ACCEPT.get(mode, set()): continue
        a, b = norm(r["stop_name"]), norm(it["n"])
        if a == b or (d < 120 and (a in b or b in a)): got.add(r["_c"])
    got |= set(MANUAL.get(it["i"], []))
    if got:
        order = {"metro": 0, "rer": 1, "train": 2, "tram": 3, "funi": 4}
        it["ln"] = sorted(got, key=lambda c: (order[lines[c]["m"]], len(lines[c]["l"]), lines[c]["l"])); n += 1
    else: it.pop("ln", None)
used = {c for it in pl["items"] for c in it.get("ln", [])}
pl["lines"] = {c: v for c, v in lines.items() if c in used}
json.dump(pl, open(PL, "w"), ensure_ascii=False, separators=(",", ":"))
print(n, "stations avec lignes ;", len(pl["lines"]), "lignes :", " ".join(sorted(pl["lines"])))
