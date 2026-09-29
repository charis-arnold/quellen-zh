import geopandas as gpd
import folium
import math
import os
import webbrowser

bach = gpd.read_file("gewaesser_mit_quellen.geojson")
seen = gpd.read_file("seen.geojson")
seen = seen[seen["flaeche_ha"] >= 5]
quellen = gpd.read_file("quellen_mit_ziel.geojson")

m = folium.Map(
    location=[47.42, 8.65], zoom_start=10,
    tiles="https://wmts.geo.admin.ch/1.0.0/ch.swisstopo.pixelkarte-grau/default/current/3857/{z}/{x}/{y}.jpeg",
    attr="© swisstopo",
)

# Seen
folium.GeoJson(
    seen[["gewaessername", "geometry"]],
    name="Seen",
    style_function=lambda f: {
        "color": "#3a7bd5", "weight": 1,
        "fillColor": "#a8c8f0", "fillOpacity": 0.6,
    },
    tooltip=folium.GeoJsonTooltip(["gewaessername"], aliases=["See"]),
).add_to(m)

# Gewässer: Linienbreite nach Anzahl Quellen oberhalb
folium.GeoJson(
    bach[["gewaessername", "quellen_oberhalb", "geometry"]],
    name="Gewässer",
    style_function=lambda f: {
        "color": "#1f5fa8",
        "weight": 0.5 + 0.8 * math.sqrt(f["properties"]["quellen_oberhalb"]),
        "opacity": 0.8,
    },
    tooltip=folium.GeoJsonTooltip(
        ["gewaessername", "quellen_oberhalb"],
        aliases=["Gewässer", "Quellen oberhalb"],
    ),
).add_to(m)

# Quellen: Farbe nach Ziel
farben = {
    "Rhein": "#2a9d8f",
    "Limmat": "#e76f51",
    "Reuss": "#8e44ad",
    "kein Anschluss": "#e63946",
    "zu weit vom Bach": "#999999",
    "Nachbarkanton": "#e9c46a",
}
gruppe = folium.FeatureGroup(name="Quellen")
for _, q in quellen.iterrows():
    name = q["flurname"] or "Quelle"
    folium.CircleMarker(
        [q.geometry.y, q.geometry.x],
        radius=3,
        color=farben.get(q["ziel"], "#000000"),
        fill=True,
        fill_opacity=0.9,
        weight=0,
        tooltip=f"{name} → {q['ziel']}",
    ).add_to(gruppe)
gruppe.add_to(m)

# Legende
eintraege = "".join(
    f'<div><span style="display:inline-block;width:10px;height:10px;'
    f'border-radius:50%;background:{f};margin-right:6px"></span>{z}</div>'
    for z, f in farben.items()
)
m.get_root().html.add_child(folium.Element(
    f'<div style="position:fixed;bottom:20px;left:20px;z-index:1000;'
    f'background:white;padding:10px 12px;border-radius:6px;'
    f'font:12px sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.3)">'
    f'<b>Quelle fliesst in …</b>{eintraege}</div>'
))

folium.LayerControl().add_to(m)
m.save("testkarte.html")
webbrowser.open("file://" + os.path.abspath("testkarte.html"))
print("Karte gespeichert und geöffnet: testkarte.html")