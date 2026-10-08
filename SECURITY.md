# Security

## Reporting a vulnerability

Report privately through GitHub:
<https://github.com/trycopilotai/improve-coverage/security/advisories/new>

That opens a private security advisory visible only to the
maintainers. Do not put the details of a vulnerability in a
public issue.

If that link shows "Not Found", private reporting is not
turned on for this repository. Open a public issue titled
"Security report waiting" that says only that you have a
report, with no details, and a maintainer will arrange a
private channel.

## What is in scope

- **Prompt content that redirects an agent.** `SKILL.md` is
  an instruction set an agent may follow. Text in it that
  makes an agent send data to a place the operator did not
  name, or act outside the repository and scope it was
  given in ways the next section does not already state, is
  a valid report.
- **The install blocks.** The two README blocks run
  `mkdir -p`, `mktemp -d`, `git clone`, `cp`, `mv` and
  `rm -rf`, all inside one skills directory under `$HOME`. A
  repository state that makes either block write or delete
  outside its install target is in scope.
- **The build and test scripts.** These are not part of the
  skill and neither install block copies them.
  `assets/build.py` finds a Chrome or Chromium binary from a
  fixed candidate list, runs it headless with a temporary
  profile directory, and writes the preview PNG and its
  stamp. `scripts/generate_demo.py` writes two SVG files;
  `scripts/verify_demo.py` reads files and writes none.
  `scripts/record_session.py` builds a synthetic git
  repository in a temporary directory, writes a small
  `python3` launcher beside it, runs the commands listed in
  `evidence/demo-manifest.json` there through `sh`, and
  rewrites the transcript and the manifest. The commands
  run the fixture's own `measure.py`, which imports and runs
  the fixture's tests. With `RECORD_RAW_DIR` set it also
  writes a copy of the capture into that directory.
  `scripts/render_invocation.py` reads an agent client's
  raw JSON-lines output and a prompt file, and prints a
  transcript to standard output; it writes no file and runs
  nothing.
  `tests/test_integrations.py` runs `git` against the
  repository root, runs the recorder once with `--print`
  (which writes nothing outside its temporary directory),
  loads the two demo scripts to compare the images with
  the transcript, and runs the renderer on small inputs it
  writes to a temporary directory.

## What the skill tells an agent to do

These are properties of the text, stated so you can decide
whether to use it. They are known limits, not findings:

- It tells the agent to run the repository's test,
  coverage, type-check and lint commands, and to dispatch
  one subagent per uncovered file, concurrently, each of
  which runs scoped coverage commands too. Those commands
  run with whatever permissions the host gives the agent.
- When a coverage provider does not work, Step 2 tells the
  agent to install a source-instrumenting one transiently,
  or to run under another runtime version. That installs
  software from wherever the repository's package manager
  fetches it.
- It tells the agent to write test files. In the default,
  interactive mode it allows an implementation change only
  with the operator's sign-off on that specific change, and
  Step 5 allows annotations, coverage-ignore directives or a
  refactor in production files when the operator chose
  that. In non-interactive mode it tells the agent not to
  edit production files at all.
- It tells the agent to commit (Steps 7 and 8). The
  interview asks whether new test files may be committed;
  in non-interactive mode the agent commits only when the
  caller's `commit` input allows it. It tells the agent not
  to push unless the operator authorized a push.
- It tells the agent to record the run in the host's private
  operational log when the host keeps one.
- In non-interactive mode it takes the scope and the
  coverage command from the calling skill and runs that
  command as given. Whoever controls the caller's inputs
  chooses the command the agent runs.
- Nothing in this repository enforces any of that text. An
  agent that follows it acts with whatever permissions its
  host gives it, and nothing here narrows them.

## What is out of scope

The skill names three companion skills
(`multi-persona-code-review`, `address-comments`,
`plan-commits`) and relies on the repository's own test,
coverage, type-check and lint tooling. None of them is in
this repository. Their behaviour, and the behaviour of
Claude Code, Codex, or any other host, is out of scope here.
Report those to their own maintainers.
