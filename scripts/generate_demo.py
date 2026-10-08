#!/usr/bin/env python3
"""Generate the terminal demo and its static poster.

Both images are reconstructed from the worked example in
evidence/transcripts/worked-example.txt. Every line of
terminal text they show is copied from that file. They show
commands run by hand from a shell on a synthetic repository,
not an agent running the skill.

    python3 scripts/generate_demo.py            # write both
    python3 scripts/generate_demo.py --check    # compare only

The demo reveals the session one command at a time and loops.
Each step stays on screen until the loop restarts, so a later
frame always contains every earlier one. The poster is the last
frame with no animation, for a reader who asked for reduced
motion.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "worked-example.txt"
DEMO = ROOT / "assets" / "demo.svg"
POSTER = ROOT / "assets" / "poster.svg"
SOURCE_LABEL = (
    "Run by hand, no agent. From evidence/transcripts/worked-example.txt"
)

WIDTH = 1280
HEIGHT = 960
MARGIN_X = 40
FIRST_BASELINE = 96
LINE_HEIGHT = 24
STEP_GAP = 10
FONT_SIZE = 16
# A monospace glyph is about 0.6 em wide. The verifier uses
# the same figure to prove the longest line fits the canvas.
GLYPH_WIDTH = 0.6 * FONT_SIZE
LABEL_FONT_SIZE = 15

BACKGROUND = "#101418"
TEXT = "#f7fbff"
MUTED = "#a7bac5"
GOOD = "#55d6be"
CHROME = ("#ff6b6b", "#ffd166", "#55d6be")

LOOP_SECONDS = 16
# Percent of the loop at which the first and the last step
# appear; the steps between are spaced evenly. Every step
# holds until HOLD_UNTIL, then the loop restarts.
FIRST_REVEAL = 6
LAST_REVEAL = 74
FADE_IN = 4
HOLD_UNTIL = 94

PROMPT = "$ "
EXIT_OK = "exit status: 0"


def steps_from_transcript(transcript: str) -> list[list[str]]:
    """One block per command: its ``$`` line, its output, its exit status.

    Every command must exit with status 0, and the transcript
    must start with a command.
    """
    lines = transcript.splitlines()
    if not lines or not lines[0].startswith(PROMPT):
        raise ValueError("the transcript does not start with a command")
    steps: list[list[str]] = []
    for line in lines:
        if line.startswith(PROMPT):
            steps.append([line])
            continue
        steps[-1].append(line)
    for block in steps:
        if block[-1] != EXIT_OK:
            raise ValueError("a command did not exit with status 0: %s" % block[0])
    return steps


def reveal_points(count: int) -> list[int]:
    """The percent of the loop at which each of ``count`` steps appears."""
    if count == 1:
        return [FIRST_REVEAL]
    span = LAST_REVEAL - FIRST_REVEAL
    return [FIRST_REVEAL + (span * index) // (count - 1) for index in range(count)]


def line_colour(line: str) -> str:
    if line.startswith(PROMPT):
        return TEXT
    if line == EXIT_OK or line.endswith("(100%)"):
        return GOOD
    return MUTED


def text_element(line: str, baseline: int) -> str:
    return (
        '    <text x="%d" y="%d" fill="%s" xml:space="preserve">%s</text>'
        % (MARGIN_X, baseline, line_colour(line), html.escape(line))
    )


def layout(steps: list[list[str]]) -> tuple[list[str], int]:
    """SVG fragments for each step, and the last baseline."""
    fragments: list[str] = []
    baseline = FIRST_BASELINE - LINE_HEIGHT - STEP_GAP
    for index, block in enumerate(steps):
        baseline += STEP_GAP
        fragments.append('    <g class="step-%d">' % (index + 1))
        for line in block:
            baseline += LINE_HEIGHT
            fragments.append("  " + text_element(line, baseline))
        fragments.append("    </g>")
    return fragments, baseline


def animation_css(count: int) -> str:
    rules = []
    points = reveal_points(count)
    for index, reveal in enumerate(points):
        number = index + 1
        rules.append(
            "    .step-%d {\n"
            "      opacity: 0;\n"
            "      animation: reveal-%d %ds infinite;\n"
            "    }" % (number, number, LOOP_SECONDS)
        )
        rules.append(
            "    @keyframes reveal-%d {\n"
            "      0%%, %d%% { opacity: 0; }\n"
            "      %d%%, %d%% { opacity: 1; }\n"
            "      100%% { opacity: 0; }\n"
            "    }" % (number, reveal, reveal + FADE_IN, HOLD_UNTIL)
        )
    selectors = ", ".join(".step-%d" % (i + 1) for i in range(count))
    rules.append(
        "    @media (prefers-reduced-motion: reduce) {\n"
        "      %s {\n"
        "        opacity: 1;\n"
        "        animation: none;\n"
        "      }\n"
        "    }" % selectors
    )
    return "\n".join(rules)


def render(transcript: str, animated: bool) -> str:
    steps = steps_from_transcript(transcript)
    fragments, last_baseline = layout(steps)
    label_baseline = HEIGHT - 28
    if last_baseline + LINE_HEIGHT > label_baseline - LABEL_FONT_SIZE:
        raise ValueError("the session does not fit the canvas")
    if animated:
        title = "Animated worked example of improve-coverage, run by hand"
        style = "  <style>\n%s\n  </style>\n" % animation_css(len(steps))
    else:
        title = "Worked example of improve-coverage, run by hand"
        style = ""
    description = (
        "A terminal shows %d commands run by hand on a synthetic repository: "
        "the caller inputs, the scope from a diff base, a coverage measurement "
        "of shapes.py, one added test file, a second measurement, and git "
        "status. No agent ran the skill." % len(steps)
    )
    chrome = "\n".join(
        '  <circle cx="%d" cy="44" r="9" fill="%s" />' % (40 + 30 * i, colour)
        for i, colour in enumerate(CHROME)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" role="img" aria-labelledby="title description">\n'
        '  <title id="title">%s</title>\n'
        '  <desc id="description">%s</desc>\n'
        "%s"
        '  <rect width="%d" height="%d" rx="24" fill="%s" />\n'
        "%s\n"
        '  <g font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        'font-size="%d">\n'
        "%s\n"
        "  </g>\n"
        '  <text x="%d" y="%d" fill="%s" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        'font-size="%d">%s</text>\n'
        "</svg>\n"
        % (
            WIDTH,
            HEIGHT,
            WIDTH,
            HEIGHT,
            title,
            description,
            style,
            WIDTH,
            HEIGHT,
            BACKGROUND,
            chrome,
            FONT_SIZE,
            "\n".join(fragments),
            MARGIN_X,
            label_baseline,
            MUTED,
            LABEL_FONT_SIZE,
            SOURCE_LABEL,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if either committed image differs from a fresh render",
    )
    arguments = parser.parse_args(argv)
    transcript = TRANSCRIPT.read_text(encoding="utf-8")
    outputs = (
        (DEMO, render(transcript, animated=True)),
        (POSTER, render(transcript, animated=False)),
    )
    if arguments.check:
        stale = [
            path.name
            for path, text in outputs
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            print("stale: %s. Run scripts/generate_demo.py." % ", ".join(stale))
            return 1
        print("demo.svg and poster.svg match the transcript")
        return 0
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("wrote %s" % path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
