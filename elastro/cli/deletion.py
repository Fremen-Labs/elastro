"""Shared dry-run previews for destructive delete commands."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import rich_click as click
from pydantic import BaseModel, Field

from elastro.cli.output import format_output
from elastro.core.client import ElasticsearchClient
from elastro.core.logger import get_logger
from elastro.core.datastream import DatastreamManager
from elastro.core.errors import OperationError
from elastro.core.ilm import IlmManager
from elastro.core.index import IndexManager
from elastro.core.snapshot import SnapshotManager
from elastro.utils.aliases import AliasManager
from elastro.utils.templates import TemplateManager

logger = get_logger(__name__)


class DeletePreview(BaseModel):
    """Preview of a delete operation for scriptable dry-run output."""

    action: str
    resource_type: str
    resource_id: str
    dry_run: bool = True
    executed: bool = False
    exists: Optional[bool] = None
    planned_api_call: str
    message: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


def resolve_output_format() -> str:
    """Read -o/--output from the root CLI context."""
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return "json"
    root = ctx
    while root.parent is not None:
        root = root.parent
    return str(root.params.get("output") or "json")


def delete_preview_payload(preview: DeletePreview) -> Dict[str, Any]:
    """Serialize a delete preview with scripting summary fields."""
    payload = preview.model_dump(mode="json")
    payload["summary"] = {
        "preview_only": True,
        "executed_count": 0,
        "would_execute": preview.exists is not False,
    }
    return payload


def emit_delete_preview(preview: DeletePreview) -> None:
    """Print a delete preview for table or JSON/YAML output."""
    logger.info(
        "delete preview action=%s resource=%s/%s exists=%s",
        preview.action,
        preview.resource_type,
        preview.resource_id,
        preview.exists,
    )
    output_fmt = resolve_output_format()
    if output_fmt == "table":
        click.echo("Delete preview (dry-run):")
        click.echo(f"  Action: {preview.action}")
        click.echo(f"  Resource: {preview.resource_type}/{preview.resource_id}")
        if preview.exists is not None:
            click.echo(f"  Exists: {'yes' if preview.exists else 'no'}")
        click.echo(f"  API: {preview.planned_api_call}")
        click.echo(f"  {preview.message}")
        for key, value in preview.metadata.items():
            click.echo(f"  {key}: {value}")
        return

    click.echo(
        format_output(delete_preview_payload(preview), output_format=output_fmt),
        nl=False,
    )


def should_prompt_for_delete(
    *, dry_run: bool, force: bool = False, yes: bool = False
) -> bool:
    """Return True when interactive confirmation is required."""
    if dry_run:
        return False
    return not (force or yes)


def preview_index_delete(client: ElasticsearchClient, name: str) -> DeletePreview:
    manager = IndexManager(client)
    exists = manager.exists(name)
    return DeletePreview(
        action="index.delete",
        resource_type="index",
        resource_id=name,
        exists=exists,
        planned_api_call=f"DELETE /{name}",
        message=(
            f"Would delete index '{name}' and all its data."
            if exists
            else f"Index '{name}' does not exist; delete would fail."
        ),
    )


def _document_exists(client: ElasticsearchClient, index: str, doc_id: str) -> bool:
    try:
        client._ensure_connected()
        return bool(client.get_client().exists(index=index, id=doc_id))
    except Exception:
        return False


def preview_document_delete(
    client: ElasticsearchClient,
    index: str,
    doc_id: str,
) -> DeletePreview:
    exists = _document_exists(client, index, doc_id)
    return DeletePreview(
        action="document.delete",
        resource_type="document",
        resource_id=f"{index}/{doc_id}",
        exists=exists,
        planned_api_call=f"DELETE /{index}/_doc/{doc_id}",
        message=(
            f"Would delete document '{doc_id}' from index '{index}'."
            if exists
            else f"Document '{doc_id}' not found in '{index}'; delete would fail."
        ),
    )


def preview_bulk_document_delete(
    client: ElasticsearchClient,
    index: str,
    ids: List[str],
) -> DeletePreview:
    index_manager = IndexManager(client)
    index_exists = index_manager.exists(index)
    sample = ids[:5]
    return DeletePreview(
        action="document.bulk_delete",
        resource_type="document",
        resource_id=index,
        exists=index_exists,
        planned_api_call=f"POST /_bulk ({len(ids)} delete operations on {index})",
        message=(
            f"Would bulk-delete {len(ids)} document(s) from '{index}'."
            if index_exists
            else f"Index '{index}' does not exist; bulk delete would fail."
        ),
        metadata={
            "id_count": len(ids),
            "sample_ids": sample,
        },
    )


def preview_datastream_delete(client: ElasticsearchClient, name: str) -> DeletePreview:
    manager = DatastreamManager(client)
    exists = manager.exists(name)
    return DeletePreview(
        action="datastream.delete",
        resource_type="datastream",
        resource_id=name,
        exists=exists,
        planned_api_call=f"DELETE /_data_stream/{name}",
        message=(
            f"Would delete data stream '{name}' and backing indices."
            if exists
            else f"Data stream '{name}' does not exist; delete would fail."
        ),
    )


def preview_template_delete(
    client: ElasticsearchClient,
    name: str,
    *,
    template_type: str = "index",
) -> DeletePreview:
    manager = TemplateManager(client)
    try:
        body = manager.get(name, template_type=template_type)
        exists = bool(body)
    except OperationError:
        exists = False
    if template_type == "component":
        planned = f"DELETE /_component_template/{name}"
        action = "template.component_delete"
    else:
        planned = f"DELETE /_index_template/{name}"
        action = "template.index_delete"
    return DeletePreview(
        action=action,
        resource_type=f"{template_type}_template",
        resource_id=name,
        exists=exists,
        planned_api_call=planned,
        message=(
            f"Would delete {template_type} template '{name}'."
            if exists
            else f"{template_type.title()} template '{name}' does not exist; delete would fail."
        ),
        metadata={"template_type": template_type},
    )


def preview_ilm_policy_delete(client: ElasticsearchClient, name: str) -> DeletePreview:
    manager = IlmManager(client)
    try:
        manager.get_policy(name)
        exists = True
    except OperationError:
        exists = False
    return DeletePreview(
        action="ilm.policy_delete",
        resource_type="ilm_policy",
        resource_id=name,
        exists=exists,
        planned_api_call=f"DELETE /_ilm/policy/{name}",
        message=(
            f"Would delete ILM policy '{name}'."
            if exists
            else f"ILM policy '{name}' does not exist; delete would fail."
        ),
    )


def preview_snapshot_repository_delete(
    client: ElasticsearchClient,
    name: str,
) -> DeletePreview:
    manager = SnapshotManager(client)
    try:
        manager.get_repository(name)
        exists = True
    except OperationError:
        exists = False
    return DeletePreview(
        action="snapshot.repository_delete",
        resource_type="snapshot_repository",
        resource_id=name,
        exists=exists,
        planned_api_call=f"DELETE /_snapshot/{name}",
        message=(
            f"Would unregister snapshot repository '{name}' (storage data is not removed)."
            if exists
            else f"Repository '{name}' does not exist; delete would fail."
        ),
    )


def preview_snapshot_delete(
    client: ElasticsearchClient,
    repository: str,
    snapshot: str,
) -> DeletePreview:
    manager = SnapshotManager(client)
    try:
        manager.get_snapshot(repository, snapshot)
        exists = True
    except OperationError:
        exists = False
    return DeletePreview(
        action="snapshot.delete",
        resource_type="snapshot",
        resource_id=f"{repository}/{snapshot}",
        exists=exists,
        planned_api_call=f"DELETE /_snapshot/{repository}/{snapshot}",
        message=(
            f"Would permanently delete snapshot '{snapshot}' from '{repository}'."
            if exists
            else f"Snapshot '{snapshot}' not found in '{repository}'; delete would fail."
        ),
        metadata={"repository": repository, "snapshot": snapshot},
    )


def preview_alias_delete(
    client: ElasticsearchClient,
    name: str,
    index: str,
) -> DeletePreview:
    manager = AliasManager(client)
    exists = manager.exists(name, index=index)
    return DeletePreview(
        action="alias.delete",
        resource_type="alias",
        resource_id=f"{index}/{name}",
        exists=exists,
        planned_api_call=f"DELETE /{index}/_alias/{name}",
        message=(
            f"Would remove alias '{name}' from index '{index}'."
            if exists
            else f"Alias '{name}' is not configured on '{index}'; delete would fail."
        ),
        metadata={"alias": name, "index": index},
    )


def preview_script_delete(client: ElasticsearchClient, script_id: str) -> DeletePreview:
    exists = False
    try:
        client._ensure_connected()
        client.get_client().get_script(id=script_id)
        exists = True
    except Exception:
        exists = False
    return DeletePreview(
        action="script.delete",
        resource_type="stored_script",
        resource_id=script_id,
        exists=exists,
        planned_api_call=f"DELETE /_scripts/{script_id}",
        message=(
            f"Would delete stored script '{script_id}'."
            if exists
            else f"Stored script '{script_id}' does not exist; delete would fail."
        ),
    )


def preview_pipeline_delete(
    client: ElasticsearchClient, pipeline_id: str
) -> DeletePreview:
    exists = False
    try:
        client._ensure_connected()
        client.get_client().ingest.get_pipeline(id=pipeline_id)
        exists = True
    except Exception:
        exists = False
    return DeletePreview(
        action="ingest.pipeline_delete",
        resource_type="ingest_pipeline",
        resource_id=pipeline_id,
        exists=exists,
        planned_api_call=f"DELETE /_ingest/pipeline/{pipeline_id}",
        message=(
            f"Would delete ingest pipeline '{pipeline_id}'."
            if exists
            else f"Ingest pipeline '{pipeline_id}' does not exist; delete would fail."
        ),
    )
