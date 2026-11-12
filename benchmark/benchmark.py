# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

#!/usr/bin/env python3
"""Measure the real action on hosted runners and retain independently usable data."""

import argparse
import csv
import io
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time
from datetime import datetime, timedelta, timezone
import zipfile

SCHEMA = 1


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def prepare():
    """Instrument a disposable copy, keeping the published action unchanged."""
    source = Path("action.yml").read_text()
    anchor = "    - name: Install packages with cache\n"
    packages = "        packages: ${{ inputs.packages }}\n"
    if source.count(anchor) != 1 or source.count(packages) != 1:
        raise RuntimeError("Update benchmark instrumentation for the current action")
    # The seed must miss, and the second job restores it on a fresh runner.
    version = "benchmark-v1-{}-{}-{}".format(
        os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"],
        os.environ["APT_UPDATE"],
    )
    source = source.replace(anchor, anchor + "      id: benchmark-cache\n")
    source = source.replace(packages, packages + f'        version: "{version}"\n')
    source = source.replace(
        "runs:\n", "outputs:\n  cache-hit:\n    description: Observed upstream cache result\n"
        "    value: ${{ steps.benchmark-cache.outputs.cache-hit }}\n"
        "  package-versions:\n    description: Cached package versions\n"
        "    value: ${{ steps.benchmark-cache.outputs.all-package-version-list }}\nruns:\n", 1,
    )
    Path(".benchmark-action").mkdir(exist_ok=True)
    Path(".benchmark-action/action.yml").write_text(source)


def start():
    # A preinstalled package would turn a measurement into a misleading no-op.
    installed = subprocess.run(
        ["dpkg-query", "-W", "-f=${Status}", "graphviz"],
        capture_output=True, text=True,
    )
    if "install ok installed" in installed.stdout:
        raise RuntimeError("graphviz is already installed on this runner image")
    Path("benchmark-start.json").write_text(json.dumps({
        "started_at": datetime.now(timezone.utc).isoformat(),
        "monotonic_ns": time.monotonic_ns(),
    }))


def record():
    # End timing before verification; include cache save and action overhead.
    end = time.monotonic_ns()
    start_path = Path("benchmark-start.json")
    started = json.loads(start_path.read_text()) if start_path.exists() else {}
    method = os.environ["METHOD"]
    hit = os.environ.get("CACHE_HIT", "")
    errors = []
    if not started:
        errors.append("measurement did not start")
    if os.environ.get("INSTALL_OUTCOME") != "success":
        errors.append("installation step did not succeed")
    if method in ("cache-hit", "cache-miss"):
        if hit != ("true" if method == "cache-hit" else "false"):
            errors.append(f"unexpected cache result: {hit!r}")
    version = ""
    try:
        # File-only cache restores need not register packages with dpkg. Exercise
        # the tool and a plugin-backed render rather than relying on dpkg status.
        result = subprocess.run(["dot", "-V"], capture_output=True, text=True, check=True)
        version = (result.stdout + result.stderr).strip()
        rendered = subprocess.run(
            ["dot", "-Tsvg"], input="digraph { a -> b }", text=True,
            capture_output=True, check=True,
        )
        if "<svg" not in rendered.stdout:
            raise RuntimeError("Graphviz did not produce SVG")
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        errors.append(str(exc))
    row = {
        "schema": SCHEMA,
        "run_id": os.environ["GITHUB_RUN_ID"],
        "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "sha": os.environ["GITHUB_SHA"],
        "started_at": started.get("started_at"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "apt_update": os.environ["APT_UPDATE"],
        "runner_image": os.environ.get("ImageOS", ""),
        "runner_image_version": os.environ.get("ImageVersion", ""),
        "duration_seconds": ((end - started["monotonic_ns"]) / 1e9) if started else None,
        "cache_hit": hit,
        "outcome": "failure" if errors else "success",
        "errors": errors,
        "graphviz_version": version,
        "apt_policy": command("apt-cache", "policy", "graphviz"),
        "cached_package_versions": os.environ.get("PACKAGE_VERSIONS", ""),
    }
    Path("benchmark-result.json").write_text(json.dumps(row, indent=2) + "\n")
    if errors:
        raise RuntimeError("; ".join(errors))


def restore_history():
    """Read the latest history artifact; API errors must be visible."""
    repository = os.environ["GITHUB_REPOSITORY"]
    response = json.loads(command(
        "gh", "api", f"repos/{repository}/actions/artifacts?name=benchmark-history&per_page=100",
    ))
    artifacts = [
        a for a in response["artifacts"] if not a["expired"]
        and a["workflow_run"]["head_branch"] == os.environ["GITHUB_REF_NAME"]
    ]
    if not artifacts:
        return []
    latest = max(artifacts, key=lambda a: a["id"])
    archive = subprocess.check_output([
        "gh", "api", f"repos/{repository}/actions/artifacts/{latest['id']}/zip",
    ])
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        return json.loads(zipped.read("benchmark-history.json"))


def summary(rows):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    rows = [r for r in rows if r["recorded_at"] >= cutoff]
    lines = [
        "# APT installation benchmark", "",
        "Rolling window: last 14 days. All retained observations are available in JSON/CSV.",
        "Successful installations only contribute to durations; failures are listed separately.",
        "Cache hit and miss are verified. p95 uses the nearest-rank method.", "",
        "| Update | Method | Success | Failed | Mean (s) | Median (s) | p95 (s) | >60 s |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for update in ("false", "true"):
        for method in ("plain", "action-no-cache", "cache-miss", "cache-hit"):
            group = [r for r in rows if r["apt_update"] == update and r["method"] == method]
            values = sorted(r["duration_seconds"] for r in group if r["outcome"] == "success")
            failed = len(group) - len(values)
            metrics = "- | - | - | -"
            if values:
                metrics = (
                    f"{statistics.mean(values):.2f} | {statistics.median(values):.2f} | "
                    f"{values[math.ceil(.95 * len(values)) - 1]:.2f} | "
                    f"{100 * sum(v > 60 for v in values) / len(values):.1f}%"
                )
            lines.append(f"| {update} | {method} | {len(values)} | {failed} | {metrics} |")
    lines += [
        "", "Timing excludes checkout, action download and runner provisioning.",
        "Plain apt keeps the runner's man-db settings; the action uses its default mandb=false.",
        "The cache backend currently installs recommended packages despite recommends=false;",
        "these rows compare actual action behavior rather than identical package sets.",
        "Runner images and package metadata are retained in the JSON for stratified analysis.",
    ]
    return "\n".join(lines) + "\n"


def summarize(directory, restore):
    history = restore_history() if restore else []
    current = [json.loads(p.read_text()) for p in Path(directory).rglob("benchmark-result.json")]
    if not current:
        raise RuntimeError("No measurements found")
    # A retried summary must not count the same observations twice.
    by_key = {
        (r["run_id"], r["attempt"], r["method"], r["apt_update"]): r
        for r in history + current if r["schema"] == SCHEMA
    }
    rows = sorted(by_key.values(), key=lambda r: r["recorded_at"])
    Path("benchmark-history.json").write_text(json.dumps(rows, indent=2) + "\n")
    # The verbose apt policy stays in JSON; the CSV is convenient for plotting.
    fields = [k for k in rows[0] if k != "apt_policy"]
    with Path("benchmark-history.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    report = summary(rows)
    if len(current) != 8:
        report += f"\nWARNING: received {len(current)} of 8 expected measurements in this run.\n"
    Path("benchmark-summary.md").write_text(report)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
            stream.write(report)
    print(report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    for operation in ("prepare", "start", "record"):
        sub.add_parser(operation)
    report = sub.add_parser("summarize")
    report.add_argument("directory")
    report.add_argument("--restore-history", action="store_true")
    args = parser.parse_args()
    if args.operation == "summarize":
        summarize(args.directory, args.restore_history)
    else:
        globals()[args.operation]()
