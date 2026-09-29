import geopandas as gpd
import pandas as pd

inv = gpd.read_file("quelleninventar.geojson").to_crs(2056)
fas = gpd.read_file("quellfassungen.geojson").to_crs(2056)
osm = gpd.read_file("quellen_osm.geojson").to_crs(2056)

inv = inv.assign(quelle="inventar", name=inv["flurname"])[["quelle", "name", "geometry"]]
fas = fas.assign(quelle="fassung", name=fas["fassbez"])[["quelle", "name", "geometry"]]
osm_name = osm["name"] if "name" in osm.columns else None
osm = osm.assign(quelle="osm", name=osm_name)[["quelle", "name", "geometry"]]

# OSM-Punkte weglassen, die näher als 25 m an einer kantonalen Quelle liegen
kanton = pd.concat([inv, fas])
naechste = gpd.sjoin_nearest(osm, kanton, max_distance=25, how="left")
osm_neu = osm[naechste.groupby(level=0)["index_right"].first().isna()]

alle = gpd.GeoDataFrame(pd.concat([inv, fas, osm_neu], ignore_index=True), crs=2056)
alle.to_crs(4326).to_file("quellen_zh_alle.geojson", driver="GeoJSON")

print(alle["quelle"].value_counts())
print("Total:", len(alle))
