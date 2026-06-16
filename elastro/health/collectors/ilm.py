"""ILM lifecycle collector — index listing and stuck lifecycle detection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from elastro.core.errors import OperationError
from elastro.core.ilm import IlmManager
from elastro.core.index import IndexManager
from elastro.core.logger import get_logger
from elastro.health.collectors.base import CollectContext, CollectorResult
from elastro.health.models import Finding, FindingStatus, RemediationAction, RemediationSafety, Severity

logger = get_logger(__name__)

_MAX_EXPLAIN = 25


class IlmCollector:
    """List indices and detect ILM lifecycle errors on unhealthy indices."""

    name = "ilm"

    def collect(self, ctx: CollectContext) -> CollectorResult:
        index_manager = IndexManager(ctx.client)
        ilm_manager = IlmManager(ctx.client)
        logger.debug("Collecting ILM lifecycle status")

        try:
            indices = index_manager.list()
            findings = self._ilm_findings(
                indices,
                ilm_manager=ilm_manager,
                health_report=ctx.options.get("health_report"),
            )
            logger.info(
                "ILM collector complete: indices=%s findings=%s",
                len(indices),
                len(findings),
            )
            return CollectorResult(
                name=self.name,
                status="ok",
                data={
                    "indices": indices,
                    "index_count": len(indices),
                    "findings": findings,
                },
            )
        except OperationError as exc:
            logger.error("ILM collector failed: %s", exc)
            return CollectorResult(name=self.name, status="error", error=str(exc))

    def _ilm_findings(
        self,
        indices: List[Dict[str, Any]],
        *,
        ilm_manager: IlmManager,
        health_report: Optional[Dict[str, Any]],
    ) -> List[Finding]:
        targets = _select_explain_targets(indices, health_report)
        findings: List[Finding] = []

        for index_name in sorted(targets)[:_MAX_EXPLAIN]:
            try:
                explain = ilm_manager.explain_lifecycle(index_name)
            except OperationError as exc:
                logger.debug(
                    "Skipping ILM explain for %s: %s",
                    index_name,
                    exc,
                )
                continue

            issue = _lifecycle_issue(explain)
            if issue is None:
                continue

            findings.append(
                Finding(
                    id=f"ilm.stuck.{index_name}",
                    category="ilm",
                    title=f"ILM lifecycle issue: {index_name}",
                    status=FindingStatus.WARN,
                    severity=Severity.MEDIUM,
                    score_impact=5,
                    summary=issue,
                    affected_resources=[index_name],
                    source="collector",
                    indicator="ilm",
                    remediation=RemediationAction(
                        id="ilm_retry",
                        label="Retry ILM step",
                        command=f"elastro ilm explain {index_name}",
                        safety=RemediationSafety.CONFIRM,
                    ),
                    metadata={"explain": explain},
                )
            )

        return findings


def _select_explain_targets(
    indices: List[Dict[str, Any]],
    health_report: Optional[Dict[str, Any]],
) -> Set[str]:
    """Choose indices worth explaining — unhealthy first, then ILM indicator hints."""
    targets: Set[str] = set()

    for entry in indices:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("index", "")).strip()
        if not name or name.startswith("."):
            continue
        health = str(entry.get("health", "green")).lower()
        if health in {"yellow", "red"}:
            targets.add(name)

    if health_report:
        indicator = (health_report.get("indicators") or {}).get("ilm") or {}
        details = indicator.get("details") or {}
        stagnating = details.get("stagnating_indices", 0)
        try:
            if int(stagnating) > 0:
                for entry in indices:
                    if not isinstance(entry, dict):
                        continue
                    name = str(entry.get("index", "")).strip()
                    if name and not name.startswith("."):
                        targets.add(name)
        except (TypeError, ValueError):
            pass

    return targets


def _lifecycle_issue(explain: Dict[str, Any]) -> Optional[str]:
    """Return a human-readable issue string when lifecycle execution is stuck."""
    if not isinstance(explain, dict):
        return None

    step = str(explain.get("step", "")).upper()
    if step == "ERROR":
        step_info = explain.get("step_info") or explain.get("failed_step")
        if step_info:
            return f"ILM step failed: {step_info}"
        return "ILM lifecycle step is in ERROR state"

    failed_step = explain.get("failed_step")
    if failed_step:
        return f"ILM failed at step: {failed_step}"

    step_info = explain.get("step_info")
    if isinstance(step_info, dict):
        reason = step_info.get("reason") or step_info.get("type")
        if reason:
            return f"ILM step blocked: {reason}"

    managed = explain.get("managed")
    action = explain.get("action")
    if managed and action in {None, "unfollow"}:
        return None
    if managed and explain.get("phase") and not explain.get("step"):
        return "ILM policy assigned but no active lifecycle step"

    return None