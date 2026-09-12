# Xsolla ramp formulas

Reverse-engineered HSL formulas for the Xsolla colour palette
(Figma: *Redesign Color Palette — Pentagram*).

Four versions ship side by side — switch them from the header dropdown.

## v1 — discrete step ladders

Hue constant; L/S from shared step ladders.

## v2 — continuous functions + lightness ladder

`L(t)`, `S(t)`, `H₀` define a continuous ramp. Named steps still sit on a
hard-coded even lightness ladder.

## v3 — pure curves (no step tables)

Equal-t samples of shared continuous `L(t)` / `S(t)`. S uses a smoothstep
and therefore has flat holds.

## v4 — continuous curves + per-family S gain

No step tables and **no flat S plateaus**. Light end of L is eased up so
early samples stay brighter. Each chromatic family multiplies the saturation
drop by a gain `k_H` fitted to Figma:

```
L(t) = 96 − 81·t^1.35
u(t) = t·(1 + 3t)/4
S(t) = clamp(100 − 30·k_H·u(t), 0, 100)
H(t) = H₀

tᵢ = i/(N−1)
```

Typical gains: majority ≈ 1.25 · Flash ≈ 1.8 · Pulse/Pink ≈ 2.4–2.45 · Mindaro ≈ 1.2.

A diagram above the palettes plots **lightness (red)** and **saturation (blue)**
against gradient progression (with a dashed high-`k` S curve on v4).

## Files

| | |
|---|---|
| `index.html` | built page |
| `template.html` | source (`/*__DATA__*/`, `/*__STAT__*/`) |
| `build.py` | applies v1–v4 → `data/generated.json` |
| `page.py` | injects data into the template |
| `data/palette.json` | Figma values |

```bash
python3 build.py && python3 page.py
```
