import json

D = json.load(open('data/generated.json'))

# The page ships v7 only. v5 is still the yardstick v7 reports itself against,
# so its mean ΔE is baked in as a number rather than carrying the whole version.
def mean_dE(ver):
    d = [r["dE_hsl"] for f in D[ver]["families"] for r in f["rows"] if r["dE_hsl"] is not None]
    return sum(d) / len(d)

payload = {"v7": D["v7"]}

body = open('template.html', encoding='utf-8').read()
body = body.replace('/*__DATA__*/', json.dumps(payload, separators=(',', ':')))
body = body.replace('/*__MEANV5__*/', repr(round(mean_dE("v5"), 6)))

doc = ('<!DOCTYPE html>\n<html lang="en">\n<head>\n'
       '<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<title>Xsolla Colour Formulas</title>\n'
       '<meta name="robots" content="noindex, nofollow">\n'
       '<meta name="description" content="Reverse-engineered HSL formulas for the Xsolla colour palette, '
       'with every Figma ramp shown edge-to-edge against the formula output.">\n'
       + body.split('</style>')[0] + '</style>\n</head>\n<body>\n'
       + '</style>'.join(body.split('</style>')[1:]).lstrip('\n')
       + '\n</body>\n</html>\n')

open('index.html', 'w', encoding='utf-8').write(doc)
print("index.html", len(doc), "bytes · v7 only · mean ΔE v5 =", round(mean_dE("v5"), 4))
