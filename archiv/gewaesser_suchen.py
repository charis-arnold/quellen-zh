from owslib.wfs import WebFeatureService

wfs = WebFeatureService("https://maps.zh.ch/wfs/OGDZHWFS", version="2.0.0", timeout=120)

suchen = ["gewaesser", "gewässer", "fliess", "bach", "see", "netz", "einzugsgebiet"]
weglassen = ["zustaend", "unterhalt", "wasserrecht", "werkhoefe", "hw_", "tiefen", "hochwasser"]

treffer = []
for name, layer in wfs.contents.items():
    if "0045_" in name or "fliessgew" in name.lower() or "oeffgew" in name:
        treffer.append(f"{name} | {layer.title}")

with open("layer.txt", "w") as f:
    f.write("\n".join(sorted(treffer)))

print(len(treffer), "Layer in layer.txt gespeichert")