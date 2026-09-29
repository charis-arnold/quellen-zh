import requests, json

query = """
[out:json][timeout:90];
node["natural"="spring"](47.15,8.35,47.70,9.00);
out;
"""

headers = {"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"}
server = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

nodes = None
for url in server:
    print("Frage", url, "...")
    r = requests.post(url, data={"data": query}, headers=headers, timeout=120)
    if r.status_code == 200:
        nodes = r.json()["elements"]
        break
    print("Fehler", r.status_code, ":", r.text[:300])

if nodes is None:
    raise SystemExit("Kein Server hat geantwortet – später nochmal versuchen.")

geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [n["lon"], n["lat"]]},
            "properties": n.get("tags", {}),
        }
        for n in nodes
    ],
}
with open("quellen_osm.geojson", "w") as f:
    json.dump(geojson, f, ensure_ascii=False)

print(len(nodes), "Quellen gefunden")