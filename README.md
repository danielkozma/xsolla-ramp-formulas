# Xsolla ramp formulas

Reverse-engineered HSL formulas for the Xsolla colour palette
(Figma: *Redesign Color Palette — Pentagram*, file `DDMmWPCTdJpmuYZ8IkrlDa`).

Three versions ship side by side — switch them from the header dropdown.

## v1 — discrete step ladders

Hue is constant down each ramp; lightness and saturation follow ladders shared by
every family, so one parameter per family — its hue — regenerates the whole set.

## v2 — continuous functions + lightness ladder

`L(t)`, `S(t)`, `H₀` define a continuous ramp. Named steps are still placed on a
hard-coded even lightness ladder inverted through `L(t)`.

## v3 — pure curves (no step tables)

Hue is fixed per family. Saturation and lightness are continuous functions of
gradient progression `t` only — no per-step lookup tables:

```
L(t) = 96 − 81·t^1.2
S(t) = 100 − 30·smoothstep(0.28, 0.55, t)
H(t) = H₀

tᵢ = i/(N−1)   # named tokens are equal samples, not a ladder
```

A diagram above the palettes plots **lightness (red)** and **saturation (blue)**
against gradient progression.

Each family card shows three columns: Figma · Formula · full continuous Gradient.

## Files

| | |
|---|---|
| `index.html` | the built page — open it directly, no build step needed to view |
| `template.html` | page source; `/*__DATA__*/` and `/*__STAT__*/` are the injection points |
| `build.py` | reads `data/palette.json`, applies v1–v3 formulas, writes `data/generated.json` |
| `page.py` | injects the generated data into the template and writes `index.html` |
| `data/palette.json` | the values as they stand in Figma |

Rebuild after changing a formula:

```bash
python3 build.py && python3 page.py
```
