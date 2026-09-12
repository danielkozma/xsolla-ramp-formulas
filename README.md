# Xsolla ramp formulas

Reverse-engineered HSL formulas for the Xsolla colour palette
(Figma: *Redesign Color Palette — Pentagram*, file `DDMmWPCTdJpmuYZ8IkrlDa`).

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

109 of 137 ramp swatches regenerate within ΔE < 1. The page lists every swatch
that moves further than that.

## Files

| | |
|---|---|
| `index.html` | the built page — open it directly, no build step needed to view |
| `template.html` | page source; `/*__DATA__*/` and `/*__STAT__*/` are the injection points |
| `build.py` | reads `data/palette.json`, applies the formulas, writes `data/generated.json` |
| `page.py` | injects the generated data into the template and writes `index.html` |
| `data/palette.json` | the values as they stand in Figma |

Rebuild after changing a formula:

```bash
python3 build.py && python3 page.py
```

Styling follows the Xsolla Digital Language dashboard
(Figma `DjKP20nZbMAfwXwddlCOSt`, frame `2789:7057`): Pilat for display,
Aktiv Grotesk for UI, and the frame's own colour and radius tokens.
