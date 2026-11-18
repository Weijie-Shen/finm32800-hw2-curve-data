# Reproduce class-report PR 191

This guide prepares the external inputs read by the class report at merge
commit `e7d8944`. It is supporting material for
<https://github.com/finm-32800/finm_midterm_report/pull/191>, not a replacement
for the course README. It does not change the report's pins.

## Requirements

- Git and access to the private class-report repository.
- uv and Python 3.12 (uv can install Python).
- XeLaTeX/latexmk with Source Sans and Source Code Pro fonts; full MacTeX
  or TeX Live is the simplest setup.
- Network access to GitHub, FRED, the Federal Reserve, and Ken French's library.

No WRDS account is needed to read this exhibit's published derived curves.
Other assets declared in the full report catalog may require licensed sources
if you choose to rebuild them; that is separate from the actual report inputs.

## Fresh clone and isolated data setup

Run the following from a new parent directory. These commands are for macOS/Linux;
Windows users can run the Python helper and set the environment variables using
PowerShell syntax instead of `export`.

```bash
git clone --branch Weijie-Shen/treasury_curve_fit https://github.com/finm-32800/finm_midterm_report.git report-review
git clone --branch reviewer-setup https://github.com/Weijie-Shen/finm32800-hw2-curve-data.git review-tools
uv run --python 3.12 python review-tools/prepare_review.py --report report-review --work review-inputs
```

Inspect `prepare_review.py` and the public upstreams before running them.
The helper invokes upstream code in fresh checkouts, installs the versions
needed to reproduce Parquet bytes, and downloads public source data anew.
The work directory must be new/empty. It selects its own ChartBook store and
git cache, so an existing store cannot make an incomplete setup appear to work.

The helper:

1. Checks out the exact Fed and French commits in the report lockfile.
2. Runs their public pulls and transformations. For the Fed input it selects
   observations through October 30, 2026 **before** the upstream wide-to-long
   transformation. This reproduces the historical vintage, including the
   pandas index, rather than substituting today's longer series.
3. Checks every rebuilt dataframe against its recorded SHA-256. Historical
   revisions or a different serialization produce a hard failure, not a new pin.
4. Makes new local snapshots using the ChartBook CLI. It does not fabricate the
   original snapshot's timestamp or copy objects from someone else's store.
5. Fetches the public git dependencies at their already-pinned commits using
   `chartbook pin`, and asserts that the lockfile bytes did not change.
6. Resolves and rehashes every external dataframe actually declared in the
   report's exhibit scripts, requiring each path to be in the isolated store.
7. Records the full-store and lineage audits separately in `frozen.log` and
   `lineage.log`. These broader checks can fail even when the actual report
   inputs are all verified; see the limitation below.

The expected Fed dataframe hash is
`4c04214626a01006a131ff11fa391453a52c6f1dc15d5daede2d7704642a2506`.
The helper refuses different Fed/French source commits so a future main update
cannot silently use an obsolete recipe.

## Build and inspect

From the same parent directory:

```bash
export CHARTBOOK_STORE="$PWD/review-inputs/store"
export CHARTBOOK_GIT_CACHE="$PWD/review-inputs/git-cache"
export CHARTBOOK_BATCH=1
cd report-review
uv run --locked doit
uv run --locked doit
uv run --locked pytest tests -k treasury_curve_fit
uv run --locked ruff format --check .
uv run --locked ruff check .
git diff --exit-code -- chartbook.toml chartbook.lock
```

On a Mac with multiple TeX installations, first use
`export PATH="/Library/TeX/texbin:$PATH"`.

The first `doit` must build the full PDF and site, and run the tests. The second
should do no work. Inspect `reports/class_report.pdf` and `docs/index.html`.
Find the section titled **An independent fit confirms the flattening**; page
and exhibit numbers change as classmates' sections are merged.

The exhibit-specific tests should pass. Compare the printed figures with the
write-up: March-to-September two-year yield +105.37 bp; ten-year +86.96 bp;
2–10-year slope change −18.40 bp, versus −16.27 bp for the Fed; maximum absolute
gap 4.05 bp; wider-bound sensitivity below 0.3 bp.

## Full-catalog limitation — not a passing check

This setup prepares **all inputs used by the report**, not every asset declared
by all six legacy FTSFR dependencies. The inherited lock also pins 30 assets
not consumed by the current exhibits: 13 dataframes, 10 charts, and 7 notebooks.
Consequently, `uv run chartbook pin --frozen` remains nonzero in this isolated
store. Read the exact asset list in `review-inputs/frozen.log`.
We also audited main's unmodified manifest and lock against the same isolated
store: its missing-asset set is exactly the same 30 assets. Our added dependency
introduces no additional missing assets.

`chartbook lineage` additionally looks for the original six snapshot records,
including their creation timestamps. Newly rebuilt, hash-identical files do
not recreate those records. Its command may return zero while printing gaps;
read `review-inputs/lineage.log` rather than relying on the exit code.

To satisfy the README's complete-store/no-gaps checks, obtain the original
matching snapshots through an authorized ChartBook store transfer, or ask the
maintainer for a coordinated update to reproducibly rebuilt snapshots. Do not
delete classmates' dependencies, modify hashes, or relabel new snapshots as old
ones. This PR preserves the existing pins and does not claim these broader
checks pass. No third-party data or snapshot records are supplied in this helper.

## What the reviewer records

Validation on November 17, 2026: a fresh report clone at `e7d8944`, a new
upstream environment, new upstream clones, a new git cache, and an empty
ChartBook store completed this setup. All 12 external input dataframes matched
the report pins. The full report/site build passed all 305 tests; the separate
exhibit command passed 17 tests. Ruff lint/format checks passed. The 36-page
report places this complete section on page 23; it was visually checked.
The second full `doit` run performed no work, and the fresh report checkout
remained clean.
The full-store check still reported the same 30 missing assets as main, and
lineage reported 36 gaps (those assets plus six original snapshot records).

Only after your own build succeeds, include this in your GitHub review:

> I cloned this branch fresh and `uv run doit` built the report with this exhibit.
>
> 1. [Your substantive comment on the exhibit or write-up.]
> 2. [Your second substantive comment.]

Also check the PR's Files changed tab: the dependency diff should add only
Weijie-Shen's dependency and its two dataframe records relative to current main.
The report reads only `treasury_curve_fits`; `fit_diagnostics` is published by
the same upstream and is pinned with it. Existing main records must be unchanged.
Mention any store/lineage limitations you encountered instead of claiming those
checks passed. Approval and the substantive review are the reviewer's own work.
