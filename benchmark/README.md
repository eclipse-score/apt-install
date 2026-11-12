# Scheduled installation benchmark

The workflow runs hourly at minute 17 and can also be dispatched manually.
GitHub may delay scheduled runs. Use the recorded UTC timestamps for analysis
by hour of day. Allow at least two weeks before drawing conclusions about tails.
Schedules run from the default branch after the workflow is merged there.

Each run measures Graphviz installation eight ways on fresh Ubuntu 24.04 runners:

| Method | Without apt update | With apt update |
|---|---|---|
| `apt-get install -y --no-install-recommends graphviz` | yes | yes |
| This action, cache disabled | yes | yes |
| This action, cache miss | yes | yes |
| This action, cache hit | yes | yes |

The uncached apt baseline keeps the runner's man-db configuration. The action
uses its default `mandb: false`. The benchmark therefore measures any remaining
benefit of this handling instead of disabling it in the baseline too.

Each cache miss seeds a unique cache for this run, attempt and update setting.
The corresponding cache-hit job runs afterward on a new runner. Instrumentation
in a temporary copy of `action.yml` forwards an upstream cache version and
exposes the observed cache result and package versions; the published action
is unchanged. Unexpected hits/misses are failures, not speed measurements.

The cache backend currently ignores `recommends: false`. It can install additional
packages, and may refresh package lists internally even with `apt_update: false`.
These variants deliberately measure actual action behavior. The JSON
records cached package versions, the Graphviz version, available apt versions,
runner image/version, commit, timestamp, duration and failures. Each installation
must render a small SVG. A preinstalled Graphviz causes the measurement to fail
rather than silently measuring a no-op.

Timing uses a monotonic clock and includes action steps, cache restore/save and
step transitions. It excludes checkout, action downloads, verification and runner
provisioning. Jobs have a 15-minute timeout. Failed installations are counted
separately from successful durations; timeouts can leave incomplete measurements,
which the summary flags. Warm-cache jobs start later than their seed jobs, so use
the individual timestamps rather than assuming all variants start simultaneously.

Every job uploads its raw JSON as a `benchmark-raw-*` artifact. The summary reads
the latest `benchmark-history` artifact on the same branch, appends the new rows
without duplicates, and uploads cumulative JSON, CSV and a Markdown report.
Artifacts are retained for 90 days; each cumulative artifact carries older data
forward while the experiment remains active. No measurement history depends on
an evictable Actions cache. API failures fail the summary instead of silently
discarding history. Workflow runs are serialized to avoid concurrent history updates.

The Actions summary reports the last 14 days: sample count, failures, mean,
median, nearest-rank p95 and the fraction strictly above 60 seconds. Use JSON/CSV
to split results by runner image or UTC hour before interpreting differences.

Download a cumulative result with:

```sh
gh run download RUN_ID --repo eclipse-score/apt-install --name benchmark-history
```

To rebuild a report offline from downloaded raw artifacts:

```sh
python3 benchmark/benchmark.py summarize path/to/raw-artifacts
```

The summary needs only Python's standard library; restoring history additionally
uses the preinstalled `gh` CLI with the workflow token's `actions: read` permission.
