import click
import json
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from elastro.core.client import ElasticsearchClient
from elastro.core.snapshot import SnapshotManager
from elastro.core.errors import OperationError

console = Console()

@click.group("snapshot")
def snapshot_group():
    """Manage Snapshots and Repositories."""
    pass

# --- REPOSITORY COMMANDS (Sub-group) ---

@snapshot_group.group("repo")
def repo_group():
    """Manage Snapshot Repositories."""
    pass

@repo_group.command("list")
@click.pass_obj
def list_repositories(client):
    """List all snapshot repositories."""
    manager = SnapshotManager(client)
    try:
        repos = manager.list_repositories()
        
        table = Table(title="Snapshot Repositories", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Location", style="dim") # Assumes FS/S3 usually has 'location' or 'bucket'

        for name, details in repos.items():
            type_ = details.get("type", "unknown")
            settings = details.get("settings", {})
            location = settings.get("location") or settings.get("bucket") or ""
            table.add_row(name, type_, location)
            
        console.print(table)
    except OperationError as e:
        console.print(f"[bold red]Error listing repositories:[/] {str(e)}")
        exit(1)

@repo_group.command("create")
@click.argument("name", type=str)
@click.argument("type", type=str) # fs, s3, etc
@click.option("--setting", "-s", multiple=True, help="Repo settings key=value (e.g. location=/tmp)")
@click.pass_obj
def create_repository(client, name, type, setting):
    """
    Create a snapshot repository.
    
    Usage:
      elastro snapshot repo create my-fs-repo fs --setting location=/tmp/repo
    """
    manager = SnapshotManager(client)
    
    # Parse settings
    settings_dict = {}
    for s in setting:
        if "=" in s:
            k, v = s.split("=", 1)
            settings_dict[k] = v
    
    try:
        if manager.create_repository(name, type, settings_dict):
            console.print(f"[bold green]Repository '{name}' created.[/]")
        else:
             console.print("[yellow]Creation not acknowledged.[/]")
    except OperationError as e:
        console.print(f"[bold red]Error creating repository:[/] {str(e)}")
        exit(1)
        
@repo_group.command("delete")
@click.argument("name", type=str)
@click.pass_obj
def delete_repository(client, name):
    """Delete a snapshot repository."""
    manager = SnapshotManager(client)
    if not click.confirm(f"Delete repository '{name}'?"):
        return
        
    try:
        if manager.delete_repository(name):
            console.print(f"[bold green]Repository '{name}' deleted.[/]")
        else:
             console.print("[yellow]Deletion not acknowledged.[/]")
    except OperationError as e:
        console.print(f"[bold red]Error deleting repository:[/] {str(e)}")
        exit(1)


# --- SNAPSHOT COMMANDS ---

@snapshot_group.command("list")
@click.argument("repository", type=str)
@click.pass_obj
def list_snapshots(client, repository):
    """List snapshots in a repository."""
    manager = SnapshotManager(client)
    try:
        snapshots = manager.list_snapshots(repository)
        
        table = Table(title=f"Snapshots in '{repository}'", box=box.ROUNDED)
        table.add_column("Snapshot", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Indices", justify="right")
        table.add_column("Start Time", style="dim")

        for s in snapshots:
            name = s.get("snapshot")
            state = s.get("state")
            indices = len(s.get("indices", []))
            start = s.get("start_time")
            
            style = "green" if state == "SUCCESS" else "red"
            
            table.add_row(name, f"[{style}]{state}[/]", str(indices), start)
            
        console.print(table)
    except OperationError as e:
        console.print(f"[bold red]Error listing snapshots:[/] {str(e)}")
        exit(1)

@snapshot_group.command("create")
@click.argument("repository", type=str)
@click.argument("snapshot", type=str)
@click.option("--indices", default="_all", help="Indices to snapshot")
@click.option("--wait", is_flag=True, help="Wait for completion")
@click.pass_obj
def create_snapshot(client, repository, snapshot, indices, wait):
    """Create a snapshot."""
    manager = SnapshotManager(client)
    try:
        resp = manager.create_snapshot(repository, snapshot, indices=indices, wait_for_completion=wait)
        if wait:
             # Full response with snapshot info usually
             snap_info = resp.get("snapshot", {})
             state = snap_info.get("state", "UNKNOWN")
             console.print(f"[bold green]Snapshot '{snapshot}' created (State: {state}).[/]")
        else:
             # Basic accepted response
             console.print(f"[bold green]Snapshot '{snapshot}' creation started.[/]")
    except OperationError as e:
        console.print(f"[bold red]Error creating snapshot:[/] {str(e)}")
        exit(1)

@snapshot_group.command("restore")
@click.argument("repository", required=False)
@click.argument("snapshot", required=False)
@click.pass_obj
def restore_snapshot(client, repository, snapshot):
    """
    Restore a snapshot (Interactive Wizard if args missing).
    """
    manager = SnapshotManager(client)
    from rich.prompt import Prompt, Confirm

    # WIZARD MODE if args missing
    if not repository or not snapshot:
        console.print(Panel("🧙 [bold blue]Restore Wizard[/]", border_style="blue"))
        
        # 1. Select Repository
        try:
            repos_dict = manager.list_repositories()
        except Exception:
            console.print("[red]Failed to list repositories.[/]")
            return
            
        repo_names = list(repos_dict.keys())
        if not repo_names:
            console.print("[yellow]No repositories found.[/]")
            return
            
        # If user didn't provide repo, ask for it
        if not repository:
            console.print("\nAvailable Repositories:")
            for i, r in enumerate(repo_names):
                console.print(f"  {i+1}. {r}")
            
            repo_idx = int(Prompt.ask("Select Repository", default="1")) - 1
            repository = repo_names[repo_idx]
            
        # 2. Select Snapshot
        if not snapshot:
            console.print(f"\nFetching snapshots from [bold]{repository}[/]...")
            try:
                snaps = manager.list_snapshots(repository)
            except Exception:
                console.print("[red]Failed to list snapshots.[/]")
                return
                
            if not snaps:
                console.print("[yellow]No snapshots found in repository.[/]")
                return

            # Sort by time desc
            snaps.sort(key=lambda x: x.get("start_time_in_millis", 0), reverse=True)
            
            # Show top 10
            console.print("\nRecent Snapshots:")
            limit = min(10, len(snaps))
            for i in range(limit):
                s = snaps[i]
                console.print(f"  {i+1}. {s['snapshot']} ({s['state']}, {len(s['indices'])} indices)")
                
            snap_idx = int(Prompt.ask("Select Snapshot", default="1")) - 1
            snapshot = snaps[snap_idx]["snapshot"]

    # 3. Restore Options
    indices = Prompt.ask("\nIndices to restore", default="_all")
    rename_pattern = None
    rename_replacement = None
    
    if Confirm.ask("Rename indices during restore?", default=False):
        rename_pattern = Prompt.ask("  Rename Pattern (Regex)", default="(.+)")
        rename_replacement = Prompt.ask("  Replacement", default="restored_$1")

    # 4. Confirm
    console.print(f"\n[bold]Plan:[/]\n  Repository: {repository}\n  Snapshot: {snapshot}\n  Indices: {indices}")
    if rename_pattern:
        console.print(f"  Rename: '{rename_pattern}' -> '{rename_replacement}'")
        
    if not Confirm.ask("\nProceed with restore?", default=False):
        console.print("Restore cancelled.")
        return

    # Execute
    try:
        resp = manager.restore_snapshot(
            repository, 
            snapshot, 
            indices=indices, 
            rename_pattern=rename_pattern, 
            rename_replacement=rename_replacement,
            wait_for_completion=False 
        )
        accepted = resp.get("accepted", False)
        if accepted:
            console.print(f"[bold green]Restore operation accepted.[/]")
        else:
             # Sometimes restores return full info if wait=True, but we default wait=False here
             console.print(f"[bold green]Restore started.[/]")
             
    except OperationError as e:
        console.print(f"[bold red]Error restoring snapshot:[/] {str(e)}")
        exit(1)

@snapshot_group.command("delete")
@click.argument("repository", type=str)
@click.argument("snapshot", type=str)
@click.pass_obj
def delete_snapshot(client, repository, snapshot):
    """Delete a snapshot."""
    manager = SnapshotManager(client)
    if not click.confirm(f"Delete snapshot '{snapshot}' from '{repository}'?"):
        return
        
    try:
        if manager.delete_snapshot(repository, snapshot):
             console.print(f"[bold green]Snapshot '{snapshot}' deleted.[/]")
        else:
             console.print("[yellow]Deletion not acknowledged.[/]")
    except OperationError as e:
        console.print(f"[bold red]Error deleting snapshot:[/] {str(e)}")
        exit(1)
