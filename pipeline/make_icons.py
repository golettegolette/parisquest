"""Icônes de l'application (écran d'accueil, onglet) : la plaque de rue Parisquest, fronton et cadre vert.
Rendu par Chromium (Playwright) ; à relancer seulement si le logo change. Les PNG restent dans site/icons."""
import asyncio, pathlib
from playwright.async_api import async_playwright
ROOT = pathlib.Path(__file__).parent; ICONS = ROOT / "site" / "icons"
OUT = "M3 23 H66 V18 C70 18 72 15 76 10 C84 2 116 2 124 10 C128 15 130 18 134 18 V23 H197 Q199 23 199 25 V69 Q199 71 197 71 H3 Q1 71 1 69 V25 Q1 23 3 23 Z"
def svg(size, maskable):
    # plaque carrée pour l'icône : même fronton, corps plus haut, « PQ » en grand
    body = "M10 60 H50 V52 C58 52 62 42 70 32 C82 14 118 14 130 32 C138 42 142 52 150 52 V60 H190 Q196 60 196 66 V186 Q196 192 190 192 H10 Q4 192 4 186 V66 Q4 60 10 60 Z"
    inner = "M16 67 H184 V180 H16 Z M57 67 V58 C65 57 69 48 76 38 C87 23 113 23 124 38 C131 48 135 57 143 58 V67"
    scale = .78 if maskable else .96
    bg = "#172B4D" if maskable else "#BBA987"
    off = 100 - 100 * scale
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 200 200">
<rect width="200" height="200" fill="{bg}"/>
<g transform="translate({off} {off + 2}) scale({scale})">
<path d="{body}" fill="#172B4D" stroke="#2D6448" stroke-width="9" stroke-linejoin="round"/>
<path d="{inner}" fill="none" stroke="#F6F2E8" stroke-width="3" stroke-linejoin="round"/>
<text x="100" y="56" text-anchor="middle" font-family="DejaVu Sans Condensed, Arial Narrow, sans-serif" font-weight="700" font-size="15" letter-spacing="2.5" fill="#F6F2E8">PARIS</text>
<text x="100" y="157" text-anchor="middle" font-family="DejaVu Sans Condensed, Arial Narrow, sans-serif" font-weight="700" font-size="92" fill="#F6F2E8">PQ</text>
</g></svg>'''
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = await b.new_page()
        for name, size, mask in [("icon-192.png", 192, False), ("icon-512.png", 512, False), ("apple-touch-icon.png", 180, False), ("icon-maskable-512.png", 512, True)]:
            await pg.set_viewport_size({"width": size, "height": size})
            await pg.set_content(f"<html><body style='margin:0'>{svg(size, mask)}</body></html>")
            await pg.screenshot(path=str(ICONS / name), clip={"x": 0, "y": 0, "width": size, "height": size})
        await b.close()
asyncio.run(main()); print("icônes prêtes")
