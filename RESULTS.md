# Results

One run so far. Everything below is measured by the simulation and scored by a
separate agent, not self-reported by the model under test.

## Run 001 — 3x3, claude-opus-5

| | |
|---|---|
| model | `claude-opus-5`, agent restricted to Bash + Read |
| puzzle | 3x3x3 |
| scramble | 20 moves, seed 20260725 |
| distance at start | 19 moves (Kociemba two-phase, near-optimal) |
| **result** | **solved = true** |
| moves | 83 (4.4x the 19-move reference solution, budget 200) |
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

**n = 1.** One model, one scramble, one puzzle of six. Not enough to rank
anything.

**This run used the old scramble generator**, which picked moves uniformly at
random and so produced cancellations — `R' R` twice, and an `L L`. The 20-move
sequence was around 16 effective moves. It does not undermine the result: the
resulting state measured 19 moves from solved, against a saturation value of
~20.8 for a randomised 3x3, so the cube was effectively fully scrambled either
way. But the *sequence* was not 20 clean moves and the record should say so.
Scrambles are now generated with no cancellation and default to 300 moves.

**Scramble length is not a difficulty dial.** A 3x3 state is at most 20 moves
from solved, and the distance of a random state saturates near 21 by about the
25-move mark. Measured with `tools/measure_saturation.py`:

| scramble moves | 1 | 5 | 8 | 12 | 20 | 30 | 100 | 300 |
|---|---|---|---|---|---|---|---|---|
| mean distance | 1.0 | 6.1 | 10.0 | 17.7 | 20.9 | 20.7 | 20.7 | 20.8 |

So sweeping scramble length only separates models in the shallow regime, roughly
1–12 moves, and that regime tests something different — short-horizon search
rather than method. Anywhere past ~25 moves, every scramble is the same task.
The default is 300 because being unambiguously randomised is the only thing the
number needs to buy.

Reproduce this exact task with:

```bash
python tools/new_task.py --cube 3x3 --moves 20 --seed 20260725
```

(the state will differ from the original run, which predates the generator fix)
