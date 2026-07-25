# TWIST

**T**wisty-puzzle **W**orld-state **I**nference & **S**equential **T**urning —
a benchmark for one question:

> Can a model solve a Rubik's cube it can only *look* at?

Not a text puzzle. A live 3D cube. The model gets screenshots and sends
keystrokes, and nothing else passes between them.

Six cubes in one window — 2x2, 3x3, 4x4, 5x5, 6x6 and a 3x3 silver mirror cube —
switchable with a button click. Every cube is driven by one keyboard layout, and
a model drives it through **that same keyboard layout** over a loopback socket.
The model's only inputs are screenshots; its only outputs are keystrokes.

Nothing here touches the network beyond `127.0.0.1`, and no asset is fetched at
runtime.

**[Results so far](RESULTS.md)** — one run: `claude-opus-5` solved a 20-move 3x3
scramble in 83 moves and 44 minutes, of which 99.1% was thinking. Five of the six
puzzles are still untested.

```
TWIST/
  app.py               the simulation (pygame + PyOpenGL window)
  agent_bridge.py      loopback JSON-lines server the app polls each frame
  agent_client.py      Python client -> import this in a harness
  agent_cli.py         shell client  -> drop this into a tool-using agent loop
  example_agent.py     end-to-end smoke test of the whole channel
  engine/              cube wrappers, key tables, mirror cube, logging, recording
  engine/vendor/       the cube engine, vendored unmodified
  tools/new_task.py    arm one graded task  <- start here
  tools/gen_prompt.py  emit the prompt for a cube (brief / runner / standalone)
  tools/score_run.py   score a finished run; --selftest checks against Kociemba
  tools/gen_keymap.py  regenerate KEYMAP.md
  tools/make_cards.py  render data cards from a run's measured numbers
  .claude/agents/      restricted solver agent definition (Claude Code)
  KEYMAP.md            full key guide (generated from engine/keymap.py)
  PROMPT.md            how to prompt the model being benchmarked
  RESULTS.md           measured runs
  shots/ runs/ videos/ screenshots, run logs, recordings (gitignored)
```

## Install

```bash
git clone https://github.com/Avi130805/twist-bench && cd twist-bench
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

Three dependencies: numpy, pygame, PyOpenGL. `kociemba` is optional (scoring
only) and `ffmpeg` is optional (recording only). The cube engine is vendored in
`engine/vendor/`, so there is nothing else to fetch — see the README there.

## Running it

You don't have to start anything by hand. **Any client call opens the window if
it isn't already up**, so an agent can never find itself talking to nothing:

```bash
python3 agent_cli.py ensure --cube 4x4 --pace 0.2
```

`ensure` is also implicit — `status`, `look`, `press` and the rest all launch the
simulation first if the port is dead. The window is started detached, so it
survives the agent's shell exiting, and if it ever dies mid-run the client
relaunches and retries once. `agent_cli.py` needs only the stdlib, so it works
under any python; it finds the repo's own `.venv` to run the app.

To open it manually (or to just play with it yourself):

```bash
python app.py
```

Flags: `--cube 4x4`, `--seed 42` (reproducible scrambles), `--pace 0.25` (pause
between agent moves so a human can follow along), `--port 8181`,
`--no-bridge` (human-only), `--no-guide` (hide the overlay).

Smoke-test the whole channel:

```bash
python example_agent.py
```

`agent_cli.py` needs only the stdlib, so `python3 agent_cli.py ...` works with any
interpreter; the app itself needs the dependencies above, which the launcher
locates in `.venv/` (or falls back to the interpreter running it).

## Watching the agent work

The window renders continuously at 60 fps and every agent move animates on
screen, so a solve is watchable in real time. The panel on the left is a live
trace of what the agent is doing:

- a status dot — **AGENT ACTIVE** (green, acted in the last 3 s), **AGENT
  CONNECTED** (blue, attached but idle), or **WAITING FOR AGENT** (grey)
- the last dozen actions, each showing the move and the keystroke that caused it
  (`R'  shift+r`), newest at the bottom, amber for agent and blue for human
- a command counter in the corner

The bottom bar shows the cube, solved state, and `move_count` — the model's
solution length, which resets to zero on each scramble.

If the agent bursts through moves faster than you can follow, start the app with
`--pace 0.25` (or `ensure --pace 0.25`) to insert a pause between agent moves.
It has no effect on the cube, only on playback speed.

## How it is put together

Little about the cube mechanics is new. The move engine and renderer come from an
earlier 6x6 cube project of mine and are vendored verbatim in `engine/vendor/`;
the mirror-cube geometry is vendored the same way in `engine/mirror_state.py`.
Everything in `engine/` outside those files is the wrapper that turns them into a
benchmark: size retargeting, the two cube families behind one interface, the key
tables, the agent channel, run logging and recording.

The vendored files are deliberately unmodified. See `engine/vendor/README.md` for
why that matters.

### How 2x2..6x6 come out of a 6x6-only engine

`engine/vendor/utils.py` hardcodes `CUBE_SIZE = 6`, but every function reads that
constant from its module globals at call time. `engine/sizing.activate(n)`
re-binds the attribute on `utils`, `cube_state` and `cube_renderer` (plus the
renderer's derived `N`/`OFF`), which retargets the whole engine at size `n`
without forking it. One size is live at a time, which is all a single window
needs. Verified: random scrambles round-trip to solved on all five sizes, and
`tools/score_run.py --selftest` checks the 3x3 move engine against Kociemba.

Slice depths per cube are `1 .. n//2` from each of the six faces. That covers
every layer on even cubes, and on odd cubes the one uncovered middle slice
differs only by a whole-cube rotation, which never changes solvedness.

### The mirror cube

A real mirror cube is a 3x3 mechanism whose cut planes are asymmetric: each
piece keeps its own box dimensions as it travels, so a scrambled cube is lumpy
and a solved one is a clean rectangular block. `engine/mirror_state.py` models
exactly that, and "solved" means every piece is back in its home position **and**
orientation. There are no colours to read — the model has to solve it by shape.

## The AI channel

The app polls a loopback socket every frame. Commands block until the render
loop has actually executed them, so a screenshot taken right after a keypress
always shows a settled cube, never a half-finished animation.

### Shell (drop straight into a tool loop)

```bash
python agent_cli.py status                       # cube, solved flag, move count
python agent_cli.py keymap                       # live key layout for this cube
python agent_cli.py select 5x5
python agent_cli.py scramble --moves 30 --seed 7
python agent_cli.py press r shift+u alt+f        # keys, exactly as a human types
python agent_cli.py move R "U'" F2               # same thing in cube notation
python agent_cli.py look                         # two isometric PNGs -> all 6 faces
python agent_cli.py shot --views top front right
python agent_cli.py camera --view top
```

Each subcommand prints one JSON object and exits non-zero on failure.

### Python

```python
from agent_client import Twist

with Twist() as cb:
    cb.select("4x4")
    cb.scramble(seed=7)
    images = cb.look()          # -> two PNG paths, show these to the model
    cb.press("shift+r", "u", "alt+f")
    print(cb.status()["solved"])
```

### Commands

| Command | Notes |
|---|---|
| `ensure` (client-side) | open the window if it is not running; implicit on every call |
| `status` / `ping` | cube, size, solved, move count, camera, legal moves |
| `keymap` | key layout for the cube currently on screen |
| `keys` | `{"keys": ["r", "shift+u"]}` — the primary interface |
| `moves` | `{"moves": ["R", "U'"]}` — sugar, translated to keystrokes |
| `select` | `2x2 3x3 4x4 5x5 6x6 mirror` |
| `scramble` | optional `moves`, optional `seed` |
| `reset` / `undo` | back to solved / step back one move |
| `camera` | `view` (`iso iso_back front back left right top bottom`) or explicit `yaw`/`pitch`/`zoom` |
| `pace` | minimum seconds between agent moves; omit the value to read it |
| `screenshot` | `views`, `tag`, `hud` — returns PNG paths |
| `state` | ground-truth sticker dump — **for scoring, not for the model** |

`move_count` counts moves made *since the scramble*, so it is the model's
solution length. Scrambling resets it to zero.

## Recording a run

```bash
python app.py --cube 3x3 --pace 0.3 --record videos/run.mp4
```

The app pipes its own frames to ffmpeg at **two different rates**: fast while the
cube is turning, slow while the model is thinking. Played back at a constant
frame rate, the thinking gaps compress by the ratio between them (24 fps vs 2 fps
by default, so 12x) while the clock burned into the HUD keeps showing true
elapsed time. The result is watchable without ever misrepresenting how long it
took. Tune with `--record-fps` and `--record-idle-fps`.

Every run also writes `runs/<timestamp>_<cube>.jsonl` — one JSON object per
command, move, screenshot and thinking pause, with wall-clock and run-relative
timestamps. That is what `tools/score_run.py` folds into its timing block, and
what you would drive an external editor from.

Close the window, `python3 agent_cli.py stop`, or send it a signal — all three
finalise the mp4 and the log.

## Scoring

```bash
python tools/score_run.py            # scores the live cube
python tools/score_run.py --selftest # verify against Kociemba
```

Pass/fail is a poor metric here — on a task this hard nearly everything scores
zero and you learn nothing about which model came closest. So the scorer reports
a gradient:

| Metric | Meaning |
|---|---|
| `solved` | the headline |
| `faces_uniform` | 0–6, moves early and often |
| `sticker_score` | 0–1, stickers matching their face's modal colour |
| `distance` | **3x3 only:** optimal solution length from here, via Kociemba |
| `distance_reduced` | distance at scramble minus distance now — negative means thrashing |

`distance` is the one that matters. A model that flails for 60 moves and leaves
the cube 20 moves from solved scored nothing; one that got it to 8 clearly did
real work. The scorer also flags the run void if the answer key was read more
than once (the one read being the scorer itself).

`--selftest` scrambles the cube, solves it with Kociemba, and replays the
solution through the real keypress path — proving the facelet mapping and the
move engine agree with an independent implementation.

## Suggested experimental design

Do not run everything at scramble depth 20 — you will get a column of zeros.
Sweep the **scramble depth** instead and find where each model breaks:

```bash
for d in 1 2 3 5 8 12 20; do
  python3 agent_cli.py scramble --moves $d --seed 1000
  # ... run the model, then score ...
done
```

A curve of "solve rate vs scramble depth", one line per model, is both a more
honest measurement and a far more interesting chart than a pass/fail table. The
cube-size axis (2x2 → 6x6) and the mirror cube give you two more difficulty
dimensions on top.

## Using it as a benchmark

**Arm the task first.** Handing a model the prompt is not enough on its own: the
model's first command will happily autostart the simulation, and a fresh
simulation holds a *solved* cube — so it reports "already solved" and the run
silently measures nothing.

```bash
python3 tools/new_task.py --cube 3x3 --depth 20 --seed 31337 --pace 0.3
```

That opens the window, selects the cube, scrambles it, and prints the task record
(keep the scramble — it is the answer key). Three independent guards stop an
unarmed run from being mistaken for a real one:

- `status` exposes `task_armed`
- the generated prompt tells the model to stop and report if it is false
- `tools/score_run.py` marks such a run `VOID` rather than scoring it

Then:

1. Generate the prompt: `python tools/gen_prompt.py --cube 3x3 --standalone`.
   See [PROMPT.md](PROMPT.md) for what it has to establish and why.
2. Give the model **only** that prompt and the images the CLI returns.
3. Let it issue `press` commands. Cap the turn count or the move count.
4. Score with `tools/score_run.py`.

Keep `state` (and the `scramble` list) out of the model's context — those are the
answer key. If a harness needs a hard wall, run the model against `agent_cli.py`
with only the `press`, `look`, `shot`, `camera` and `status` subcommands exposed.

## Portability notes

Some pygame builds ship without SDL_ttf or SDL_image. On those, `pygame.font`
raises on import and `pygame.image.save` cannot write PNG — which would cost you
the HUD and the screenshots, i.e. the entire visual channel. TWIST does not
depend on either:

- `engine/textfont.py` renders text through the `pygame._freetype` extension,
  falling back to `pygame.font` automatically when that one is healthy.
- `engine/pngwrite.py` encodes screenshots with nothing but `zlib`.

So a stock `pip install pygame` is enough regardless of how it was built. This
was found the hard way on the development machine, where both were missing.
