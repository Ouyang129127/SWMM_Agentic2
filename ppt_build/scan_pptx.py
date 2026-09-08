import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

ppt = sys.argv[1]
with zipfile.ZipFile(ppt) as z:
    names = set(z.namelist())
    bad = []
    for name in z.namelist():
        if not (name.endswith(".xml") or name.endswith(".rels")):
            continue
        data = z.read(name).decode("utf-8", errors="replace")
        try:
            ET.fromstring(data)
        except Exception as exc:
            bad.append((name, "xml_parse", str(exc)))
        for pat in ['val=""', 'cx="0"', 'cy="0"', "NaN", "undefined", "Infinity", 'typeface=""', 'color=""']:
            if pat in data:
                bad.append((name, pat, ""))
    print("bad count", len(bad))
    for item in bad[:120]:
        print(item)

    missing = []
    for name in [n for n in z.namelist() if n.endswith(".rels")]:
        data = z.read(name).decode("utf-8", errors="ignore")
        for target in re.findall(r'Target="([^"]+)"', data):
            if target.startswith("http") or target.startswith("#"):
                continue
            if name == "_rels/.rels":
                full = target
            elif "/_rels/" in name:
                folder = name.split("/_rels/")[0]
                full = posixpath.normpath(folder + "/" + target)
            else:
                full = target
            if full not in names:
                missing.append((name, target, full))
    print("missing relationships", len(missing))
    for item in missing[:120]:
        print(item)
