import json, math, colorsys

# ---------- colour utils ----------
def hex2rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def rgb2hex(r,g,b):
    f=lambda v: max(0,min(255,int(round(v))))
    return '#%02X%02X%02X' % (f(r),f(g),f(b))

def hex2hsl(h):
    r,g,b = [v/255 for v in hex2rgb(h)]
    H,L,S = colorsys.rgb_to_hls(r,g,b)
    return H*360, S*100, L*100

def hsl2hex(H,S,L):
    r,g,b = colorsys.hls_to_rgb((H%360)/360, L/100, S/100)
    return rgb2hex(r*255,g*255,b*255)

# sRGB <-> OKLab
def _lin(c):
    c/=255
    return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def _unlin(c):
    c = 12.92*c if c<=0.0031308 else 1.055*(c**(1/2.4))-0.055
    return c*255

def rgb2oklab(r,g,b):
    r,g,b = _lin(r),_lin(g),_lin(b)
    l = 0.4122214708*r + 0.5363325363*g + 0.0514459929*b
    m = 0.2119034982*r + 0.6806995451*g + 0.1073969566*b
    s = 0.0883024619*r + 0.2817188376*g + 0.6299787005*b
    l_,m_,s_ = l**(1/3) if l>0 else 0, m**(1/3) if m>0 else 0, s**(1/3) if s>0 else 0
    return (0.2104542553*l_ + 0.7936177850*m_ - 0.0040720468*s_,
            1.9779984951*l_ - 2.4285922050*m_ + 0.4505937099*s_,
            0.0259040371*l_ + 0.7827717662*m_ - 0.8086757660*s_)

def oklab2rgb(L,a,b):
    l_ = L + 0.3963377774*a + 0.2158037573*b
    m_ = L - 0.1055613458*a - 0.0638541728*b
    s_ = L - 0.0894841775*a - 1.2914855480*b
    l,m,s = l_**3, m_**3, s_**3
    r =  4.0767416621*l - 3.3077115913*m + 0.2309699292*s
    g = -1.2684380046*l + 2.6097574011*m - 0.3413193965*s
    bb=-0.0041960863*l - 0.7034186147*m + 1.7076147010*s
    return _unlin(r), _unlin(g), _unlin(bb)

def hex2oklch(h):
    L,a,b = rgb2oklab(*hex2rgb(h))
    return L*100, math.hypot(a,b), (math.degrees(math.atan2(b,a))) % 360

def oklch2rgb_raw(L,C,H):
    a = C*math.cos(math.radians(H)); b = C*math.sin(math.radians(H))
    return oklab2rgb(L/100,a,b)

def in_gamut(rgb, tol=0.5):
    return all(-tol <= v <= 255+tol for v in rgb)

def oklch2hex(L,C,H):
    """Gamut-map by reducing chroma until sRGB-representable."""
    rgb = oklch2rgb_raw(L,C,H)
    if not in_gamut(rgb):
        lo, hi = 0.0, C
        for _ in range(40):
            mid = (lo+hi)/2
            if in_gamut(oklch2rgb_raw(L,mid,H)): lo = mid
            else: hi = mid
        rgb = oklch2rgb_raw(L,lo,H)
    return rgb2hex(*rgb)

def max_chroma(L,H):
    lo, hi = 0.0, 0.5
    for _ in range(40):
        mid = (lo+hi)/2
        if in_gamut(oklch2rgb_raw(L,mid,H)): lo = mid
        else: hi = mid
    return lo

def dE(h1,h2):
    """OKLab Euclidean distance x100 — ~1.0 is a just-noticeable difference."""
    a = rgb2oklab(*hex2rgb(h1)); b = rgb2oklab(*hex2rgb(h2))
    return 100*math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))

def maxch(h1,h2):
    return max(abs(x-y) for x,y in zip(hex2rgb(h1), hex2rgb(h2)))

# ---------- the formulas ----------
CHROMATIC_STEPS = [25,50,100,200,300,400,500,600,700,800]

def L_of(step):
    return 96.0 if step == 25 else 95 - step/10

def S_of(step):
    return max(70.0, min(100.0, 120 - step/10))

HUES = {"Edge":10, "Flash":32, "Yellow":50, "Mindaro":75, "Pulse":110,
        "Mint":145, "Brand":190, "Core":250, "Pink":350}

def hsl_formula(fam, step):
    return hsl2hex(HUES[fam], S_of(step), L_of(step))

# neutrals
NEUTRAL_H = {"light":75, "dark":190}
def neutral_S(theme, L):
    # light: tint fades with lightness.  dark: tint grows into the shadows.
    return L/10 if theme=="light" else 11 + (100-L)/9

def neutral_formula(theme, step):
    L = L_of(step)
    return hsl2hex(NEUTRAL_H[theme], neutral_S(theme,L), L)

def greyscale_formula(theme, step):
    return hsl2hex(0, 0, L_of(step))

# ---------- ladder, extended ----------
def L_ladder(step):
    if step == 25: return 96.0
    if step <= 800: return 95 - step/10
    return 15 - (step-800)/20          # half-rate tail for the near-black surface steps

def L_of(step): return L_ladder(step)   # rebind

# ---------- assemble ----------
P = json.load(open('data/palette.json'))
CHROM = ["Brand","Core","Mindaro","Pulse","Flash","Edge","Pink","Yellow","Mint"]

def entry(orig, gen):
    e = {"orig":orig, "hsl":gen}
    for k in ("orig","hsl"):
        H,S,L = hex2hsl(e[k]); e[k+"_hsl"] = [round(H), round(S), round(L)]
    e["dE_hsl"] = round(dE(orig, gen), 2)
    e["px_hsl"] = maxch(orig, gen)
    return e

out = {"families":[], "hues":HUES}

for fam in CHROM:
    steps = P["light"][fam]
    rows=[]
    for s in CHROMATIC_STEPS:
        o = steps[str(s)]
        rows.append({"step":str(s), **entry(o, hsl_formula(fam,s))})
    out["families"].append({
        "name":fam, "kind":"chromatic", "theme":"both", "hue":HUES[fam], "rows":rows})

for theme in ("light","dark"):
    steps = P[theme]["Neutral"]
    rows=[]
    for k,v in steps.items():
        if k in ("White","Black"): continue
        s=int(k)
        rows.append({"step":k, **entry(v, neutral_formula(theme,s))})
    out["families"].append({"name":"Neutral", "kind":"neutral", "theme":theme,
        "hue":NEUTRAL_H[theme], "rows":rows})

for theme in ("light","dark"):
    steps = P[theme]["Greyscale"]
    rows=[]
    for k,v in steps.items():
        s=int(k)
        g = greyscale_formula(theme,s)
        rows.append({"step":k, **entry(v, g)})
    out["families"].append({"name":"Greyscale", "kind":"grey", "theme":theme,
        "hue":0, "rows":rows})

json.dump(out, open('data/generated.json','w'), indent=1)

# ---------- report ----------
print(f"{'family':<12}{'theme':<7}{'mean ΔE':>9}{'max':>7}   worst step")
for f in out["families"]:
    dh=[r["dE_hsl"] for r in f["rows"]]
    w = max(f["rows"], key=lambda r:r["dE_hsl"])
    print(f'{f["name"]:<12}{f["theme"]:<7}{sum(dh)/len(dh):9.2f}{max(dh):7.2f}   {w["step"]:>4} {w["orig"]}→{w["hsl"]} ({w["px_hsl"]}/255)')
