# Git and Vercel Workflow

## Objective

Every production deployment must be reproducible from a reviewed Git commit that has already been pushed to GitHub. Never deploy application code directly from a dirty working tree.

## Scope Control

1. Inspect `git status -sb` and the relevant diff before staging.
2. Preserve unrelated user changes.
3. Stage explicit paths. Do not use `git add -A` in a mixed working tree.
4. Do not commit credential files, `.env` files, `.vercel/project.json`, raw secrets, or transient server logs.
5. Keep deployment procedure changes in this file; other documents link here.

## Preflight

Run from the repository root:

```powershell
git status -sb
git branch --show-current
git remote -v
gh auth status
vercel whoami
Get-Content .vercel\project.json
```

Confirm that the Vercel link points to the intended `network-ai-mvp` project before deploying.

## Validation Gate

Run checks appropriate to the changed scope. For application changes, the minimum gate is:

```powershell
python -m unittest discover -s tests
node --check src\network_ai_mvp\static\app.js
node --check src\network_ai_mvp\static\monitoring.js
git diff --check
```

Do not commit or deploy when a required check fails. Record only durable changes in documentation; do not paste transient command output into rule files.

## Commit and Push

Stage only reviewed files, inspect the staged diff, then commit and push the current branch:

```powershell
git add -- <reviewed-paths>
git diff --cached --check
git diff --cached --stat
git commit -m "<concise change description>"
$branch = git branch --show-current
git push -u origin $branch
git status -sb
```

The pushed commit SHA is the only valid source for a production artifact.

## Preferred Vercel Integration

Prefer Vercel Git integration with a protected production branch:

- Feature-branch pushes create preview deployments.
- Required checks run before merge.
- Merging the protected production branch creates the production deployment.
- The production alias moves only after the deployment reaches `READY`.

Until Git-triggered production deployment is configured and verified, use the clean-worktree CLI procedure below.

## Manual Production Deployment

Create a detached temporary worktree from the pushed commit so unrelated local changes cannot enter the deployment:

```powershell
$sha = git rev-parse HEAD
$shortSha = git rev-parse --short HEAD
$deployRoot = Join-Path $env:TEMP "network-ai-mvp-deploy-$shortSha"

git worktree add --detach $deployRoot $sha
New-Item -ItemType Directory -Path (Join-Path $deployRoot '.vercel') -Force | Out-Null
Copy-Item .vercel\project.json (Join-Path $deployRoot '.vercel\project.json')
```

The `data/` directory is intentionally excluded from Git. If the production UI requires a reference snapshot, include only a reviewed and redacted snapshot in the temporary deployment artifact:

```powershell
rg -l -i 'password|passwd|secret|token|community\s+\S+|enable\s+secret' data
Copy-Item data (Join-Path $deployRoot 'data') -Recurse
```

Any sensitive-data match must be reviewed before deployment. Snapshot inclusion does not make Vercel a live collector; see [`architecture.md`](architecture.md).

Deploy the clean artifact:

```powershell
vercel deploy --prod --yes --force --cwd $deployRoot
```

## Production Verification

Deployment success requires all of the following:

1. Vercel reports `READY` and the expected production alias.
2. `/health` returns `status=ok` and `mode=read-only`.
3. `/operations` loads meaningful content with the expected static asset version.
4. The changed user flow is exercised in a browser.
5. Browser console errors are checked.
6. Vercel runtime error logs are checked when available.

Useful commands:

```powershell
vercel inspect <deployment-url> --cwd $deployRoot
Invoke-RestMethod https://network-ai-mvp.vercel.app/health
Invoke-WebRequest https://network-ai-mvp.vercel.app/operations -UseBasicParsing
vercel logs <deployment-url> --since 10m --level error --cwd $deployRoot
```

Firewall verification must use the company public egress IP. Private workstation addresses are not visible to Vercel Firewall. Do not change Firewall rules as an implicit part of an application deployment.

## Cleanup

After verification, remove the temporary worktree and confirm the primary working tree still contains only the expected uncommitted changes:

```powershell
$resolvedTemp = [System.IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')
$resolvedDeploy = [System.IO.Path]::GetFullPath($deployRoot)
if (-not $resolvedDeploy.StartsWith($resolvedTemp + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe cleanup path: $resolvedDeploy"
}

git worktree remove --force $resolvedDeploy
git worktree list
git status -sb
```

Resolve and verify the absolute temporary path before any recursive cleanup on Windows.

## Failure and Rollback

- If a build fails, keep the current production alias unchanged and inspect build logs.
- If production verification fails after aliasing, use `vercel rollback` to restore the last verified deployment.
- Fix the source, repeat validation, create a new commit, push it, and deploy that commit. Do not patch a deployed artifact without a corresponding Git commit.

## Session Completion

- Report the branch, commit SHA, push result, production URL, deployment state, and verification outcome to the user.
- Keep process IDs, deployment IDs, timestamps, and raw command logs out of durable rule files.
- Update `PROJECT_STATUS.md` only when product capability or a durable limitation changes.
- Update `NEXT_TASK.md` only when the prioritized backlog changes.
- Do not append session-by-session histories to documentation.
