"""Basic security posture collector — TLS hints and native realm checks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.models import Finding, FindingStatus, RemediationAction, RemediationSafety, Severity

logger = get_logger(__name__)

_PRIVILEGED_CLUSTER_PRIVS = frozenset({"all", "manage", "manage_security"})


class SecurityCollector:
    """Collect lightweight security findings without mutating cluster state."""

    name = "security"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        logger.debug("Collecting basic security posture")
        hosts = _resolve_hosts(ctx)
        findings: List[Finding] = []
        findings.extend(_tls_findings(hosts))
        findings.extend(_native_realm_findings(ctx))

        logger.info("Security collector complete: findings=%s", len(findings))
        return CollectorResult(
            name=self.name,
            status="ok",
            data={
                "hosts": hosts,
                "findings": findings,
            },
        )


def _resolve_hosts(ctx: CollectContext) -> List[str]:
    hosts = getattr(ctx.client, "hosts", None)
    if isinstance(hosts, str):
        return [hosts]
    if isinstance(hosts, Sequence):
        return [str(item) for item in hosts]
    return []


def _tls_findings(hosts: List[str]) -> List[Finding]:
    findings: List[Finding] = []
    for host in hosts:
        lowered = host.lower()
        if lowered.startswith("http://"):
            findings.append(
                Finding(
                    id="security.tls.plain_http",
                    category="security",
                    title="Cluster connection uses plain HTTP",
                    status=FindingStatus.WARN,
                    severity=Severity.HIGH,
                    score_impact=10,
                    summary=(
                        f"Elastro is configured to connect via HTTP ({host}). "
                        "Use HTTPS in production."
                    ),
                    affected_resources=[host],
                    source="collector",
                    remediation=RemediationAction(
                        id="enable_tls",
                        label="Use HTTPS endpoints",
                        command="elastro config set elasticsearch.hosts '[\"https://...\"]'",
                        safety=RemediationSafety.SUGGEST,
                    ),
                )
            )
    return findings


def _native_realm_findings(ctx: CollectContext) -> List[Finding]:
    findings: List[Finding] = []
    es = ctx.client.client
    try:
        users = es.security.get_user()
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 403 or "security" in str(exc).lower():
            logger.debug("Security API unavailable: %s", exc)
            findings.append(
                Finding(
                    id="security.api.unavailable",
                    category="security",
                    title="Security API not accessible",
                    status=FindingStatus.SKIPPED,
                    severity=Severity.LOW,
                    score_impact=0,
                    summary=(
                        "Cannot inspect native realm users; credentials lack "
                        "manage_security or monitor privileges."
                    ),
                    source="collector",
                )
            )
            return findings
        logger.warning("Security user lookup failed: %s", exc, exc_info=True)
        return findings

    if not isinstance(users, dict):
        return findings

    elastic_user = users.get("elastic")
    if isinstance(elastic_user, dict) and elastic_user.get("enabled", True):
        findings.append(
            Finding(
                id="security.user.elastic_enabled",
                category="security",
                title="Default elastic user is enabled",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=5,
                summary=(
                    "The built-in 'elastic' superuser is enabled. Prefer "
                    "dedicated service accounts with least privilege."
                ),
                affected_resources=["elastic"],
                source="collector",
                remediation=RemediationAction(
                    id="review_users",
                    label="Review native realm users",
                    command="elastro security users",
                    safety=RemediationSafety.OBSERVE,
                ),
            )
        )

    try:
        roles = es.security.get_role()
    except Exception as exc:
        logger.debug("Security role lookup failed: %s", exc)
        return findings

    if isinstance(roles, dict):
        findings.extend(_overprivileged_role_findings(roles))

    return findings


def _overprivileged_role_findings(roles: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    for role_name, role_body in roles.items():
        if not isinstance(role_body, dict):
            continue
        cluster_privs = {
            str(item).lower()
            for item in (role_body.get("cluster") or [])
            if item
        }
        if not cluster_privs.intersection(_PRIVILEGED_CLUSTER_PRIVS):
            continue
        if role_name in {"superuser", "elastic"}:
            continue
        findings.append(
            Finding(
                id=f"security.role.privileged.{role_name}",
                category="security",
                title=f"Role '{role_name}' has elevated cluster privileges",
                status=FindingStatus.WARN,
                severity=Severity.MEDIUM,
                score_impact=5,
                summary=(
                    f"Role '{role_name}' grants cluster privileges: "
                    f"{', '.join(sorted(cluster_privs))}."
                ),
                affected_resources=[role_name],
                source="collector",
                remediation=RemediationAction(
                    id="review_roles",
                    label="Review RBAC roles",
                    command="elastro security roles",
                    safety=RemediationSafety.OBSERVE,
                ),
            )
        )
    return findings