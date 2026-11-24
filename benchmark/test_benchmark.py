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

"""Regression coverage for misleading cache results and statistical reporting."""

from contextlib import chdir
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import benchmark


def observation(duration=10, outcome="success", **extra):
    return dict(
        schema=1, run_id="123", attempt="1", method="plain", apt_update="false",
        recorded_at=datetime.now(timezone.utc).isoformat(),
        duration_seconds=duration, outcome=outcome, **extra,
    )


class BenchmarkTest(unittest.TestCase):
    def test_warm_retry_uses_latest_seed_attempt_and_prepares_without_installing(self):
        source = Path(__file__).resolve().parents[1].joinpath("action.yml").read_text()
        env = dict(METHOD="cache-hit", APT_UPDATE="false", GITHUB_RUN_ID="123",
                   GITHUB_RUN_ATTEMPT="4", GITHUB_REPOSITORY="owner/repo")

        def download(args, **kwargs):
            directory = Path(args[-1])
            for attempt in (1, 3):
                seed = directory / str(attempt)
                seed.mkdir()
                (seed / "benchmark-result.json").write_text(json.dumps({"attempt": str(attempt)}))

        with tempfile.TemporaryDirectory() as directory, chdir(directory), \
                patch.dict(os.environ, env), patch.object(benchmark.subprocess, "run", side_effect=download):
            Path("action.yml").write_text(source)
            benchmark.prepare()
            self.assertIn('version: "benchmark-v1-123-3-false"',
                          Path(".benchmark-action/action.yml").read_text())
            dependencies = Path(".benchmark-dependencies/action.yml").read_text()
            self.assertIn("uses: awalsh128/cache-apt-pkgs-action@v1.4.3", dependencies)
            conditions = [line.strip() for line in dependencies.splitlines() if line.strip().startswith("if:")]
            self.assertEqual(conditions, ["if: ${{ false }}"] * 4)
            self.assertFalse(Path("benchmark-start.json").exists())

    def test_history_on_second_page_is_restored_for_its_branch(self):
        unrelated = {"id": 200, "expired": False, "workflow_run": {"head_branch": "other"}}
        retained = {"id": 1, "expired": False, "workflow_run": {"head_branch": "main", "id": 123}}
        pages = [{"artifacts": [unrelated] * 100}, {"artifacts": [retained]}]

        def download(args, **kwargs):
            self.assertIn("123", args)
            Path(args[-1], "benchmark-history.json").write_text(json.dumps([observation()]))

        with patch.dict(os.environ, GITHUB_REPOSITORY="owner/repo", GITHUB_REF_NAME="main"), \
                patch.object(benchmark, "command", return_value=json.dumps(pages)) as api, \
                patch.object(benchmark.subprocess, "run", side_effect=download):
            self.assertEqual(len(benchmark.restore_history()), 1)
            self.assertIn("--paginate", api.call_args.args)
            self.assertIn("--slurp", api.call_args.args)

    def test_even_sample_median_and_nearest_rank_p95_exclude_failed_installs(self):
        rows = [observation(d) for d in (1, 2, 60, 100)]
        rows.append(observation(999, "failure"))
        report = benchmark.summary(rows)
        self.assertIn("| false | plain | 4 | 1 | 40.75 | 31.00 | 100.00 | 25.0% |", report)

    def test_summary_limits_window_without_erasing_retained_history(self):
        old = observation(999)
        old["recorded_at"] = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        report = benchmark.summary([old, observation(5)])
        self.assertIn("| false | plain | 1 | 0 | 5.00 | 5.00 | 5.00 | 0.0% |", report)

    def test_unexpected_cache_miss_is_persisted_as_failure(self):
        env = dict(METHOD="cache-hit", CACHE_HIT="false", APT_UPDATE="false",
                   INSTALL_OUTCOME="success", GITHUB_RUN_ID="123", GITHUB_RUN_ATTEMPT="1",
                   GITHUB_SHA="abc")
        with tempfile.TemporaryDirectory() as directory, chdir(directory), patch.dict(os.environ, env), \
                patch.object(benchmark, "command", return_value="candidate"), \
                patch.object(benchmark.subprocess, "run", return_value=subprocess.CompletedProcess(
                    [], 0, stdout="<svg></svg>", stderr="dot version")):
            Path("benchmark-start.json").write_text(json.dumps({
                "started_at": "2026-01-01T00:00:00+00:00", "monotonic_ns": 0,
            }))
            with self.assertRaisesRegex(RuntimeError, "unexpected cache result"):
                benchmark.record()
            row = json.loads(Path("benchmark-result.json").read_text())
            self.assertEqual(row["outcome"], "failure")
            self.assertEqual(row["cache_hit"], "false")

    def test_summary_retry_deduplicates_and_preserves_history(self):
        row = observation()
        older = observation(20)
        older["run_id"] = "122"
        with tempfile.TemporaryDirectory() as directory, chdir(directory), \
                patch.object(benchmark, "restore_history", return_value=[older, row]):
            Path("raw").mkdir()
            Path("raw/benchmark-result.json").write_text(json.dumps(row))
            benchmark.summarize("raw", True)
            history = json.loads(Path("benchmark-history.json").read_text())
            self.assertEqual(len(history), 2)
            self.assertEqual({r["run_id"] for r in history}, {"122", "123"})
            self.assertIn("received 1 of 8", Path("benchmark-summary.md").read_text())

    def test_retry_keeps_both_attempts_without_flagging_complete_variants_as_missing(self):
        rows = []
        for method in ("plain", "action-no-cache", "cache-miss", "cache-hit"):
            for update in ("false", "true"):
                rows.append({**observation(), "method": method, "apt_update": update})
        rows.extend({**row, "attempt": "2"} for row in rows[-2:])
        with tempfile.TemporaryDirectory() as directory, chdir(directory):
            for index, row in enumerate(rows):
                path = Path("raw", str(index))
                path.mkdir(parents=True)
                (path / "benchmark-result.json").write_text(json.dumps(row))
            benchmark.summarize("raw", False)
            self.assertEqual(len(json.loads(Path("benchmark-history.json").read_text())), 10)
            self.assertNotIn("WARNING", Path("benchmark-summary.md").read_text())


if __name__ == "__main__":
    unittest.main()
