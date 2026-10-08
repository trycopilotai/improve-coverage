#!/usr/bin/env python3
"""The repository suite.

Facts this repository states in more than one place are
pinned here where a script can compare them: the name and
version, the claim and the transcript behind it, the demo
images, the install blocks, and the evidence hashes. It also
records the worked example again and compares it with the
committed transcript.

Runs offline with the standard library, `git`, and a POSIX
`sh` with `cat` and `cp` (the worked example's commands):

    python3 tests/test_integrations.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "improve-coverage"
PACKAGE = ROOT / "skills" / NAME
SKILL = PACKAGE / "SKILL.md"
INTERFACE = PACKAGE / "agents" / "openai.yaml"
RECORDER = ROOT / "scripts" / "record_session.py"
README = ROOT / "README.md"
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "worked-example.txt"
MANIFEST = ROOT / "evidence" / "demo-manifest.json"
CLAIM = "Worked example, by hand: shapes.py 57% to 100%, tests only."
BEFORE_LINE = "shapes.py: 4 of 7 lines ran (57%); not run: 7, 8, 9"
AFTER_LINE = "shapes.py: 7 of 7 lines ran (100%)"
SCOPE_COMMAND = "git diff --name-only base"
STATUS_COMMAND = "git status --short"
COMPANIONS = ("multi-persona-code-review", "address-comments", "plan-commits")
REPOSITORY = "https://github.com/trycopilotai/" + NAME


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    ).stdout


def load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(product: str) -> dict:
    return json.loads(read(ROOT / product / "plugin.json"))


def frontmatter(text: str) -> dict:
    """The `key: value` pairs between the two `---` lines."""
    lines = text.splitlines()
    if lines[0] != "---":
        raise AssertionError("SKILL.md does not open with frontmatter")
    end = lines.index("---", 1)
    fields: dict = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([a-z_-]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
            continue
        if key is None or not line.startswith(" "):
            raise AssertionError("unexpected frontmatter line: " + line)
        fields[key] = (fields[key] + " " + line.strip()).strip()
    for name, value in fields.items():
        if value.startswith(">-"):
            fields[name] = value[2:].strip()
    return fields


def interface_yaml(text: str) -> dict:
    """The quoted scalars under `interface:` in agents/openai.yaml."""
    lines = text.splitlines()
    if lines[0] != "interface:":
        raise AssertionError("openai.yaml does not start with interface:")
    fields: dict = {}
    key = None
    for line in lines[1:]:
        match = re.match(r"^  ([a-z_]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
            continue
        fields[key] = (fields[key] + " " + line.strip()).strip()
    for name, value in fields.items():
        if not (value.startswith('"') and value.endswith('"')):
            raise AssertionError(name + " is not a double-quoted scalar")
        fields[name] = value[1:-1]
    return fields


def install_blocks() -> list:
    return re.findall(r"```sh\nset -eu\n(.*?)```", read(README), flags=re.S)


def blocks(transcript: str) -> list:
    """Each command of the transcript, in order, with the lines it printed."""
    found: list = []
    for line in transcript.splitlines():
        if line.startswith("$ "):
            found.append((line[2:], []))
            continue
        found[-1][1].append(line)
    return found


def section(text: str, heading: str) -> str:
    """The body of one `## ` section of a Markdown file."""
    match = re.search(
        r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", text, flags=re.S | re.M
    )
    if match is None:
        raise AssertionError("no section " + heading)
    return match.group(1)


class LayoutTest(unittest.TestCase):
    def test_skill_is_a_symlink_into_the_canonical_package(self) -> None:
        link = ROOT / "skill"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(str(link)), "skills/" + NAME)
        self.assertFalse(PACKAGE.is_symlink())

    def test_package_holds_what_the_readme_says_it_installs(self) -> None:
        found = sorted(
            path.relative_to(PACKAGE).as_posix()
            for path in PACKAGE.rglob("*")
            if path.is_file()
        )
        self.assertEqual(found, ["SKILL.md", "agents/openai.yaml"])

    def test_history_has_no_co_author_trailer(self) -> None:
        messages = git("log", "--all", "--format=%B")
        self.assertNotIn("co-authored-by", messages.lower())


class SkillTest(unittest.TestCase):
    def test_frontmatter_is_name_and_description_only(self) -> None:
        fields = frontmatter(read(SKILL))
        self.assertEqual(sorted(fields), ["description", "name"])
        self.assertEqual(fields["name"], NAME)
        self.assertRegex(NAME, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(NAME), 64)
        self.assertTrue(fields["description"])
        self.assertLessEqual(len(fields["description"]), 1024)

    def test_skill_stays_under_five_hundred_lines(self) -> None:
        self.assertLess(len(read(SKILL).splitlines()), 500)

    def test_non_interactive_mode_needs_both_inputs(self) -> None:
        body = " ".join(section(read(SKILL), "Non-interactive mode").split())
        for name in ("`scope`", "`coverage_cmd`", "`target`", "`exclusions`", "`commit`"):
            self.assertIn(name, body)
        self.assertIn("The mode applies only when the caller passes both", body)
        self.assertIn("If neither input is passed, run the Step 1 interview as usual.", body)
        self.assertIn("If only one of the two is passed", body)
        self.assertIn("do not start the interview", body)
        self.assertIn("do not edit production files for any reason", body)
        self.assertIn("Do not push.", body)

    def test_interview_stays_the_default(self) -> None:
        text = read(SKILL)
        self.assertIn("## Step 1 — Interview until the scope is rock-solid", text)
        step_one = " ".join(text.split("## Step 1", 1)[1].split("## Step 2", 1)[0].split())
        self.assertIn("Skip this step in non-interactive mode.", step_one)
        self.assertIn("Interview the operator and keep iterating", step_one)

    def test_skill_and_readme_name_the_same_companions(self) -> None:
        skill = read(SKILL)
        missing = " ".join(section(read(README), "Not included").split())
        for name in COMPANIONS:
            self.assertIn("`%s`" % name, skill)
            self.assertIn("`%s`, published as `trycopilotai/%s`" % (name, name), missing)


class ManifestTest(unittest.TestCase):
    def test_both_manifests_agree(self) -> None:
        claude = manifest(".claude-plugin")
        codex = manifest(".codex-plugin")
        for field in (
            "name",
            "version",
            "description",
            "license",
            "homepage",
            "repository",
            "keywords",
            "skills",
        ):
            self.assertEqual(claude[field], codex[field], field)
        self.assertEqual(claude["name"], NAME)
        self.assertEqual(claude["skills"], "./skills/")
        self.assertEqual(claude["repository"], REPOSITORY)
        self.assertEqual(claude["license"], "MIT")
        self.assertRegex(claude["version"], r"^\d+\.\d+\.\d+$")

    def test_a_release_tag_on_head_is_the_manifest_version(self) -> None:
        tags = git("tag", "--points-at", "HEAD").split()
        releases = [tag for tag in tags if tag.startswith("v")]
        if not releases:
            self.skipTest("HEAD carries no release tag")
        self.assertEqual(releases, ["v" + manifest(".claude-plugin")["version"]])

    def test_codex_interface_matches_the_agent_file(self) -> None:
        interface = manifest(".codex-plugin")["interface"]
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "websiteURL",
        ):
            self.assertTrue(interface.get(field), field)
        prompts = interface["defaultPrompt"]
        self.assertEqual(len(prompts), 1)
        self.assertIn("$" + NAME, prompts[0])
        agent = interface_yaml(read(PACKAGE / "agents" / "openai.yaml"))
        self.assertEqual(agent["default_prompt"], prompts[0])
        self.assertEqual(agent["display_name"], interface["displayName"])
        self.assertEqual(agent["short_description"], interface["shortDescription"])


class ReadmeTest(unittest.TestCase):
    def test_claim_is_on_its_own_line(self) -> None:
        self.assertIn(CLAIM, read(README).splitlines())
        self.assertLessEqual(len(CLAIM), 60)

    def test_transcript_shows_the_results_behind_the_claim(self) -> None:
        printed = blocks(read(TRANSCRIPT))
        for command, lines in printed:
            self.assertEqual(lines[-1], "exit status: 0", command)
        outputs = dict(printed)
        self.assertEqual(outputs[SCOPE_COMMAND], ["shapes.py", "exit status: 0"])
        measured = [lines[-2] for command, lines in printed if "measure.py" in command]
        self.assertEqual(measured, [BEFORE_LINE, AFTER_LINE])
        self.assertEqual(printed[-1], (STATUS_COMMAND, ["?? test_triangle.py", "exit status: 0"]))

    def test_each_install_block_pins_the_manifest_version(self) -> None:
        version = manifest(".claude-plugin")["version"]
        blocks = install_blocks()
        self.assertEqual(len(blocks), 2)
        roots = []
        for block in blocks:
            self.assertEqual(
                re.findall(r"^release=(\S+)$", block, flags=re.M),
                ["v" + version],
            )
            self.assertIn(REPOSITORY + " \\\n", block)
            self.assertIn('--branch "$release"', block)
            target = re.findall(r'^install_target="\$HOME/(\S+)"$', block, flags=re.M)
            self.assertEqual(len(target), 1)
            roots.append(target[0])
        self.assertEqual(
            sorted(roots),
            [".agents/skills/" + NAME, ".claude/skills/" + NAME],
        )

    def test_relative_links_resolve(self) -> None:
        targets = re.findall(r"\]\(([^)#]+)\)", read(README))
        self.assertTrue(targets)
        for target in targets:
            if target.startswith("http"):
                continue
            self.assertTrue((ROOT / target).exists(), target)

    def test_readme_says_what_was_not_measured(self) -> None:
        text = " ".join(read(README).split())
        self.assertIn("no agent run of it is evidenced here", text)
        self.assertIn("No agent invoked the skill to produce the evidence here", text)
        self.assertIn("has not been measured", text)
        self.assertIn("written by hand for the example", text)

    def test_demo_is_offered_with_a_reduced_motion_poster(self) -> None:
        text = read(README)
        picture = re.search(r"<picture>(.*?)</picture>", text, flags=re.S)
        self.assertIsNotNone(picture)
        body = picture.group(1)
        self.assertIn('media="(prefers-reduced-motion: reduce)"', body)
        self.assertIn('srcset="assets/poster.svg"', body)
        self.assertIn('src="assets/demo.svg"', body)


class EvidenceTest(unittest.TestCase):
    def test_manifest_hashes_match_the_files(self) -> None:
        record = json.loads(read(MANIFEST))
        self.assertEqual(
            record["skill"],
            {"path": str(SKILL.relative_to(ROOT)), "sha256": sha256(SKILL)},
        )
        self.assertEqual(
            record["interface"],
            {"path": str(INTERFACE.relative_to(ROOT)), "sha256": sha256(INTERFACE)},
        )
        self.assertEqual(
            record["programs"],
            [{"path": str(RECORDER.relative_to(ROOT)), "sha256": sha256(RECORDER)}],
        )
        self.assertEqual(record["output"]["path"], str(TRANSCRIPT.relative_to(ROOT)))
        self.assertEqual(record["output"]["sha256"], sha256(TRANSCRIPT))
        self.assertIs(record["output"]["edited"], False)
        self.assertEqual(record["output"]["transforms"], [])
        self.assertIs(record["agent"]["invoked_the_skill"], False)

    def test_manifest_commands_are_the_ones_in_the_transcript(self) -> None:
        record = json.loads(read(MANIFEST))
        commands = [command for command, _lines in blocks(read(TRANSCRIPT))]
        self.assertEqual(record["invocation"]["commands"], commands)
        self.assertIn(SCOPE_COMMAND, commands)
        self.assertEqual(commands[-1], STATUS_COMMAND)

    def test_a_fresh_recording_equals_the_transcript(self) -> None:
        fresh = subprocess.run(
            [sys.executable, "-B", str(RECORDER), "--print"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        self.assertEqual(fresh.returncode, 0, fresh.stdout + fresh.stderr)
        self.assertEqual(fresh.stdout, read(TRANSCRIPT))


class DemoTest(unittest.TestCase):
    def test_images_agree_with_the_transcript(self) -> None:
        verifier = load(ROOT / "scripts" / "verify_demo.py", "verify_demo")
        generator = verifier.load_generator()
        self.assertEqual(verifier.problems_in(generator, read(TRANSCRIPT)), [])


class SocialPreviewTest(unittest.TestCase):
    def test_preview_is_the_size_github_expects(self) -> None:
        header = (ROOT / "assets" / "social-preview.png").read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (1280, 640))

    def test_stamp_binds_the_source_and_the_render(self) -> None:
        recorded = {}
        for line in read(ROOT / "assets" / "social-preview.sha256").splitlines():
            value, name = line.split()
            recorded[name] = value
        for name in ("social-preview.html", "social-preview.png"):
            self.assertEqual(recorded[name], sha256(ROOT / "assets" / name), name)

    def test_preview_source_carries_the_claim(self) -> None:
        text = " ".join(read(ROOT / "assets" / "social-preview.html").split())
        self.assertIn(CLAIM, text)


class SupportFilesTest(unittest.TestCase):
    def test_license_is_mit(self) -> None:
        self.assertTrue(read(ROOT / "LICENSE").startswith("MIT License\n"))

    def test_security_names_this_repository_for_reports(self) -> None:
        self.assertIn(
            REPOSITORY + "/security/advisories/new",
            read(ROOT / "SECURITY.md"),
        )

    def test_contributing_names_the_check_command(self) -> None:
        self.assertIn("make check", read(ROOT / "CONTRIBUTING.md"))


if __name__ == "__main__":
    unittest.main()
