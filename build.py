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

def dE(h1,h2):
    """OKLab Euclidean distance x100 — ~1.0 is a just-noticeable difference."""
    a = rgb2oklab(*hex2rgb(h1)); b = rgb2oklab(*hex2rgb(h2))
    return 100*math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))

def maxch(h1,h2):
    return max(abs(x-y) for x,y in zip(hex2rgb(h1), hex2rgb(h2)))

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

# ---------- shared constants ----------
CHROMATIC_STEPS = [25,50,100,200,300,400,500,600,700,800]
HUES = {"Edge":10, "Flash":32, "Yellow":50, "Mindaro":75, "Pulse":110,
        "Mint":145, "Brand":190, "Core":250, "Pink":350}
NEUTRAL_H = {"light":75, "dark":190}
CHROM = ["Brand","Core","Mindaro","Pulse","Flash","Edge","Pink","Yellow","Mint"]

P = json.load(open('data/palette.json'))

def entry(orig, gen, extra=None):
    """Build a comparison row. orig may be None when Figma has no swatch
    (e.g. chromatic step 900) — formula is still sampled, ΔE left blank."""
    e = {"orig": orig, "hsl": gen, "missing": orig is None}
    H, S, L = hex2hsl(gen)
    e["hsl_hsl"] = [round(H), round(S), round(L)]
    if orig is None:
        e["orig_hsl"] = None
        e["dE_hsl"] = None
        e["px_hsl"] = None
    else:
        H, S, L = hex2hsl(orig)
        e["orig_hsl"] = [round(H), round(S), round(L)]
        e["dE_hsl"] = round(dE(orig, gen), 2)
        e["px_hsl"] = maxch(orig, gen)
    if extra:
        e.update(extra)
    return e

# =====================================================================
# v1 — discrete step ladders (the original reconstruction)
# =====================================================================
def L_ladder(step):
    if step == 25: return 96.0
    if step <= 800: return 95 - step/10
    return 15 - (step-800)/20

def S_of(step):
    return max(70.0, min(100.0, 120 - step/10))

def hsl_formula_v1(fam, step):
    return hsl2hex(HUES[fam], S_of(step), L_ladder(step))

def neutral_S(theme, L):
    return L/10 if theme=="light" else 11 + (100-L)/9

def neutral_formula_v1(theme, step):
    L = L_ladder(step)
    return hsl2hex(NEUTRAL_H[theme], neutral_S(theme,L), L)

def greyscale_formula_v1(theme, step):
    return hsl2hex(0, 0, L_ladder(step))

def build_v1():
    out = {"id":"v1", "label":"v1", "families":[], "hues":HUES}
    for fam in CHROM:
        steps = P["light"][fam]
        rows=[]
        for s in CHROMATIC_STEPS:
            o = steps[str(s)]
            rows.append({"step":str(s), **entry(o, hsl_formula_v1(fam,s))})
        out["families"].append({
            "name":fam, "kind":"chromatic", "theme":"both", "hue":HUES[fam], "rows":rows})

    for theme in ("light","dark"):
        steps = P[theme]["Neutral"]
        rows=[]
        for k,v in steps.items():
            if k in ("White","Black"): continue
            s=int(k)
            rows.append({"step":k, **entry(v, neutral_formula_v1(theme,s))})
        out["families"].append({"name":"Neutral", "kind":"neutral", "theme":theme,
            "hue":NEUTRAL_H[theme], "rows":rows})

    for theme in ("light","dark"):
        steps = P[theme]["Greyscale"]
        rows=[]
        for k,v in steps.items():
            s=int(k)
            g = greyscale_formula_v1(theme,s)
            rows.append({"step":k, **entry(v, g)})
        out["families"].append({"name":"Greyscale", "kind":"grey", "theme":theme,
            "hue":0, "rows":rows})
    return out

# =====================================================================
# v2 — continuous H/S/L gradient functions + even lightness steps
#
# Parameter t ∈ [0, 1] runs light → dark along a continuous ramp.
# Named steps (25, 50, …) sit where L(t) hits the even lightness ladder
# (96, 90, 85, 75, …, 15) — equal ΔL on the design-token scale, which
# keeps early stops light instead of equal-Δt / equal-OKLab packing that
# over-darkens 50/100/200.
# =====================================================================

def L_cont(t):
    """Lightness: linear fade from Figma's light end (~96) to dark (~15).
    A slight ease (exponent > 1) keeps more of the continuous ramp in the
    light half so the gradient column doesn't dive into midtones too fast."""
    return 96.0 - 81.0 * (t ** 1.25)

def S_cont(t):
    """Saturation: full chroma in the lights, eases down to a floor of 70.
    Anchored in L-space rather than raw t, so it still tracks the Figma
    majority pattern 100 → 90 → 80 → 70 as lightness falls through 75→45."""
    L = L_cont(t)
    # L 75→45 maps onto the S 100→70 drop (the old steps 200→500)
    return clamp(100.0 - (75.0 - L), 70.0, 100.0)

def H_cont(H0, t):
    """Hue is constant down each family (Figma holds it to within rounding)."""
    return H0

def neutral_S_cont(theme, t):
    L = L_cont(t)
    return L/10 if theme=="light" else 11 + (100-L)/9

def sample_hex(kind, hue, theme, t):
    L = L_cont(t)
    if kind == "chromatic":
        return hsl2hex(H_cont(hue, t), S_cont(t), L)
    if kind == "neutral":
        return hsl2hex(hue, neutral_S_cont(theme, t), L)
    return hsl2hex(0, 0, L)

def t_for_L(L):
    """Invert L(t) = 96 − 81·t^1.25."""
    u = clamp((96.0 - L) / 81.0, 0.0, 1.0)
    return u ** (1.0 / 1.25)

def lightness_ladder_positions(step_keys):
    """Place each named step where L(t) equals the even lightness ladder.

    Targets come from the same ladder v1 uses (and Figma mostly follows):
      25→96, 50→90, 100→85, then −10 per step down to 800→15.
    Solving t = L⁻¹(target) keeps 50/100/200 as light as the scale intends,
    while the continuous gradient between them stays well-defined.
    """
    out = []
    for k in step_keys:
        out.append(t_for_L(L_ladder(int(k))))
    if out:
        out[0] = 0.0
    return out

def gradient_css_stops(kind, hue, theme, n=24):
    stops = []
    for i in range(n):
        t = i/(n-1)
        hexv = sample_hex(kind, hue, theme, t)
        stops.append(f"{hexv} {round(100*t, 2)}%")
    return f"linear-gradient(to bottom, {', '.join(stops)})"

def build_family_v2(name, kind, theme, hue, step_keys, orig_map, positions):
    rows = []
    for k, t in zip(step_keys, positions):
        o = orig_map[k]
        gen = sample_hex(kind, hue, theme, t)
        L, S = L_cont(t), (S_cont(t) if kind=="chromatic"
                           else (neutral_S_cont(theme,t) if kind=="neutral" else 0.0))
        rows.append({
            "step": k,
            **entry(o, gen, {
                "t": round(t, 4),
                "L": round(L, 2),
                "S": round(S, 2),
                "H": round(H_cont(hue, t) if kind!="grey" else 0, 1),
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue, "rows": rows,
        "gradient": gradient_css_stops(kind, hue, theme),
        "positions": [round(t, 4) for t in positions],
    }

def build_v2():
    out = {
        "id": "v2", "label": "v2", "families": [], "hues": HUES,
        "meta": {
            "L": "L(t) = 96 − 81·t^1.25",
            "S": "S(t) = clamp(100 − (75 − L(t)), 70, 100)",
            "H": "H(t) = H₀  (constant per family)",
            "steps": "tᵢ = L⁻¹(ladder) where ladder = 96,90,85,75,…,15 (shared)",
        },
    }
    # Shared placement per key-list so every family lines up on the same tᵢ
    pos_cache = {}
    def positions_for(keys):
        key = tuple(keys)
        if key not in pos_cache:
            pos_cache[key] = lightness_ladder_positions(keys)
        return pos_cache[key]

    for fam in CHROM:
        steps = P["light"][fam]
        keys = [str(s) for s in CHROMATIC_STEPS]
        out["families"].append(
            build_family_v2(fam, "chromatic", "both", HUES[fam], keys, steps,
                            positions_for(keys)))

    for theme in ("light","dark"):
        steps = P[theme]["Neutral"]
        keys = [k for k in steps if k not in ("White","Black")]
        out["families"].append(
            build_family_v2("Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps,
                            positions_for(keys)))

    for theme in ("light","dark"):
        steps = P[theme]["Greyscale"]
        keys = list(steps.keys())
        out["families"].append(
            build_family_v2("Greyscale", "grey", theme, 0, keys, steps,
                            positions_for(keys)))

    out["shared_positions"] = {
        str(len(k)): [round(t, 4) for t in pos] for k, pos in pos_cache.items()
    }
    return out

# =====================================================================
# v3 — pure continuous curves, no hard-coded step ladders
#
# Everything is a function of t ∈ [0, 1]. Hue is fixed per family.
# Saturation and lightness are smooth curves (no per-step tables).
# Named Figma tokens are only labels: they sample the curve at equal
# progression t = i/(N−1).
# =====================================================================

def smoothstep(edge0, edge1, x):
    """Hermite smoothstep — C¹ ease between edge0 and edge1."""
    if x <= edge0: return 0.0
    if x >= edge1: return 1.0
    u = (x - edge0) / (edge1 - edge0)
    return u * u * (3.0 - 2.0 * u)

def L_v3(t):
    """Lightness curve: eased fade from near-white to near-black.
    Endpoints and ease are fitted to the Figma majority ramp as a whole,
    not to individual named steps."""
    return 96.0 - 81.0 * (t ** 1.2)

def S_v3(t):
    """Saturation curve: holds full chroma, then eases down to a floor.
    The ease window is a property of the curve shape (fitted to the
    overall Figma envelope), not a list of step values."""
    drop = smoothstep(0.28, 0.55, t)
    return 100.0 - 30.0 * drop   # 100 → 70

def H_v3(H0, t):
    return H0

def neutral_S_v3(theme, t):
    L = L_v3(t)
    return L / 10.0 if theme == "light" else 11.0 + (100.0 - L) / 9.0

def sample_hex_v3(kind, hue, theme, t):
    L = L_v3(t)
    if kind == "chromatic":
        return hsl2hex(H_v3(hue, t), S_v3(t), L)
    if kind == "neutral":
        return hsl2hex(hue, neutral_S_v3(theme, t), L)
    return hsl2hex(0, 0, L)

def equal_t_positions(n):
    """Named tokens sample the curve at equal progression — no ladder."""
    if n <= 1: return [0.0]
    return [i / (n - 1) for i in range(n)]

def gradient_css_v3(kind, hue, theme, n=32):
    stops = []
    for i in range(n):
        t = i / (n - 1)
        stops.append(f"{sample_hex_v3(kind, hue, theme, t)} {round(100 * t, 2)}%")
    return f"linear-gradient(to bottom, {', '.join(stops)})"

def curve_samples(kind="chromatic", theme="both", n=64):
    """Dense samples of L(t) and S(t) for the diagram."""
    ts, Ls, Ss = [], [], []
    for i in range(n):
        t = i / (n - 1)
        ts.append(round(t, 4))
        Ls.append(round(L_v3(t), 3))
        if kind == "chromatic":
            Ss.append(round(S_v3(t), 3))
        elif kind == "neutral":
            Ss.append(round(neutral_S_v3(theme, t), 3))
        else:
            Ss.append(0.0)
    return {"t": ts, "L": Ls, "S": Ss}

def build_family_v3(name, kind, theme, hue, step_keys, orig_map):
    n = len(step_keys)
    positions = equal_t_positions(n)
    rows = []
    for k, t in zip(step_keys, positions):
        o = orig_map[k]
        gen = sample_hex_v3(kind, hue, theme, t)
        L = L_v3(t)
        S = (S_v3(t) if kind == "chromatic"
             else (neutral_S_v3(theme, t) if kind == "neutral" else 0.0))
        rows.append({
            "step": k,
            **entry(o, gen, {
                "t": round(t, 4),
                "L": round(L, 2),
                "S": round(S, 2),
                "H": round(H_v3(hue, t) if kind != "grey" else 0, 1),
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue, "rows": rows,
        "gradient": gradient_css_v3(kind, hue, theme),
        "positions": [round(t, 4) for t in positions],
    }

def build_v3():
    out = {
        "id": "v3", "label": "v3", "families": [], "hues": HUES,
        "meta": {
            "L": "L(t) = 96 − 81·t^1.2",
            "S": "S(t) = 100 − 30·smoothstep(0.28, 0.55, t)",
            "H": "H(t) = H₀  (constant per family)",
            "steps": "tᵢ = i/(N−1)  — equal progression, no step ladder",
        },
        "curves": {
            "chromatic": curve_samples("chromatic"),
            "neutral_light": curve_samples("neutral", "light"),
            "neutral_dark": curve_samples("neutral", "dark"),
            "grey": curve_samples("grey"),
        },
    }

    for fam in CHROM:
        steps = P["light"][fam]
        keys = [str(s) for s in CHROMATIC_STEPS]
        out["families"].append(
            build_family_v3(fam, "chromatic", "both", HUES[fam], keys, steps))

    for theme in ("light", "dark"):
        steps = P[theme]["Neutral"]
        keys = [k for k in steps if k not in ("White", "Black")]
        out["families"].append(
            build_family_v3("Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps))

    for theme in ("light", "dark"):
        steps = P[theme]["Greyscale"]
        keys = list(steps.keys())
        out["families"].append(
            build_family_v3("Greyscale", "grey", theme, 0, keys, steps))

    return out

# =====================================================================
# v4 — continuous curves with no plateaus + per-family saturation gain
#
# L(t) eases a bit more at the light end so early samples (e.g. 50) stay
# lighter. S(t) is a single smooth drop with a non-zero initial slope
# (no flat hold at 100 or floor at 70). Each chromatic family multiplies
# the saturation drop by a gain k_H fitted to Figma.
# =====================================================================

# Saturation drop gain per chromatic family (fitted to Figma S, dark-weighted).
S_GAIN = {
    "Brand": 1.25, "Core": 1.25, "Edge": 1.25, "Yellow": 1.25, "Mint": 1.25,
    "Mindaro": 1.20, "Flash": 1.80, "Pulse": 2.45, "Pink": 2.40,
}

def L_v4(t):
    """Lightness: same endpoints as v3, higher ease so the light end
    falls more slowly — step-50 at equal-t lands near Figma (~92)."""
    return 96.0 - 81.0 * (t ** 1.35)

def S_drop_v4(t):
    """Unit drop shape u(t) ∈ [0,1], strictly increasing, u'(0) > 0.
    u(t) = t·(1 + 3t)/4  — no plateau at either end."""
    return t * (1.0 + 3.0 * t) / 4.0

def S_v4(t, k=1.0):
    """Saturation: continuous decline from 100, scaled by family gain k.
    S(t) = clamp(100 − 30·k·u(t), 0, 100)"""
    return clamp(100.0 - 30.0 * k * S_drop_v4(t), 0.0, 100.0)

def H_v4(H0, t):
    return H0

def neutral_S_v4(theme, t):
    L = L_v4(t)
    return L / 10.0 if theme == "light" else 11.0 + (100.0 - L) / 9.0

def sample_hex_v4(kind, hue, theme, t, k=1.0):
    L = L_v4(t)
    if kind == "chromatic":
        return hsl2hex(H_v4(hue, t), S_v4(t, k), L)
    if kind == "neutral":
        return hsl2hex(hue, neutral_S_v4(theme, t), L)
    return hsl2hex(0, 0, L)

def gradient_css_v4(kind, hue, theme, k=1.0, n=32):
    stops = []
    for i in range(n):
        t = i / (n - 1)
        stops.append(f"{sample_hex_v4(kind, hue, theme, t, k)} {round(100 * t, 2)}%")
    return f"linear-gradient(to bottom, {', '.join(stops)})"

def curve_samples_v4(kind="chromatic", theme="both", k=1.0, n=64):
    ts, Ls, Ss = [], [], []
    for i in range(n):
        t = i / (n - 1)
        ts.append(round(t, 4))
        Ls.append(round(L_v4(t), 3))
        if kind == "chromatic":
            Ss.append(round(S_v4(t, k), 3))
        elif kind == "neutral":
            Ss.append(round(neutral_S_v4(theme, t), 3))
        else:
            Ss.append(0.0)
    return {"t": ts, "L": Ls, "S": Ss}

def build_family_v4(name, kind, theme, hue, step_keys, orig_map, k=1.0):
    n = len(step_keys)
    positions = equal_t_positions(n)
    rows = []
    for key, t in zip(step_keys, positions):
        o = orig_map[key]
        gen = sample_hex_v4(kind, hue, theme, t, k)
        L = L_v4(t)
        S = (S_v4(t, k) if kind == "chromatic"
             else (neutral_S_v4(theme, t) if kind == "neutral" else 0.0))
        rows.append({
            "step": key,
            **entry(o, gen, {
                "t": round(t, 4),
                "L": round(L, 2),
                "S": round(S, 2),
                "H": round(H_v4(hue, t) if kind != "grey" else 0, 1),
                "k": k,
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue,
        "k": k, "rows": rows,
        "gradient": gradient_css_v4(kind, hue, theme, k),
        "positions": [round(t, 4) for t in positions],
    }

def build_v4():
    out = {
        "id": "v4", "label": "v4", "families": [], "hues": HUES,
        "s_gain": S_GAIN,
        "meta": {
            "L": "L(t) = 96 − 81·t^1.35",
            "S": "S(t) = clamp(100 − 30·k_H·t·(1 + 3t)/4, 0, 100)",
            "H": "H(t) = H₀  (constant per family)",
            "k": "k_H = per-family saturation gain (fitted to Figma)",
            "steps": "tᵢ = i/(N−1)  — equal progression, no step ladder",
        },
        "curves": {
            # Base curve at k=1, plus a high-gain example for the diagram
            "chromatic": curve_samples_v4("chromatic", k=1.0),
            "chromatic_hi": curve_samples_v4("chromatic", k=2.45),
            "neutral_light": curve_samples_v4("neutral", "light"),
            "neutral_dark": curve_samples_v4("neutral", "dark"),
            "grey": curve_samples_v4("grey"),
        },
    }

    for fam in CHROM:
        steps = P["light"][fam]
        keys = [str(s) for s in CHROMATIC_STEPS]
        k = S_GAIN[fam]
        out["families"].append(
            build_family_v4(fam, "chromatic", "both", HUES[fam], keys, steps, k))

    for theme in ("light", "dark"):
        steps = P[theme]["Neutral"]
        keys = [k for k in steps if k not in ("White", "Black")]
        out["families"].append(
            build_family_v4("Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps, 1.0))

    for theme in ("light", "dark"):
        steps = P[theme]["Greyscale"]
        keys = list(steps.keys())
        out["families"].append(
            build_family_v4("Greyscale", "grey", theme, 0, keys, steps, 1.0))

    return out

# =====================================================================
# v5 — full 0→100 domain; named steps are interior samples; sine S
#
# The continuous scale runs from 0 to 100 (t ∈ [0, 1]). Token numbers
# map as scale = step/10 (so 25 → 2.5, 800 → 80, 900 → 90). Chromatic
# 900 is formula-only (Figma has no swatch). Saturation uses an
# asymmetric raised-cosine: flat at both ends, but the drop is front-
# loaded so half the unit curve is done by t = 1/3.
# =====================================================================

# Chromatic samples on the 0→100 scale (900 is formula-only).
CHROMATIC_STEPS_V5 = [25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

# Saturation drop gain per chromatic family (fitted to Figma on t=step/1000).
S_GAIN_V5 = {
    "Brand": 1.25, "Core": 1.25, "Edge": 1.25, "Yellow": 1.25, "Mint": 1.25,
    "Mindaro": 1.30, "Flash": 1.65, "Pulse": 2.00, "Pink": 1.95,
}

# Power bias so g(1/3) = 1/2 → half the S-drop by one-third of the ramp.
# g(t) = t^p keeps u flat at both ends (u'(0)=u'(1)=0) while breaking symmetry.
S_POWER_V5 = math.log(0.5) / math.log(1.0 / 3.0)  # ≈ 0.6309

def step_to_t_v5(step_key):
    """Map a Figma token onto the 0→100 scale. White=0, Black=100,
    numeric tokens use step/1000 (display scale = step/10)."""
    if step_key == "White":
        return 0.0
    if step_key == "Black":
        return 1.0
    return int(step_key) / 1000.0

def L_v5(t):
    """Lightness across the full 0→100 domain. Fitted so interior
    samples near Figma's 25…800 ladder stay close, while t=0 / t=1
    extrapolate lighter / darker than those named ends."""
    return 99.0 - 98.0 * (t ** 0.83)

def S_unit_v5(t):
    """Asymmetric raised-cosine unit curve: u(0)=0, u(1)=1, u'(0)=u'(1)=0.
    g(t)=t^p with p=log(1/2)/log(1/3) so g(1/3)=1/2 — the drop is already
    halfway by one-third of the ramp, then flattens into the dark end."""
    g = t ** S_POWER_V5
    return (1.0 - math.cos(math.pi * g)) / 2.0

def S_v5(t, k=1.0):
    """S(t) = clamp(100 − 30·k_H·u(t), 0, 100) with asymmetric sine u(t)."""
    return clamp(100.0 - 30.0 * k * S_unit_v5(t), 0.0, 100.0)

def H_v5(H0, t):
    return H0

def neutral_S_v5(theme, t):
    L = L_v5(t)
    return L / 10.0 if theme == "light" else 11.0 + (100.0 - L) / 9.0

def sample_hex_v5(kind, hue, theme, t, k=1.0):
    L = L_v5(t)
    if kind == "chromatic":
        return hsl2hex(H_v5(hue, t), S_v5(t, k), L)
    if kind == "neutral":
        return hsl2hex(hue, neutral_S_v5(theme, t), L)
    return hsl2hex(0, 0, L)

def gradient_css_v5(kind, hue, theme, k=1.0, n=40):
    stops = []
    for i in range(n):
        t = i / (n - 1)
        stops.append(f"{sample_hex_v5(kind, hue, theme, t, k)} {round(100 * t, 2)}%")
    return f"linear-gradient(to bottom, {', '.join(stops)})"

def curve_samples_v5(kind="chromatic", theme="both", k=1.0, n=64):
    ts, scales, Ls, Ss = [], [], [], []
    for i in range(n):
        t = i / (n - 1)
        ts.append(round(t, 4))
        scales.append(round(100.0 * t, 2))
        Ls.append(round(L_v5(t), 3))
        if kind == "chromatic":
            Ss.append(round(S_v5(t, k), 3))
        elif kind == "neutral":
            Ss.append(round(neutral_S_v5(theme, t), 3))
        else:
            Ss.append(0.0)
    return {"t": ts, "scale": scales, "L": Ls, "S": Ss}

def build_family_v5(name, kind, theme, hue, step_keys, orig_map, k=1.0):
    rows = []
    positions = []
    for key in step_keys:
        t = step_to_t_v5(key)
        positions.append(t)
        o = orig_map.get(key)  # None when Figma has no swatch (chromatic 900)
        gen = sample_hex_v5(kind, hue, theme, t, k)
        L = L_v5(t)
        S = (S_v5(t, k) if kind == "chromatic"
             else (neutral_S_v5(theme, t) if kind == "neutral" else 0.0))
        rows.append({
            "step": key,
            **entry(o, gen, {
                "t": round(t, 4),
                "scale": round(100.0 * t, 2),
                "L": round(L, 2),
                "S": round(S, 2),
                "H": round(H_v5(hue, t) if kind != "grey" else 0, 1),
                "k": k,
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue,
        "k": k, "rows": rows,
        "gradient": gradient_css_v5(kind, hue, theme, k),
        "positions": [round(t, 4) for t in positions],
    }

def build_v5():
    out = {
        "id": "v5", "label": "v5", "families": [], "hues": HUES,
        "s_gain": S_GAIN_V5,
        "s_power": round(S_POWER_V5, 6),
        "meta": {
            "L": "L(t) = 99 − 98·t^0.83",
            "S": "S(t) = clamp(100 − 30·k_H·(1 − cos(π·t^p))/2, 0, 100)",
            "p": "p = log(1/2)/log(1/3) ≈ 0.631  →  half the S-drop by t = 1/3",
            "H": "H(t) = H₀  (constant per family)",
            "k": "k_H = per-family saturation gain (fitted to Figma)",
            "steps": "scale = step/10 ∈ (0,100); t = scale/100 — includes 900 (formula-only on chromatics)",
            "domain": "full gradient 0 → 100",
        },
        "curves": {
            "chromatic": curve_samples_v5("chromatic", k=1.0),
            "chromatic_hi": curve_samples_v5("chromatic", k=2.0),
            "neutral_light": curve_samples_v5("neutral", "light"),
            "neutral_dark": curve_samples_v5("neutral", "dark"),
            "grey": curve_samples_v5("grey"),
        },
    }

    for fam in CHROM:
        steps = P["light"][fam]
        keys = [str(s) for s in CHROMATIC_STEPS_V5]
        k = S_GAIN_V5[fam]
        out["families"].append(
            build_family_v5(fam, "chromatic", "both", HUES[fam], keys, steps, k))

    for theme in ("light", "dark"):
        steps = P[theme]["Neutral"]
        keys = [k for k in steps if k not in ("White", "Black")]
        out["families"].append(
            build_family_v5("Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps, 1.0))

    for theme in ("light", "dark"):
        steps = P[theme]["Greyscale"]
        keys = list(steps.keys())
        out["families"].append(
            build_family_v5("Greyscale", "grey", theme, 0, keys, steps, 1.0))

    return out

# ---------- assemble ----------
def main():
    out = {
        "v1": build_v1(), "v2": build_v2(), "v3": build_v3(),
        "v4": build_v4(), "v5": build_v5(), "default": "v5",
    }
    json.dump(out, open('data/generated.json', 'w'), indent=1)

    for ver_id in ("v1", "v2", "v3", "v4", "v5"):
        ver = out[ver_id]
        print(f"\n=== {ver_id} ===")
        print(f"{'family':<12}{'theme':<7}{'mean ΔE':>9}{'max':>7}   worst step")
        for f in ver["families"]:
            dh = [r["dE_hsl"] for r in f["rows"] if r["dE_hsl"] is not None]
            compared = [r for r in f["rows"] if r["dE_hsl"] is not None]
            w = max(compared, key=lambda r: r["dE_hsl"]) if compared else f["rows"][0]
            extra = ""
            if ver_id in ("v4", "v5") and f["kind"] == "chromatic":
                extra = f"  k={f['k']}"
            mean = (sum(dh) / len(dh)) if dh else 0.0
            mx = max(dh) if dh else 0.0
            print(f'{f["name"]:<12}{f["theme"]:<7}{mean:9.2f}{mx:7.2f}   '
                  f'{w["step"]:>4} {w["orig"]}→{w["hsl"]} ({w["px_hsl"]}/255){extra}')
        if ver_id == "v2":
            print("shared t (10):", out["v2"]["shared_positions"].get("10"))
        if ver_id in ("v3", "v4"):
            print("equal t (10):", [round(i/9, 4) for i in range(10)])
        if ver_id == "v4":
            print("S gains:", out["v4"]["s_gain"])
            print(f"L(1/9)={L_v4(1/9):.2f}  (step 50 target ~92)")
        if ver_id == "v5":
            print("S gains:", out["v5"]["s_gain"])
            print("S power p:", out["v5"]["s_power"])
            brand = next(f for f in out["v5"]["families"] if f["name"] == "Brand")
            print("Brand samples:", [(r["step"], r["scale"], r["L"], r["S"], r.get("missing")) for r in brand["rows"]])
            print(f"L(0)={L_v5(0):.1f}  L(0.025)={L_v5(0.025):.1f}  "
                  f"L(0.8)={L_v5(0.8):.1f}  L(0.9)={L_v5(0.9):.1f}  L(1)={L_v5(1):.1f}")
            print(f"S_unit(0)={S_unit_v5(0):.3f}  S_unit(1/3)={S_unit_v5(1/3):.3f}  "
                  f"S_unit(0.5)={S_unit_v5(0.5):.3f}  S_unit(1)={S_unit_v5(1):.3f}")

if __name__ == "__main__":
    main()
