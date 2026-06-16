#!/usr/bin/env bash
# Reproducible security verification gate for Elastro releases.
# Mirrors CI checks and ReleaseFlow/Trivy production posture.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Elastro security audit ==="
echo "Root: $ROOT"
echo

echo ">> Python runtime (pip-audit / requirements.txt)"
pip-audit -r requirements.txt
echo

echo ">> GUI production npm (omit dev)"
(
  cd packages/gui
  npm ci --silent
  npm audit --omit=dev --audit-level=high
)
echo

if command -v trivy >/dev/null 2>&1; then
  echo ">> Trivy production scan (runtime lockfiles, HIGH+)"
  trivy fs \
    --severity HIGH,CRITICAL \
    --scanners vuln \
    --skip-version-check \
    --exit-code 1 \
    "$ROOT"
  echo

  echo ">> Trivy full-tree scan with documented dev suppressions"
  trivy fs \
    --severity HIGH,CRITICAL \
    --scanners vuln \
    --include-dev-deps \
    --ignorefile "$ROOT/security/trivyignore.yaml" \
    --skip-version-check \
    --exit-code 1 \
    "$ROOT"
else
  echo ">> Trivy not installed; skipping filesystem scan"
  echo "   Install: https://trivy.dev/latest/getting-started/installation/"
fi

echo
echo "=== Security audit passed ==="