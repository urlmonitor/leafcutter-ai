---
description: Generate a project report — either a time-boxed activity report (today/week/custom) or a full codebase analysis report
---

**Role:** Switch persona to **Senior Engineering Manager & Technical Analyst**.
**Goal:** Gather git metrics and codebase statistics, then deliver a structured report as an artifact with an executive summary in chat.

# PHASE 0: DETERMINE REPORT TYPE

Ask the user which type of report they want, OR infer from context:

| Mode | Trigger | What it produces |
|---|---|---|
| **activity** | "today", "this week", "last 3 days", any time reference | Time-boxed git activity report |
| **codebase** | "full report", "project stats", "how big is the project" | Full codebase analysis |
| **both** | "everything", "full blown" | Both reports combined |

If the user provides a time range, use it. Otherwise default to:
- **activity** → today (`--since="YYYY-MM-DDT00:00:00"` using current date)
- **codebase** → always full scan

---

# MODE A: TIME-BOXED ACTIVITY REPORT

## A1. Git Commit Summary
// turbo-all
Collect all metrics for the specified time range. Replace `$SINCE` with the appropriate `--since` value.

### Total commits and messages
```powershell
git log --since="$SINCE" --oneline --format="%h %s" -n 200
```

### Insertions and deletions per commit
```powershell
git log --since="$SINCE" --shortstat --format="" | findstr /V "^$"
```

### Categorized Insertions by Role & Human Time Estimate
```powershell
git log --since="$SINCE" --numstat --format="" | Where-Object { $_ -match '\d' } | ForEach-Object {
    $parts = $_ -split '\t'
    if ($parts[0] -ne '-') {
        $added = [int]$parts[0]
        $file = $parts[2]
        $role = "Other"
        
        if ($file -match '^tickets/') { $role = "BA / Product Owner" }
        elseif ($file -match '^docs/architecture/' -or $file -match '^adr/') { $role = "System Architect" }
        elseif ($file -match '^docs/' -or $file -match '^changelogs/') { $role = "Technical Writer" }
        elseif ($file -match '^unit_tests/' -or $file -match '^tests/') { $role = "QA Engineer" }
        elseif ($file -match '\.py$') { $role = "Senior Engineer (Python)" }
        elseif ($file -match '\.sql$') { $role = "Senior Engineer (SQL)" }
        elseif ($file -match '^leafcutter/' -or $file -match '^scripts/' -or $file -match '^\.claude/' -or $file -match '^\.agents/') { $role = "DevOps / Release" }
        
        [PSCustomObject]@{Role=$role; Added=$added}
    }
} | Group-Object Role | ForEach-Object {
    $totalAdded = ($_.Group | Measure-Object Added -Sum).Sum
    $days = 0
    if ($_.Name -eq "BA / Product Owner") { $days = [math]::Round($totalAdded / 300, 1) }
    elseif ($_.Name -eq "System Architect") { $days = [math]::Round($totalAdded / 150, 1) }
    elseif ($_.Name -eq "Technical Writer") { $days = [math]::Round($totalAdded / 250, 1) }
    elseif ($_.Name -eq "QA Engineer") { $days = [math]::Round($totalAdded / 150, 1) }
    elseif ($_.Name -match "Senior Engineer") { $days = [math]::Round($totalAdded / 100, 1) }
    elseif ($_.Name -eq "DevOps / Release") { $days = [math]::Round($totalAdded / 200, 1) }
    else { $days = [math]::Round($totalAdded / 200, 1) }
    
    [PSCustomObject]@{Role=$_.Name; AddedLines=$totalAdded; EstimatedDays=$days}
} | Sort-Object EstimatedDays -Descending | Format-Table -AutoSize
```
### Total deletions
```powershell
git log --since="$SINCE" --numstat --format="" | Where-Object { $_ -match '\d' } | ForEach-Object { $parts = $_ -split '\t'; if ($parts[1] -ne '-') { [int]$parts[1] } else { 0 } } | Measure-Object -Sum | Select-Object -ExpandProperty Sum
```

### Unique files touched
```powershell
git log --since="$SINCE" --name-only --format="" | Where-Object { $_ -ne '' } | Sort-Object -Unique | Measure-Object | Select-Object -ExpandProperty Count
```

### Files by extension
```powershell
git log --since="$SINCE" --name-only --format="" | Where-Object { $_ -ne '' } | Sort-Object -Unique | ForEach-Object { [System.IO.Path]::GetExtension($_) } | Group-Object | Sort-Object Count -Descending | Format-Table Count, Name -AutoSize
```

### Commit counts (feature vs merge)
```powershell
git log --since="$SINCE" --no-merges --oneline | Measure-Object | Select-Object -ExpandProperty Count
```
```powershell
git log --since="$SINCE" --merges --oneline | Measure-Object | Select-Object -ExpandProperty Count
```

### New files created
```powershell
git log --since="$SINCE" --diff-filter=A --name-only --format="" | Where-Object { $_ -ne '' } | Sort-Object -Unique | Measure-Object | Select-Object -ExpandProperty Count
```

### Files deleted
```powershell
git log --since="$SINCE" --diff-filter=D --name-only --format="" | Where-Object { $_ -ne '' } | Sort-Object -Unique | Measure-Object | Select-Object -ExpandProperty Count
```

### Time span (first and last commit)
```powershell
git log --since="$SINCE" --format="%ai %s" | Select-Object -Last 1; git log --since="$SINCE" --format="%ai %s" | Select-Object -First 1
```

### Completed Tickets
```powershell
git log --since="$SINCE" --name-status --format="" | Where-Object { $_ -match '(A|R\d*)\s+.*99_done/.*\.md$' } | ForEach-Object { $parts = $_ -split '\s+'; $file = $parts[-1]; $name = [System.IO.Path]::GetFileNameWithoutExtension($file); Write-Host "- $name" } | Sort-Object -Unique
```

### Recent Changelogs
```powershell
git log --since="$SINCE" --diff-filter=A --name-only --format="" | Where-Object { $_ -match '^changelogs/.*\.md$' } | Sort-Object -Unique | ForEach-Object { $content = Get-Content $_ -Raw -ErrorAction SilentlyContinue; $title = ""; $summary = ""; if ($content -match '(?m)^title:\s*"(.*?)"') { $title = $matches[1] }; if ($content -match '(?m)^summary:\s*"(.*?)"') { $summary = $matches[1] }; Write-Host "- $($title): $($summary)" }
```

## A2. Build the Activity Report Artifact

Create an artifact with:

### Required Sections

1. **Raw Metrics Table** — Commits, lines added/deleted, net change, files touched, new/deleted files, active window
2. **File Type Breakdown** — Table of extensions with count
3. **Completed Tickets** — List the tickets that were moved to `99_done` during this period, extracted from the script output.
4. **Changelog Highlights** — Present the titles and summaries from the recently generated changelogs in the `changelogs/` folder to provide a business-focused picture of what was achieved.
5. **Work Streams Completed** — Group commits into logical work streams by reading commit messages and combining them with the context of completed tickets and changelogs. For each stream:
   - Name and description
   - What was accomplished
   - Complexity assessment (🟢 Low / 🟡 Medium / 🔴 High)
6. **Cross-Functional Team Time Estimate** — Do not guess or estimate 'senior dev hours' blindly. You MUST use the output from the `Categorized Insertions by Role` script run in Phase A1. Present the data as a table:
   - Role
   - Lines Added
   - Estimated Working Days (from the script's calculation)
   - Then provide the sum of all days to give the overall "Human Team Equivalent".
   - Below the table, include a specific **Methodology & Sources** explanation block. Explain the "Wer schreibt der bleibt" philosophy and list the industry baselines used for the calculations (e.g., 100 lines/day for debugged code from Senior Devs citing industry standards / Fred Brooks, 300 lines/day for BAs, etc.) so the reader understands why the numbers are robust and not hallucinated.

### Time Estimation Guidelines
"Wer schreibt der bleibt!" - To accurately reflect the true human effort of writing code, tickets, tests, and documentation, ALWAYS base your time estimations mathematically on the volume of lines added/modified per role using these realistic industry baselines:

- **Business Analysis & Planning (BA/PO):** ~300 lines of tickets/specs per day.
- **System Architecture:** ~150 lines of ADRs/diagrams/registry JSON per day.
- **Senior Engineering (Python/SQL):** ~100 lines of production logic/complex queries per day.
- **QA & Testing:** ~150 lines of unit/integration tests per day.
- **DevOps / Release Pipeline:** ~200 lines of hooks/configs/templates/scripts per day.
- **Technical Writing:** ~250 lines of markdown docs/changelogs per day.

**Formula:** 
1. Categorize the inserted/modified lines by directory or file type to the appropriate role.
2. Divide the lines by that role's daily baseline to get **Working Days**.
3. Sum the days across all roles to calculate the true "Human Team Equivalent" (where 1 week = 5 working days).



---

# MODE B: FULL CODEBASE REPORT

## B1. File & Line Counts
// turbo-all

### File count by extension
```powershell
Get-ChildItem -Recurse -File -Include *.py,*.sql,*.md,*.yaml,*.yml,*.toml,*.json,*.sh,*.html,*.css,*.js,*.tsx,*.ts,*.cfg,*.ini,*.txt | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|node_modules|\.mypy_cache|\.pytest_cache|alembic\\versions)\\' } | Group-Object Extension | Sort-Object Count -Descending | Select-Object Count, @{N='Extension';E={$_.Name}}, @{N='TotalSizeKB';E={ [math]::Round(($_.Group | Measure-Object Length -Sum).Sum / 1024, 1) }} | Format-Table -AutoSize
```

### Python lines
```powershell
Get-ChildItem -Recurse -File -Filter *.py | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions)\\' } | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count } | Measure-Object -Sum | Select-Object Sum, Count
```

### SQL lines
```powershell
Get-ChildItem -Recurse -File -Filter *.sql | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions)\\' } | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count } | Measure-Object -Sum | Select-Object Sum, Count
```

### Markdown lines
```powershell
Get-ChildItem -Recurse -File -Filter *.md | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions)\\' } | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count } | Measure-Object -Sum | Select-Object Sum, Count
```

### Total source lines (all code + docs)
```powershell
Get-ChildItem -Recurse -File -Include *.py,*.sql,*.md,*.yaml,*.yml,*.toml,*.sh,*.cfg,*.ini | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions|node_modules)\\' } | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count } | Measure-Object -Sum | Select-Object -ExpandProperty Sum
```

## B2. Symbol Counts

### Python classes and functions
```powershell
Get-ChildItem -Recurse -File -Filter *.py | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions)\\' } | ForEach-Object { $content = Get-Content $_.FullName -ErrorAction SilentlyContinue; $classes = ($content | Select-String '^\s*class\s+\w+').Count; $functions = ($content | Select-String '^\s*def\s+\w+').Count; [PSCustomObject]@{Classes=$classes; Functions=$functions} } | Measure-Object -Property Classes, Functions -Sum | Format-Table Property, Sum -AutoSize
```

### SQL object counts
```powershell
$sqlFiles = Get-ChildItem -Recurse -File -Filter *.sql | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|alembic\\versions)\\' }; $procs = 0; $funcs = 0; $views = 0; $matViews = 0; $triggers = 0; foreach ($f in $sqlFiles) { $c = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue; if ($c) { $procs += ([regex]::Matches($c, '(?i)CREATE\s+(OR\s+REPLACE\s+)?PROCEDURE')).Count; $funcs += ([regex]::Matches($c, '(?i)CREATE\s+(OR\s+REPLACE\s+)?FUNCTION')).Count; $views += ([regex]::Matches($c, '(?i)CREATE\s+(OR\s+REPLACE\s+)?VIEW')).Count; $matViews += ([regex]::Matches($c, '(?i)CREATE\s+MATERIALIZED\s+VIEW')).Count; $triggers += ([regex]::Matches($c, '(?i)CREATE\s+(OR\s+REPLACE\s+)?TRIGGER')).Count } }; Write-Host "Procedures: $procs | Functions: $funcs | Views: $views | MatViews: $matViews | Triggers: $triggers"
```

### SQLAlchemy model count
```powershell
Get-ChildItem -Recurse -File -Filter *.py -Path "models" | Where-Object { $_.FullName -notmatch '\\__pycache__\\' } | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Select-String '__tablename__').Count } | Measure-Object -Sum | Select-Object -ExpandProperty Sum
```

## B3. Complexity Analysis

### File size distribution (Python, excl. debugging)
```powershell
$over200 = (Get-ChildItem -Recurse -File -Filter *.py | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions|debugging)\\' } | ForEach-Object { $lines = (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count; if ($lines -gt 200) { $lines } } | Measure-Object).Count; $over500 = (Get-ChildItem -Recurse -File -Filter *.py | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions|debugging)\\' } | ForEach-Object { $lines = (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count; if ($lines -gt 500) { $lines } } | Measure-Object).Count; $over1000 = (Get-ChildItem -Recurse -File -Filter *.py | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions|debugging)\\' } | ForEach-Object { $lines = (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count; if ($lines -gt 1000) { $lines } } | Measure-Object).Count; Write-Host ">200: $over200 | >500: $over500 | >1000: $over1000"
```

### Top 20 largest Python files
```powershell
Get-ChildItem -Recurse -File -Filter *.py | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|\.mypy_cache|\.pytest_cache|alembic\\versions)\\' } | ForEach-Object { $lines = (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count; [PSCustomObject]@{File=$_.Name; Lines=$lines} } | Sort-Object Lines -Descending | Select-Object -First 20 | Format-Table Lines, File -AutoSize
```

### Top 15 largest SQL files
```powershell
Get-ChildItem -Recurse -File -Filter *.sql | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|alembic\\versions)\\' } | ForEach-Object { $lines = (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count; [PSCustomObject]@{File=$_.Name; Lines=$lines} } | Sort-Object Lines -Descending | Select-Object -First 15 | Format-Table Lines, File -AutoSize
```

## B4. Testing & Infrastructure

### Test suite stats
```powershell
$testFiles = Get-ChildItem -Recurse -File -Filter *.py -Path "unit_tests" | Where-Object { $_.FullName -notmatch '\\__pycache__\\' }; $testFunctions = 0; foreach ($f in $testFiles) { $testFunctions += (Get-Content $f.FullName -ErrorAction SilentlyContinue | Select-String '^\s*def\s+test_').Count }; $testLines = ($testFiles | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count } | Measure-Object -Sum).Sum; Write-Host "Files: $($testFiles.Count) | Functions: $testFunctions | Lines: $testLines"
```

### Infrastructure counts
```powershell
$dockerfiles = (Get-ChildItem -Recurse -File -Filter Dockerfile* | Measure-Object).Count; $composeFiles = (Get-ChildItem -Recurse -File -Filter docker-compose* | Measure-Object).Count; $migrations = (Get-ChildItem -Recurse -File -Filter *.py -Path "alembic\versions" -ErrorAction SilentlyContinue | Measure-Object).Count; $shellScripts = (Get-ChildItem -Recurse -File -Filter *.sh | Where-Object { $_.FullName -notmatch '\\\.venv\\' } | Measure-Object).Count; Write-Host "Dockerfiles: $dockerfiles | Compose: $composeFiles | Migrations: $migrations | Shell: $shellScripts"
```

### Agent infrastructure
```powershell
$rules = (Get-ChildItem -Recurse -File -Path ".agents\rules" -ErrorAction SilentlyContinue | Measure-Object).Count; $skills = (Get-ChildItem -Directory -Path ".agents\skills" -ErrorAction SilentlyContinue | Measure-Object).Count; $workflows = (Get-ChildItem -File -Path ".agents\workflows" -Filter *.md -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Host "Rules: $rules | Skills: $skills | Workflows: $workflows"
```

### Debug tooling
```powershell
$debugScripts = Get-ChildItem -Recurse -File -Path "debugging\scripts" -Include *.py,*.sql,*.sh -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '\\__pycache__\\' }; $debugLines = ($debugScripts | ForEach-Object { (Get-Content $_.FullName -ErrorAction SilentlyContinue | Measure-Object).Count } | Measure-Object -Sum).Sum; Write-Host "Scripts: $($debugScripts.Count) | Lines: $debugLines"
```

## B5. Git History

### Total commits and project age
```powershell
$totalCommits = (git log --oneline | Measure-Object).Count; $firstCommit = git log --reverse --format="%ai" | Select-Object -First 1; $branches = (git branch -a | Measure-Object).Count; Write-Host "Commits: $totalCommits | First: $firstCommit | Branches: $branches"
```

### Commit frequency (last 6 months)
```powershell
git log --since="$((Get-Date).AddMonths(-6).ToString('yyyy-MM-01'))" --format="%ai" | ForEach-Object { $_.Substring(0,7) } | Group-Object | Sort-Object Name | Format-Table Count, Name -AutoSize
```

### Directory structure with file counts
```powershell
Get-ChildItem -Directory | Where-Object { $_.Name -notmatch '^\.(git|venv|mypy_cache|pytest_cache)$' -and $_.Name -ne '__pycache__' -and $_.Name -ne 'node_modules' } | ForEach-Object { $dir = $_.Name; $count = (Get-ChildItem -Recurse -File -Path $_.FullName | Where-Object { $_.FullName -notmatch '\\(\.git|__pycache__|\.venv|alembic\\versions)\\' }).Count; $pyCount = (Get-ChildItem -Recurse -File -Filter *.py -Path $_.FullName | Where-Object { $_.FullName -notmatch '\\__pycache__\\' }).Count; $sqlCount = (Get-ChildItem -Recurse -File -Filter *.sql -Path $_.FullName | Where-Object { $_.FullName -notmatch '\\__pycache__\\' }).Count; [PSCustomObject]@{Directory=$dir; TotalFiles=$count; Python=$pyCount; SQL=$sqlCount} } | Sort-Object TotalFiles -Descending | Format-Table -AutoSize
```

## B6. Build the Codebase Report Artifact

Create an artifact with:

### Required Sections

1. **Executive Summary** — Total lines, files, commits, project age in one glance
2. **Lines of Code Breakdown** — Table by language with %, visual bar chart (ASCII)
3. **Architecture Inventory**:
   - Python symbols (classes, functions, models, workers)
   - SQL objects (procedures, functions, views, mat views, triggers)
   - Collector services list
4. **Directory Structure** — Table with directory, total files, Python count, SQL count, purpose
5. **Testing** — Test files, functions, lines, test-to-code ratio
6. **Infrastructure & DevOps** — Docker, shell scripts, migrations, commit guardian, agent config
7. **Debug Tooling** — Script count and line count
8. **Complexity Hotspots**:
   - File size distribution (>200, >500, >1000 lines)
   - Top 10 largest Python files with risk rating
   - Top 10 largest SQL files with risk rating
9. **Development Velocity** — Monthly commit trend (last 6 months) with ASCII visualization
10. **System Complexity Score** — Overall rating (Low/Medium/Medium-High/High) with per-dimension breakdown
11. **Industry Comparison** — Table comparing Brain Trader metrics against typical solo project and small team baselines

### Industry Comparison Baselines
Use these reference points:

| Metric | Solo Project | Small Team (3-5) |
|---|---|---|
| Lines of Code | 5–20K | 100–500K |
| SQL Objects | 5–15 | 50–200 |
| DB Models | 3–8 | 20–60 |
| Workers | 0–2 | 5–15 |
| Tests | 10–50 | 200–1000 |
| Documentation | 500–2K lines | 10–30K |

---

# PHASE 3: EXECUTIVE SUMMARY IN CHAT

After creating the report artifact, provide a concise executive summary in chat.

### For Activity Reports:
```
## 📊 Activity Report — Executive Briefing

**Period:** [start] → [end]
**Commits:** [N] ([feature] feature + [merge] merges)
**Lines:** +[added] / -[deleted] (net [net])
**Files:** [touched] touched | [new] new | [deleted] deleted

### Work Streams
1. [Stream 1] — [1-line summary] (🔴/🟡/🟢)
2. [Stream 2] — [1-line summary] (🔴/🟡/🟢)
...

### Cross-Functional Team Equivalent: [X–Y] working weeks for a team of [Z]
```

### For Codebase Reports:
```
## 🏛️ Codebase Report — Executive Briefing

**Total:** [X]K lines | [Y] files | [Z] commits over [N] months
**Python:** [X]K lines ([Y] classes, [Z] functions)
**SQL:** [X]K lines ([Y] objects)
**Tests:** [X] functions | Docs: [X]K lines

### Complexity: [RATING]
- [Top 3 complexity observations]

### Tech Debt Hotspots
- [Top 3 files that need attention]
```

Keep the chat summary to ~15 lines. The full detail is in the artifact.

# RULES
- All commands run from the project root.
- Use PowerShell syntax (this is Windows).
- Exclude `.git`, `__pycache__`, `.venv`, `node_modules`, `.mypy_cache`, `.pytest_cache`, `alembic\versions` from all file scans.
- Round percentages to 1 decimal place.
- Use emoji indicators (🟢🟡🔴) for visual scanning in complexity assessments.
- If the user asks for "both" modes, combine into a single artifact with clear section headers.
- Always include the current UTC timestamp in the report header.
- For the time estimate, state assumptions clearly (e.g., "assumes familiarity with codebase and domain").
