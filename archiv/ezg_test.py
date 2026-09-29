import json
import requests
import geopandas as gpd

quellen = gpd.read_file("quellen_mit_ziel.geojson").to_crs(2056)
url = "https://api3.geo.admin.ch/rest/services/api/MapServer/identify"
headers = {"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"}

zeilen = []
for _, q in quellen.head(3).iterrows():
    x, y = q.geometry.x, q.geometry.y
    params = {
        "geometry": f"{x},{y}",
        "geometryType": "esriGeometryPoint",
        "layers": "all:ch.bafu.wasser-teileinzugsgebiete_2,ch.bafu.wasser-teileinzugsgebiete_40",
        "sr": 2056,
        "tolerance": 0,
        "mapExtent": f"{x-100},{y-100},{x+100},{y+100}",
        "imageDisplay": "100,100,96",
        "returnGeometry": "false",
        "lang": "de",
    }
    r = requests.get(url, params=params, headers=headers, timeout=60)
    zeilen.append(f"\n### {q['flurname']} → Modell: {q['ziel']}  (Status {r.status_code})")
    for res in r.json().get("results", []):
        zeilen.append(res.get("layerBodId", "?"))
        attr = res.get("attributes") or res.get("properties")
        zeilen.append(json.dumps(attr, ensure_ascii=False, indent=2))

with open("ezg_test.txt", "w") as f:
    f.write("\n".join(zeilen))
print("Fertig – siehe ezg_test.txt")