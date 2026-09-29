import geopandas as gpd
from collections import Counter

bach = gpd.read_file("daten/gewaesser.gpkg", layer="fliessgewaesser")
bach = bach.explode(index_parts=False)  # MultiLines in einzelne Linien zerlegen

zeilen = []
zeilen.append(f"{len(bach)} Linienabschnitte, Geometrie: {bach.geom_type.unique()}")
zeilen.append(f"Spalten: {list(bach.columns)}")
zeilen.append("")
zeilen.append(bach.drop(columns="geometry").head(5).to_string())
zeilen.append("")

# Anfangs- und Endpunkte zählen (auf 1 m gerundet)
def punkt(p):
    return (round(p[0]), round(p[1]))

starts = Counter(punkt(g.coords[0]) for g in bach.geometry)
enden = Counter(punkt(g.coords[-1]) for g in bach.geometry)

zusammen_enden = sum(1 for n in enden.values() if n >= 2)
zusammen_starts = sum(1 for n in starts.values() if n >= 2)

zeilen.append(f"Punkte, an denen 2+ Linien ENDEN:   {zusammen_enden}")
zeilen.append(f"Punkte, an denen 2+ Linien BEGINNEN: {zusammen_starts}")

with open("gewaesser_info.txt", "w") as f:
    f.write("\n".join(zeilen))

print("Fertig – siehe gewaesser_info.txt")