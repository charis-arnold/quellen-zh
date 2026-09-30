import os
import geopandas as gpd
import shapely


opt = {"layer_options": {"COORDINATE_PRECISION": 0}}

SENKEN = ["Rhein", "Limmat", "Reuss"]

# --- Bäche: nur die, die Quellwasser führen ---
bach = gpd.read_file("daten/gewaesser.gpkg", layer="bach_mit_quellen")

# Senken: Skript 03 stoppt beim Erreichen der Senke, darum steht dort 0.
# Wir setzen stattdessen die Zahl aller Quellen, die in diesem Fluss ankommen.
ankommend = gpd.read_file("daten/quellen_vergleich.geojson")["ziel"].value_counts()
ist_senke = bach["gewaessername"].isin(SENKEN)
bach.loc[ist_senke, "quellen_oberhalb"] = bach.loc[ist_senke, "gewaessername"].map(ankommend)

bach = bach[bach["quellen_oberhalb"] > 0]
bach = bach[["gewaessername", "quellen_oberhalb", "geometry"]]
bach["geometry"] = bach.simplify(5)
bach.to_file("baeche.geojson", driver="GeoJSON", **opt)

# --- Beschriftung: ein Punkt pro grossem Fluss ---
SCHWELLE = 100  # Sihl hat 136, der nächstkleinere (Tobelbach) 68

groesse = bach.groupby("gewaessername")["quellen_oberhalb"].max()
namen = groesse[groesse >= SCHWELLE].index

punkte = []
for name in namen:
    linie = shapely.line_merge(bach[bach["gewaessername"] == name].union_all())
    if linie.geom_type == "MultiLineString":
        linie = max(linie.geoms, key=lambda g: g.length)  # längstes Stück
    punkte.append({
        "name": name,
        "geometry": linie.interpolate(0.5, normalized=True),  # Mitte
    })

beschriftung = gpd.GeoDataFrame(punkte, crs=bach.crs)
beschriftung.to_file("beschriftung.geojson", driver="GeoJSON", **opt)
print("Beschriftet:", list(namen))


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
