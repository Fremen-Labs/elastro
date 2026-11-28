"""Pre-built ILM policies and index templates for APM and Beats."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from elastro.config import get_config
from elastro.core.client import ElasticsearchClient
from elastro.core.errors import OperationError, ValidationError
from elastro.core.ilm import IlmManager
from elastro.core.logger import get_logger
from elastro.utils.templates import TemplateManager as IndexTemplateManager

logger = get_logger(__name__)

_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
_SHIPPED_NAMES = (
    "apm-traces",
    "apm-metrics",
    "filebeat-logs",
    "metricbeat-metrics",
)
_ALIASES = {
    "apm-traces": "apm-traces",
    "apm-metrics": "apm-metrics",
    "filebeat-logs": "filebeat-logs",
    "filebeat": "filebeat-logs",
    "metricbeat-metrics": "metricbeat-metrics",
    "metricbeat": "metricbeat-metrics",
}


class TemplateInfo(BaseModel):
    """Shipped or override coverage template metadata."""

    name: str
    description: str = ""
    index_patterns: List[str] = Field(default_factory=list)
    aliases: List[str] = Field(default_factory=list)
    ilm_policy_name: Optional[str] = None
    index_template_name: Optional[str] = None
    applied: Optional[bool] = None


class TemplateApplyResult(BaseModel):
    """Planned or applied ILM policy and index template bodies."""

    name: str
    dry_run: bool
    ilm_policy_name: str
    ilm_policy: Dict[str, Any]
    index_template_name: str
    index_template: Dict[str, Any]
    applied: bool = False


class TemplateManager:
    """Load and apply coverage ILM + index templates."""

    def __init__(self, client: Optional[ElasticsearchClient] = None) -> None:
        self._client = client

    def list(self, *, include_applied: bool = False) -> List[TemplateInfo]:
        """Return shipped (and optional override) templates.

        ``include_applied`` queries the cluster and requires a client.
        """
        infos: List[TemplateInfo] = []
        seen: set[str] = set()
        for name in _discover_names(self._templates_path()):
            if name in seen:
                continue
            seen.add(name)
            asset = _load_asset(name, extra_dir=self._templates_path())
            infos.append(_info_from_asset(asset))

        if include_applied:
            if self._client is None:
                raise ValidationError(
                    "Elasticsearch client is required to check applied status"
                )
            for info in infos:
                info.applied = self._is_applied(info)
        return infos

    def apply(
        self,
        name: str,
        *,
        dry_run: bool = False,
        ilm_policy_name: Optional[str] = None,
        retention_days: Optional[int] = None,
        rollover_max_size: Optional[str] = None,
        hot_max_age: Optional[str] = None,
        warm_min_age: Optional[str] = None,
        delete_min_age: Optional[str] = None,
        index_patterns: Optional[List[str]] = None,
        index_template_name: Optional[str] = None,
    ) -> TemplateApplyResult:
        """Create or preview the ILM policy and composable index template."""
        asset = _load_asset(name, extra_dir=self._templates_path())
        planned = _build_bodies(
            asset,
            ilm_policy_name=ilm_policy_name,
            retention_days=retention_days,
            rollover_max_size=rollover_max_size,
            hot_max_age=hot_max_age,
            warm_min_age=warm_min_age,
            delete_min_age=delete_min_age,
            index_patterns=index_patterns,
            index_template_name=index_template_name,
        )
        result = TemplateApplyResult(
            name=str(asset.get("name") or _canonical_name(name)),
            dry_run=dry_run,
            ilm_policy_name=planned["ilm_policy_name"],
            ilm_policy=planned["ilm_policy"],
            index_template_name=planned["index_template_name"],
            index_template=planned["index_template"],
            applied=False,
        )
        if dry_run:
            logger.info(
                "Dry-run coverage template %s policy=%s template=%s",
                result.name,
                result.ilm_policy_name,
                result.index_template_name,
            )
            return result

        if self._client is None:
            raise ValidationError("Elasticsearch client is required to apply templates")

        logger.info(
            "Applying coverage template %s policy=%s template=%s",
            result.name,
            result.ilm_policy_name,
            result.index_template_name,
        )
        ilm = IlmManager(self._client)
        index_templates = IndexTemplateManager(self._client)
        try:
            ilm.create_policy(result.ilm_policy_name, result.ilm_policy)
        except (OperationError, ValidationError):
            raise
        except Exception as exc:
            logger.error(
                "Failed to apply ILM policy %s: %s",
                result.ilm_policy_name,
                exc,
                exc_info=True,
            )
            raise OperationError(
                f"Failed to apply ILM policy '{result.ilm_policy_name}': {exc}"
            ) from exc

        try:
            index_templates.create(result.index_template_name, result.index_template)
        except (OperationError, ValidationError):
            logger.error(
                "Index template %s failed after ILM policy %s was written",
                result.index_template_name,
                result.ilm_policy_name,
            )
            raise
        except Exception as exc:
            logger.error(
                "Index template %s failed after ILM policy %s was written: %s",
                result.index_template_name,
                result.ilm_policy_name,
                exc,
                exc_info=True,
            )
            raise OperationError(
                f"Failed to apply index template '{result.index_template_name}': {exc}"
            ) from exc

        result.applied = True
        return result

    def _templates_path(self) -> Optional[Path]:
        try:
            raw = (get_config().get("coverage") or {}).get("templates_path")
        except Exception:
            raw = None
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        return path if path.is_dir() else None

    def _is_applied(self, info: TemplateInfo) -> bool:
        assert self._client is not None
        ilm = IlmManager(self._client)
        index_templates = IndexTemplateManager(self._client)
        policy_ok = False
        template_ok = False
        if info.ilm_policy_name:
            try:
                policy_ok = bool(ilm.get_policy(info.ilm_policy_name))
            except (OperationError, ValidationError):
                policy_ok = False
        if info.index_template_name:
            try:
                template_ok = bool(
                    index_templates.get(info.index_template_name, template_type="index")
                )
            except OperationError:
                template_ok = False
        return policy_ok and template_ok


def _canonical_name(name: str) -> str:
    key = (name or "").strip()
    if not key:
        raise ValidationError("Template name is required")
    resolved = _ALIASES.get(key)
    if resolved:
        return resolved
    extra = _optional_extra_dir()
    if extra and (extra / f"{key}.yaml").is_file():
        return key
    known = ", ".join(_SHIPPED_NAMES)
    raise ValidationError(
        f"Unknown coverage template '{name}'. Expected one of: {known}"
    )


def _optional_extra_dir() -> Optional[Path]:
    try:
        raw = (get_config().get("coverage") or {}).get("templates_path")
    except Exception:
        return None
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.is_dir() else None


def _discover_names(extra_dir: Optional[Path]) -> List[str]:
    names = list(_SHIPPED_NAMES)
    if extra_dir is None:
        return names
    extra = sorted(path.stem for path in extra_dir.glob("*.yaml") if path.is_file())
    for name in extra:
        if name not in names:
            names.append(name)
    return names


def _load_asset(name: str, *, extra_dir: Optional[Path]) -> Dict[str, Any]:
    canonical = _canonical_name(name)
    candidates: List[Path] = []
    if extra_dir is not None:
        candidates.append(extra_dir / f"{canonical}.yaml")
        candidates.append(extra_dir / f"{name}.yaml")
    candidates.append(_ASSETS_DIR / f"{canonical}.yaml")
    for path in candidates:
        if not path.is_file():
            continue
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise OperationError(
                f"Failed to load coverage template '{canonical}': {exc}"
            ) from exc
        if not isinstance(loaded, dict):
            raise OperationError(f"Coverage template '{canonical}' is not a mapping")
        return loaded
    raise ValidationError(f"Coverage template '{canonical}' was not found")


def _info_from_asset(asset: Dict[str, Any]) -> TemplateInfo:
    name = str(asset.get("name") or "")
    ilm = asset.get("ilm") or {}
    policy_name = str(ilm.get("policy_name") or f"elastro-{name}")
    return TemplateInfo(
        name=name,
        description=str(asset.get("description") or ""),
        index_patterns=list(asset.get("index_patterns") or []),
        aliases=list(asset.get("aliases") or []),
        ilm_policy_name=policy_name,
        index_template_name=f"elastro-{name}" if name else None,
        applied=None,
    )


def _build_bodies(
    asset: Dict[str, Any],
    *,
    ilm_policy_name: Optional[str],
    retention_days: Optional[int],
    rollover_max_size: Optional[str],
    hot_max_age: Optional[str],
    warm_min_age: Optional[str],
    delete_min_age: Optional[str],
    index_patterns: Optional[List[str]] = None,
    index_template_name: Optional[str] = None,
) -> Dict[str, Any]:
    name = str(asset.get("name") or "coverage")
    ilm_block = copy.deepcopy(asset.get("ilm") or {})
    policy = copy.deepcopy(ilm_block.get("policy") or {})
    phases = policy.setdefault("phases", {})
    hot_actions = phases.setdefault("hot", {}).setdefault("actions", {})
    rollover = hot_actions.setdefault("rollover", {})
    if rollover_max_size:
        rollover["max_primary_shard_size"] = rollover_max_size
    if hot_max_age:
        rollover["max_age"] = hot_max_age
    if warm_min_age and "warm" in phases:
        phases["warm"]["min_age"] = warm_min_age
    resolved_delete = delete_min_age
    if retention_days is not None:
        if retention_days < 1:
            raise ValidationError("retention_days must be >= 1")
        resolved_delete = f"{retention_days}d"
    if resolved_delete:
        phases.setdefault("delete", {}).setdefault("actions", {}).setdefault(
            "delete", {}
        )
        phases["delete"]["min_age"] = resolved_delete

    policy_name = ilm_policy_name or str(
        ilm_block.get("policy_name") or f"elastro-{name}"
    )
    template = copy.deepcopy(asset.get("template") or {})
    settings = template.setdefault("template", {}).setdefault("settings", {})
    settings["index.lifecycle.name"] = policy_name
    patterns = [item for item in (index_patterns or []) if item]
    if patterns:
        template["index_patterns"] = patterns
    elif "index_patterns" not in template:
        template["index_patterns"] = list(asset.get("index_patterns") or [])
    meta = template.setdefault("_meta", {})
    meta.setdefault("managed_by", "elastro")
    meta["coverage_template"] = name
    template_name = (index_template_name or "").strip() or f"elastro-{name}"

    return {
        "ilm_policy_name": policy_name,
        "ilm_policy": {"policy": policy},
        "index_template_name": template_name,
        "index_template": template,
    }
