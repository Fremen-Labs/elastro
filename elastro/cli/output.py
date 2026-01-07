import json
import yaml
from typing import Any
from rich.console import Console
from rich.table import Table
from rich import box
from io import StringIO
from elastro.config import get_config

def format_output(data: Any, output_format: str = None) -> str:
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

    display_console = Console(file=StringIO(), force_terminal=True)
    
    if output_format == "json":
        # Handle objects that are not directly JSON serializable
        if hasattr(data, "body"):
             data = data.body
        
        json_str = json.dumps(data, indent=2, default=str)
        # Use Rich Syntax for highlighting
        from rich.syntax import Syntax
        syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
        
        display_console.print(syntax)
        return display_console.file.getvalue()

    elif output_format == "yaml":
        if hasattr(data, "body"):
             data = data.body
        yaml_str = yaml.dump(data, default_flow_style=False)
        from rich.syntax import Syntax
        syntax = Syntax(yaml_str, "yaml", theme="monokai", word_wrap=True)
        
        display_console.print(syntax)
        return display_console.file.getvalue()
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
