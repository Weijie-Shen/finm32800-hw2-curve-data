"""Prepare public inputs for PR 191 in an isolated ChartBook store.

Run with Python 3.12 and uv/git on PATH. This invokes pinned public upstream
code; inspect those repositories before running. It never changes a pin, uses
the author's existing store, or publishes raw data. Full-store/lineage gaps
are recorded separately from verification of the report's actual inputs.
"""

import argparse
import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path


def run(command, cwd, env, log=None, check=True):
    print("Running:", " ".join(map(str, command)), flush=True)
    if log:
        with log.open("w") as stream:
            result = subprocess.run(
                command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, check=False
            )
    else:
        result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log or 'output above'}")
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument(
        "--work",
        required=True,
        type=Path,
        help="New, empty directory for upstream clones, environment, store and logs",
    )
    args = parser.parse_args()
    report = args.report.resolve()
    work = args.work.resolve()
    if work.exists() and any(work.iterdir()):
        parser.error("--work must be empty; choose a new directory to avoid hidden cached inputs")
    work.mkdir(parents=True, exist_ok=True)
    original_lock = (report / "chartbook.lock").read_bytes()
    lock = json.loads(original_lock)
    records = {r["id"]: r for r in lock["records"]}
    deps = {d["id"]: d for d in records[lock["root"]]["dependencies"]}
    expected_commits = {
        "ftsfr/fed_yield_curve": "5bb7217c30f422bab5c9b87e3fc3410461ea4391",
        "ftsfr/ken_french_data_library": "31f1e3467c7f6f830b77336423b2160a6e33dfc9",
    }
    for name, commit in expected_commits.items():
        if deps[name]["location"]["commit"] != commit:
            raise RuntimeError(f"{name} pin has changed; review the setup recipe before using it")
    env = dict(os.environ)
    env.update(
        CHARTBOOK_STORE=str(work / "store"),
        CHARTBOOK_GIT_CACHE=str(work / "git-cache"),
        MPLCONFIGDIR=str(work / "matplotlib"),
        PYTHONUNBUFFERED="1",
    )
    # Clear any caller-selected working-file links; only pinned assets may be read.
    env["CHARTBOOK_BATCH"] = "1"
    run(["uv", "sync", "--locked"], report, env, work / "report_environment.log")
    run(["uv", "venv", "--python", "3.12", str(work / "upstream-env")], report, env)
    python = work / "upstream-env" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "chartbook==0.5.1",
            "numpy==1.26.4",
            "pandas==2.2.3",
            "pyarrow==20.0.0",
            "requests==2.32.3",
        ],
        report,
        env,
        work / "upstream_environment.log",
    )
    for name, commit in expected_commits.items():
        folder = work / name.split("/")[1]
        run(["git", "clone", deps[name]["location"]["repository"], str(folder)], report, env)
        run(["git", "checkout", "--detach", commit], folder, env)
        if name.endswith("fed_yield_curve"):
            run([str(python), "src/pull_fed_yield_curve.py"], folder, env, work / "fed_pull.log")
            # Restore the pinned historical vintage BEFORE melt/sort/dropna:
            # filtering the final long table retains different pandas indices.
            # The exact expected hash below must match, otherwise stop.
            code = (
                "import pandas as pd; from pathlib import Path; "
                "p=Path('_data/fed_yield_curve.parquet'); d=pd.read_parquet(p); "
                "d.loc[:'2026-10-30'].to_parquet(p)"
            )
            run([str(python), "-c", code], folder, env)
        else:
            run(
                [str(python), "src/pull_fama_french_25_portfolios.py"],
                folder,
                env,
                work / "french_pull.log",
            )
        run(
            [str(python), "src/create_ftsfr_datasets.py"],
            folder,
            env,
            work / (folder.name + "_transform.log"),
        )
        for record in records.values():
            if record.get("pipeline") != name or record.get("kind") != "Dataframe":
                continue
            path = folder / record["location"]["path"]
            actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != record["content_hash"]:
                raise RuntimeError(
                    f"Historical hash mismatch for {record['id']}: {actual}; "
                    "do not update pins or bypass the check"
                )
            print("Verified rebuilt bytes:", record["id"], actual, flush=True)
        run(
            [
                str(python.parent / ("chartbook.exe" if os.name == "nt" else "chartbook")),
                "snapshot",
                "--no-gc-reminder",
            ],
            folder,
            env,
            work / (folder.name + "_snapshot.log"),
        )
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=folder).strip():
            raise RuntimeError(f"Upstream source was modified: {folder}")
    # For already-pinned git dependencies this fetches the recorded commits,
    # not the latest branch tips. Unused FTSFR assets can still cause exit 1.
    pin_exit = run(
        ["uv", "run", "--locked", "chartbook", "pin"], report, env, work / "pin.log", check=False
    )
    if (report / "chartbook.lock").read_bytes() != original_lock:
        raise RuntimeError("Unexpected lockfile change; inspect the diff before proceeding")
    if pin_exit not in (0, 1):
        raise RuntimeError(f"Unexpected pin exit {pin_exit}; see pin.log")
    refs = set()
    for path in (report / "src/exhibits").glob("*.py"):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "UPSTREAM" for t in node.targets
            ):
                refs.update(ast.literal_eval(node.value))
    # FRED is the report's own pull, built by doit. Every external input must
    # resolve inside this isolated store and match its lockfile hash.
    code = """
import hashlib, json, os
from pathlib import Path
from chartbook import data
root=Path(os.environ['CHARTBOOK_STORE']).resolve()
lock=json.loads(Path('chartbook.lock').read_text())
records={r['id']:r for r in lock['records']}
for ref in json.loads(os.environ['REVIEW_REFS']):
    if ref == 'fred': continue
    p=Path(data.path(ref)).resolve()
    assert p.is_relative_to(root), (ref,p,root)
    digest='sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
    assert digest == records[ref]['content_hash'], ref
    print(ref, digest, flush=True)
"""
    env["REVIEW_REFS"] = json.dumps(sorted(refs))
    run(["uv", "run", "--locked", "python", "-c", code], report, env, work / "verified_inputs.log")
    frozen_exit = run(
        ["uv", "run", "--locked", "chartbook", "pin", "--frozen"],
        report,
        env,
        work / "frozen.log",
        check=False,
    )
    lineage_exit = run(
        ["uv", "run", "--locked", "chartbook", "lineage"],
        report,
        env,
        work / "lineage.log",
        check=False,
    )
    status = {
        "report_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=report, text=True
        ).strip(),
        "external_inputs_verified": sorted(refs - {"fred"}),
        "lockfile_unchanged": True,
        "pin_exit": pin_exit,
        "frozen_exit": frozen_exit,
        "lineage_exit": lineage_exit,
        "note": "Read lineage.log: its exit code can be zero even when gaps are reported.",
    }
    (work / "setup_results.json").write_text(json.dumps(status, indent=2) + "\n")
    print("All external inputs used by this report match their pins in the isolated store.")
    print("Full-store frozen exit:", frozen_exit, "(zero means passed). See frozen.log.")
    print("Lineage audit: read lineage.log; a zero exit does not guarantee no gaps.")
    print("Build with CHARTBOOK_STORE set to", work / "store")


if __name__ == "__main__":
    main()
