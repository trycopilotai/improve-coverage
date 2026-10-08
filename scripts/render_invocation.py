#!/usr/bin/env python3
"""Render an agent invocation's raw JSON-lines output as text.

    python3 scripts/render_invocation.py --client claude-code \
        --prompt prompt.txt --root <fixture> --plugin-root <clone> \
        --home <home> --hostname <name> raw.jsonl > transcript.txt

Writes the prompt, every tool call (its name, and its arguments
re-serialised as JSON with sorted keys, each argument string cut
at LIMIT characters after the replacements below), each call's
status where the raw output records it, and the final message
with the same replacements applied. A call a Claude Code sub-agent
made is marked "(sub-agent)". For Codex, a command is written
with its status and exit code, any other completed item except
reasoning as its whole item object, and the last agent message
is the final message. The replacements, in this order, each applied to a
whole path prefix and never inside a longer name: each
--plugin-root (the directory the client loaded the skill
from) becomes /plugin, the fixture's absolute path /work, a
client scratch directory /private/tmp/claude-<uid>/<slug>
/scratch, the home directory ~, and each --hostname host.
Standard library only; output depends only on the inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

LIMIT = 300
# A path or name ends at a separator, a quote, whitespace, a closing
# bracket, a comma, semicolon or colon, a full stop that ends a
# sentence, or the end.
STOP = "/\\\\\\s\"'`)\\]},;:"
END = r"(?=[" + STOP + r"]|\.(?![\w-])|$)"
# The scratch slug is one path segment; it never takes in the
# character that ends it, nor a full stop that ends a sentence.
SCRATCH = re.compile(r"/private/tmp/claude-[0-9]+/[^" + STOP + r"]*[^." + STOP + r"]" + END)


def prefix(text: str, path: str, replacement: str) -> str:
    """Replace `path` where it is a whole path prefix."""
    pattern = r"(?<![\w.-])" + re.escape(path.rstrip("/")) + END
    return re.sub(pattern, lambda match: replacement, text)


def edits(options):
    """The declared transforms, in order, as one function of text."""

    def apply(text: str) -> str:
        for path in options.plugin_root:
            text = prefix(text, path, "/plugin")
        text = prefix(text, options.root, "/work")
        text = SCRATCH.sub(lambda match: "/scratch", text)
        text = prefix(text, options.home, "~")
        for name in sorted(options.hostname, key=len, reverse=True):
            text = re.sub(
                r"(?<![\w.-])" + re.escape(name) + r"(?![\w-]|\.\w)",
                lambda match: "host",
                text,
            )
        return text

    return apply


# The transforms. main() sets them; cut() runs them on each whole
# argument string first, so a cut never splits a path they replace.
EDIT = [lambda text: text]


def cut(value):
    if isinstance(value, str):
        value = EDIT[0](value)
        if len(value) > LIMIT:
            return value[:LIMIT] + "...[%d more characters]" % (len(value) - LIMIT)
        return value
    if isinstance(value, dict):
        return {key: cut(item) for key, item in value.items()}
    if isinstance(value, list):
        return [cut(item) for item in value]
    return value


def arguments(value) -> str:
    return json.dumps(cut(value), ensure_ascii=False, sort_keys=True)


def claude_code(events):
    calls, final, model, version = [], None, None, None
    results = {}
    for event in events:
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            model, version = event.get("model"), event.get("claude_code_version")
        elif kind in ("assistant", "user"):
            content = event["message"].get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use":
                    name = block["name"]
                    if event.get("parent_tool_use_id"):
                        name += " (sub-agent)"
                    calls.append((block["id"], name, block.get("input")))
                elif block.get("type") == "tool_result":
                    results[block["tool_use_id"]] = (
                        "error" if block.get("is_error") else "ok"
                    )
        elif kind == "result":
            final = event.get("result")
    header = ["client: Claude Code %s" % version, "model: %s" % model]
    lines = [
        "%s %s\n  status: %s" % (name, arguments(given), results.get(ident, "unknown"))
        for ident, name, given in calls
    ]
    return header, lines, final


def codex(events):
    lines, final = [], None
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event["item"]
        if item.get("type") == "command_execution":
            lines.append(
                "command_execution %s\n  status: %s, exit %s"
                % (arguments({"command": item["command"]}), item.get("status"), item.get("exit_code"))
            )
        elif item.get("type") == "agent_message":
            final = item["text"]
        elif item.get("type") not in ("reasoning",):
            lines.append("%s %s" % (item.get("type"), arguments(item)))
    return ["client: Codex"], lines, final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("claude-code", "codex"), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--plugin-root", action="append", default=[])
    parser.add_argument("--home", required=True)
    parser.add_argument("--hostname", action="append", default=[])
    parser.add_argument("raw")
    options = parser.parse_args(argv)
    with open(options.raw, encoding="utf-8") as stream:
        events = [json.loads(line) for line in stream if line.strip()]
    with open(options.prompt, encoding="utf-8") as stream:
        prompt = stream.read().rstrip("\n")
    EDIT[0] = edits(options)
    render = claude_code if options.client == "claude-code" else codex
    header, lines, final = render(events)
    text = "\n".join(
        header
        + ["", "## prompt", "", prompt, "", "## tool calls", ""]
        + ["%d. %s" % (number, line) for number, line in enumerate(lines, 1)]
        + ["", "## final message", "", final if final is not None else "(none)", ""]
    )
    sys.stdout.write(EDIT[0](text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
