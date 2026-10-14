"""Rapprochement des stations du jeu avec la fréquentation IDFM (validations, libellés abrégés)."""
import json
import re
import unicodedata

ABBR = {"st": "saint", "ste": "sainte", "av": "avenue", "bd": "boulevard", "pl": "place", "pte": "porte", "gds": "grands",
        "egli": "eglise", "nat": "nationale"}
DROP = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "a", "sur", "s"}


def toks(s, abbr=False):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\([^)]*\)", " ", s)
    out = [t for t in re.split(r"[^a-z0-9]+", s) if t and t not in DROP]
    return [ABBR.get(t, t) if abbr else t for t in out]


def match_score(vt, st):
    """Chaque mot (souvent abrégé) du libellé de validation doit commencer un mot de la station, dans l'ordre."""
    if not vt or not st:
        return 0
    j, hit, first = 0, 0, None
    for t in vt:
        while j < len(st) and not st[j].startswith(t):
            j += 1
        if j == len(st):
            return 0
        if first is None:
            first = j
        hit += 1
        j += 1
    if first > 1:
        return 0
    return hit / len(st) + (0.2 if first == 0 else 0)


def merged_tokens(s):
    """Variante où les articles sont soudés au mot suivant (« La Tour » -> « latour »)."""
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"\([^)]*\)", " ", s)
    raw = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    out, carry = [], ""
    for t in raw:
        if t in DROP:
            carry += t
            continue
        out.append(carry + t)
        carry = ""
    return out


def load(path):
    rows = json.load(open(path, encoding="utf-8"))
    out = {}
    for r in rows:
        name = r.get("libelle_arret") or ""
        if name in ("Inconnu", ""):
            continue
        out[name] = out.get(name, 0) + (r.get("validations") or 0)
    return [(toks(n, abbr=True), n, v) for n, v in out.items()]


def attach(items, path):
    vals = load(path)
    matched = 0
    for it in items:
        if it["k"] != "station" or it.get("x", {}).get("mode") not in ("metro", "rail"):
            continue
        st, st2 = toks(it["n"]), merged_tokens(it["n"])
        best, bs = None, 0.0
        for vt, vn, v in vals:
            sc = max(match_score(vt, st), match_score(vt, st2) - 0.05)
            if sc > bs:
                best, bs = (vn, v), sc
        if best and bs >= 0.5:
            it.setdefault("x", {})["valid"] = int(best[1])
            it["x"]["valid_lib"] = best[0]
            matched += 1
    return matched
