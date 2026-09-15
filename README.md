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

Playgrounds probe the live functions — one for the chromatic hues (with L and S
plotted beside it) and one pair for the neutrals, light and dark, each showing
its perceptual lift.

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
r(t) = (3t)⁶                   # 1 at the knee, t = 1/3
S(t) = 100 − 30·r/(1 + r)      # one curve, every hue
```

**Saturation is a switch, not a slide.** A power law starts falling at `t = 0`
and falls fastest there, so the light steps paid for the dark end: 100 / 200 /
300 came out at S 92 / 87 / 83 where the palette holds a flat 100 / 100 / 90.
The Hill form puts all the motion in a window around its knee — `(t/c)ⁿ` is
negligible below it and saturates above it — so S sits on 100 through the
lights, swings 100 → 70 across the mids, and settles on the floor for the dark
tail. Those are the three regimes the palette actually has, and `n` is the one
knob for how sharply it changes its mind. No clamp: the ratio is bounded by
construction.

| step | 25 | 50 | 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 |
|---|---|---|---|---|---|---|---|---|---|---|
| palette S | 100 | 100 | 100 | 100 | 90 | 80 | 70 | 70 | 70 | 71 |
| `t^(2/3)` | 97 | 95 | 92 | 87 | 83 | 80 | 76 | 73 | 70 | 68 |
| Hill | 100 | 100 | 100 | 99 | 90 | 78 | 72 | 71 | 70 | 70 |

**No per-family saturation gain — one group curve instead.** The palette's own
ramps are identical through step 500; only Pulse, Flash and Pink peel off, and
only in the dark tail, where the palette runs them 70 / 60 / 39 / 26 across
500–800 while every other ramp holds flat on 70. A whole-ramp gain chasing that
desaturated the light and mid steps, which were already exact. The UI families
get the same one-line switch as everything else, with three numbers changed:

```
dₛ(H) = |H − 32| / (28 up, 50 down)     # 1 outside the lobe, 0.6 at its centre
g(H) = 1 − 0.4·cos²(½π·dₛ)  if dₛ<1 else 1
u(t) = (1.6t)³
S(t) = 100 − 106·g(H)·u/(1 + u)         # UI families
```

The drop is deep enough to run past the shared floor, the knee sits later than
the shared one (t = 5/8 against 1/3) and the order is gentle, so it reads as one
slope instead of a hold and a step down.

**The drop is weighted by hue**, on the same cos² lobe shape the lightness bend
uses, because the three ramps do not peel off together: the palette keeps
Flash's 600 and 700 up on S 70 while Pulse and Pink have already fallen to 60
and 39. The lobe sits on Flash's own hue and takes 40% off the drop there, and
it is asymmetric for the same reason the lightness lobe is: it reaches out to
hue 150 on the green side, so Pulse sits inside it at g 0.90, and dies at 342 on
the warm side so Pink keeps almost all of the drop at 0.98. Drops come out 95
for Pulse, 64 for Flash, 104 for Pink.

**One curve cannot do both ends.** The palette's UI ramp turns twice — once near
step 250 and once near 550 — and a Hill turns once. The knee is set so the fall is
already under way at 300, and it is also the one knob that lowers the middle of
a one-knee curve without moving either end: pulling it in from 2/3 to 5/8, with
the drop rescaled from 114 to 106 to hold the dark end, takes about two points
out of steps 400–600 and leaves 100 / 200 and 800 where they were. The ramp runs
S 100 / 97 / 89 / 78 / 64 / 50 / 38 / 28 against the palette's 100 / 100 / 90 /
80 / 70 / 60 / 39 / 26 — on the numbers at the ends, a little under through the
middle, which is the way round that reads correctly. A two-term version fitted
every step and drew a visibly two-stage curve; the single curve is the one that
ships. Hue stays the only per-family parameter and the group the only
other one.

The three UI ramps go from mean ΔE 2.81 uncorrected to **2.31**, and the whole
palette from 1.84 to **1.71**.

No integration is needed because the ends pin themselves whatever the
exponent does — what v5 proves, v7 gets for free. It fits the current palette
better than v5 does (mean ΔE **1.71** against 2.11); the drift from v5's own
output is 1.06, almost all of it the saturation change in the mids. The
fan-out survives: Mindaro 6.5 / 8.9 / 11.2 L against v5's 6.5 / 8.9 / 11.0,
where v6's flat cut gives 4.5 / 7.5.

**The light neutral keeps a floor of tint.**

```
neutral·lt  hsl(  75, L/10 + 0.7,  L )
neutral·dk  hsl( 190, 22 − L/9,    L )
```

`L/10` on its own sat under the palette at **every** step of the light ramp —
by 0.4 S at the top and 1.1 at the bottom, mean 0.68 — which reads as a formula
column visibly greyer than the current one through the mids. The slope was not
the problem: least squares on the Figma swatches gives `L/10.11`, so 1/10 is
right and only the floor was missing. `L/10` forces S → 0 as L → 0, but the
palette's light neutrals still carry ~2 points of tint at step 900. Adding the
offset takes the light ramp from mean ΔE 0.92 to **0.86** (300: 1.29 → 1.00,
400: 1.30 → 1.08, 600: 0.31 → 0.16). Step 800 is the one that gets worse,
2.08 → 2.35, and it is not a saturation miss — the formula is too *light*
there. The dark ramp was already sitting slightly above the palette's chroma,
so `22 − L/9` is unchanged.

**Neutral lift is quoted on the palette cards, not just the playground.** The
tinted neutrals still get measured against the grey of the same nominal L: the
light ramp peaks at **+1.66** OKLab points (step 400), the dark at **+2.17**
(step 500), against 24.3 for Mindaro at the same step. That is the evidence for
giving neutrals no correction — and it survives the floor, which buys 0.19 of
lift against an order of magnitude of headroom. The two neutral cards carry the
number in their header (`peak lift`) and in every swatch tooltip, off the same
`perceptualLift()` the neutral playground plots — the card and the playground
cannot disagree. The chromatic cards do not quote it; there the dip already
answers for it.

Measured cost of each simplification on its own, against v5's output:

| dropped | mean ΔE |
|---|---|
| per-family gain dropped | — |
| neutral S rounded (dark) | 0.00 |
| hue lobe cos² → triangle | 0.30 |
| endpoints 99.5/98.5 → 100/100 | 0.50 |
| **bend → flat cut** | **1.07** |

Only the last one is expensive, and it is the one that costs the fan-out — so
v7 keeps a localised correction and drops everything else.

## Files

| | |
|---|---|
| `index.html` | built page — v7 only, cards grouped Brand & Labels · UI (Semantic) · Neutrals, a playground under each |
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
