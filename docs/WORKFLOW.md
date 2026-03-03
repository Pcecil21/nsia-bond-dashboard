# Development Workflow

## Branch Strategy

```bash
# Always work on a feature branch, never directly on main
git checkout -b feature/my-change

# When done, commit and push
git add -A
git commit -m "feat: describe what you did"
git push -u origin feature/my-change

# Merge via GitHub PR (keeps main clean)
```

## Working with AI (Claude Code)

1. **Commit before AI sessions** — create a snapshot so you can revert if needed:
   ```bash
   git add -A && git commit -m "checkpoint: before AI session"
   ```

2. **Commit after AI sessions** — capture what changed:
   ```bash
   git diff --stat          # review what changed
   git add -A && git commit -m "feat: describe AI-assisted changes"
   ```

3. **Scope Claude to one project** — always `cd` into the specific app folder before starting. Never let Claude operate on your entire Dev directory.

4. **Review diffs** — before accepting AI changes, run `git diff` to understand what was modified.

## Secrets Management

- **Never commit `.env` files** — they contain API keys and secrets
- Keep a `.env.example` with variable names (no values) for reference
- `.gitignore` already excludes `.env` and `.env.local`
- If you accidentally commit secrets:
  ```bash
  git rm --cached .env
  git commit -m "fix: remove .env from tracking"
  ```
  Then rotate the exposed keys immediately.

## Daily Workflow

```bash
# Start of session
cd C:\Users\pceci\OneDrive\Dev\apps\<project>
git status                    # check state
git checkout -b feature/xxx   # new branch

# Work...

# End of session
git add -A
git commit -m "feat: what you did"
git push -u origin feature/xxx
```
