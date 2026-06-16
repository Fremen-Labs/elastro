"""Oversharding finding guide — Elasticsearch-specific remediation context."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from elastro.health.shards import format_bytes

_ELASTIC_TARGET_MIN_GB = 10
_ELASTIC_TARGET_MAX_GB = 50
_ELASTIC_DOCS_PER_SHARD = 200_000_000
_MASTER_INDICES_PER_GB_HEAP = 3000
_DEFAULT_MAX_SHARDS_PER_NODE = 1000


def _aggregate_oversharded_by_index(
    oversharded: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in oversharded:
        if not isinstance(row, dict):
            continue
        index_name = str(row.get("index", "")).strip()
        if index_name:
            grouped[index_name].append(row)

    summary: List[Dict[str, Any]] = []
    for index_name, shards in grouped.items():
        sizes = [
            int(item.get("store_bytes") or 0)
            for item in shards
            if int(item.get("store_bytes") or 0) > 0
        ]
        smallest = min(sizes) if sizes else 0
        summary.append(
            {
                "index": index_name,
                "oversharded_shard_count": len(shards),
                "smallest_bytes": smallest,
                "smallest_human": format_bytes(smallest),
            }
        )

    summary.sort(
        key=lambda item: (
            -int(item.get("oversharded_shard_count", 0)),
            str(item.get("index", "")),
        )
    )
    return summary


def _detail_text(sections: Dict[str, Any]) -> str:
    lines: List[str] = []
    why = sections.get("why")
    if why:
        lines.append(str(why))
        lines.append("")

    implications = sections.get("implications") or []
    if implications:
        lines.append("Performance implications:")
        for item in implications:
            lines.append(f"  • {item}")
        lines.append("")

    resolution = sections.get("resolution") or []
    if resolution:
        lines.append("How to resolve:")
        for index, step in enumerate(resolution, start=1):
            if not isinstance(step, dict):
                continue
            title = step.get("title", f"Step {index}")
            body = step.get("body", "")
            lines.append(f"  {index}. {title}")
            if body:
                lines.append(f"     {body}")
            for command in step.get("commands") or []:
                lines.append(f"     $ {command}")
        lines.append("")

    top_indices = sections.get("top_indices") or []
    if top_indices:
        lines.append("Most affected indices (by oversharded shard count):")
        for item in top_indices[:10]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "  • {index}: {count} shard(s), smallest {smallest}".format(
                    index=item.get("index", "unknown"),
                    count=item.get("oversharded_shard_count", 0),
                    smallest=item.get("smallest_human", "unknown"),
                )
            )
        lines.append("")

    cautions = sections.get("cautions") or []
    if cautions:
        lines.append("Before you change production indices:")
        for item in cautions:
            lines.append(f"  • {item}")

    return "\n".join(lines).rstrip()


def build_oversharding_guide(
    analysis: Dict[str, Any],
    *,
    es_version: Optional[str] = None,
) -> Tuple[str, Dict[str, Any], List[str]]:
    """Return detail text, metadata sections, and affected index names."""
    oversharded_count = int(analysis.get("oversharded_count", 0))
    threshold = int(analysis.get("overshard_threshold_bytes", 1024 * 1024))
    threshold_human = format_bytes(threshold)
    measured = int(analysis.get("measured_shards", 0))
    total = int(analysis.get("total_shards", 0))
    avg_bytes = float(analysis.get("avg_bytes", 0))
    oversharded_rows = analysis.get("oversharded") or []
    top_indices = _aggregate_oversharded_by_index(oversharded_rows)

    pct = 0.0
    if measured > 0:
        pct = round((oversharded_count / measured) * 100, 1)

    why = (
        f"Elastro flagged {oversharded_count} assigned shard(s) under {threshold_human} "
        f"({pct}% of {measured} measured shards). Elasticsearch production guidance "
        f"targets primary shard sizes between {_ELASTIC_TARGET_MIN_GB}GB and "
        f"{_ELASTIC_TARGET_MAX_GB}GB (and below {_ELASTIC_DOCS_PER_SHARD:,} documents "
        f"per shard). Shards at sub-megabyte sizes are far below that band — typical "
        f"causes are aggressive ILM rollover on low-volume streams, too many primaries "
        f"in index templates, or empty/near-empty backing indices that were never deleted."
    )

    implications = [
        (
            "Search cost scales with shard count, not just data size: each shard is "
            "searched on a single thread, so many tiny shards inflate coordination "
            "overhead and can exhaust the search thread pool under concurrent load."
        ),
        (
            "Every index and shard carries fixed heap and cluster-state overhead "
            "(segment metadata, mappings, allocation bookkeeping). A cluster with "
            f"{total:,} total shards pays this cost even when individual shards hold "
            f"almost no documents (cluster average store: {format_bytes(avg_bytes)})."
        ),
        (
            f"Master-eligible nodes should stay below ~{_MASTER_INDICES_PER_GB_HEAP:,} "
            "indices per GB of heap; oversharding increases index count and slows "
            "cluster-state updates during allocation and mapping changes."
        ),
        (
            f"Default `cluster.max_shards_per_node` is {_DEFAULT_MAX_SHARDS_PER_NODE:,} "
            "for non-frozen shards — dense small-shard layouts hit this ceiling during "
            "rollover or reindex before disk is full."
        ),
    ]

    resolution: List[Dict[str, Any]] = [
        {
            "title": "Inventory the worst offenders",
            "body": (
                "List oversharded shards and group by index to decide whether the "
                "problem is a template, a single bloated index pattern, or ILM rollover."
            ),
            "commands": [
                "elastro health shards --analyze -o table",
                "elastro -o json health shards --analyze | jq '.analysis.oversharded[:20]'",
            ],
        },
        {
            "title": "Fix time-series / data-stream rollover (most common)",
            "body": (
                "If indices come from ILM, avoid rollover driven only by `max_age` on "
                "low-traffic streams — that creates many small backing indices. Prefer "
                "`max_primary_shard_size` (Elastic recommends 10gb–50gb bounds via ILM "
                "rollover) and delete empty backing indices. Update the matching index "
                "template's `index.number_of_shards` for *new* backing indices; existing "
                "small indices must be reindexed or shrunk."
            ),
            "commands": [
                "elastro health ilm --stuck-only -o table",
                'curl -X GET "$ES_HOST/_data_stream/*?filter_path=data_streams.name"',
            ],
        },
        {
            "title": "Shrink read-only indices to fewer primaries",
            "body": (
                "For indices no longer written to, use the Shrink API: target primary "
                "count must divide the source primary count, index must be read-only "
                "and green, and every shard copy must sit on one node. ILM warm-phase "
                "shrink is an option for managed indices."
            ),
            "commands": [
                "curl -X PUT \"$ES_HOST/my-index/_settings\" -H 'Content-Type: application/json' "
                "-d '{\"index.blocks.write\": true}'",
                'curl -X POST "$ES_HOST/my-index/_shrink/my-index-shrunk" '
                "-H 'Content-Type: application/json' "
                '-d \'{"settings": {"index.number_of_shards": 1}}\'',
            ],
        },
        {
            "title": "Combine or reindex small static indices",
            "body": (
                "Merge indices with compatible mappings via Reindex into a destination "
                "with fewer primaries (`index.number_of_shards` set at create time). "
                "Delete source indices after validation and repoint aliases."
            ),
            "commands": [
                "curl -X POST \"$ES_HOST/_reindex\" -H 'Content-Type: application/json' "
                '-d \'{"source": {"index": "logs-2099.10.*"}, "dest": {"index": "logs-2099.10"}}\'',
            ],
        },
        {
            "title": "Prevent recurrence in templates",
            "body": (
                "Lower `index.number_of_shards` in component/index templates for new "
                "indices and validate with a canary index before rolling template changes "
                "to production writers."
            ),
            "commands": [
                'curl -X GET "$ES_HOST/_index_template/my-template"',
            ],
        },
    ]

    cautions = [
        "Shard count is fixed at index creation — you cannot lower `index.number_of_shards` in place.",
        "Shrink, reindex, and template changes need spare disk for a second copy of data during migration.",
        "The current write index on a data stream cannot be shrunk; roll the stream first.",
        "Force-merge only reduces segments inside a shard; it does not fix too many primaries.",
    ]

    sections: Dict[str, Any] = {
        "finding_id": "shards.oversharded",
        "why": why,
        "implications": implications,
        "resolution": resolution,
        "cautions": cautions,
        "top_indices": top_indices[:10],
        "threshold_human": threshold_human,
        "oversharded_count": oversharded_count,
        "measured_shards": measured,
        "elastic_guidance": {
            "target_shard_size_gb": f"{_ELASTIC_TARGET_MIN_GB}-{_ELASTIC_TARGET_MAX_GB}",
            "max_docs_per_shard": _ELASTIC_DOCS_PER_SHARD,
        },
        "references": [
            "https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/size-shards",
            "https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-indices-shrink",
            "https://www.elastic.co/docs/reference/elasticsearch/index-lifecycle-actions/ilm-rollover",
        ],
    }
    if es_version:
        sections["elasticsearch_version"] = es_version

    affected = [
        str(item.get("index", "")) for item in top_indices[:10] if item.get("index")
    ]
    return _detail_text(sections), {"detail_sections": sections}, affected
