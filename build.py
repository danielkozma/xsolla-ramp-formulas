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


    return out

# =====================================================================
# v5 — full 0→100 domain; named steps are interior samples; sine S
#
# The continuous scale runs from 0 to 100 (t ∈ [0, 1]). Token numbers
# map as scale = step/10 (so 25 → 2.5, 800 → 80, 850 → 85, 900 → 90).
# Chromatic 850/900 are formula-only when Figma has no swatch.
#
# Saturation: asymmetric raised-cosine, front-loaded (half drop by t=1/3).
# Lightness: power curve whose exponent is auto-biased by hue — yellow–
# green hues (perceptually light) get a steeper early drop, then ease out.
# =====================================================================

# Chromatic samples on the 0→100 scale (850/900 often formula-only).
CHROMATIC_STEPS_V5 = [25, 50, 100, 200, 300, 400, 500, 600, 700, 800, 850, 900]

# Saturation drop gain per chromatic family (fitted to Figma on t=step/1000).
S_GAIN_V5 = {
    "Brand": 1.25, "Core": 1.25, "Edge": 1.25, "Yellow": 1.25, "Mint": 1.25,
    "Mindaro": 1.30, "Flash": 1.65, "Pulse": 2.00, "Pink": 1.95,
}

# Power bias so g(1/3) = 1/2 → half the S-drop by one-third of the ramp.
S_POWER_V5 = math.log(0.5) / math.log(1.0 / 3.0)  # ≈ 0.6309

# Lightness: a power law whose exponent is bent by hue instead of being scaled.
# The bend is the derivative of a Gaussian in log t — zero total area, so it
# steepens the exponent before the centre and relaxes it after by the same
# amount. Both ends of the ramp are fixed; the curvature lands on the light steps.
L_POWER_BASE_V5 = 0.83
L_PEAK_HUE_V5 = 75.0   # Mindaro / chartreuse — perceptually lightest region
# Half-widths of the hue lobe, in degrees. Asymmetric: greens stay perceptually
# light much further round the wheel than the warm side, so the correction
# fades out at hue 220 going up and at 345 going down.
LOBE_UP_V5 = 145.0     # 75° → 220° (green, cyan, into teal)
LOBE_DN_V5 = 90.0      # 75° → 345° (yellow, orange, red)
BEND_REF_V5 = 0.50     # bend strength at the peak hue
BEND_TC_V5 = 0.055     # bend centre on the 0→1 scale (≈ step 55)
BEND_SIGMA_V5 = 1.15   # bend width, in log-scale units

def step_to_t_v5(step_key):
    """Map a Figma token onto the 0→100 scale. White=0, Black=100,
    numeric tokens use step/1000 (display scale = step/10)."""
    if step_key == "White":
        return 0.0
    if step_key == "Black":
        return 1.0
    return int(step_key) / 1000.0

def hue_light_weight_v5(H):
    """1 at the yellow-green peak (perceptually lightest), easing to 0 at the
    edge of the lobe — 220° on the green side, 345° on the warm side. Squared
    half-cosine, so it leaves the peak and meets zero with zero slope: smooth
    in hue, no hard-coded family tables."""
    delta = (H - L_PEAK_HUE_V5 + 180.0) % 360.0 - 180.0      # signed, −180..180
    span = LOBE_UP_V5 if delta >= 0.0 else LOBE_DN_V5
    d = abs(delta) / span
    if d >= 1.0:
        return 0.0
    c = math.cos(math.pi / 2.0 * d)
    return c * c

def bend_delta_v5(H=None):
    """How hard this hue bends the lightness exponent. 0 for achromatic sets
    and for hues opposite the perceptual peak — those keep the plain power law."""
    if H is None:
        return 0.0
    return BEND_REF_V5 * hue_light_weight_v5(H)

def _bend_G_v5(x):
    """Gaussian in log t, centred on the bend centre."""
    z = (x - math.log(BEND_TC_V5)) / BEND_SIGMA_V5
    return math.exp(-0.5 * z * z)

def L_v5(t, H=None):
    """Lightness across the full 0→100 domain.

    Base ramp: drop = 98.5·t^p, a straight line in log-log with p = 0.83.
    The hue correction bends that line by making the exponent a function of
    scale position, q(t) = p + Δ·G'(ln t). G' is a Gaussian derivative, so its
    area is zero and integrating q closes into one Gaussian factor:

        drop(t) = 98.5 · t^p · exp( Δ·[G(ln t) − G(0)] )

    Δ=0 is exactly the base curve, drop(1)=98.5 for every Δ, and monotonicity
    holds while Δ·e^(−½)/σ < p (the fitted Δ ≤ 0.5 leaves q ≥ 0.57).
    """
    # Light end sits at 99.5 (was 99) so step 25 stays a touch brighter
    # without changing the curve shape or the ~1 dark end.
    if t <= 0.0:
        return 99.5
    x = math.log(t)
    d = bend_delta_v5(H)
    drop = 98.5 * math.exp(L_POWER_BASE_V5 * x + d * (_bend_G_v5(x) - _bend_G_v5(0.0)))
    return 99.5 - drop

def L_q_v5(t, H=None):
    """Local exponent of the ramp at t — the quantity the bend reshapes."""
    if t <= 0.0:
        return L_POWER_BASE_V5
    x = math.log(t)
    d = bend_delta_v5(H)
    return L_POWER_BASE_V5 - d * ((x - math.log(BEND_TC_V5)) / BEND_SIGMA_V5 ** 2) * _bend_G_v5(x)

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

def neutral_S_v5(theme, t, H=None):
    L = L_v5(t, H)
    return L / 10.0 if theme == "light" else 11.0 + (100.0 - L) / 9.0

def sample_hex_v5(kind, hue, theme, t, k=1.0):
    H_for_L = hue if kind == "chromatic" else None
    L = L_v5(t, H_for_L)
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

def curve_samples_v5(kind="chromatic", theme="both", k=1.0, H=None, n=64):
    ts, scales, Ls, Ss = [], [], [], []
    use_H = H if kind == "chromatic" else None
    for i in range(n):
        t = i / (n - 1)
        ts.append(round(t, 4))
        scales.append(round(100.0 * t, 2))
        Ls.append(round(L_v5(t, use_H), 3))
        if kind == "chromatic":
            Ss.append(round(S_v5(t, k), 3))
        elif kind == "neutral":
            Ss.append(round(neutral_S_v5(theme, t), 3))
        else:
            Ss.append(0.0)
    return {"t": ts, "scale": scales, "L": Ls, "S": Ss}

def merge_steps_v5(existing_keys, extra=(850, 900)):
    """Keep existing numeric tokens, ensure extra steps are present, sort."""
    nums = {int(k) for k in existing_keys if str(k).isdigit()}
    nums.update(extra)
    return [str(n) for n in sorted(nums)]

def build_family_v5(name, kind, theme, hue, step_keys, orig_map, k=1.0):
    rows = []
    positions = []
    bend = round(bend_delta_v5(hue if kind == "chromatic" else None), 4)
    for key in step_keys:
        t = step_to_t_v5(key)
        positions.append(t)
        o = orig_map.get(key)  # None when Figma has no swatch
        gen = sample_hex_v5(kind, hue, theme, t, k)
        H_for_L = hue if kind == "chromatic" else None
        L = L_v5(t, H_for_L)
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
                "bend": bend,
                "q": round(L_q_v5(t, H_for_L), 3),
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue,
        "k": k, "bend": bend, "rows": rows,
        "gradient": gradient_css_v5(kind, hue, theme, k),
        "positions": [round(t, 4) for t in positions],
    }

def build_v5():
    out = {
        "id": "v5", "label": "v5", "families": [], "hues": HUES,
        "s_gain": S_GAIN_V5,
        "s_power": round(S_POWER_V5, 6),
        "formula": {
            "L0": 99.5,
            "L_range": 98.5,
            "L_power_base": L_POWER_BASE_V5,
            "L_peak_hue": L_PEAK_HUE_V5,
            "lobe_up": LOBE_UP_V5,
            "lobe_dn": LOBE_DN_V5,
            "bend_ref": BEND_REF_V5,
            "bend_tc": BEND_TC_V5,
            "bend_sigma": BEND_SIGMA_V5,
            "S_drop": 30.0,
            "S_power": round(S_POWER_V5, 6),
            "steps": CHROMATIC_STEPS_V5,
        },
        "meta": {
            "L": "L(t,H) = 99.5 − 98.5·t^0.83·exp(Δ(H)·[G(ln t) − G(0)])",
            "G": "G(x) = exp(−½((x − ln 0.055)/1.15)²); bend q(t) = 0.83 + Δ·G′(ln t)",
            "d": "Δ(H) = 0.5·w(H) — 0 for cool hues and achromatic sets",
            "w": "w(H) = cos²(½π·d) for d<1 else 0; d = |H−75°| / (145° up, 90° down)",
            "S": "S(t) = clamp(100 − 30·k_H·(1 − cos(π·t^q))/2, 0, 100)",
            "q": "q = log(1/2)/log(1/3) ≈ 0.631  →  half the S-drop by t = 1/3",
            "H": "H(t) = H₀  (constant per family)",
            "k": "k_H = per-family saturation gain (fitted to Figma)",
            "steps": "scale = step/10 ∈ (0,100); t = scale/100 — includes 850 & 900",
            "domain": "full gradient 0 → 100",
        },
        "curves": {
            # Shared S; L shown at Brand hue and at Mindaro (peak bias)
            "chromatic": curve_samples_v5("chromatic", k=1.0, H=190),
            "chromatic_hi": curve_samples_v5("chromatic", k=2.0, H=190),
            "chromatic_L_peak": curve_samples_v5("chromatic", k=1.0, H=L_PEAK_HUE_V5),
            "neutral_light": curve_samples_v5("neutral", "light"),
            "neutral_dark": curve_samples_v5("neutral", "dark"),
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
        keys = merge_steps_v5([k for k in steps if k not in ("White", "Black")])
        out["families"].append(
            build_family_v5("Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps, 1.0))


    return out

# =====================================================================
# v6 — the dumb version. An experiment: how much of v5 survives if every
# function is replaced by the stupidest thing that could work?
#
#   v5                                          v6
#   ------------------------------------------  --------------------------------
#   two-sided cos² hue lobe (145°/90°)          one triangle, 120° each way
#   Gaussian-derivative bend of the exponent    subtract 0.10·w from the exponent
#   raised cosine on t^0.631 for S              one power, t^(2/3)
#   nine fitted saturation gains                two: 1.25, or 2 for the vivid three
#   L0 99.5 / L_range 98.5                      100 and 100
#
# Five constants and one Math.pow per channel. It lands a mean ΔE of 1.0 from
# v5's output and fits the current palette just as closely (2.07 vs v5's 2.11).
# =====================================================================
P_BASE_V6 = 0.82       # lightness exponent for hues that need no correction
P_AMP_V6 = 0.10        # …and how much the light-reading hues take off it
LOBE_V6 = 120.0        # triangle half-width in degrees, same both ways
S_DROP_V6 = 30.0       # saturation lost from t=0 to t=1 at k=1
S_POWER_V6 = 2.0/3.0   # the whole S curve
K_VIVID_V6 = ("Flash", "Pulse", "Pink")

def k_v6(name):
    return 2.0 if name in K_VIVID_V6 else 1.25

def hue_weight_v6(H):
    """Triangle instead of v5's squared cosine — worth 0.1 ΔE, and it is one line."""
    d = abs((H - L_PEAK_HUE_V5 + 180.0) % 360.0 - 180.0)
    return max(0.0, 1.0 - d / LOBE_V6)

def p_v6(H=None):
    return P_BASE_V6 if H is None else P_BASE_V6 - P_AMP_V6 * hue_weight_v6(H)

def L_v6(t, H=None):
    return 100.0 - 100.0 * (t ** p_v6(H)) if t > 0.0 else 100.0

def S_v6(t, k=1.0):
    return clamp(100.0 - S_DROP_V6 * k * (t ** S_POWER_V6), 0.0, 100.0)

def neutral_S_v6(theme, L):
    """v5's neutral saturation was already linear in L; these are the round versions."""
    return L / 10.0 if theme == "light" else 22.0 - L / 9.0

def sample_hex_v6(kind, hue, theme, t, k=1.0):
    L = L_v6(t, hue if kind == "chromatic" else None)
    if kind == "chromatic":
        return hsl2hex(hue, S_v6(t, k), L)
    return hsl2hex(hue, neutral_S_v6(theme, L), L)

def gradient_css_v6(kind, hue, theme, k=1.0, n=40):
    stops = [f"{sample_hex_v6(kind, hue, theme, i/(n-1), k)} {round(100*i/(n-1), 2)}%"
             for i in range(n)]
    return f"linear-gradient(to bottom, {', '.join(stops)})"

def curve_samples_v6(kind="chromatic", theme="both", k=1.0, H=None, n=64):
    ts, scales, Ls, Ss = [], [], [], []
    use_H = H if kind == "chromatic" else None
    for i in range(n):
        t = i / (n - 1)
        L = L_v6(t, use_H)
        ts.append(round(t, 4)); scales.append(round(100.0*t, 2)); Ls.append(round(L, 3))
        Ss.append(round(S_v6(t, k) if kind == "chromatic" else neutral_S_v6(theme, L), 3))
    return {"t": ts, "scale": scales, "L": Ls, "S": Ss}

def build_family_v6(name, kind, theme, hue, step_keys, orig_map, v5_rows, k=1.0):
    rows, positions = [], []
    p = round(p_v6(hue if kind == "chromatic" else None), 4)
    v5_by_step = {r["step"]: r["hsl"] for r in v5_rows}
    d5 = []
    for key in step_keys:
        t = step_to_t_v5(key)
        positions.append(t)
        gen = sample_hex_v6(kind, hue, theme, t, k)
        L = L_v6(t, hue if kind == "chromatic" else None)
        S = S_v6(t, k) if kind == "chromatic" else neutral_S_v6(theme, L)
        ref = v5_by_step.get(key)
        e5 = round(dE(ref, gen), 2) if ref else None
        if e5 is not None:
            d5.append(e5)
        rows.append({
            "step": key,
            **entry(orig_map.get(key), gen, {
                "t": round(t, 4),
                "scale": round(100.0 * t, 2),
                "L": round(L, 2),
                "S": round(S, 2),
                "H": round(hue, 1),
                "k": k,
                "p": p,
                "dE_v5": e5,
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue,
        "k": k, "p": p, "rows": rows,
        "d5": round(sum(d5)/len(d5), 2) if d5 else None,
        "gradient": gradient_css_v6(kind, hue, theme, k),
        "positions": [round(t, 4) for t in positions],
    }

def build_v6(v5):
    """v5 is passed in so every family can report how far the dumb version drifts."""
    v5_fam = {(f["name"], f["theme"]): f["rows"] for f in v5["families"]}
    out = {
        "id": "v6", "label": "v6", "families": [], "hues": HUES,
        "formula": {
            "L0": 100.0, "L_range": 100.0,
            "p_base": P_BASE_V6, "p_amp": P_AMP_V6,
            "lobe": LOBE_V6, "peak_hue": L_PEAK_HUE_V5,
            "S_drop": S_DROP_V6, "S_power": round(S_POWER_V6, 6),
            "k_vivid": list(K_VIVID_V6),
            "steps": CHROMATIC_STEPS_V5,
        },
        "meta": {
            "w": "w(H) = max(0, 1 \u2212 |H\u221275\u00b0|/120)   \u2014 a triangle",
            "p": "p(H) = 0.82 \u2212 0.10\u00b7w(H)",
            "L": "L(t,H) = 100 \u2212 100\u00b7t^p(H)",
            "S": "S(t) = clamp(100 \u2212 30\u00b7k\u00b7t^(2/3), 0, 100),  k = 1.25 or 2",
            "N": "neutral S = L/10 (light), 22 \u2212 L/9 (dark)",
        },
        "curves": {
            "chromatic": curve_samples_v6("chromatic", k=1.25, H=190),
            "chromatic_L_peak": curve_samples_v6("chromatic", k=1.25, H=L_PEAK_HUE_V5),
            "neutral_light": curve_samples_v6("neutral", "light"),
            "neutral_dark": curve_samples_v6("neutral", "dark"),
        },
    }

    for fam in CHROM:
        keys = [str(s) for s in CHROMATIC_STEPS_V5]
        out["families"].append(build_family_v6(
            fam, "chromatic", "both", HUES[fam], keys, P["light"][fam],
            v5_fam[(fam, "both")], k_v6(fam)))

    for theme in ("light", "dark"):
        steps = P[theme]["Neutral"]
        keys = merge_steps_v5([k for k in steps if k not in ("White", "Black")])
        out["families"].append(build_family_v6(
            "Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps,
            v5_fam[("Neutral", theme)], 1.0))

    rows = [r for f in out["families"] for r in f["rows"]]
    d5 = [r["dE_v5"] for r in rows if r["dE_v5"] is not None]
    dc = [r["dE_hsl"] for r in rows if r["dE_hsl"] is not None]
    out["vs_v5"] = {"mean": round(sum(d5)/len(d5), 2), "max": round(max(d5), 2)}
    out["vs_current"] = {"mean": round(sum(dc)/len(dc), 2), "max": round(max(dc), 2)}
    return out

# =====================================================================
# v7 — the middle ground. Same intent as v5, none of the calculus.
#
# v5 derives its bend properly: the exponent is perturbed by a Gaussian
# derivative, which has zero area, and the perturbation is integrated to a
# closed form so the endpoints provably hold. v7 skips all of that and slides
# a varying exponent straight into the power law:
#
#     e(t) = 0.84 − 0.20·w(H)·b(t),   b(t) = 4c·t/(t+c)²   (c = 0.09)
#     L(t,H) = 100 − 100·t^e(t)
#
# b is the same bell in log-t that v5 draws with a Gaussian, written without
# ln or exp: zero at t=0, 1 at t=c, slow decay after. No integration is
# needed because t^e is 0 at t=0 and 1 at t=1 whatever e does — the ends pin
# themselves. The gains and the endpoints are v6's dumb versions; the hue lobe
# is v5's, which is one cos and buys real accuracy. Saturation is neither —
# every power law tried there bled chroma out of the light steps, so it is a
# Hill switch instead (see below).
#
# The light-end fan-out is intact (Mindaro 6.5 / 8.9 / 11.2 against v5's
# 6.5 / 8.9 / 11.0).
# =====================================================================
P_BASE_V7 = 0.84       # exponent away from the dip
DIP_V7 = 0.20          # how far the dip pulls it down at w = 1
DIP_C_V7 = 0.09        # where the dip bottoms out, on the 0–1 scale
# One saturation curve for all nine hues. The palette's own ramps are identical
# through step 500; only Pulse, Pink and Flash peel off in the dark tail — seven
# hand-edited swatches, not a hue effect. A whole-ramp gain chasing them
# desaturated the light and mid steps, which were already exact, so it is gone.
#
# The curve is a switch, not a slide. A power law starts falling at t = 0 and
# falls fastest there, so every light step paid for the dark end's desaturation:
# 100/200/300 came out at S 92/87/83 where the palette holds a flat 100/100/90.
# A Hill function moves all of that motion into a window around its knee:
#
#     S(t) = 100 − 30·(t/c)^n / (1 + (t/c)^n),   c = 1/3, n = 6
#
# (t/c)^n is negligible below the knee and saturates above it, so S sits on 100
# through the lights, swings 100 → 70 across the mids, and settles on the floor
# for the dark tail — the three regimes the palette actually has. n sets how
# sharply it changes its mind; the ends need no clamp because the ratio is
# bounded by construction.
S_DROP_V7 = 30.0       # 100 at the light end down to a floor of 70
S_KNEE_V7 = 1.0/3.0    # half the drop is spent here — the 0–1 scale, so step 333
S_ORDER_V7 = 6.0       # how abruptly the hold gives way to the floor

# The UI families (Pulse, Flash, Pink) keep falling where the rest hold their
# floor: the palette runs them 70 → 60 → 39 → 26 across 500–800 while every other
# ramp sits flat on 70. They get the same one-line switch as everything else —
# same Hill, three different numbers. The drop is deep enough to run past the
# floor, the knee sits late (t = 0.8 instead of 1/3) and the order is gentle, so
# it is one smooth fall rather than a hold and a second step down.
#
# The drop is weighted by hue, on the same cos² lobe shape the lightness bend
# uses, because the three ramps do not peel off together: the palette keeps
# Flash's 600 and 700 up on S 70 while Pulse and Pink have already fallen to 60
# and 39. The lobe sits on Flash's own hue and takes 40% off the drop there. It
# is asymmetric, like the lightness lobe: it reaches out to hue 150 on the green
# side, so Pulse sits inside it, and dies at 342 on the warm side so Pink keeps
# very nearly the whole drop.
#
# One curve cannot both hold the palette's mids and reach its dark tail — the
# palette turns twice (once near step 250, once near 550) and a Hill turns once.
# The knee is set so the fall is already under way at 300, and pulling it in from
# 2/3 to 5/8 (with the drop rescaled to keep the dark end where it was) takes a
# couple of points out of the middle without moving either end — the only knob
# that does that on a curve with one knee.
SEMANTIC_V7 = ("Pulse", "Flash", "Pink")
GROUPS_V7 = [
    ("Brand & Labels", ["Brand", "Core", "Mindaro", "Mint", "Yellow", "Edge"]),
    ("UI (Semantic)",  list(SEMANTIC_V7)),
]
S_UI_DROP_V7 = 106.0     # deep enough that the ramp runs past the shared floor
S_UI_KNEE_V7 = 0.625     # the knee — early enough that the fall is under way by 300
S_UI_ORDER_V7 = 3.0      # gentle, so it is one slope and not a staircase
S_UI_HUE_V7 = 32.0       # centre of the lobe — Flash's hue, where the drop is cut
S_UI_LOBE_UP_V7 = 118.0  # 32° → 150° (yellow, green) — gone only at 150
S_UI_LOBE_DN_V7 = 50.0   # 32° → 342° (red, magenta)
S_UI_CUT_V7 = 0.4        # how much of the drop the lobe takes away at its centre

def S_hue_gain_v7(H):
    """1 outside the lobe, 0.6 at its centre — the same cos² shape as w(H), and
    asymmetric for the same reason: it reaches out to 150 on the green side."""
    delta = (H - S_UI_HUE_V7 + 180.0) % 360.0 - 180.0
    span = S_UI_LOBE_UP_V7 if delta >= 0.0 else S_UI_LOBE_DN_V7
    d = abs(delta) / span
    if d >= 1.0:
        return 1.0
    return 1.0 - S_UI_CUT_V7 * math.cos(math.pi / 2 * d) ** 2

def S_v7(t, ui_hue=None):
    """Full chroma until the knee, then one swing down to the floor.

    Pass a hue for the UI ramp: same switch, a deeper hue-weighted drop and a
    later, gentler knee, so it keeps going where the shared one levels off."""
    if ui_hue is None:
        r = (t / S_KNEE_V7) ** S_ORDER_V7
        return clamp(100.0 - S_DROP_V7 * r / (1.0 + r), 0.0, 100.0)
    u = (t / S_UI_KNEE_V7) ** S_UI_ORDER_V7
    return clamp(100.0 - S_UI_DROP_V7 * S_hue_gain_v7(ui_hue) * u / (1.0 + u),
                 0.0, 100.0)

def dip_shape_v7(t):
    """A bell in log t with no ln in sight: 0 at t=0, 1 at t=c, fat tail after."""
    return 4.0 * DIP_C_V7 * t / ((t + DIP_C_V7) ** 2)

def L_exponent_v7(t, H=None):
    """The exponent at this point on the scale — v5's bent q, done by hand."""
    if H is None:
        return P_BASE_V7
    return P_BASE_V7 - DIP_V7 * hue_light_weight_v5(H) * dip_shape_v7(t)

def L_v7(t, H=None):
    return 100.0 if t <= 0.0 else 100.0 - 100.0 * (t ** L_exponent_v7(t, H))

# The light ramp never reaches neutral grey: the palette holds ~2 points of tint
# at its darkest step, where L/10 alone has already fallen to 0.85. The slope was
# right (least squares gives L/10.11) — only the floor was missing, so the offset
# goes in and nothing else moves.
NEUTRAL_S_FLOOR_V7 = 0.7

def neutral_S_v7(theme, L):
    return L / 10.0 + NEUTRAL_S_FLOOR_V7 if theme == "light" else 22.0 - L / 9.0

def sample_hex_v7(kind, hue, theme, t, semantic=False):
    L = L_v7(t, hue if kind == "chromatic" else None)
    if kind == "chromatic":
        return hsl2hex(hue, S_v7(t, hue if semantic else None), L)
    return hsl2hex(hue, neutral_S_v7(theme, L), L)

def gradient_css_v7(kind, hue, theme, n=40, semantic=False):
    stops = [f"{sample_hex_v7(kind, hue, theme, i/(n-1), semantic)} {round(100*i/(n-1), 2)}%"
             for i in range(n)]
    return f"linear-gradient(to bottom, {', '.join(stops)})"

def curve_samples_v7(kind="chromatic", theme="both", H=None, n=64, semantic=False):
    ts, scales, Ls, Ss = [], [], [], []
    use_H = H if kind == "chromatic" else None
    for i in range(n):
        t = i / (n - 1)
        L = L_v7(t, use_H)
        ts.append(round(t, 4)); scales.append(round(100.0*t, 2)); Ls.append(round(L, 3))
        Ss.append(round(S_v7(t, use_H if semantic else None) if kind == "chromatic"
                        else neutral_S_v7(theme, L), 3))
    return {"t": ts, "scale": scales, "L": Ls, "S": Ss}

def build_family_v7(name, kind, theme, hue, step_keys, orig_map, v5_rows, group=""):
    rows, positions = [], []
    H_for_L = hue if kind == "chromatic" else None
    sem = name in SEMANTIC_V7
    dip = round(DIP_V7 * (hue_light_weight_v5(hue) if kind == "chromatic" else 0.0), 4)
    v5_by_step = {r["step"]: r["hsl"] for r in v5_rows}
    d5 = []
    for key in step_keys:
        t = step_to_t_v5(key)
        positions.append(t)
        gen = sample_hex_v7(kind, hue, theme, t, sem)
        L = L_v7(t, H_for_L)
        S = (S_v7(t, hue if sem else None) if kind == "chromatic"
             else neutral_S_v7(theme, L))
        ref = v5_by_step.get(key)
        e5 = round(dE(ref, gen), 2) if ref else None
        if e5 is not None:
            d5.append(e5)
        rows.append({
            "step": key,
            **entry(orig_map.get(key), gen, {
                "t": round(t, 4),
                "scale": round(100.0 * t, 2),
                "L": round(L, 2),
                "S": round(S, 2),
                "H": round(hue, 1),
                "e": round(L_exponent_v7(t, H_for_L), 3),
                "dE_v5": e5,
            }),
        })
    return {
        "name": name, "kind": kind, "theme": theme, "hue": hue,
        "group": group, "semantic": sem,
        "s_gain": round(S_hue_gain_v7(hue), 3) if sem else None,
        "dip": dip, "rows": rows,
        "d5": round(sum(d5)/len(d5), 2) if d5 else None,
        "gradient": gradient_css_v7(kind, hue, theme, semantic=sem),
        "positions": [round(t, 4) for t in positions],
    }

def build_v7(v5):
    v5_fam = {(f["name"], f["theme"]): f["rows"] for f in v5["families"]}
    out = {
        "id": "v7", "label": "v7", "families": [], "hues": HUES,
        "formula": {
            "L0": 100.0, "L_range": 100.0,
            "p_base": P_BASE_V7, "dip": DIP_V7, "dip_c": DIP_C_V7,
            "L_peak_hue": L_PEAK_HUE_V5, "lobe_up": LOBE_UP_V5, "lobe_dn": LOBE_DN_V5,
            "S_drop": S_DROP_V7, "S_knee": round(S_KNEE_V7, 6),
            "S_order": S_ORDER_V7,
            "S_ui_drop": S_UI_DROP_V7, "S_ui_knee": round(S_UI_KNEE_V7, 6),
            "S_ui_order": S_UI_ORDER_V7, "semantic": list(SEMANTIC_V7),
            "S_ui_hue": S_UI_HUE_V7,
            "S_ui_lobe_up": S_UI_LOBE_UP_V7, "S_ui_lobe_dn": S_UI_LOBE_DN_V7,
            "S_ui_cut": S_UI_CUT_V7,
            "groups": [{"name": g, "families": f} for g, f in GROUPS_V7],
            "steps": CHROMATIC_STEPS_V5,
        },
        "meta": {
            "b": "b(t) = 4c\u00b7t/(t+c)\u00b2 with c = 0.09  \u2014 a log-t bell, no ln",
            "e": "e(t) = 0.84 \u2212 0.20\u00b7w(H)\u00b7b(t)",
            "L": "L(t,H) = 100 \u2212 100\u00b7t^e(t)   \u2014 the ends pin themselves",
            "S": "S(t) = 100 \u2212 30\u00b7(3t)\u2076/(1 + (3t)\u2076)  \u2014 one curve, every hue",
            "S_ui": "UI: S(t) = 100 \u2212 106\u00b7g(H)\u00b7u/(1 + u), u = (1.6t)\u00b3",
            "S_g": "g(H) = 1 \u2212 0.4\u00b7cos\u00b2(\u00bd\u03c0\u00b7d), d = |H\u221232| / (118 up, 50 down)",
            "w": "w(H) as in v5 \u2014 cos\u00b2 lobe, 145\u00b0 up and 90\u00b0 down",
        },
        "curves": {
            "chromatic": curve_samples_v7("chromatic", H=190),
            "chromatic_semantic": curve_samples_v7("chromatic", H=110, semantic=True),
            "chromatic_L_peak": curve_samples_v7("chromatic", H=L_PEAK_HUE_V5),
            "neutral_light": curve_samples_v7("neutral", "light"),
            "neutral_dark": curve_samples_v7("neutral", "dark"),
        },
    }

    for group, fams in GROUPS_V7:
        for fam in fams:
            keys = [str(s) for s in CHROMATIC_STEPS_V5]
            out["families"].append(build_family_v7(
                fam, "chromatic", "both", HUES[fam], keys, P["light"][fam],
                v5_fam[(fam, "both")], group))

    for theme in ("light", "dark"):
        steps = P[theme]["Neutral"]
        keys = merge_steps_v5([k for k in steps if k not in ("White", "Black")])
        out["families"].append(build_family_v7(
            "Neutral", "neutral", theme, NEUTRAL_H[theme], keys, steps,
            v5_fam[("Neutral", theme)], "Neutrals"))

    rows = [r for f in out["families"] for r in f["rows"]]
    d5 = [r["dE_v5"] for r in rows if r["dE_v5"] is not None]
    dc = [r["dE_hsl"] for r in rows if r["dE_hsl"] is not None]
    out["vs_v5"] = {"mean": round(sum(d5)/len(d5), 2), "max": round(max(d5), 2)}
    out["vs_current"] = {"mean": round(sum(dc)/len(dc), 2), "max": round(max(dc), 2)}
    return out

# ---------- assemble ----------
def main():
    v5 = build_v5()
    out = {
        "v1": build_v1(), "v2": build_v2(), "v3": build_v3(),
        "v4": build_v4(), "v5": v5, "v6": build_v6(v5), "v7": build_v7(v5),
        "default": "v5",
    }
    json.dump(out, open('data/generated.json', 'w'), indent=1)

    for ver_id in ("v1", "v2", "v3", "v4", "v5", "v6", "v7"):
        ver = out[ver_id]
        print(f"\n=== {ver_id} ===")
        print(f"{'family':<12}{'theme':<7}{'mean ΔE':>9}{'max':>7}   worst step")
        for f in ver["families"]:
            dh = [r["dE_hsl"] for r in f["rows"] if r["dE_hsl"] is not None]
            compared = [r for r in f["rows"] if r["dE_hsl"] is not None]
            w = max(compared, key=lambda r: r["dE_hsl"]) if compared else f["rows"][0]
            extra = ""
            if ver_id in ("v4", "v5", "v6") and f["kind"] == "chromatic":
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
        if ver_id == "v7":
            print("vs v5:", out["v7"]["vs_v5"], " vs current:", out["v7"]["vs_current"])
            print("dip per family:", {f["name"]: f["dip"] for f in out["v7"]["families"]
                                      if f["kind"] == "chromatic"})
            print("drift per family:", {f["name"]+"\u00b7"+f["theme"]: f["d5"]
                                        for f in out["v7"]["families"]})
            print("e(t) at hue 75:", {s: round(L_exponent_v7(s/1000, 75), 3)
                                      for s in (25, 50, 100, 200, 300, 500, 900)})
        if ver_id == "v6":
            print("vs v5:", out["v6"]["vs_v5"], " vs current:", out["v6"]["vs_current"],
                  " (v5 vs current mean:",
                  round(sum(r["dE_hsl"] for f in v5["families"] for r in f["rows"]
                            if r["dE_hsl"] is not None) /
                        len([r for f in v5["families"] for r in f["rows"]
                             if r["dE_hsl"] is not None]), 2), ")")
            print("p per family:", {f["name"]: f["p"] for f in out["v6"]["families"]
                                    if f["kind"] == "chromatic"})
            print("drift per family:", {f["name"]+"·"+f["theme"]: f["d5"]
                                        for f in out["v6"]["families"]})
        if ver_id == "v5":
            print("S gains:", out["v5"]["s_gain"])
            print("S power p:", out["v5"]["s_power"])
            brand = next(f for f in out["v5"]["families"] if f["name"] == "Brand")
            print("Brand samples:", [(r["step"], r["scale"], r["L"], r["S"], r.get("missing")) for r in brand["rows"]])
            print(f"bend Δ: Mindaro={bend_delta_v5(75):.3f} Yellow={bend_delta_v5(50):.3f} "
                  f"Pulse={bend_delta_v5(110):.3f} Flash={bend_delta_v5(32):.3f} "
                  f"Edge={bend_delta_v5(10):.3f} Mint={bend_delta_v5(145):.3f} "
                  f"Pink={bend_delta_v5(350):.3f} Brand={bend_delta_v5(190):.3f} "
                  f"Core={bend_delta_v5(250):.3f}")
            print(f"q(Mindaro) at 25/55/200/900 = {L_q_v5(.025,75):.2f}/{L_q_v5(.055,75):.2f}/"
                  f"{L_q_v5(.2,75):.2f}/{L_q_v5(.9,75):.2f}  · L(1)={L_v5(1.0,75):.2f}")
            print(f"L_Mindaro(0.1)={L_v5(0.1,75):.1f}  L_Brand(0.1)={L_v5(0.1,190):.1f}  "
                  f"L_Mindaro(0.5)={L_v5(0.5,75):.1f}  L_Brand(0.5)={L_v5(0.5,190):.1f}")
            print(f"S_unit(0)={S_unit_v5(0):.3f}  S_unit(1/3)={S_unit_v5(1/3):.3f}  "
                  f"S_unit(0.5)={S_unit_v5(0.5):.3f}  S_unit(1)={S_unit_v5(1):.3f}")

if __name__ == "__main__":
    main()
