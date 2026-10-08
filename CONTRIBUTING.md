# Contributing

This repository is one skill, `SKILL.md`, and the scripts
that record the worked example, build and check the demo
images, and test the repository.

## Run the checks first

```sh
make check
```

That runs `tests/test_integrations.py`. It needs `python3`
with nothing outside the standard library, `git`, a POSIX
`sh` with `cat` and `cp` (the worked example's commands),
and a real clone with its history and tags, because it reads
`git log` and the release tag. It records the worked
example again in a temporary directory and compares the
result with the committed transcript byte for byte.

**The suite pins prose.** These will fail on an
innocent-looking edit:

- the claim line at the top of the README must appear
  verbatim;
- each install block must carry its own `release=` pin at
  the version both plugin manifests ship;
- `SKILL.md` must stay under 500 lines and keep its
  "Non-interactive mode" section;
- `evidence/demo-manifest.json` records the SHA-256 of
  `SKILL.md`, of `agents/openai.yaml`, of
  `scripts/record_session.py` and of the transcript, so an
  edit to one of those four files, prose included, fails
  until the manifest is refreshed as described next.

If you change one of those, change the thing it describes
too.

## Changing the skill or the worked example

After an edit to `SKILL.md`, to `agents/openai.yaml`, or to
`scripts/record_session.py`, run:

```sh
make record
make demo
```

`make record` runs `scripts/record_session.py`. It builds
the synthetic repository in a throwaway directory, runs the
commands listed in the manifest, writes the transcript, and
rewrites the manifest's hashes, date and interpreter. If a
command exits non-zero it rewrites neither file and exits 1.
It needs `sh`, `cat`, `cp`, `git` and `python3`. `make demo` rebuilds
the two images from the transcript. `make assets` rebuilds
the social preview and needs Chrome or Chromium;
`make asset-check` does not.

## What is most useful

Open an issue for any of these. The labels
`good first issue` and `help wanted` mark the ones that are
ready to pick up.

- **A report of trying it.** Say which host ran it, which
  language and coverage tool the repository used, whether
  you used the interview or non-interactive mode, and where
  the agent first left the skill's text.
- **A place where the text is ambiguous** for a caller in
  non-interactive mode: an input it does not define, or a
  step whose behaviour in that mode it does not state.
- **A dependency the README does not list.** Name the step
  that needs something this repository does not include.

## Pull requests

Prose changes to `SKILL.md` are welcome. Say what the text
told an agent to do before the change and what it tells it
after.

Keep `SKILL.md` under 500 lines; the suite enforces it.
Frontmatter carries `name` and `description` and nothing
else.

The top-level `skill` is a symlink to
`skills/improve-coverage/`. Do not reverse that orientation.

Commit with your own identity and no `Co-authored-by`
trailer of any kind. The suite fails on one anywhere in
history, so do not apply review suggestions through the
GitHub UI, and do not squash-merge a pull request that has
more than one author.
