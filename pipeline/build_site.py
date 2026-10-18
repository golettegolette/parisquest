"""Assemble la version hébergée (GitHub Pages) dans site/ à partir de parisquest.html."""
import json, shutil, time, pathlib

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
src = (ROOT / "parisquest.html").read_text()
head_part, body_part = src.split("</style>", 1)
head_part = head_part.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
VERSION = time.strftime("%Y%m%d%H%M")
# Serveur : site/supabase/config.json = {"url": "https://xxxx.supabase.co", "anonKey": "..."} (clé publique, sans danger)
CONF = SITE / "supabase" / "config.json"
SUPABASE = ""
if CONF.exists():
    c = json.loads(CONF.read_text())
    if c.get("url") and c.get("anonKey"):
        SUPABASE = ('\n<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js"></script>\n'
                    f'<script>window.PQ_SUPABASE = {json.dumps({"url": c["url"], "anonKey": c["anonKey"], "payments": bool(c.get("payments"))})};</script>')
ML_VER = "4.7.1"

index = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Parisquest : collectionnez Paris. Rendez-vous sur place pour capturer arbres remarquables, monuments, fontaines, stations et 18 000 lieux de la capitale.">
<meta name="theme-color" content="#172B4D">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Parisquest">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@{ML_VER}/dist/maplibre-gl.css">
<script src="https://unpkg.com/maplibre-gl@{ML_VER}/dist/maplibre-gl.js"></script>
<script>window.PQ_HOSTED = true;</script>{SUPABASE}
{head_part}</style>
</head>
<body>{body_part.replace("</script>", "", 0)}
<script>
if ("serviceWorker" in navigator && location.protocol === "https:") navigator.serviceWorker.register("sw.js").catch(() => {{}});
</script>
</body>
</html>
"""
(SITE / "index.html").write_text(index)

(SITE / "manifest.webmanifest").write_text(json.dumps({
    "name": "Parisquest", "short_name": "Parisquest", "lang": "fr",
    "description": "Collectionnez Paris, lieu par lieu.",
    "start_url": "./", "scope": "./", "display": "standalone", "orientation": "portrait",
    "background_color": "#BBA987", "theme_color": "#172B4D",
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}, ensure_ascii=False, indent=2))

(SITE / "sw.js").write_text(f"""// Parisquest : cache hors ligne de l'application et des données (réseau d'abord, cache en secours).
const CACHE = "parisquest-{VERSION}";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icons/icon-192.png", "./data/places.json", "./data/map.json", "./data/quests.json", "./data/streets.json"];
self.addEventListener("install", e => {{ e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); }});
self.addEventListener("activate", e => {{ e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); }});
self.addEventListener("fetch", e => {{
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then(r => {{ if (r.ok) {{ const c = r.clone(); caches.open(CACHE).then(k => k.put(e.request, c)); }} return r; }})
    .catch(() => caches.match(e.request, {{ ignoreSearch: true }}).then(r => r || caches.match("./index.html"))));
}});
""")
(SITE / ".nojekyll").write_text("")

# Icônes : générées une fois par make_icons.py (plaque de rue avec fronton), gardées dans site/icons

# Chaîne de données, pour mémoire
PIPE = SITE / "pipeline"; PIPE.mkdir(exist_ok=True)
for f in ["build2.py", "db.py", "wikidata.py", "ridership.py", "build_site.py", "make_icons.py", "build_server.py", "ponts.py", "vestiges.py", "acces.py", "lines.py", "quests.py", "requetes.sql", "parisquest.html", "journal-donnees.md"]:
    shutil.copy(ROOT / f, PIPE / f)
print("site prêt", VERSION)
