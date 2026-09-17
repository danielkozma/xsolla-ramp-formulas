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

Playgrounds probe the live functions — one for the chromatic hues and one pair
for the neutrals, light and dark, each with L and S plotted beside it.

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

**Neutral lift is quoted in the swatch tooltips.** The tinted neutrals are
measured against the grey of the same nominal L: the light ramp peaks at
**+1.66** OKLab points (step 400), the dark at **+2.17** (step 500), against
24.3 for Mindaro at the same step. That is the evidence for giving neutrals no
correction — and it survives the floor, which buys 0.19 of lift against an order
of magnitude of headroom. The number rides in every neutral swatch tooltip, off
the same `perceptualLift()` the playground uses. Neither the card headers nor
the plots carry it: there is one scale on a plot, 0–100, and two lines on it.

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

## Adjusted hue correction — brand colours

The app bar's right-hand switch, **Current / Adjusted**, picks the hue weight
used for the brand colours: the Brand & Labels cards, the brand playground, the
formula panel and the brand palette on the Partner Customisation screen. The UI
(Semantic) families and the neutrals keep the current curve either way.
Adjusted is the default; the choice is kept in `localStorage` (`xcf.corr`).

The current lobe only ever darkens, so the blues it leaves alone read far too
dark — worst in the mids and darks, where hue 250 sits 10–14 OKLab points under
grey. Adjusted replaces the lobe with one smooth curve round the whole wheel,
and lets its negative part lift the **dark** end.

The curve passes through four points — each a peak or a trough — and every
stretch between two neighbours is a half-cosine, which is flat at both ends, so
the joins have no corners:

```
points: (75, 1) · (245, −0.4) · (290, −0.05) · (359, −0.1)
x    = (H − H₀) / (H₁ − H₀)                       # between neighbours H₀ → H₁
w(H) = w₁ + (w₀ − w₁)·(1 + cos(π·x)) / 2
e(t)   = 0.84 − 0.20·w·b(t)                  if w ≥ 0   # the light-end dip, as before
L(t,H) = 100 − 100·t^0.84·(1 + 0.7·w·u(t)) if w < 0   # the dark-end lift
u(t)   = t·(1 − t⁶)                                      # 0 at both ends
```

It dips the light end around 75, lifts hardest at 245, nearly lets go at 290
and lifts a little again at 359.

**The lift takes a share off the darkness instead of bending the exponent.**
The first versions raised the exponent by `λ·|w|·t²`, then `t⁴`. Because
`t^e` is pinned to black at t = 1, a lift strong enough for the darks either
lifted the middle just as hard (`t²`) or squeezed it into a near-flat plateau
(`t⁴`). Multiplying the darkness by `1 + λ·w·u(t)` has no pinned end to fight.
`u` is ~0 on the lights and grows into the darks. A plain `u = t` left the
lifted ramp stopping at L 28 instead of black, so `u = t·(1 − t⁶)`, which hands
the share back just past step 900, lets every ramp still run from 100 to 0. The
ramp keeps falling everywhere as long as `λ·|w|` stays under about 0.93; the
sidebar refuses anything above 0.9. The only steep stretch is the last
sliver past 900, where the lifted ramp drops to black about three times as
fast as the plain one. With the same points, Core (250):

| step | 300 | 400 | 500 | 600 | 700 | 800 | 850 | 900 |
|---|---|---|---|---|---|---|---|---|
| no lift | 64 | 54 | 44 | 35 | 26 | 17 | 13 | 8 |
| exponent, `t²` | 74 | 71 | 67 | 63 | 57 | 47 | 39 | 30 |
| exponent, `t⁴/0.64` | 65 | 59 | 55 | 53 | 51 | 47 | 42 | 35 |
| darkness × `(1 + 0.7·w·t)` | 67 | 59 | 52 | 45 | 40 | 35 | 33 | 31 |
| darkness × `(1 + 0.7·w·t·(1 − t⁶))` | 67 | 59 | 52 | 45 | 38 | 30 | 25 | 19 |

Mean ΔE against Figma, current → adjusted: Brand 0.92 → 1.62, Core 0.92 →
4.69, Edge 1.29 → 1.18, Mindaro 3.12 → 3.11, Mint 1.82 → 1.73, Yellow
2.61 → 2.28. Brand (w −0.07) and Edge (w −0.04) take a small dark-end lift;
the Figma ramps carry none.

### Editing the curve

Both tabs share a sidebar (on Xsolla Palettes it sticks under the app bar while
the palettes scroll). Its **Adjusted correction** block has a hue and a weight
field for each of the four points, plus **Lift strength**. Edits apply as you
type, once every field is valid (hue 0–359, no two points on the same hue,
weight −1 to 1, lift 0–2, and lift × the strongest negative weight at most 0.9). The fields are disabled while the switch is on
Current.

An edit redraws everything that shows the brand curve: the Brand & Labels
cards (recomputed in the browser, ΔE included, and identical to the built
cards at the defaults), the formula panel, the brand playground and the
Partner Customisation screen. Edits are kept in `localStorage` (`xcf.adj2` — the lift changed scale, so values saved under the old key are ignored).
**Reset** goes back to the values built into the page, and **Copy values**
copies `ADJ_KNOTS_V7` / `ADJ_LIFT_V7` lines to paste into `build.py`, so the
built default can be updated with `python3 build.py && python3 page.py`.

The Brand and Neutral hue sliders stay on Partner Customisation only.

## Partner Customisation — the palette on a real screen

The app bar carries a two-way switch: **Xsolla Palettes** is the page above,
**Partner Customisation** puts the formulas on a real checkout (Figma:
*Xsolla Buttons & Fields*, node 55:12895). The choice is kept in `localStorage`
(`xcf.mode`), and Xsolla Palettes is the default. The pen tool that used to sit
here is kept in `backup-v8-pen-tool/`.

The view is one viewport tall: hue controls on the left, the screen centred on
a black canvas on the right. The screen is **not responsive** — it is laid out
at its Figma size, 1004 × 837, and when the canvas is smaller than that (less a
32px gutter) the whole frame is scaled down as one picture.

Every colour in the frame that comes from the **dark neutral** or **brand**
palette is a CSS variable computed in the browser from the v7 functions; every
other colour (white, black, Xsolla Gold yellow, the icon tile `#253536`, the
Klarna pink, card logos) stays the hex it was drawn in.

```
brand   hsl( Hb, S(t),            L(t, Hb) )    # the shared Hill and the bent power law
neutral hsl( Hn, 22 − L/9,        L(t) )        # the dark neutral, unbent
```

| used on screen | steps |
|---|---|
| Brand | 100 · 200 · 300 · 400 · 500 · 700 |
| Dark neutral | 25 · 50 · 100 · 400 · 700 · 800 · 850 · 900 |

The Figma semantic tokens that carry alpha are rebuilt from the same steps:
`content/primary` = N50, `content/tertiary` = N50 at 58%, `border/secondary` =
B100 at 15%, `overlay/mono` = B100 at 6%. Single-colour icons are drawn as CSS
masks so they take their colour from those variables.

Two sliders, **Brand hue** and **Neutral hue**, both open on 190°. Under each is
the live ramp, with a dot on the steps the screen paints with. Under them,
**Move both hues together** (on by default, kept in `localStorage` as
`xcf.link`) links the sliders: dragging either one moves the other by the same
amount, wrapping round the wheel, so the gap between the two hues is kept. The hues are kept
in `localStorage` (`xcf.partner`); **Reset to Xsolla** puts both back on 190°.
At 190° the screen is the formula's Xsolla palette, not the Figma hexes — N900
comes out `#11191A` against the drawn `#141D1F`.

Assets exported from the Figma frame live in `assets/partner/`; the display face
is Pilat Wide Bold, served from `fonts/pilat/pilat_wide_bold.woff2`.

## Files

| | |
|---|---|
| `index.html` | built page — v7 only, cards grouped Brand & Labels · UI (Semantic) · Neutrals, a playground under each, Xsolla Palettes / Partner Customisation switch and Current / Adjusted correction switch in the app bar |
| `template.html` | source (`/*__DATA__*/`, `/*__MEANV5__*/`) |
| `build.py` | applies v1–v7 → `data/generated.json` |
| `page.py` | injects v7 into the template |
| `data/palette.json` | Figma values |
| `middleware.js` | password gate (see below) |
| `assets/partner/` | icons, logos and images from the Figma checkout frame |
| `backup-all-versions/` | the previous page, all seven versions, unmodified |
| `backup-v8-pen-tool/` | the page with the Math / Pen tool switch, before Partner Customisation |

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
