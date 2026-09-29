from owslib.wfs import WebFeatureService

wfs = WebFeatureService("https://maps.zh.ch/wfs/OGDZHWFS", version="2.0.0", timeout=120)

treffer = []
for name, layer in wfs.contents.items():
    text = (name + " " + (layer.title or "")).lower()
    if any(s in text for s in ["kanton", "gemeindegrenz", "gemeinden", "hoheit"]):
        treffer.append(f"{name} | {layer.title}")

with open("grenze_layer.txt", "w") as f:
    f.write("\n".join(sorted(treffer)))
print(len(treffer), "Layer in grenze_layer.txt gespeichert")
