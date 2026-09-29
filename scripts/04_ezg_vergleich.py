import json
import os
import time
import requests
import geopandas as gpd

quellen = gpd.read_file("quellen_mit_ziel.geojson").to_crs(2056)
url = "https://api3.geo.admin.ch/rest/services/api/MapServer/identify"
headers = {"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"}

cache_datei = "daten/ezg_cache.json"
cache = json.load(open(cache_datei)) if os.path.exists(cache_datei) else {}

def schluessel(g):
    return f"{round(g.x)},{round(g.y)}"

# 1. Einzugsgebiet jeder Quelle abfragen (nur was noch nicht im Cache ist)
for _, q in quellen.iterrows():
    key = schluessel(q.geometry)
    if key in cache:
        continue
    x, y = q.geometry.x, q.geometry.y
    params = {
        "geometry": f"{x},{y}",
        "geometryType": "esriGeometryPoint",
        "layers": "all:ch.bafu.wasser-teileinzugsgebiete_2",
        "sr": 2056,
        "tolerance": 0,
        "mapExtent": f"{x-100},{y-100},{x+100},{y+100}",
        "imageDisplay": "100,100,96",
        "returnGeometry": "false",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=60)
        res = r.json().get("results", [])
        attr = res[0].get("attributes", {}) if res else {}
        cache[key] = {"ezg_name": attr.get("gewaessername") or "", "ezg_nr": attr.get("label")}
    except Exception as e:
        print("Fehler bei", key, e)
        continue
    if len(cache) % 100 == 0:
        print(len(cache), "abgefragt ...")
        json.dump(cache, open(cache_datei, "w"), ensure_ascii=False)
    time.sleep(0.05)

json.dump(cache, open(cache_datei, "w"), ensure_ascii=False)

# 2. Vergleichen
import difflib

def norm(s):
    s = (s or "").strip().lower()
    s = s.split("|")[0].strip()  # mehrsprachige Namen: nur den ersten
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("hwe ", "")):
        s = s.replace(a, b)
    return "" if s in ("-", "–") else s

def passt(a, b):
    if len(a) < 4 or len(b) < 4:
        return a == b
    if a in b or b in a:
        return True
    if difflib.SequenceMatcher(None, a, b).ratio() >= 0.85:
        return True
    ta = [t for t in a.split() if len(t) >= 6]
    tb = [t for t in b.split() if len(t) >= 6]
    return any(x in y or y in x for x in ta for y in tb)

ezg_namen, ergebnis = [], []
for _, q in quellen.iterrows():
    ezg = cache.get(schluessel(q.geometry), {}).get("ezg_name", "")
    ezg_namen.append(ezg)
    e_n = norm(ezg)
    weg_text = q["weg_namen"] if isinstance(q["weg_namen"], str) else ""
    weg = [norm(w) for w in weg_text.split("|") if w] + [norm(q["ziel"])]

    if q["ziel"] in ("kein Anschluss", "zu weit vom Bach"):
        ergebnis.append("nicht verfolgt")
    elif not e_n:
        ergebnis.append("EZG ohne Namen")
    elif any(passt(e_n, w) for w in weg if w):
        ergebnis.append("stimmt")
    else:
        ergebnis.append("abweichend")

quellen["ezg_name"] = ezg_namen
quellen["vergleich"] = ergebnis
quellen.to_crs(4326).to_file("quellen_vergleich.geojson", driver="GeoJSON")

# 3. Zusammenfassung
zaehl = quellen["vergleich"].value_counts()
vergleichbar = zaehl.get("stimmt", 0) + zaehl.get("abweichend", 0)
zeilen = [
    zaehl.to_string(),
    "",
    f"Übereinstimmung: {zaehl.get('stimmt', 0) / vergleichbar:.0%} "
    f"von {vergleichbar} vergleichbaren Quellen" if vergleichbar else "keine vergleichbaren Quellen",
    "",
    "Beispiele für Abweichungen (Flurname | BAFU-Einzugsgebiet | unser Weg):",
]
for _, q in quellen[quellen["vergleich"] == "abweichend"].head(40).iterrows():
    zeilen.append(f"  {q['flurname']} | {q['ezg_name']} | {q['andock']} | {str(q['weg_namen'])[:70]}")
with open("ezg_vergleich.txt", "w") as f:
    f.write("\n".join(zeilen))
print("Fertig – siehe ezg_vergleich.txt")