# ADR 001: Notebook Output Stripping with nbstripout

## Status
Accepted

## Context
Jupyter notebooks (`.ipynb`) store cell outputs (data, plots, print statements) inside the JSON file. Committing outputs causes:
- Noisy, unreadable diffs in pull requests
- Bloated git history
- Merge conflicts on output-only changes

We needed a way to automatically strip outputs before they reach git history, without disrupting the local development experience (outputs should still be visible while working).

## Decision
Use **nbstripout** as a **git filter** (not a pre-commit hook).

The git filter is configured once per clone via `nbstripout install`, and `.gitattributes` is committed to the repo to activate it for all `.ipynb` files.

### What to avoid
| Approach | Problem |
|---|---|
| nbstripout as a pre-commit hook | Always fails the first commit; requires staging twice to succeed |
| Both git filter and pre-commit hook | Redundant; double-processing |
| Neither | Notebook outputs bloat git history |

## Setup (run once after cloning)

```bash
# Install nbstripout into the project venv
uv add --dev nbstripout

# Register the git filter in .git/config (local only, not committed)
nbstripout install
```

The `.gitattributes` file is already committed and activates the filter:
```
*.ipynb filter=nbstripout
```

## How it works

```
git add notebook.ipynb
  → git clean filter runs nbstripout automatically
  → git stores the stripped version (no outputs)
  → your local file still has outputs (unaffected)

git checkout notebook.ipynb
  → git smudge filter runs cat (no-op)
  → you get the stripped file back
```

## Consequences
- Every contributor must run `nbstripout install` after cloning (local setup step).
- Notebooks in git history will never contain outputs — diffs are clean and readable.
- Local workflow is unaffected — outputs remain visible in the working copy.
