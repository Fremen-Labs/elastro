"""Read-only Elastic Fleet / Kibana helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import urllib3
from pydantic import BaseModel, Field

from elastro.config import get_config
from elastro.core.errors import OperationError, ValidationError
from elastro.core.logger import get_logger

logger = get_logger(__name__)


class FleetAgent(BaseModel):
    """A single Fleet agent row."""

    id: str
    name: Optional[str] = None
    status: Optional[str] = None
    policy_id: Optional[str] = None
    last_checkin: Optional[str] = None
    upgrade_status: Optional[str] = None


class FleetStatus(BaseModel):
    """Aggregated Fleet agent counts."""

    total: int = 0
    online: int = 0
    offline: int = 0
    error: int = 0
    updating: int = 0
    inactive: int = 0
    unenrolled: int = 0
    agents: List[FleetAgent] = Field(default_factory=list)


class FleetClient:
    """Thin Kibana Fleet API client (read-only)."""

    def __init__(
        self,
        kibana_url: str,
        api_key: str,
        *,
        timeout: float = 30.0,
    ) -> None:
        url = (kibana_url or "").strip()
        key = (api_key or "").strip()
        if not url:
            raise ValidationError("Fleet kibana_url is required")
        if not key:
            raise ValidationError("Fleet API key is required")
        if not url.startswith(("http://", "https://")):
            raise ValidationError("Fleet kibana_url must be an http(s) URL")
        self._base = url.rstrip("/")
        self._api_key = key
        self._timeout = urllib3.Timeout(total=timeout)
        self._http = urllib3.PoolManager()

    @classmethod
    def from_config(cls) -> "FleetClient":
        """Build a client from ``coverage.fleet`` config (never logs the key)."""
        coverage = get_config().get("coverage") or {}
        fleet = coverage.get("fleet") or {}
        return cls(
            kibana_url=str(fleet.get("kibana_url") or ""),
            api_key=str(fleet.get("api_key") or ""),
        )

    def status(self) -> FleetStatus:
        """Return agent status counts, falling back to listing agents."""
        try:
            data = self._request("GET", "/api/fleet/agent-status")
            counts = _status_from_payload(data)
            counts.agents = []
            return counts
        except OperationError as exc:
            if "HTTP 404" not in str(exc):
                raise
            logger.info("Fleet agent-status endpoint missing; aggregating agents")
            agents = self.list_agents()
            return _status_from_agents(agents)

    def list_agents(self, policy_id: Optional[str] = None) -> List[FleetAgent]:
        """List Fleet agents, optionally filtered by policy id."""
        params: Dict[str, Any] = {"perPage": 100, "showInactive": "true"}
        if policy_id:
            params["policyId"] = policy_id
        data = self._request("GET", "/api/fleet/agents", params=params)
        items = data.get("items") or data.get("list") or []
        agents: List[FleetAgent] = []
        if not isinstance(items, list):
            return agents
        for item in items:
            agent = _agent_from_item(item)
            if agent is not None:
                agents.append(agent)
        return agents

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        logger.debug("Fleet %s %s", method, path)
        try:
            response = self._http.request(
                method,
                url,
                headers=self._headers(),
                timeout=self._timeout,
            )
        except Exception as exc:
            logger.error("Fleet request failed path=%s", path, exc_info=True)
            raise OperationError(f"Fleet request failed for {path}") from exc

        status = int(response.status)
        if status >= 400:
            logger.error("Fleet request HTTP %s path=%s", status, path)
            raise OperationError(f"Fleet request failed: HTTP {status} for {path}")
        try:
            payload = json.loads(response.data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OperationError(f"Fleet response was not JSON for {path}") from exc
        if not isinstance(payload, dict):
            raise OperationError(f"Unexpected Fleet payload for {path}")
        return payload

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"ApiKey {self._api_key}",
            "kbn-xsrf": "true",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


def _agent_from_item(item: Any) -> Optional[FleetAgent]:
    if not isinstance(item, dict):
        return None
    agent_id = str(item.get("id") or "").strip()
    if not agent_id:
        return None
    meta = item.get("local_metadata") or {}
    host = meta.get("host") if isinstance(meta, dict) else {}
    if not isinstance(host, dict):
        host = {}
    upgrade = item.get("upgrade_details") or {}
    upgrade_state = None
    if isinstance(upgrade, dict):
        upgrade_state = upgrade.get("state")
    name = host.get("hostname") or item.get("name")
    return FleetAgent(
        id=agent_id,
        name=str(name) if name else None,
        status=str(item["status"]) if item.get("status") is not None else None,
        policy_id=(
            str(item["policy_id"]) if item.get("policy_id") is not None else None
        ),
        last_checkin=(
            str(item["last_checkin"]) if item.get("last_checkin") is not None else None
        ),
        upgrade_status=str(upgrade_state) if upgrade_state is not None else None,
    )


def _status_from_payload(data: Dict[str, Any]) -> FleetStatus:
    online = int(data.get("online") or 0)
    offline = int(data.get("offline") or 0)
    error = int(data.get("error") or 0)
    updating = int(data.get("updating") or 0)
    inactive = int(data.get("inactive") or 0)
    unenrolled = int(data.get("unenrolled") or 0)
    total = int(data.get("total") or 0)
    if total <= 0:
        total = online + offline + error + updating + inactive + unenrolled
    return FleetStatus(
        total=total,
        online=online,
        offline=offline,
        error=error,
        updating=updating,
        inactive=inactive,
        unenrolled=unenrolled,
    )


def _status_from_agents(agents: List[FleetAgent]) -> FleetStatus:
    counts = {
        "online": 0,
        "offline": 0,
        "error": 0,
        "updating": 0,
        "inactive": 0,
        "unenrolled": 0,
    }
    for agent in agents:
        key = (agent.status or "").lower()
        if key in counts:
            counts[key] += 1
        elif key:
            counts["error"] += 1
    return FleetStatus(
        total=len(agents),
        agents=agents,
        **counts,
    )
