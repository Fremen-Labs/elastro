"""
Ingest mapping and pipeline commands.
"""

import json
import rich_click as click
from rich.console import Console
from rich.table import Table

from elastro.core.client import ElasticsearchClient


@click.group(name="ingest")
def ingest_group() -> None:
    """
    Manage ingest node pipelines.
    """
    pass


@ingest_group.command(name="pipelines")
@click.option("--id", help="Fetch a specific pipeline ID")
@click.pass_obj
def list_pipelines(client: ElasticsearchClient, id: str) -> None:
    """
    List or fetch ingest pipelines.
    """
    console = Console()
    try:
        es = client.client
        res = es.ingest.get_pipeline(id=id) if id else es.ingest.get_pipeline()
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Pipeline ID")
        table.add_column("Description")
        table.add_column("Version")
        table.add_column("Processor Count")
        
        for k, v in res.items():
            table.add_row(
                k,
                str(v.get("description", "N/A")),
                str(v.get("version", "N/A")),
                str(len(v.get("processors", [])))
            )
            
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Ingest Error:[/bold red] {str(e)}")


@ingest_group.command(name="simulate")
@click.argument("id")
@click.option("--doc", "-d", required=True, help="Raw JSON Document String to simulate against the ingest nodes")
@click.pass_obj
def simulate_pipeline(client: ElasticsearchClient, id: str, doc: str) -> None:
    """
    Simulate a document through an ingest pipeline securely.
    
    The document string must be valid JSON wrapped in quotes, optionally containing the index routing target (e.g. '{"_index":"my-test", "_source":{"message":"hello"}}').
    """
    console = Console()
    try:
        es = client.client
        
        # Parse doc into native dict
        doc_json = json.loads(doc)
        if "_source" not in doc_json:
             doc_json = {"_source": doc_json}
             
        body = {
            "docs": [doc_json]
        }
        res = es.ingest.simulate(id=id, body=body)
        
        console.print(f"[bold green]Simulation Results for Pipeline: {id}[/bold green]")
        for doc_res in res.get("docs", []):
             if "error" in doc_res:
                  console.print("[bold red]ERROR![/bold red]")
                  console.print(doc_res["error"])
             else:
                  console.print(doc_res.get("doc", {}))
                  
    except json.JSONDecodeError:
        console.print("[bold red]Simulation Error:[/bold red] The --doc parameter must be a valid JSON string.")
    except Exception as e:
        console.print(f"[bold red]Simulation Error:[/bold red] {str(e)}")
