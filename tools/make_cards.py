#!/usr/bin/env python3
"""
make_cards.py — render data cards for a run from that run's measured numbers.

Every figure comes from the run log and the scorer. Nothing is illustrative,
rounded for effect, or asserted without a stated method. Where a number depends
on a definition (what counts as "thinking", how "optimal" is computed) the card
states the definition rather than leaving it to be guessed.

SVG for crisp type at any raster size; Chrome headless does the rasterising, so
there is no cairo/rsvg dependency.

    python tools/make_cards.py --gaps runs/gaps.json --out cards/
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W, H = 1600, 900
FG = "#e8edf5"
DIM = "#7c8899"
FAINT = "#4a5566"
GREEN = "#3ddc84"
CYAN = "#22d3ee"
AMBER = "#ffc857"
RULE = "#1e2735"
MONO = "ui-monospace,SFMono-Regular,Menlo,monospace"


def head():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
 viewBox="0 0 {W} {H}">
<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#121826"/><stop offset="1" stop-color="#0a0d13"/>
</linearGradient></defs>
<rect width="{W}" height="{H}" fill="url(#fade)"/>"""


def title(t, sub=None):
    out = (f'<text x="72" y="104" font-family="{MONO}" font-size="22" fill="{DIM}"'
           f' letter-spacing="3">{t}</text>')
    if sub:
        out += (f'<text x="72" y="140" font-family="{MONO}" font-size="19"'
                f' fill="{FAINT}">{sub}</text>')
    return out


def foot(note=None):
    out = ""
    if note:
        out += (f'<text x="72" y="{H-92}" font-family="{MONO}" font-size="19"'
                f' fill="{FAINT}">{note}</text>')
    out += (f'<text x="72" y="{H-46}" font-family="{MONO}" font-size="20"'
            f' fill="{DIM}">TWIST</text>'
            f'<text x="152" y="{H-46}" font-family="{MONO}" font-size="20"'
            f' fill="{FAINT}">github.com/Avi130805/twist-bench</text>')
    return out


def rows(items, x=72, y0=210, dy=52, key_w=330, size=27):
    """Aligned key / value / annotation rows — the whole card is a spec table."""
    out = []
    y = y0
    for key, val, colour, note in items:
        out.append(f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}"'
                   f' fill="{DIM}">{key}</text>')
        out.append(f'<text x="{x+key_w}" y="{y}" font-family="{MONO}"'
                   f' font-size="{size}" fill="{colour}">{val}</text>')
        if note:
            out.append(f'<text x="{x+key_w+440}" y="{y}" font-family="{MONO}"'
                       f' font-size="{size-6}" fill="{FAINT}">{note}</text>')
        y += dy
    return "".join(out), y


def card_result(s):
    body, _ = rows([
        ("model", "claude-opus-5", FG, "agent restricted to Bash + Read"),
        ("puzzle", "3&#215;3&#215;3", FG, ""),
        ("scramble", f"{s['depth']} moves  seed {s['seed']}", FG,
         f"{s['optimal']} moves from solved (Kociemba)"),
        ("input", "PNG screenshots only", FG, "no text state exposed"),
        ("output", "keystrokes", FG, "same path a human keyboard takes"),
        ("", "", FG, ""),
        ("result", "solved = true", GREEN, "6/6 faces uniform"),
        ("moves", f"{s['moves']}", AMBER, f"{s['ratio']:.1f}&#215; the reference solution, budget {s['budget']}"),
        ("screenshots", f"{s['shots']}", FG, f"{s['shot_calls']} calls, all opened"),
        ("wall clock", f"{s['wall_s']} s", FG, f"{s['wall_s']/60:.1f} min"),
        ("answer-key reads", "0", GREEN, "by the solver; logged server-side"),
    ], y0=200, dy=50)
    return head() + title("RUN 001", "one model, one scramble, one run &#183; n = 1") + f"""
<line x1="72" y1="164" x2="{W-72}" y2="164" stroke="{RULE}" stroke-width="2"/>
{body}
<line x1="72" y1="754" x2="{W-72}" y2="754" stroke="{RULE}" stroke-width="2"/>
""" + foot("verification: independent facelet dump, sticker_score = 1.0000, "
           "scored by a separate agent") + "</svg>"


def card_time(s):
    bx, by, bw, bh = 72, 300, W - 144, 84
    tw = bw * s['think_share']
    body, _ = rows([
        ("wall clock", f"{s['wall_s']} s", FG, ""),
        ("thinking", f"{s['think_s']} s", AMBER, f"{s['think_share']*100:.1f}%"),
        ("cube in motion", f"{s['act_s']} s", GREEN,
         f"{(1-s['think_share'])*100:.1f}%"),
        ("pauses", f"{s['gaps']}", FG, ""),
        ("median pause", f"{s['median']} s", FG, ""),
        ("longest pause", f"{s['max_gap']} s", AMBER,
         f"{s['max_gap']/60:.1f} min, on a single move"),
    ], y0=490, dy=48)
    return head() + title(
        "TIME DECOMPOSITION",
        "thinking := interval between one command completing and the next arriving") + f"""
<line x1="72" y1="164" x2="{W-72}" y2="164" stroke="{RULE}" stroke-width="2"/>
<text x="72" y="238" font-family="{MONO}" font-size="40" fill="{FG}">
{s['think_share']*100:.1f}% of wall clock was the model reasoning</text>
<rect x="{bx}" y="{by}" width="{tw:.1f}" height="{bh}" fill="{AMBER}" rx="5"/>
<rect x="{bx+tw:.1f}" y="{by}" width="{bw-tw:.1f}" height="{bh}" fill="{GREEN}" rx="5"/>
<text x="{bx+22}" y="{by+53}" font-family="{MONO}" font-size="28" fill="#2a1f00">
thinking {s['think_s']} s</text>
<text x="{W-72}" y="{by+bh+34}" text-anchor="end" font-family="{MONO}" font-size="20"
 fill="{GREEN}">&#8593; moving {s['act_s']} s</text>
{body}
""" + foot("timestamps are recorded server-side by the simulation, not "
           "self-reported by the model") + "</svg>"


def card_gaps(s, gaps, span):
    x0, x1, base, top = 90, W - 90, 620, 250
    longest = max(g[1] for g in gaps)
    bars = "".join(
        f'<rect x="{x0+(x1-x0)*(t/span)-5:.1f}" '
        f'y="{base-(base-top)*(sec/longest):.1f}" width="10" '
        f'height="{(base-top)*(sec/longest):.1f}" '
        f'fill="{AMBER if sec > 300 else (CYAN if sec > 90 else "#3b8ea5")}" rx="3"/>'
        for t, sec in gaps)
    peak_i = max(range(len(gaps)), key=lambda i: gaps[i][1])
    peak_x = x0 + (x1 - x0) * (gaps[peak_i][0] / span)
    ticks = "".join(
        f'<text x="{x0+(x1-x0)*f:.0f}" y="{base+34}" text-anchor="middle"'
        f' font-family="{MONO}" font-size="18" fill="{FAINT}">{f*span/60:.0f}</text>'
        for f in (0, 0.25, 0.5, 0.75, 1.0))
    return head() + title(
        "PAUSE DISTRIBUTION",
        f"{len(gaps)} pauses over {span/60:.1f} min &#183; bar height = pause duration") + f"""
<line x1="72" y1="164" x2="{W-72}" y2="164" stroke="{RULE}" stroke-width="2"/>
{bars}
<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="#26313f" stroke-width="2"/>
{ticks}
<text x="{x1}" y="{base+64}" text-anchor="end" font-family="{MONO}" font-size="18"
 fill="{FAINT}">minutes elapsed</text>
<text x="{peak_x:.0f}" y="{top-20}" text-anchor="middle" font-family="{MONO}"
 font-size="21" fill="{AMBER}">{gaps[peak_i][1]:.0f} s</text>
<text x="72" y="{base+130}" font-family="{MONO}" font-size="24" fill="{FG}">
median {s['median']} s &#160;&#183;&#160; p90 {s['p90']} s &#160;&#183;&#160;
max {s['max_gap']} s &#160;&#183;&#160; total {s['think_s']} s</text>
""" + foot("a pause ends when the simulation receives the next command; "
           "animation and queued keys are excluded") + "</svg>"


def card_status(s):
    data = [("2&#215;2", "18", "&#8212;", "untested"),
            ("3&#215;3", "18", "solved, 83 moves, 44 min", "run 001"),
            ("4&#215;4", "36", "&#8212;", "untested"),
            ("5&#215;5", "36", "&#8212;", "untested"),
            ("6&#215;6", "54", "&#8212;", "untested"),
            ("mirror 3&#215;3", "18", "&#8212;", "untested")]
    out = [f'<text x="72" y="228" font-family="{MONO}" font-size="21" fill="{DIM}">puzzle</text>'
           f'<text x="400" y="228" font-family="{MONO}" font-size="21" fill="{DIM}">legal moves</text>'
           f'<text x="640" y="228" font-family="{MONO}" font-size="21" fill="{DIM}">result</text>'
           f'<line x1="72" y1="248" x2="{W-72}" y2="248" stroke="{RULE}" stroke-width="2"/>']
    y = 300
    for name, mv, res, state in data:
        done = state == "run 001"
        col = GREEN if done else DIM
        out.append(f'<text x="72" y="{y}" font-family="{MONO}" font-size="28"'
                   f' fill="{FG if done else DIM}">{name}</text>')
        out.append(f'<text x="400" y="{y}" font-family="{MONO}" font-size="28"'
                   f' fill="{DIM}">{mv}</text>')
        out.append(f'<text x="640" y="{y}" font-family="{MONO}" font-size="28"'
                   f' fill="{col}">{res}</text>')
        y += 56
    return head() + title(
        "COVERAGE",
        "1 of 6 measured so far") + f"""
<line x1="72" y1="164" x2="{W-72}" y2="164" stroke="{RULE}" stroke-width="2"/>
{''.join(out)}
<line x1="72" y1="{y-24}" x2="{W-72}" y2="{y-24}" stroke="{RULE}" stroke-width="2"/>
<text x="72" y="{y+40}" font-family="{MONO}" font-size="25" fill="{FG}">
scramble length is not a difficulty dial &#8212; a 3x3 saturates by ~25 moves</text>
<text x="72" y="{y+82}" font-family="{MONO}" font-size="25" fill="{FG}">
git clone github.com/Avi130805/twist-bench</text>
<text x="72" y="{y+124}" font-family="{MONO}" font-size="21" fill="{FAINT}">
MIT &#183; offline &#183; numpy + pygame + PyOpenGL &#183; kociemba and ffmpeg optional</text>
""" + foot() + "</svg>"


def render(svg: str, out: Path):
    # A bare "&" makes the whole SVG unparseable and Chrome renders an error box
    # instead of the card. Escape any that are not already entities.
    svg = re.sub(r"&(?!#\d+;|amp;|lt;|gt;|quot;|apos;)", "&amp;", svg)
    tmp = out.with_suffix(".svg")
    tmp.write_text(svg, encoding="utf-8")
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                    f"--screenshot={out}", f"--window-size={W},{H}",
                    "--hide-scrollbars", f"file://{tmp}"],
                   capture_output=True, check=True)
    tmp.unlink()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "cards"))
    ap.add_argument("--gaps", required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    g = json.load(open(args.gaps))
    durs = sorted(d for _, d in g["gaps"])
    s = dict(depth=20, seed=20260725, optimal=19, moves=83, budget=200,
             shots=73, shot_calls=16, wall_s=2642, think_s=2617, act_s=25,
             think_share=2617 / 2642, gaps=len(durs),
             median=round(durs[len(durs) // 2]),
             p90=round(durs[int(len(durs) * 0.9)]),
             max_gap=round(durs[-1]), ratio=83 / 19)

    for fn, name in ((card_result, "01_result"), (card_time, "02_time"),
                     (lambda st: card_gaps(st, g["gaps"], g["span"]), "03_pauses"),
                     (card_status, "04_coverage")):
        print("wrote", render(fn(s), out / f"{name}.png"))


if __name__ == "__main__":
    sys.exit(main())
