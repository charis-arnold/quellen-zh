import geopandas as gpd
import folium
import os
import webbrowser
from shapely.geometry import Point

# See finden
seen = gpd.read_file("daten/gewaesser.gpkg", layer="seen")
see = seen[seen["gewaessername"].str.contains("Pfäffiker", na=False)]
print(see[["gewaessername", "flaeche_ha"]].to_string(), "\n")
see_geom = see.union_all()

# Bäche im Umkreis von 1.5 km
bach = gpd.read_file("daten/gewaesser.gpkg", layer="fliessgewaesser")
bach = bach.explode(index_parts=False)
nah = bach[bach.distance(see_geom) < 1500].copy()

def ende_bis_see(g):
    return min(Point(g.coords[0]).distance(see_geom),
               Point(g.coords[-1]).distance(see_geom))

nah["ende_m"] = nah.geometry.apply(ende_bis_see).round(1)

print("Bäche, deren Linienende weniger als 300 m vom See liegt:")
print(nah[nah["ende_m"] < 300][["gewaessername", "ende_m"]]
      .sort_values("ende_m").to_string())

# Karte
def farbe(d):
    if d <= 20:
        return "#2a9d8f"
    if d <= 100:
        return "#f4a261"
    return "#999999"

mitte = see.to_crs(4326).union_all().centroid
m = folium.Map(
    location=[mitte.y, mitte.x], zoom_start=13,
    tiles="https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-grau/default/current/3857/{z}/{x}/{y}.jpeg",
    attr="© swisstopo",
)

folium.GeoJson(
    see.to_crs(4326)[["gewaessername", "geometry"]],
    style_function=lambda f: {"color": "#3a7bd5", "weight": 1,
                              "fillColor": "#a8c8f0", "fillOpacity": 0.5},
).add_to(m)

puffer = gpd.GeoDataFrame(geometry=[see_geom.buffer(20)], crs=2056).to_crs(4326)
folium.GeoJson(
    puffer,
    style_function=lambda f: {"color": "#e63946", "weight": 1,
                              "dashArray": "4 4", "fill": False},
).add_to(m)

folium.GeoJson(
    nah.to_crs(4326)[["gewaessername", "ende_m", "geometry"]],
    style_function=lambda f: {"color": farbe(f["properties"]["ende_m"]), "weight": 3},
    tooltip=folium.GeoJsonTooltip(["gewaessername", "ende_m"],
                                  aliases=["Gewässer", "Linienende bis See (m)"]),
).add_to(m)

# Quellen im Umkreis von 3 km
farben = {"Rhein": "#2a9d8f", "Limmat": "#e76f51", "Reuss": "#8e44ad",
          "kein Anschluss": "#e63946", "zu weit vom Bach": "#999999"}
quellen = gpd.read_file("quellen_mit_ziel.geojson").to_crs(2056)
quellen = quellen[quellen.distance(see_geom) < 3000].to_crs(4326)
for _, q in quellen.iterrows():
    folium.CircleMarker(
        [q.geometry.y, q.geometry.x], radius=4,
        color=farben.get(q["ziel"], "#000000"), fill=True,
        fill_opacity=0.9, weight=0,
        tooltip=f"{q['flurname'] or 'Quelle'} → {q['ziel']}",
    ).add_to(m)

m.save("pfaeffikersee_check.html")
webbrowser.open("file://" + os.path.abspath("pfaeffikersee_check.html"))
print("\nKarte geöffnet: pfaeffikersee_check.html")