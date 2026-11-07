Run `hooks/pre-implement.sh` before coding.

It passes when the intent states an Outcome and a Success / Evidence. It does not require requirements, architecture, implementation steps, or exhaustive acceptance criteria.

When this repo is installed as a plugin, `hooks.json` runs `pre-implement-hook.sh` before every Edit and Write. In a project that has `intent/current-feature.md`, code edits are blocked until the check passes. Markdown files are never blocked, and projects without that file are left alone. The starter's own repository is skipped too, because it has to ship a blank intent template.
