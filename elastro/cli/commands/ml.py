"""
Machine Learning commands for the CLI.
"""

import rich_click as click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from elastro.core.client import ElasticsearchClient
from elastro.cli.output import format_output

console = Console()


@click.group("ml")
def ml_group() -> None:
    """
    Manage Machine Learning anomaly detection workflows.
    """
    pass


@ml_group.command("init-job")
@click.pass_obj
def init_job(client: ElasticsearchClient) -> None:
    """
    Interactive wizard to deploy a Machine Learning Anomaly Detection Job.

    This command guides you through deploying a single-metric ML job
    over an existing Index or Datastream without hand-writing JSON.
    """
    console.print("\n[bold cyan]Elastro ML Anomaly Detection Wizard[/bold cyan]")
    console.print(
        "This wizard will configure a basic Single Metric anomaly detection job.\n"
    )

    # 1. Job ID
    job_id = Prompt.ask("Enter a new [bold]Job ID[/bold]", default="anomaly-job-01")

    # 2. Source Index
    index_pattern = Prompt.ask(
        "Target [bold]Index or Datastream Pattern[/bold]", default="logs-*"
    )

    # 3. Time Field
    time_field = Prompt.ask("Primary [bold]Time Field[/bold]", default="@timestamp")

    # 4. Metric Field
    metric_field = Prompt.ask("Metric Field to Analyze", default="response.time")

    # 5. Function Type
    function_idx = Prompt.ask(
        "\nSelect Analysis Function:\n  1. High Mean (Detect Spikes)\n  2. Low Mean (Detect Drops)\n  3. Count (Detect Log Volume Anomalies)\nChoice",
        choices=["1", "2", "3"],
        default="1",
    )

    func_map = {"1": "high_mean", "2": "low_mean", "3": "count"}
    function_type = func_map[function_idx]

    # Generate the ES mapping JSON
    job_config = {
        "description": f"Elastro Scaffolded Job: detect '{function_type}' on '{metric_field}'",
        "analysis_config": {
            "bucket_span": "15m",
            "detectors": [
                {
                    "function": function_type,
                    "field_name": metric_field if function_type != "count" else None,
                }
            ],
            "influencers": [],
        },
        "data_description": {"time_field": time_field},
    }

    # Scrub null fields
    if function_type == "count":
        del job_config["analysis_config"]["detectors"][0]["field_name"]

    console.print("\n[bold green]Generated Configuration:[/bold green]")
    console.print(format_output(job_config, format_type="json"))

    if not Confirm.ask("\nDeploy this ML Job to the cluster?"):
        console.print("[dim]Operation aborted.[/dim]")
        return

    try:
        # ES API call: PUT _ml/anomaly_detectors/<job_id>
        response = client.client.ml.put_job(job_id=job_id, body=job_config)
        console.print(f"[bold green]Success![/bold green] ML Job '{job_id}' deployed.")

        # Scaffold the datafeed
        datafeed_id = f"datafeed-{job_id}"
        datafeed_config = {"job_id": job_id, "indices": [index_pattern]}
        client.client.ml.put_datafeed(datafeed_id=datafeed_id, body=datafeed_config)
        console.print(
            f"[bold green]Success![/bold green] Datafeed '{datafeed_id}' attached."
        )

    except Exception as e:
        console.print(f"[bold red]Error deploying ML Job:[/bold red] {str(e)}")
