# Security remediation record — June 2026

Elastro **1.13.1** security uplift (PR-SEC-1 through PR-SEC-4).

## Baseline (ReleaseFlow Trivy, pre-remediation)

| Severity | Count |
|----------|------:|
| CRITICAL | 0 |
| HIGH | 21 |
| MEDIUM | 23 |
| LOW | 4 |

Source: `security/scans/api-1.13.1.trivy.json.zst` (2026-06-16).

## Remediation PRs

| PR | Scope | Key changes |
|----|-------|-------------|
| PR-SEC-1 | GUI npm | `axios` → 1.18.0; overrides for `form-data`, `follow-redirects`, `picomatch`, `postcss`, `yaml` |
| PR-SEC-2 | Python runtime | `starlette` ≥ 1.3.1, `urllib3` ≥ 2.7.0, `python-dotenv` ≥ 1.2.2, `fastapi` ≥ 0.135; Python floor **3.10** |
| PR-SEC-3 | CI gates | `pip-audit`, `npm audit --omit=dev`, `mypy`, `ruff format` in GitHub Actions |
| PR-SEC-4 | Verification | `scripts/security-audit.sh`, `security/trivyignore.yaml`, this record |

## Post-remediation verification (local, 2026-06-16)

| Check | Result |
|-------|--------|
| `pip-audit -r requirements.txt` | 0 vulnerabilities |
| `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| `trivy fs` (production posture, dev deps excluded) | 0 HIGH/CRITICAL |
| Health + API tests | 269 passed |
| `mypy .` | 154 files clean |

## Residual risk (documented)

| Package | Severity | Status | Mitigation |
|---------|----------|--------|------------|
| `esbuild` (via `vite` devDep) | HIGH | Dev-only | `security/trivyignore.yaml` until vite@8 upgrade; not in shipped wheel/GUI bundle |

## Re-run audit

```bash
bash scripts/security-audit.sh
```

## Release gate alignment

- `release.yaml` → `security.scan.ignoreFile: security/trivyignore.yaml`
- `release.yaml` → `severityFail: [CRITICAL, HIGH]`
- CI mirrors runtime audits on every PR