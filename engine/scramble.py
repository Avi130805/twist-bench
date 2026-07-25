"""
scramble.py — well-formed random scrambles.

Picking moves uniformly at random produces sequences that partly cancel: `R' R`
is two "moves" that do nothing, `L L` is two moves that are really one. A naive
20-move scramble can be 16 effective moves, which makes the length a lie.

Two rules, both standard practice in cubing:

  1. never turn the same layer twice in a row  (kills R R, R' R, R2 R)
  2. never turn three consecutive moves on the same axis  (kills R L R, which is
     redundant because opposite faces commute)

That is enough for the length to mean what it says.

On saturation
-------------
None of this makes scramble length a difficulty dial. A 3x3 state is at most 20
moves from solved (God's number, half-turn metric) and the overwhelming majority
of random states sit at 17-18. Past roughly 25 well-formed moves the distribution
has converged and more moves change nothing — a 30-move scramble and a 300-move
scramble are the same task. `tools/measure_saturation.py` measures this directly.
"""

AXIS = {"U": 1, "D": 1, "R": 0, "L": 0, "F": 2, "B": 2}
SUFFIXES = ("", "'", "2")

DEFAULT_LENGTH = 300


def _layer(move: str):
    """('R', 2) for '2R2' — the physical layer this move turns."""
    depth = 1
    i = 0
    while i < len(move) and move[i].isdigit():
        i += 1
    if i:
        depth = int(move[:i])
    return move[i], depth


def random_scramble(base_moves, rng, length: int = DEFAULT_LENGTH) -> list:
    """`length` moves with no cancellation, drawn from `base_moves`.

    base_moves are un-suffixed move names for the cube in question, e.g.
    ["U","D","R","L","F","B"] for a 3x3 or the 18 slice moves of a 6x6.
    """
    if not base_moves:
        raise ValueError("no legal moves to scramble with")

    out = []
    prev_layer = None      # (face, depth) of the previous move
    prev_axis = None
    prev2_axis = None

    for _ in range(length):
        for _attempt in range(64):
            base = rng.choice(base_moves)
            face, depth = _layer(base)
            axis = AXIS[face]
            if (face, depth) == prev_layer:
                continue                      # rule 1
            if axis == prev_axis == prev2_axis:
                continue                      # rule 2
            break
        else:
            # Degenerate move set (a cube with one legal layer). Take it anyway
            # rather than spin: correctness of the state is unaffected.
            face, depth, axis = _layer(base)[0], _layer(base)[1], AXIS[_layer(base)[0]]

        out.append(base + rng.choice(SUFFIXES))
        prev_layer = (face, depth)
        prev2_axis, prev_axis = prev_axis, axis

    return out


def count_cancellations(moves) -> int:
    """How many adjacent pairs act on the same layer. Should be 0."""
    return sum(1 for i in range(1, len(moves))
               if _layer(moves[i]) == _layer(moves[i - 1]))
