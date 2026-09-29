import os
import geopandas as gpd

opt = {"layer_options": {"COORDINATE_PRECISION": 0}}

# --- Bäche: nur die, die Quellwasser führen ---
bach = gpd.read_file("daten/gewaesser.gpkg", layer="bach_mit_quellen")
bach = bach[bach["quellen_oberhalb"] > 0]
bach = bach[["gewaessername", "quellen_oberhalb", "geometry"]]
bach["geometry"] = bach.simplify(5)
bach.to_file("baeche.geojson", driver="GeoJSON", **opt)

# --- Seen: nur die grossen ---
seen = gpd.read_file("daten/gewaesser.gpkg", layer="seen")
seen = seen[seen["flaeche_ha"] >= 5]
seen = seen[["gewaessername", "geometry"]]
seen["geometry"] = seen.simplify(10)
seen.to_file("seen.geojson", driver="GeoJSON", **opt)

# --- Quellen: mit Ziel und Sicherheit ---
quellen = gpd.read_file("daten/quellen_vergleich.geojson").to_crs(2056)
quellen = quellen[["flurname", "ziel", "andock", "vergleich", "geometry"]]
quellen.to_file("quellen.geojson", driver="GeoJSON", **opt)

# --- Kontrolle ---
for name in ["baeche", "seen", "quellen"]:
    groesse = os.path.getsize(f"{name}.geojson") / 1024
    print(f"{name}.geojson: {groesse:.0f} kB")
