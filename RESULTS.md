# Results

One run so far. Everything below is measured by the simulation and scored by a
separate agent, not self-reported by the model under test.

## Run 001 — 3x3, claude-opus-5

| | |
|---|---|
| model | `claude-opus-5`, agent restricted to Bash + Read |
| puzzle | 3x3x3 |
| scramble | depth 20, seed 20260725 |
| optimal solution | 19 moves (Kociemba) |
| **result** | **solved = true** |
| moves | 83 (4.4x optimal, budget 200) |
| screenshots | 73 PNGs across 16 calls |
| wall clock | 2642 s (44.0 min) |
| thinking | 2617 s (99.1%) |
| cube in motion | 25 s (0.9%) |
| pauses | 28 — median 37 s, p90 248 s, max 659 s |
| answer-key reads by solver | 0 |
| solver code written | none |

Verification: independent facelet dump, 6/6 faces uniform, `sticker_score` 1.0000,
`distance` 0. Scored with `tools/score_run.py`.

### Notes

**The last layer dominated the run.** Pauses stayed under a minute for the first
~30 minutes while the model worked layer by layer. Then a single 11-minute pause
at the 33-minute mark. By its own account it spent that time tracing the Sune
algorithm by hand to work out its permutation, found the permutation it needed
happened to match, and applied it in one shot.

**It abandoned the isometric views almost immediately.** After the first `look`
it switched to flat single-face shots (`shot --views front back left right top
bottom`) and never reasoned from an isometric again until the final check. Its
stated reason: foreshortened faces made grid assignment unreliable, and per-face
lighting made the same colour look different across faces. Colour discrimination
itself was never the problem — face orientation conventions were.

**It re-derived state from scratch every time** rather than carrying a remembered
board forward, re-photographing all six faces after each algorithm. It predicted
specific sticker changes before each press and checked them after, and reported
no mismatches across all ten press batches.

### Caveats

n = 1. One model, one scramble depth, one run, on one puzzle of six. This is not
enough to rank anything. The useful experiment is a scramble-depth sweep
(1, 2, 3, 5, 8, 12, 20) across several models — that produces a curve, and a curve
is what tells you where a model actually breaks.

Reproduce this exact task with:

```bash
python tools/new_task.py --cube 3x3 --depth 20 --seed 20260725
```
