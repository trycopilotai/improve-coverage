#!/usr/bin/env python3
"""Record the worked example again and refresh the evidence manifest.

    python3 scripts/record_session.py

The worked example follows the skill's non-interactive mode
by hand, from a shell, on a synthetic repository this script
builds in a throwaway directory. No agent runs. The steps it
shows are: read the inputs a caller would pass, list the
scope from a diff base, measure it, add one test file, and
measure again. The test file is written into this script; an
agent following the skill would write it in Step 3.

The synthetic repository has two commits. The first adds
``shapes.py``, an untouched module ``units.py``, one test,
and ``measure.py``, the repository's coverage command, which
uses the standard library's ``trace`` module. The tag
``base`` marks that commit. The second commit adds a
triangle branch to ``shapes.py``.

The commands are the ones listed in
``evidence/demo-manifest.json``. The transcript is what a
shell would show: each command line, its output, and its
exit status. Nothing is edited: the commands print relative
paths only.

The manifest's hashes of ``SKILL.md``, ``agents/openai.yaml``,
this script and the transcript are then rewritten, with the
date and the interpreter. Run ``make demo`` afterwards to
rebuild the images.

If a command exits non-zero, the script prints the capture,
writes neither file, and exits 1. ``python3
scripts/record_session.py --print`` prints a fresh capture
and writes nothing.

Set ``RECORD_RAW_DIR`` to a directory to also keep a copy of
the capture there.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "demo-manifest.json"

MEASURE = '''\
"""Line coverage of the named files while this directory's tests run.

    python3 measure.py FILE...

The coverage command of this example repository. It runs
every test_*.py file here under the standard library's trace
module, then prints, for each FILE, how many of its
executable lines ran and which did not. A FILE that no test
imports still counts, at 0%. It exits 1 if a test fails.
"""

import dis
import io
import os
import sys
import trace
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))


def executable_lines(path):
    with open(path) as handle:
        code = compile(handle.read(), path, "exec")
    lines = set()
    pending = [code]
    while pending:
        current = pending.pop()
        for _offset, line in dis.findlinestarts(current):
            if line:
                lines.add(line)
        for constant in current.co_consts:
            if hasattr(constant, "co_code"):
                pending.append(constant)
    return lines


def run_tests():
    suite = unittest.defaultTestLoader.discover(HERE, pattern="test_*.py")
    runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
    return runner.run(suite)


def main(names):
    ignored = sorted({sys.prefix, sys.exec_prefix, sys.base_prefix})
    tracer = trace.Trace(count=1, trace=0, ignoredirs=ignored)
    result = tracer.runfunc(run_tests)
    ran = {}
    for (filename, line) in tracer.results().counts:
        ran.setdefault(os.path.realpath(filename), set()).add(line)
    failed = len(result.failures) + len(result.errors)
    print("tests: %d ran, %d failed" % (result.testsRun, failed))
    for name in names:
        path = os.path.realpath(os.path.join(HERE, name))
        lines = executable_lines(path)
        hit = lines & ran.get(path, set())
        text = "%s: %d of %d lines ran (%d%%)" % (
            name,
            len(hit),
            len(lines),
            100 * len(hit) // len(lines),
        )
        missed = sorted(lines - hit)
        if missed:
            text += "; not run: " + ", ".join(str(line) for line in missed)
        print(text)
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
'''

SHAPES_BEFORE = '''\
"""Areas of simple shapes."""


def area(kind, size):
    if kind == "square":
        return size * size
    raise ValueError("unknown shape: " + kind)
'''

SHAPES_AFTER = '''\
"""Areas of simple shapes."""


def area(kind, size):
    if kind == "square":
        return size * size
    if kind == "triangle":
        return size * size / 2
    raise ValueError("unknown shape: " + kind)
'''

UNITS = '''\
"""Unit conversions. No test imports this file."""


def to_metres(feet):
    return feet * 0.3048
'''

TEST_SHAPES = '''\
import unittest

import shapes


class SquareTest(unittest.TestCase):
    def test_square(self):
        self.assertEqual(shapes.area("square", 3), 9)
'''

# The one test file the example adds. It was written by hand
# for this example; in a real run an agent writes it (Step 3).
TEST_TRIANGLE = '''\
import unittest

import shapes


class TriangleTest(unittest.TestCase):
    def test_triangle_is_half_the_square(self):
        self.assertEqual(shapes.area("triangle", 4), 8)

    def test_unknown_shape_is_refused(self):
        with self.assertRaises(ValueError):
            shapes.area("circle", 1)
'''

CALLER_INPUTS = """\
scope: diff base "base", less test files
coverage_cmd: python3 measure.py <files in scope>
target: 100% of lines
commit: no
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repository: Path, environment: dict, *arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Example",
            "-c",
            "user.email=example@example.com",
            *arguments,
        ],
        cwd=str(repository),
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def build_fixture(base: Path, environment: dict) -> Path:
    """The synthetic repository, its caller inputs and the hand-written test."""
    repository = base / "example"
    repository.mkdir()
    write(base / "caller-inputs.txt", CALLER_INPUTS)
    write(base / "hand-written" / "test_triangle.py", TEST_TRIANGLE)
    write(repository / "measure.py", MEASURE)
    write(repository / "shapes.py", SHAPES_BEFORE)
    write(repository / "units.py", UNITS)
    write(repository / "test_shapes.py", TEST_SHAPES)
    git(repository, environment, "init", "-q", "-b", "main")
    git(repository, environment, "add", "-A")
    git(repository, environment, "commit", "-q", "-m", "Start the example")
    git(repository, environment, "tag", "base")
    write(repository / "shapes.py", SHAPES_AFTER)
    git(repository, environment, "commit", "-q", "-am", "Add triangle areas")
    return repository


def capture(commands: list) -> tuple:
    """Run the commands on a fresh fixture; return the transcript and a failure flag."""
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch).resolve()
        bindir = base / "bin"
        bindir.mkdir()
        launcher = bindir / "python3"
        launcher.write_text(
            '#!/bin/sh\nexec %s "$@"\n' % shlex.quote(sys.executable),
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        environment = {
            "PATH": "%s:/usr/bin:/bin" % bindir,
            "HOME": str(base),
            "LC_ALL": "C",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        repository = build_fixture(base, environment)
        lines = []
        failed = False
        for command in commands:
            result = subprocess.run(
                ["sh", "-c", command],
                cwd=str(repository),
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
            )
            lines.append("$ " + command)
            lines.extend(result.stdout.splitlines())
            lines.append("exit status: %d" % result.returncode)
            if result.returncode != 0:
                failed = True
    return "\n".join(lines) + "\n", failed


def main(argv: list) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw, failed = capture(manifest["invocation"]["commands"])
    if "--print" in argv:
        sys.stdout.write(raw)
        return int(failed)

    raw_dir = os.environ.get("RECORD_RAW_DIR")
    if raw_dir:
        Path(raw_dir, "worked-example.source.txt").write_text(raw, encoding="utf-8")

    if failed:
        sys.stdout.write(raw)
        print("a command exited non-zero; nothing written")
        return 1
    transcript = ROOT / manifest["output"]["path"]
    transcript.write_text(raw, encoding="utf-8")

    manifest["date"] = datetime.date.today().isoformat()
    manifest["invocation"]["interpreter"] = "Python " + platform.python_version()
    manifest["skill"]["sha256"] = sha256(ROOT / manifest["skill"]["path"])
    manifest["interface"]["sha256"] = sha256(ROOT / manifest["interface"]["path"])
    for item in manifest["programs"]:
        item["sha256"] = sha256(ROOT / item["path"])
    manifest["output"]["sha256"] = sha256(transcript)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote %s" % transcript.relative_to(ROOT))
    print("wrote %s" % MANIFEST.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
