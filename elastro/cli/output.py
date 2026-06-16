import json
import yaml
from typing import Any, Optional, cast
from rich.console import Console
from rich.table import Table
from rich import box
from io import StringIO
from elastro.config import get_config


def format_output(data: Any, output_format: Optional[str] = None) -> str:
    """
    Format output data based on the specified format.

    Args:
        data: Data to format
        output_format: Output format (json, yaml, table)

    Returns:
        Formatted string or None (if printing directly)
    """
    # If output_format not provided, try to get from config
    if not output_format:
        try:
            config = get_config()
            output_format = config.get("cli", {}).get("output_format", "json")
        except:
            output_format = "json"

    if output_format == "json":
        # Plain JSON for scriptable stdout (pipes, jq, CI artifacts).
        if hasattr(data, "body"):
            data = data.body
        return json.dumps(data, indent=2, default=str) + "\n"

    elif output_format == "yaml":
        if hasattr(data, "body"):
            data = data.body
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    elif output_format == "table":
        console = Console()

        if hasattr(data, "body"):
            data = data.body

        # Handle different data types
        rows = []
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            # If it's a dict, check if it looks like a response with "items" or "hits"
            if "items" in data:
                rows = data["items"]
            elif "hits" in data and "hits" in data["hits"]:
                rows = [h["_source"] for h in data["hits"]["hits"]]
            else:
                rows = [data]
        else:
            return str(data)

        if not rows:
            return "No data to display."

        # Determine columns
        if not isinstance(rows[0], dict):
            return str(data)

        # Get all unique keys for columns
        headers = set()
        for row in rows:
            headers.update(row.keys())
        sorted_headers = sorted(list(headers))

        buf = StringIO()
        console = Console(file=buf, force_terminal=False)

        table = Table(box=box.ROUNDED)
        for header in sorted_headers:
            table.add_column(str(header), style="cyan")

        for row in rows:
            table.add_row(*[str(row.get(h, "")) for h in sorted_headers])

        console.print(table)
        return buf.getvalue()

    else:
        return str(data)
