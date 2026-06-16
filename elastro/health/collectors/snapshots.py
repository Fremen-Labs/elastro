"""Snapshot repository health collector."""

from __future__ import annotations

from typing import Any, Dict, List

from elastro.core.errors import OperationError
from elastro.core.logger import get_logger
from elastro.core.snapshot import SnapshotManager
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.models import Finding, FindingStatus, Severity

logger = get_logger(__name__)


class SnapshotsCollector:
    """List snapshot repositories and verify accessibility."""

    name = "snapshots"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        manager = SnapshotManager(ctx.client)
        logger.debug("Collecting snapshot repository status")

        try:
            repositories = manager.list_repositories() or {}
            repo_names = sorted(repositories.keys())
            verified: Dict[str, Any] = {}
            findings: List[Finding] = []

            for repo_name in repo_names:
                try:
                    response = ctx.client.client.snapshot.verify_repository(
                        name=repo_name
                    )
                    body = response.body if hasattr(response, "body") else response
                    nodes = body.get("nodes", {}) if isinstance(body, dict) else {}
                    verified[repo_name] = {
                        "status": "ok",
                        "nodes": list(nodes.keys()),
                    }
                except Exception as exc:
                    logger.warning(
                        "Snapshot repository verification failed for %s: %s",
                        repo_name,
                        exc,
                    )
                    verified[repo_name] = {"status": "error", "error": str(exc)}
                    findings.append(
                        Finding(
                            id=f"snapshots.verify.{repo_name}",
                            category="snapshots",
                            title=f"Snapshot repository verification failed: {repo_name}",
                            status=FindingStatus.WARN,
                            severity=Severity.HIGH,
                            score_impact=5,
                            summary=str(exc),
                            affected_resources=[repo_name],
                            source="collector",
                            metadata={"repository": repo_name},
                        )
                    )

            logger.info(
                "Snapshots collector complete: repositories=%s findings=%s",
                len(repo_names),
                len(findings),
            )
            return CollectorResult(
                name=self.name,
                status="ok",
                data={
                    "repositories": repo_names,
                    "count": len(repo_names),
                    "verified": verified,
                    "findings": findings,
                },
            )
        except OperationError as exc:
            logger.error("Snapshots collector failed: %s", exc)
            return CollectorResult(name=self.name, status="error", error=str(exc))
