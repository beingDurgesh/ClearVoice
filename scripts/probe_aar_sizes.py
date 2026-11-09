import urllib.request

def size(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "python-urllib"})
    return int(urllib.request.urlopen(req, timeout=60).headers.get("Content-Length", -1))

arts = {
    "ui": "androidx/compose/ui/ui",
    "ui-graphics": "androidx/compose/ui/ui-graphics",
    "ui-unit": "androidx/compose/ui/ui-unit",
    "material3": "androidx/compose/material3/material3",
    "foundation": "androidx/compose/foundation/foundation",
    "runtime": "androidx/compose/runtime/runtime",
}
for v in ["1.7.6", "1.7.5", "1.7.8", "1.6.11", "1.8.2"]:
    for art, path in arts.items():
        url = f"https://dl.google.com/dl/android/maven2/{path}/{v}/{art}-{v}.aar"
        try:
            s = size(url)
            if s > 100000:
                print(v, art, s)
        except Exception:
            pass
