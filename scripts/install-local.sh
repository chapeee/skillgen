#!/usr/bin/env bash
# Install (or refresh) the local skillgendev clone as a global command, like `npm link`.
# The macOS and Linux twin of install-local.ps1; see that file for the full story.
#
#   scripts/install-local.sh                 install or refresh
#   scripts/install-local.sh --run-tests     also run ruff, mypy and pytest
#   scripts/install-local.sh --no-extras     without the probe extra (Playwright)
#   scripts/install-local.sh --skip-chromium do not download Chromium for the probe
#   scripts/install-local.sh --uninstall     remove the global command and its cache
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
no_extras=0; skip_chromium=0; run_tests=0; uninstall=0
for argument in "$@"; do
  case "$argument" in
    --no-extras) no_extras=1 ;;
    --skip-chromium) skip_chromium=1 ;;
    --run-tests) run_tests=1 ;;
    --uninstall) uninstall=1 ;;
    *) echo "unknown option: $argument" >&2; exit 2 ;;
  esac
done

step() { printf '\033[36m==> %s\033[0m\n' "$1"; }
ok() { printf '    \033[32m%s\033[0m\n' "$1"; }

# The package name lives in pyproject.toml, so a rename needs no change here.
name="$(sed -n 's/^name = "\(.*\)"/\1/p' "$repo_root/pyproject.toml" | head -n 1)"
echo "Local install of $name from $repo_root"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi
ok "$(uv --version)"

step "Removing any previous global $name"
if uv tool uninstall "$name" >/dev/null 2>&1; then ok "previous install removed"; else ok "no previous install"; fi
step "Clearing uv's cache for $name"
uv cache clean "$name"
if [ "$uninstall" = 1 ]; then echo "$name is uninstalled."; exit 0; fi

step "Removing old build output from the clone"
rm -rf -- "$repo_root/build" "$repo_root/dist"
find "$repo_root/src" -maxdepth 1 -name '*.egg-info' -type d -exec rm -rf -- {} +

spec=".[probe]"; [ "$no_extras" = 1 ] && spec="."
step "Installing $name globally from $repo_root ($spec, editable)"
(cd "$repo_root" && uv tool install --editable "$spec" --force --reinstall)

step "Making sure uv's tool folder is on PATH"
uv tool update-shell >/dev/null 2>&1 || true
bin_dir="$(uv tool dir --bin)"
case ":$PATH:" in *":$bin_dir:"*) ;; *) export PATH="$bin_dir:$PATH"; ok "added $bin_dir to PATH for this shell" ;; esac

step "Checking the global $name"
"$name" --version
"$name" doctor || true
if [ "$no_extras" = 0 ] && [ "$skip_chromium" = 0 ]; then
  step "Downloading Chromium for the probe"
  "$name" doctor --fix | tail -n 1 || true
fi

if [ "$run_tests" = 1 ]; then
  step "Running the checks in the clone"
  (cd "$repo_root" && uv sync --all-extras && uv run ruff check . && uv run ruff format --check . \
    && uv run mypy && uv run pytest)
fi

echo
echo "Done. '$name' now runs the code in $repo_root from any folder."
echo "  Code changes apply at once (editable install); rerun after changing dependencies."
echo "  Logs: every run writes .$name/logs/*.log in your project; see them with '$name logs'."
