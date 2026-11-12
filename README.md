# Installing packages... the convenient way

## Why use this action?

Just running `apt install` in a GitHub Actions workflow is not the best way to
install packages. It can be slow. Really really slow. Using this action will
speed up the installation of packages via `apt`.

### Example

Installing graphviz with different methods:


| Method | Mean (s) | Median (s) | 30–60s | >60s |
|--------|----------|------------|--------|------|
| apt install graphviz | 🔴 26.0 | 🟡 20.0 | 1,4% | 9,5% |
| via this action | 🟢 6.5 | 🟢 6.0 | 0 | 0 |


## How to use

Add the following step to your GitHub Actions workflow to install packages via `apt`:

```yaml
    - name: Install dependencies
      uses: eclipse-score/apt-install@main
      with:
        packages: dia doxygen doxygen-doc doxygen-gui doxygen-latex graphviz mscgen
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `packages` | A space-separated list of packages to install via `apt`. | *required* |
| `cache` | Use a cache to speed up the installation. See also [Caching Caveats](https://github.com/awalsh128/cache-apt-pkgs-action#caveats) | `true` |
| `mandb` | Update the `mandb` database after installing packages. | `false` |
| `apt_update` | Run `apt update` before installing packages. | `false` |
| `recommends` | Install recommended dependencies. | `false` |

## Why yet another action?

While it's true that there are already several actions that install packages via `apt`, none quite matches our expectations.
We wanted an action that is fast, efficient, and easy to use. This action is designed to be a drop-in replacement for `apt install` in GitHub Actions workflows, while allowing all the flexibility you need.

## Measurements in Detail

Installing graphviz 375 times every 10 minutes with different methods, measuring the time it takes to install the package.

| Method | Mean (s) | Median (s) | 30–60s | >60s |
|--------|----------|------------|--------|------|
| Install via setup-graphviz action | 🔴 27.5 | 🔴 23.0 | 1.1% | 9.1% |
| Install via apt | 🔴 26.5 | 🟡 20.0 | 1.3% | 9.9% |
| Install via setup-graphviz action, no apt update | 🔴 24.5 | 🟡 17.0 | 4.3% | 10.1% |
| Install via apt, no apt update, no recommends | 🔴 23.5 | 🟡 14.0 | 4.8% | 10.7% |
| Download and install .deb files | 🔴 23.2 | 🟡 17.0 | 3.5% | 8.0% |
| Get .deb files from GitHub cache and install them | 🔴 21.9 | 🟡 15.0 | 5.6% | 7.5% |
| Install via apt, no apt update | 🔴 21.0 | 🟡 14.0 | 4.3% | 7.2% |
| Install via setup-graphviz action, no mandb | 🟡 16.3 | 🟡 15.0 | 1.9% | - |
| Install via apt, no mandb | 🟡 14.8 | 🟡 13.0 | 2.1% | 0.5% |
| Download and install .deb files, no mandb | 🟡 10.8 | 🟢 10.0 | - | - |
| Install via setup-graphviz action, no apt update, no mandb | 🟡 10.0 | 🟢 8.0 | 0.5% | - |
| Install via apt, no apt update, no mandb | 🟢 8.5 | 🟢 7.0 | 0.3% | 0.3% |
| Get .deb files from GitHub cache and install them, no mandb | 🟢 8.3 | 🟢 7.0 | 0.5% | - |
| Install via apt, no apt update, no recommends, no mandb | 🟢 7.4 | 🟢 6.0 | - | - |
| Install via cache-apt-pkgs action, no mandb | 🟢 6.6 | 🟢 6.0 | - | - |
| Install via cache-apt-pkgs action | 🟢 6.5 | 🟢 6.0 | - | - |

## Current runner benchmarks

The hourly [benchmark workflow](.github/workflows/benchmark.yml) compares direct
APT installation with uncached, cold-cache and warm-cache action runs, each with
and without an explicit package-list update. See [benchmark documentation](benchmark/README.md)
for methodology, retained JSON/CSV data and the rolling 14-day report. The older
measurements above predate GitHub's disabling of automatic man-db updates and
should not be interpreted as current runner performance.
