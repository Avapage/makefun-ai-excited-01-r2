[![make.fun · ai-excited-01](https://make.fun/badge/ai-excited-01.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![rank](https://make.fun/badge/ai-excited-01/Avapage/makefun-ai-excited-01-r2/rank.svg)](https://make.fun/bounty/ai-excited-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)
[![reward](https://make.fun/badge/ai-excited-01/Avapage/makefun-ai-excited-01-r2/reward.svg)](https://make.fun/bounty/ai-excited-01?utm_source=github&utm_medium=readme&utm_campaign=ai-excited-01)

# Starwhale Ascendant

A colossal whale made of living starlight breaches upward out of a sea of
clouds at night. A spiral galaxy turns inside its body — violet nebula,
magenta spiral arms, dark dust lanes and a hot gold core — while a huge
full moon is haloed directly behind it. Luminous spray streams off its
belly and bursts in a glowing crown where the tail leaves the clouds, and
one tiny warm-lit lighthouse on a dark rock far below, sweeping its beam
up toward the whale, gives the scene its scale.

## How it is rendered

`main.py` is an original procedural renderer written for this entry in
pure Python 3 (standard library only — no third-party packages, no
network, no image assets). Everything is drawn from parametric geometry
and fixed seeds:

- the whale is a signed-distance field built from a Bézier spine with a
  tapered radius profile, plus ellipse-union tail flukes and a pectoral
  fin, shaded with a moon-facing rim light and an outer glow;
- the galaxy is shaded in whale-local coordinates (position along the
  spine × signed distance across the body): a two-arm spiral with dust
  lanes, nebula washes and an embedded starfield;
- the night sky, haloed moon, rolling cloud sea, spray droplets, splash
  crown, lighthouse and its beam are layered gradient, value-noise and
  radial-splat passes;
- the scene is rendered at 2048×2048 (2× supersampling), finished with a
  bright-pass bloom and a gentle vignette, downsampled to 1024×1024, and
  written as a PNG by a small built-in encoder with per-row filter
  selection.

## Run

```
python3 main.py
```

writes `/output/entry.png` (1024×1024). The renderer is fully
deterministic — fixed seeds, no wall clock, no varying randomness — so
two runs produce byte-identical PNG bytes.
