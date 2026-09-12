# Xsolla ramp formulas

Reverse-engineered HSL formulas for the Xsolla colour palette
(Figma: *Redesign Color Palette — Pentagram*, file `DDMmWPCTdJpmuYZ8IkrlDa`).

Two versions ship side by side — switch them from the header dropdown.

## v1 — discrete step ladders

Hue is constant down each ramp; lightness and saturation follow ladders shared by
every family, so one parameter per family — its hue — regenerates the whole set.

```
L(step) = 96                       if step = 25
        = 95 − step/10             if step ≤ 800
        = 15 − (step − 800)/20     below 800

S(step) = clamp(120 − step/10, 70, 100)

chromatic   hsl( H,   S(step),          L(step) )
neutral·lt  hsl( 75,  L/10,             L )
neutral·dk  hsl( 190, 11 + (100−L)/9,   L )
greyscale   hsl( 0,   0%,               L )
```

109 of 137 ramp swatches regenerate within ΔE < 1.

## v2 — continuous gradient functions

A single parameter `t ∈ [0, 1]` defines the full ramp. Hue, saturation and
lightness each have their own function, fitted to the majority Figma pattern:

```
L(t) = 96 − 81·t
S(t) = clamp(100 − 120·max(0, t − ⅓), 70, 100)
H(t) = H₀

chromatic   hsl( H₀, S(t), L(t) )
neutral·lt  hsl( 75,  L(t)/10,            L(t) )
neutral·dk  hsl( 190, 11+(100−L(t))/9,    L(t) )
greyscale   hsl( 0,   0%,                 L(t) )
```

Named steps (25, 50, 100, …) are **not** at equal `t`. Their positions are
solved so OKLab lightness is equally spaced on the greyscale `L(t)` curve —
one shared table for every family. Drift from Figma is larger by design: the
continuous system is the source of truth.

Each family card shows three columns: Figma · Formula · full continuous Gradient.

## Files

| | |
|---|---|
| `index.html` | the built page — open it directly, no build step needed to view |
| `template.html` | page source; `/*__DATA__*/` and `/*__STAT__*/` are the injection points |
| `build.py` | reads `data/palette.json`, applies v1 + v2 formulas, writes `data/generated.json` |
| `page.py` | injects the generated data into the template and writes `index.html` |
| `data/palette.json` | the values as they stand in Figma |

Rebuild after changing a formula:

```bash
python3 build.py && python3 page.py
```

Styling follows the Xsolla Digital Language dashboard
(Figma `DjKP20nZbMAfwXwddlCOSt`, frame `2789:7057`): Pilat for display,
Aktiv Grotesk for UI, and the frame's own colour and radius tokens.
