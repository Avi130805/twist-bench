# The benchmark prompt

Two prompts, generated not hand-written. The key table comes straight out of
`engine/keymap.py` and the paths come from wherever this repo actually lives, so
neither can drift from the simulation and a published copy carries nobody else's
absolute paths.

**The brief** — the task itself: puzzle, key table, protocol, rules. This is what
the model reads to know what to do.

```bash
python tools/gen_prompt.py --cube 4x4 --out briefs/task_4x4.md
```

**The runner** — the harness wrapper: hard tool restrictions, how to invoke the
CLI, where the brief lives. This is what you paste into a subagent spawn or an
eval harness.

```bash
python tools/gen_prompt.py --cube 4x4 --runner --brief briefs/task_4x4.md
```

Flags: `--budget N`, `--guided` (adds a method hint — easier variant),
`--discover` (drops the key table; the model has to call `keymap` itself),
`--tool "..."` (override how your harness names the CLI).

They are separate on purpose. The brief is addressed to a puzzle solver; the
runner is addressed to a *coding agent* that has to be talked out of behaving
like one. See "The model will try to write a solver" below.

## What the prompt has to establish

Six things, in this order. Anything less and you are measuring the wrong thing.

1. **The puzzle**, concretely — including that a 4x4/6x6 has no fixed centres and
   can hit parity, and that the mirror cube is solved by *shape*, not colour.
2. **What solved means.** For colour cubes it is "six uniform faces, any colour on
   any face". Saying "restore it to the original colour scheme" would be wrong —
   the sim doesn't require that and the model would waste moves.
3. **That screenshots are the only source of truth.** Models will otherwise assume
   a text state dump exists and hallucinate one.
4. **The key table and the direction convention.** Clockwise-looking-at-the-face is
   not optional detail; get this wrong and every algorithm the model knows inverts.
5. **The observe → predict → act → verify loop**, with an explicit instruction to
   re-read the cube when the result surprises it. This is the single biggest
   determinant of score.
6. **The rules** — move budget, no `truth`, no `space`/`backspace`/`z`.

## Deliberate choices

**Give the key table.** Without it you are benchmarking key-discovery, not cube
solving. If you *want* that harder variant, use `--discover`; the model then has to
call `keymap` and read the layout for itself.

**Don't give the method.** The default prompt says nothing about cross/F2L or
reduction. That is the capability under test. `--guided` adds a one-line method
hint if you want an easier tier to compare against.

**Cap sequence length at 1–8 moves.** Long blind sequences are the classic failure:
a model runs a 20-move algorithm from a misread state and destroys work it can't
recover. Forcing short bursts with a verification screenshot between them makes
errors cheap and recoverable, and it makes the transcript legible when you review
what went wrong.

**Tell it re-reading is cheap.** Models under-photograph. Screenshots and camera
moves cost nothing and don't count against the budget — say so explicitly.

**Name the anti-cheat.** `truth` returns the full sticker layout. It is there so
*you* can score runs. If the model can reach the CLI at all it can reach that
subcommand, so the prompt forbids it by name — and your harness should not expose
it in the first place. See "Sealing the channel" below.

## Suggested move budgets

| Cube | Budget | Roughly |
|---|---|---|
| 2x2 | 80 | ~4x an ordinary human solve |
| 3x3 | 200 | ~4x |
| 4x4 | 450 | ~4x |
| 5x5 | 700 | ~4x |
| 6x6 | 1000 | ~4x |
| mirror | 200 | same as 3x3 |

Generous on purpose. A tight budget measures algorithmic efficiency; a loose one
measures whether the model can solve the thing at all, which is the interesting
question first.

## The model will try to write a solver

This is the failure mode that will bite you first, and it is not malice — it is a
capable coding agent doing the obviously sensible engineering thing. Point one at
this task with an unrestricted toolbelt and within a minute it is writing
`solver.py`, importing `kociemba`, or building a scratch file that tracks the cube
state for it. Every one of those answers a *different* question than "can you
solve this by looking at it".

The generated prompt forbids all of it explicitly, but a prompt rule is a request,
not a control. **Restrict the tools as well.** The model needs exactly two
capabilities:

- run `agent_cli.py` (and nothing else)
- read the PNG files that come back

No `Write`, no `Edit`, no reading source files, no package installs.

If you drive this with Claude Code, `.claude/agents/cube-solver.md` in this repo
is a ready-made restricted agent: `tools: Bash, Read` plus a system prompt that
states the rules. It is what produced the run in [RESULTS.md](RESULTS.md). Note
that Claude Code registers agent definitions at session start, so you need to
restart it after cloning before the agent type appears.

A shell is still a shell, so treat any of this as a fence rather than a wall and
verify afterwards.

### Detecting it afterwards

- **Answer-key access is logged.** The `state`/`truth` command writes `TRUTH —
  answer key read` into the on-screen activity trace and the status line, so it is
  visible live and unmissable in a recording.
- **Check for created files** in the working directory and scratch space.
- **Read the move history** (`truth` after the run). A human-style solve shows
  recognisable structure — layer by layer, repeated algorithms, the occasional
  correction. A machine solve is ~20 moves of unstructured optimum with no
  wasted motion and no retries. They do not look alike.

## Sealing the channel

The prompt asks the model not to use `truth`, `space`, `backspace` or `z`. If you
want that enforced rather than requested, expose only these subcommands to the
model and drop the rest:

```
look   shot   press   camera   status
```

`status` still reports `solved`, which is the model's own stopping signal. If you
want to withhold even that, take `status` out too and score the run yourself from
outside — the model can tell a solved cube from a screenshot anyway.

## Scoring a run

```python
from agent_client import Twist

with Twist() as cb:                 # opens the window if it isn't up
    cb.select("4x4")
    task = cb.scramble(moves=40, seed=1234)   # task["scramble"] replays exactly
    # ... hand the generated prompt + cb.look() images to the model ...
    result = cb.status()
    print(result["solved"], result["move_count"])
```

Record per task: cube, seed, scramble, `solved`, `move_count`, wall clock, number
of screenshots taken. The scramble seed makes any run reproducible — the same seed
on the same cube always produces the same scramble.

## Prompt for a scoring/grader model

If you grade transcripts with a second model rather than with `status`:

```
You are grading an attempt to solve a Rubik's cube from screenshots.
The attempt is solved only if the final screenshot shows every visible face
in a single uniform colour AND the two isometric views together cover all six
faces. Partial credit: count how many of the six faces are uniform.
Do not reward a plausible-sounding explanation over what the image shows.
```

For the mirror cube, replace the criterion with: *"solved only if the final
screenshots show a clean rectangular block with no piece protruding or recessed."*
