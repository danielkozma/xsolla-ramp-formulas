# Xsolla ramp formulas

Reverse-engineered HSL formulas for the Xsolla colour palette
(Figma: *Redesign Color Palette — Pentagram*).

The published page ships **v7 only**. Earlier versions v1–v6 are kept in
`backup-all-versions/` (the page exactly as it was, with the version dropdown)
and `build.py` still computes all seven — v7's numbers are quoted against v5.

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

## v5 — full 0→100 domain + bent lightness exponent (default)

Functions and the gradient span **0→100**. Named tokens map as
`scale = step/10` (so 25 → 2.5, 800 → 80, 900 → 90) — interior samples,
not ends. Chromatic **900** is formula-only (Figma has no swatch).

Saturation is a raised-cosine that stays flat at both ends but is
**front-loaded**: `g(t) = t^p` with `p = log(½)/log(⅓)` so half the unit
drop is done by `t = 1/3`.

Lightness is a power law whose **exponent is bent by hue** rather than scaled by
it. The bend is the derivative of a Gaussian in `ln t`, so its area is zero: it
steepens the exponent before `t_c` and relaxes it by the same amount after, which
fixes both ends of every ramp and lands the curvature on the light steps, where
25 / 50 / 100 / 200 were too close together.

```
d(H) = |H − 75| / (145° up, 90° down)   # 0 at hue 75, 1 at 220 / 345
w(H) = cos²(½π·d)  if d < 1 else 0
Δ(H) = 0.50·w(H)
G(x) = exp(−½·((x − ln 0.055)/1.15)²)
q(t) = 0.83 + Δ·G′(ln t)                # the local exponent
L(t,H) = 99.5 − 98.5·t^0.83·exp(Δ·[G(ln t) − G(0)])

q    = log(1/2) / log(1/3) ≈ 0.631
u(t) = (1 − cos(π·t^q))/2
S(t) = clamp(100 − 30·k_H·u(t), 0, 100)
H(t) = H₀

scale = step/10
t     = scale/100
```

Neutrals carry no correction: their perceptual lift (how much lighter a tinted
step reads than a grey of the same nominal L) peaks near 2 OKLab points against
roughly 24 across the chromatic ramps, so there is nothing to cancel.

Typical gains: majority ≈ 1.25 · Flash ≈ 1.65 · Pulse/Pink ≈ 2.0 / 1.95 ·
Mindaro ≈ 1.3.

Playgrounds probe the live functions — one for the chromatic hues (with the
correction curve and the exponent beside it) and one pair for the neutrals, light
and dark, each showing its perceptual lift.

## v6 — the dumb version

An experiment: every function replaced by the stupidest thing that could work.

```
w(H) = max(0, 1 − |H − 75|/120)     # a triangle, not a cosine lobe
p(H) = 0.82 − 0.10·w(H)             # a flat cut, not a bend
L(t,H) = 100 − 100·t^p(H)
S(t) = clamp(100 − 30·k·t^(2/3), 0, 100)
k = 2 for Flash / Pulse / Pink, else 1.25
neutral S = L/10 (light), 22 − L/9 (dark)
```

Mean ΔE 1.01 from v5's output, and it fits the current palette just as closely
(2.07 against v5's 2.11) from about a fifth of the machinery. What it loses is
the light-end fan-out — Mindaro's 25→50 gap comes back as 4.5 L against v5's 6.5.
Replacing the power law itself with straight lines is the one simplification that
breaks: mean ΔE 2.1, worst swatch 7.1.

## v7 — the middle ground

v5's intent without v5's calculus. The exponent still dips where the light
steps are, but along a rational bell instead of a Gaussian derivative, and it
is slid straight into the power law rather than integrated:

```
b(t) = 4c·t/(t + c)²          # c = 0.09 — a bell in log t, no ln
e(t) = 0.84 − 0.20·w(H)·b(t)  # w(H) is v5's cos² lobe, unchanged
L(t,H) = 100 − 100·t^e(t)     # t^e is 0 at t=0 and 1 at t=1 for any e
S(t) = clamp(100 − 37.5·t^(2/3), 0, 100)   # one curve, every hue
```

**No per-family saturation gain.** The palette's own ramps are identical
through step 500; only Pulse, Pink and Flash peel off, and only in the dark
tail — seven hand-edited swatches, not a hue effect. A whole-ramp gain chasing
them desaturated the light and mid steps, which were already exact. Dropping
it improves the fit (mean ΔE 1.99 → 1.88) and leaves hue as the single
per-family parameter, so the hue playground reproduces every card exactly.

No integration is needed because the ends pin themselves whatever the
exponent does — what v5 proves, v7 gets for free. Mean ΔE **0.59** from v5's
output with no swatch past 1.43, and it fits the current palette marginally
better. The fan-out survives: Mindaro 6.5 / 8.9 / 11.2 L against v5's
6.5 / 8.9 / 11.0, where v6's flat cut gives 4.5 / 7.5.

Measured cost of each simplification on its own, against v5's output:

| dropped | mean ΔE |
|---|---|
| per-family gain dropped | — |
| neutral S rounded | 0.00 |
| hue lobe cos² → triangle | 0.30 |
| S raised cosine → `t^(2/3)` | 0.44 |
| endpoints 99.5/98.5 → 100/100 | 0.50 |
| **bend → flat cut** | **1.07** |

Only the last one is expensive, and it is the one that costs the fan-out — so
v7 keeps a localised correction and drops everything else.

## Files

| | |
|---|---|
| `index.html` | built page — v7 only |
| `template.html` | source (`/*__DATA__*/`, `/*__MEANV5__*/`) |
| `build.py` | applies v1–v7 → `data/generated.json` |
| `page.py` | injects v7 into the template |
| `data/palette.json` | Figma values |
| `middleware.js` | password gate (see below) |
| `backup-all-versions/` | the previous page, all seven versions, unmodified |

```bash
python3 build.py && python3 page.py
```

## Password

The whole site sits behind a single shared password, enforced by
`middleware.js` (Vercel Routing Middleware) before anything static is served —
the page, `data/`, and `fonts/` alike.

Set it as an environment variable on the Vercel project:

| | |
|---|---|
| Name | `SITE_PASSWORD` |
| Where | Vercel → **xsolla-ramp-formulas** → Settings → Environment Variables |
| Environments | Production, Preview, Development |

or from the CLI:

```bash
vercel env add SITE_PASSWORD production
```

Redeploy after changing it. Until it is set, every route serves the login
screen with a note saying so.

The password is never sent over the network: the login page hashes it in the
browser (salted SHA-256) and stores the hash in the `xcf_gate` cookie, which
the middleware compares against a hash of `SITE_PASSWORD`. Changing
`SITE_PASSWORD` invalidates every existing cookie. The cookie lasts 30 days.

This is a shared-link gate, not per-user auth — anyone with the password gets in.

To run it locally:

```bash
SITE_PASSWORD=whatever vercel dev
```
