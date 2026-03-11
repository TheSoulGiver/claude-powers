#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Error: project directory does not exist: $PROJECT_DIR" >&2
  exit 1
fi

cd "$PROJECT_DIR"

if [[ ! -f package.json ]]; then
  echo "Error: package.json not found in: $PROJECT_DIR" >&2
  exit 1
fi

PACKAGES=(
  "react"
  "react-dom"
  "react-is"
  "@mui/material"
  "@mui/icons-material"
  "@mui/joy"
  "@mui/styled-engine-sc"
  "@emotion/react"
  "@emotion/styled"
  "styled-components"
  "antd"
  "@chakra-ui/react"
  "@base-ui/react"
  "@fluentui/react-components"
  "@fluentui/web-components"
  "@fontsource/roboto"
  "@fontsource/inter"
  "next-themes"
  "react-icons"
)

get_declared_version() {
  local pkg="$1"
  node -e '
const fs = require("fs");
const pkg = process.argv[1];
const raw = fs.readFileSync("package.json", "utf8");
const data = JSON.parse(raw);
const declared =
  (data.dependencies && data.dependencies[pkg]) ||
  (data.devDependencies && data.devDependencies[pkg]) ||
  (data.peerDependencies && data.peerDependencies[pkg]) ||
  "";
process.stdout.write(declared);
' "$pkg"
}

get_installed_version() {
  local pkg="$1"
  local json
  json="$(npm ls "$pkg" --depth=0 --json 2>/dev/null || true)"
  node -e '
const fs = require("fs");
const pkg = process.argv[1];
const raw = fs.readFileSync(0, "utf8");
let parsed = {};
try {
  parsed = JSON.parse(raw);
} catch (err) {
  process.stdout.write("");
  process.exit(0);
}
const dep = parsed.dependencies && parsed.dependencies[pkg];
process.stdout.write(dep && dep.version ? dep.version : "");
' "$pkg" <<<"$json"
}

echo "# UI Stack Audit"
echo "Project: $PROJECT_DIR"
echo
printf "%-35s %-22s %-22s\n" "Package" "Declared" "Installed"
printf "%0.s-" {1..84}
echo

for pkg in "${PACKAGES[@]}"; do
  declared="$(get_declared_version "$pkg")"
  installed="$(get_installed_version "$pkg")"

  if [[ -z "$declared" ]]; then
    declared="(missing)"
  fi
  if [[ -z "$installed" ]]; then
    installed="(not installed)"
  fi

  printf "%-35s %-22s %-22s\n" "$pkg" "$declared" "$installed"
done

echo
echo "Use this table to build the component-library responsibility matrix."
