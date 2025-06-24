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

| Method | Mean (s) | Median (s) | 30–60s | >60s |
|--------|----------|------------|--------|------|
| Install via setup-graphviz action | 🔴 28.6 | 🔴 23.0 | 4 | 31 |
| Install via apt | 🔴 26.0 | 🟡 20.0 | 4 | 27 |
| Install via setup-graphviz action, no apt update | 🔴 25.3 | 🟡 17.0 | 11 | 32 |
| Install via apt, no apt update, no recommends | 🔴 24.1 | 🟡 14.0 | 13 | 33 |
| Download and install .deb files | 🔴 23.6 | 🟡 17.0 | 13 | 24 |
| Get .deb files from GitHub cache and install them | 🔴 21.4 | 🟡 15.0 | 15 | 23 |
| Install via apt, no apt update | 🔴 21.3 | 🟡 14.0 | 12 | 21 |
| Install via setup-graphviz action, no mandb | 🟡 16.3 | 🟡 15.0 | 6 | 0 |
| Install via apt, no mandb | 🟡 14.5 | 🟡 13.0 | 6 | 2 |
| Download and install .deb files, no mandb | 🟡 10.6 | 🟢 9.0 | 0 | 0 |
| Install via setup-graphviz action, no apt update, no mandb | 🟢 9.8 | 🟢 8.0 | 1 | 0 |
| Install via apt, no apt update, no mandb | 🟢 8.3 | 🟢 7.0 | 1 | 0 |
| Get .deb files from GitHub cache and install them, no mandb | 🟢 8.2 | 🟢 7.0 | 2 | 0 |
| Install via apt, no apt update, no recommends, no mandb | 🟢 7.5 | 🟢 7.0 | 0 | 0 |
| Install via cache-apt-pkgs action | 🟢 6.6 | 🟢 6.0 | 0 | 0 |
| Install via cache-apt-pkgs action, no mandb | 🟢 6.5 | 🟢 6.0 | 0 | 0 |
