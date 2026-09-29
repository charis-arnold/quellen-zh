import requests, os
import geopandas as gpd

url = "https://maps.zh.ch/wfs/OGDZHWFS"
headers = {"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"}

layer = {
    "quelleninventar": "ms:ogd-0532_aln_fns_quelleninventar_gb_p",
    "quellfassungen": "ms:ogd-0317_giszhpub_gs_quellfassungen_ogd_p",
}

os.makedirs("daten", exist_ok=True)

for kurzname, typename in layer.items():
    print(f"\nLade {kurzname} ...")
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": typename,
        "srsName": "EPSG:2056",
    }
    r = requests.get(url, params=params, headers=headers, timeout=300)
    r.raise_for_status()

    gml = f"daten/{kurzname}.gml"
    with open(gml, "wb") as f:
        f.write(r.content)

    gdf = gpd.read_file(gml)
    if gdf.crs is None:
        gdf = gdf.set_crs(2056)

    print(f"{len(gdf)} Punkte")
    print("Spalten:", list(gdf.columns))
    print(gdf.head(3))

    gdf.to_crs(4326).to_file(f"{kurzname}.geojson", driver="GeoJSON")
    print(f"Gespeichert: {kurzname}.geojson")