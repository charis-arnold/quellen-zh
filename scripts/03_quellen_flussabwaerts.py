import geopandas as gpd
import pandas as pd
import networkx as nx
import shapely
from shapely.geometry import Point
from collections import Counter, defaultdict
import os
import requests
import numpy as np
import json
import time

TOL = 10          # Meter: so nah muss ein Linienende an einer anderen Linie liegen
MAX_QUELLE = 250  # Meter: maximale Distanz Quelle → Bach
SENKEN = ["Rhein", "Limmat", "Reuss"]

def knoten(xy):
    return (round(xy[0]), round(xy[1]))

# 1. Daten laden (LV95, Meter)
bach = gpd.read_file("daten/gewaesser.gpkg", layer="fliessgewaesser")
bach = bach.explode(index_parts=False).reset_index(drop=True)
seen = gpd.read_file("daten/gewaesser.gpkg", layer="seen").reset_index(drop=True)
quellen = gpd.read_file("quelleninventar.geojson").to_crs(2056)

geoms = list(bach.geometry)
tree = shapely.STRtree(geoms)

# 2. Linienenden mit benachbarten Linien verknüpfen
print("Verknüpfe Linien ...")
schnitte = defaultdict(set)
verbinder = []
for i, g in enumerate(geoms):
    for xy in (g.coords[0], g.coords[-1]):
        p = Point(xy)
        beste = None
        for j in tree.query(p.buffer(TOL)):
            if j == i:
                continue
            d = geoms[j].distance(p)
            if d <= TOL and (beste is None or d < beste[0]):
                beste = (d, j)
        if beste is None:
            continue
        d, j = beste
        L = geoms[j].length
        pos = geoms[j].project(p)
        if pos < 0.5:
            pos = 0.0
        elif pos > L - 0.5:
            pos = L
        else:
            pos = round(pos, 2)
            schnitte[j].add(pos)
        q = geoms[j].interpolate(pos)
        verbinder.append((knoten(xy), knoten((q.x, q.y)), d))

# 3. Netz aufbauen (Linien an den Verknüpfungsstellen aufgetrennt)
print("Baue Netz ...")
G = nx.Graph()
teile = {}
for i, g in enumerate(geoms):
    L = g.length
    cuts = [0.0] + sorted(c for c in schnitte[i] if 0 < c < L) + [L]
    teile[i] = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        pa, pb = g.interpolate(a), g.interpolate(b)
        ka, kb = knoten((pa.x, pa.y)), knoten((pb.x, pb.y))
        teile[i].append((a, b, ka, kb))
        if ka != kb:
            G.add_edge(ka, kb, seg=i, w=b - a)
for k1, k2, d in verbinder:
    if k1 != k2 and not G.has_edge(k1, k2):
        G.add_edge(k1, k2, w=d)

# 4. Seen als Knoten: alle Netzpunkte im/am See (20 m) hängen am See
liste = list(G.nodes)
kn = gpd.GeoDataFrame(
    {"knoten": liste},
    geometry=gpd.points_from_xy([k[0] for k in liste], [k[1] for k in liste]),
    crs=2056,
)
puffer = seen.loc[seen["flaeche_ha"] >= 5, ["geometry"]].copy()
puffer["geometry"] = puffer.buffer(150)
for _, row in gpd.sjoin(kn, puffer, predicate="within").iterrows():
        G.add_edge(row["knoten"], ("see", row["index_right"]), w=1)

# 5. Senken: alle Punkte auf Rhein, Limmat, Reuss
senke_von = {}
for i in bach.index[bach["gewaessername"].isin(SENKEN)]:
    for _, _, ka, kb in teile[i]:
        senke_von[ka] = senke_von[kb] = bach.at[i, "gewaessername"]
senke_von = {k: v for k, v in senke_von.items() if k in G}

# 5b. Kantonsgrenze als zusätzlicher Ausgang
if not os.path.exists("daten/kanton.gml"):
    print("Lade Kantonsgrenze ...")
    r = requests.get(
        "https://maps.zh.ch/wfs/OGDZHWFS",
        params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": "ms:ogd-0095_arv_basis_up_kanton_f",
            "srsName": "EPSG:2056",
        },
        headers={"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"},
        timeout=300,
    )
    r.raise_for_status()
    with open("daten/kanton.gml", "wb") as f:
        f.write(r.content)

kanton = gpd.read_file("daten/kanton.gml")
if kanton.crs is None:
    kanton = kanton.set_crs(2056)
kanton["km2"] = (kanton.area / 1e6).round(0)
print(kanton.drop(columns="geometry").to_string())
zh = kanton[kanton["abkuerzung"] == "ZH"]
if zh.empty:
    raise SystemExit("Keine Fläche um 1730 km² gefunden – siehe Tabelle oben")
kanton_geom = zh.union_all()
rand = kanton_geom.boundary

GRENZ_MAX = 300  # Meter

# Höhen über die swisstopo-API, mit Cache
HOEHEN_CACHE = "daten/hoehen_cache.json"
hoehen = json.load(open(HOEHEN_CACHE)) if os.path.exists(HOEHEN_CACHE) else {}
abgefragt = 0

def hoehe(k):
    global abgefragt
    key = f"{k[0]},{k[1]}"
    if key not in hoehen:
        try:
            r = requests.get(
                "https://api3.geo.admin.ch/rest/services/height",
                params={"easting": k[0], "northing": k[1], "sr": 2056},
                headers={"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"},
                timeout=30,
            )
            hoehen[key] = float(r.json()["height"])
        except Exception:
            hoehen[key] = None
        abgefragt += 1
        if abgefragt % 200 == 0:
            print(f"  {abgefragt} Höhen abgefragt ...")
            json.dump(hoehen, open(HOEHEN_CACHE, "w"))
        time.sleep(0.05)
    return hoehen[key]

# Teilnetze ohne Senke, die die Grenze berühren
kandidaten = []
for komp in nx.connected_components(G):
    if any(k in senke_von for k in komp):
        continue
    punkte = [k for k in komp if k[0] != "see"]
    if not punkte:
        continue
    pts = shapely.points(np.array(punkte, dtype=float))
    d = shapely.distance(rand, pts)
    d[~shapely.contains(kanton_geom, pts)] = 0
    if d.min() > GRENZ_MAX:
        continue  # berührt die Grenze nicht
    abstand = dict(zip(punkte, d))
    enden = {k for k in punkte if G.degree(k) == 1}
    enden.add(punkte[int(np.argmin(d))])  # grenznächster Punkt immer als Kandidat
    kandidaten.append([(k, abstand[k]) for k in enden])

print(f"Teilnetze an der Grenze: {len(kandidaten)}, "
      f"Endpunkte: {sum(len(c) for c in kandidaten)}")

# Pro Teilnetz: tiefster Endpunkt – Ausgang nur, wenn er an der Grenze liegt
ausgaenge = innen_tiefster = 0
for enden in kandidaten:
    mit_hoehe = [(hoehe(k), k, dd) for k, dd in enden]
    mit_hoehe = [t for t in mit_hoehe if t[0] is not None]
    if not mit_hoehe:
        continue
    h, k, dd = min(mit_hoehe)
    if dd <= GRENZ_MAX:
        senke_von[k] = "Nachbarkanton"
        ausgaenge += 1
    else:
        innen_tiefster += 1

json.dump(hoehen, open(HOEHEN_CACHE, "w"))
print(f"Ausgänge an der Kantonsgrenze: {ausgaenge}")
print(f"Tiefster Punkt im Innern (kein Ausgang): {innen_tiefster}")

# 6. Fliessrichtung: kürzester Weg zur nächsten Senke, als Baum ohne Schleifen
print("Berechne Fliesswege ...")
for s in senke_von:
    G.add_edge("MEER", s, w=0)
pred, dist = nx.dijkstra_predecessor_and_distance(G, "MEER", weight="w")
unten = {
    n: p[0] for n, p in pred.items()
    if p and n not in senke_von and n != "MEER"
}
G.remove_node("MEER")

# 7. Natürliche Quellen andocken und flussabwärts verfolgen
print("Verfolge Quellen flussabwärts ...")
# Andocken mit Gelände: Höhenprofil Quelle → Bach
PROFIL_CACHE = "daten/profil_cache.json"
profile = json.load(open(PROFIL_CACHE)) if os.path.exists(PROFIL_CACHE) else {}
profil_abgefragt = 0

def profil(x1, y1, x2, y2):
    global profil_abgefragt
    key = f"{round(x1)},{round(y1)},{round(x2)},{round(y2)}"
    if key not in profile:
        geom = json.dumps({"type": "LineString", "coordinates": [[x1, y1], [x2, y2]]})
        try:
            r = requests.get(
                "https://api3.geo.admin.ch/rest/services/profile.json",
                params={"geom": geom, "sr": 2056, "nb_points": 10},
                headers={"User-Agent": "quellen-zh/1.0 (charisarnold.ch)"},
                timeout=30,
            )
            profile[key] = [p["alts"]["COMB"] for p in r.json()]
        except Exception:
            profile[key] = None
        profil_abgefragt += 1
        if profil_abgefragt % 200 == 0:
            print(f"  {profil_abgefragt} Profile abgefragt ...")
            json.dump(profile, open(PROFIL_CACHE, "w"))
        time.sleep(0.05)
    return profile[key]

# Test mit der ersten Quelle, bevor alles läuft
t = quellen.geometry.iloc[0]
test = profil(t.x, t.y, t.x + 100, t.y)
print("Testprofil:", test)
if not test:
    raise SystemExit("Höhenprofil-API liefert nichts – bitte Terminal-Ausgabe zeigen")

KANDIDATEN = 4    # so viele verschiedene Bäche werden geprüft
TOL_ENDE = 2      # Bach darf höchstens 2 m höher liegen als die Quelle
TOL_RUECKEN = 5   # kein Punkt dazwischen mehr als 5 m über der Quelle

wahl_seg, wahl_dist, andock = [], [], []
for _, q in quellen.iterrows():
    p = q.geometry
    kand = sorted((geoms[j].distance(p), j) for j in tree.query(p.buffer(MAX_QUELLE)))
    kand = [(d, j) for d, j in kand if d <= MAX_QUELLE]
    if not kand:
        wahl_seg.append(None)
        wahl_dist.append(None)
        andock.append("zu weit")
        continue

    # pro Gewässer nur den nächsten Abschnitt
    gesehen, auswahl = set(), []
    for d, j in kand:
        name = bach.at[j, "gewaessername"]
        schl = name if isinstance(name, str) and name else f"#{j}"
        if schl in gesehen:
            continue
        gesehen.add(schl)
        auswahl.append((d, j))
        if len(auswahl) == KANDIDATEN:
            break

    gewaehlt = None
    for d, j in auswahl:
        if d < 5:  # Quelle liegt praktisch am Bach
            gewaehlt = (d, j)
            break
        z = geoms[j].interpolate(geoms[j].project(p))
        prof = profil(p.x, p.y, z.x, z.y)
        if not prof or prof[0] is None or prof[-1] is None:
            continue
        h_q, h_b = prof[0], prof[-1]
        dazwischen = [h for h in prof[1:-1] if h is not None]
        if h_b <= h_q + TOL_ENDE and (not dazwischen or max(dazwischen) <= h_q + TOL_RUECKEN):
            gewaehlt = (d, j)
            break

    if gewaehlt:
        andock.append("Gelände" if gewaehlt == auswahl[0] else "Gelände, anderer Bach")
    else:
        gewaehlt = auswahl[0]
        andock.append("nächster, unsicher")
    wahl_dist.append(gewaehlt[0])
    wahl_seg.append(gewaehlt[1])

json.dump(profile, open(PROFIL_CACHE, "w"))
nah = quellen.copy()
nah["index_right"] = wahl_seg
nah["distanz_m"] = wahl_dist
print(pd.Series(andock).value_counts().to_string())

seg_zaehler, see_zaehler, senke_zaehler = Counter(), Counter(), Counter()
zu_weit = ohne_ziel = 0
ziel = []
wege = []

for _, q in nah.iterrows():
    if pd.isna(q["index_right"]):
        zu_weit += 1
        ziel.append("zu weit vom Bach")
        wege.append("")
        continue
    i = int(q["index_right"])
    pos = geoms[i].project(q.geometry)
    a, b, ka, kb = next((t for t in teile[i] if t[0] <= pos <= t[1]), teile[i][-1])
    if ka not in dist or kb not in dist:
        ohne_ziel += 1
        ziel.append("kein Anschluss")
        wege.append("")
        continue
    besucht = {i}
    n = ka if dist[ka] < dist[kb] else kb
    while n in unten:
        m = unten[n]
        kante = G.edges[n, m]
        if "seg" in kante:
            besucht.add(kante["seg"])
        if m[0] == "see":
            see_zaehler[m[1]] += 1
        n = m
    for s in besucht:
        seg_zaehler[s] += 1
    senke_zaehler[senke_von.get(n, "?")] += 1
    ziel.append(senke_von.get(n, "?"))
    namen = {bach.at[s, "gewaessername"] for s in besucht}
    wege.append("|".join(sorted(x for x in namen if isinstance(x, str) and x)))

# 8. Speichern
quellen["ziel"] = ziel
quellen["weg_namen"] = wege
quellen["distanz_bach_m"] = pd.to_numeric(nah["distanz_m"]).round(0).values
quellen["andock"] = andock
quellen.to_crs(4326).to_file("quellen_mit_ziel.geojson", driver="GeoJSON")

bach["quellen_oberhalb"] = [seg_zaehler.get(i, 0) for i in range(len(bach))]
seen["quellen_zufluss"] = [see_zaehler.get(i, 0) for i in range(len(seen))]
bach.to_file("daten/gewaesser.gpkg", layer="bach_mit_quellen", driver="GPKG")
bach[bach["quellen_oberhalb"] > 0].to_crs(4326).to_file(
    "gewaesser_mit_quellen.geojson", driver="GeoJSON")
seen[seen["quellen_zufluss"] > 0].to_crs(4326).to_file(
    "seen_mit_quellen.geojson", driver="GeoJSON")

# 9. Zusammenfassung
zeilen = [
    f"Netzknoten: {G.number_of_nodes()}, Teilnetze: {nx.number_connected_components(G)}",
    f"Mit Rhein/Limmat/Reuss verbunden: {len(dist) / G.number_of_nodes():.0%} der Knoten",
    "",
    f"Natürliche Quellen: {len(quellen)}",
    f"  bis zu einem Fluss verfolgt: {sum(senke_zaehler.values())}",
    f"  mehr als {MAX_QUELLE} m vom nächsten Bach: {zu_weit}",
    f"  Bach ohne Anschluss: {ohne_ziel}",
    "",
    "Wo die Quellen ankommen:",
    *[f"  {k}: {v}" for k, v in senke_zaehler.most_common()],
    "",
    "Gewässer mit den meisten Quellen oberhalb:",
    bach[~bach["gewaessername"].isin(SENKEN)]
        .groupby("gewaessername")["quellen_oberhalb"].max()
        .sort_values(ascending=False).head(15).to_string(),
    "",
    "Seen mit den meisten Quellen im Zufluss:",
    seen.sort_values("quellen_zufluss", ascending=False)
        .head(10)[["gewaessername", "quellen_zufluss"]].to_string(),
]
with open("flussabwaerts_info.txt", "w") as f:
    f.write("\n".join(zeilen))
print("Fertig – siehe flussabwaerts_info.txt")