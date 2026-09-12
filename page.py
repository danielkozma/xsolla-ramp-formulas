import json

D = json.load(open('data/generated.json'))

def stats(ver):
    rows = [r for f in ver["families"] for r in f["rows"]]
    return {
        "n": len(rows),
        "inv": sum(1 for r in rows if r["dE_hsl"] < 1),
        "sli": sum(1 for r in rows if 1 <= r["dE_hsl"] < 3),
        "vis": sum(1 for r in rows if r["dE_hsl"] >= 3),
    }

stat = {vid: stats(D[vid]) for vid in ("v1", "v2")}

body = open('template.html', encoding='utf-8').read()
body = body.replace('/*__DATA__*/', json.dumps(D, separators=(',',':')))
body = body.replace('/*__STAT__*/', json.dumps(stat, separators=(',',':')))

doc = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n'
       '<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="description" content="Reverse-engineered HSL formulas for the Xsolla colour palette, '
       'with every Figma ramp shown edge-to-edge against the formula output.">\n'
       + body.split('</style>')[0] + '</style>\n</head>\n<body>\n'
       + '</style>'.join(body.split('</style>')[1:]).lstrip('\n')
       + '\n</body>\n</html>\n')

open('index.html','w',encoding='utf-8').write(doc)
print("index.html", len(doc), "bytes", stat)
