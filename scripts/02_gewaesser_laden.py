import requests, os
import geopandas as gpd

url = "https://maps.zh.ch/wfs/OGDZHWFS"
headers = {"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"}

layer = {
    "fliessgewaesser": "ms:ogd-0045_giszhpub_wb_fliessgewaesser_l",
    "seen": "ms:ogd-0045_giszhpub_wb_stehgewaesser_f",
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
    r = requests.get(url, params=params, headers=headers, timeout=600)
    r.raise_for_status()

    gml = f"daten/{kurzname}.gml"
    with open(gml, "wb") as f:
        f.write(r.content)

    gdf = gpd.read_file(gml)
    if gdf.crs is None:
        gdf = gdf.set_crs(2056)

    print(f"{len(gdf)} Objekte, Geometrie: {gdf.geom_type.unique()}")
    print("Spalten:", list(gdf.columns))
    print(gdf.drop(columns="geometry").head(3).to_string())

    # für die Netzwerkanalyse in Metern (LV95) behalten
    gdf.to_file("daten/gewaesser.gpkg", layer=kurzname, driver="GPKG")
    # für D3/QGIS zusätzlich als GeoJSON in Längen-/Breitengrad
    gdf.to_crs(4326).to_file(f"{kurzname}.geojson", driver="GeoJSON")
    print(f"Gespeichert: {kurzname}.geojson")