"""Main CLI for Busy Bridge."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from .client import Busy38Client, Busy38Error
from .config import Config
from .import_settings import detect_installed_system_configs, import_detection_to_squid_store
from .formatters import (
    format_cheatcode_result,
    format_health,
    format_mission_details,
    format_mission_list,
    format_tool_details,
    format_tool_list,
    format_tool_result,
)

console = Console()

pass_client = click.make_pass_decorator(Busy38Client)


@click.group()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--url", help="Busy38 API URL")
@click.option("--api-key", help="Busy38 API key")
@click.pass_context
def cli(ctx: click.Context, config: Optional[str], url: Optional[str], api_key: Optional[str]):
    """Busy Bridge - CLI gateway to Busy38's sophisticated agent capabilities.
    
    Use Busy38's IDE, missions, and tool creation from the command line.
    """
    cfg_path = Path(config).expanduser().resolve() if config else Config.default_path()
    cfg = Config.from_file(cfg_path)

    # CLI options override loaded config.
    if url:
        cfg.url = url
    if api_key:
        cfg.api_key = api_key

    # Keep path for settings import/export commands.
    ctx.meta["config_path"] = cfg_path

    ctx.obj = Busy38Client(cfg)


# Health command
@cli.command()
@pass_client
def health(client: Busy38Client):
    """Check Busy38 API health."""
    try:
        status = client.health()
        format_health(status)
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.group()
def settings():
    """Settings import and configuration helpers."""
    pass


@settings.command("show")
@click.pass_context
def settings_show(ctx: click.Context):
    """Show active Busy Bridge settings."""
    client: Busy38Client = ctx.obj
    cfg = client.config
    cfg_path = Path(ctx.meta.get("config_path", Config.default_path()))
    console.print(f"[bold]Config file:[/bold] {cfg_path}")
    console.print(f"[bold]Busy URL:[/bold] {cfg.url}")
    console.print(f"[bold]Agent ID:[/bold] {cfg.agent_id}")
    console.print(f"[bold]Timeout:[/bold] {cfg.timeout}")
    console.print(f"[bold]Model settings:[/bold] {cfg.model_settings or {}}")
    if cfg.imported_from:
        console.print(f"[bold]Imported from:[/bold] {cfg.imported_from}")
    if cfg.imported_at:
        console.print(f"[bold]Imported at:[/bold] {cfg.imported_at}")


@settings.command("detect")
@click.option("--source", help="Specific source system (e.g. openclaw)")
def settings_detect(source: Optional[str]):
    """Detect importable model settings from installed agent systems."""
    found = detect_installed_system_configs(source=source)
    if not found:
        console.print("[yellow]No importable agent-system model settings detected.[/yellow]")
        return
    console.print(f"[green]Detected {len(found)} import candidate(s):[/green]")
    for hit in found:
        console.print(f"- [bold]{hit.system}[/bold] ({hit.config_path})")
        console.print(f"  model settings: {hit.model_settings or {}}")
        console.print(f"  agent settings: {hit.agent_settings or {}}")
        console.print(f"  plaintext secrets detected: {len(hit.secrets)}")


@settings.command("import")
@click.option("--source", help="Specific source system to import from (e.g. openclaw)")
@click.option("--dry-run", is_flag=True, help="Preview import without writing config")
@click.option("--to-squidstore", is_flag=True, help="Also import detected settings/secrets into Squid store")
@click.option("--squidstore-db", type=click.Path(), help="Squid store DB path override")
@click.option("--target-agent-id", default="busy-bridge", help="Target agent_id in Squid store")
@click.pass_context
def settings_import(
    ctx: click.Context,
    source: Optional[str],
    dry_run: bool,
    to_squidstore: bool,
    squidstore_db: Optional[str],
    target_agent_id: str,
):
    """Import detected model settings into Busy Bridge config."""
    client: Busy38Client = ctx.obj
    found = detect_installed_system_configs(source=source)
    if not found:
        console.print("[yellow]No importable settings found.[/yellow]")
        return

    selected = found[0]
    cfg = client.config
    preview = dict(cfg.model_settings or {})
    preview.update(selected.model_settings)

    console.print(f"[green]Import source:[/green] {selected.system} ({selected.config_path})")
    console.print(f"[green]Merged model settings:[/green] {preview}")
    if dry_run:
        console.print("[cyan]Dry run only; no file written.[/cyan]")
        if to_squidstore:
            console.print("[cyan]Dry run only; no Squid store writes.[/cyan]")
        return

    cfg.apply_model_import(selected.system, selected.model_settings)
    cfg_path = Path(ctx.meta.get("config_path", Config.default_path()))
    written = cfg.save(cfg_path)
    console.print(f"[green]✓ Imported settings saved to {written}[/green]")

    if to_squidstore:
        result = import_detection_to_squid_store(
            selected,
            target_agent_id=target_agent_id,
            db_path=Path(squidstore_db).expanduser().resolve() if squidstore_db else None,
            import_secrets=True,
            import_settings=True,
        )
        if result.success:
            console.print(
                f"[green]✓ Squid store import complete ({result.db_path})[/green]\\n"
                f"- settings records: {result.imported_settings_count}\\n"
                f"- secret records: {result.imported_secret_count}"
            )
        else:
            lines = [f"[yellow]Squid store import had errors ({result.db_path}):[/yellow]"]
            for e in result.errors:
                lines.append(f"- {e}")
            console.print("\\n".join(lines))


# Tool commands
@cli.group()
def tool():
    """Tool operations."""
    pass


@tool.command("use")
@click.argument("description")
@pass_client
def use_tool(client: Busy38Client, description: str):
    """Execute a tool via plain English description.
    
    Example: busy-bridge tool use "Search the web for OpenClaw docs"
    """
    try:
        with console.status("[bold green]Executing tool..."):
            result = client.use_tool(description)
        format_tool_result(result)
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@tool.command("list")
@pass_client
def list_tools(client: Busy38Client):
    """List available tools."""
    try:
        tools = client.list_tools()
        format_tool_list(tools)
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@tool.command("show")
@click.argument("name")
@pass_client
def show_tool(client: Busy38Client, name: str):
    """Show detailed information about a tool."""
    try:
        tool_info = client.lookup_tool(name)
        format_tool_details(tool_info)
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@tool.command("make")
@click.argument("description")
@click.option("--follow", "-f", is_flag=True, help="Follow mission progress")
@pass_client
def make_tool(client: Busy38Client, description: str, follow: bool):
    """Create a new tool via mission.
    
    Example: busy-bridge tool make "Create an RSS reader that checks every 3 hours"
    """
    try:
        with console.status("[bold green]Starting tool creation mission..."):
            result = client.make_tool(description)
        
        mission_id = result.get("mission_id")
        console.print(f"[green]✓[/green] Tool creation mission started: {mission_id}")
        
        if follow:
            console.print("\n[dim]Following mission progress...[/dim]")
            # TODO: Implement streaming follow
            console.print("[yellow]Streaming not yet implemented - use 'show mission' to check status[/yellow]")
        
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# Mission commands
@cli.group()
def mission():
    """Mission operations."""
    pass


@mission.command("start")
@click.argument("objective")
@click.option("--role", "-r", default="mission_agent", help="Agent role")
@click.option("--max-steps", "-s", default=6, help="Maximum steps")
@click.option("--follow", "-f", is_flag=True, help="Follow mission progress")
@pass_client
def start_mission(client: Busy38Client, objective: str, role: str, max_steps: int, follow: bool):
    """Start a new mission.
    
    Example: busy-bridge mission start "Analyze codebase for security issues"
    """
    try:
        with console.status("[bold green]Starting mission..."):
            result = client.start_mission(
                objective=objective,
                role=role,
                max_steps=max_steps,
            )
        
        mission_id = result.get("mission_id")
        console.print(f"[green]✓[/green] Mission started: {mission_id}")
        
        if follow:
            console.print("\n[dim]Following mission progress...[/dim]")
            # TODO: Implement streaming follow
            console.print("[yellow]Streaming not yet implemented - use 'show mission' to check status[/yellow]")
        
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@mission.command("list")
@pass_client
def list_missions(client: Busy38Client):
    """List all missions."""
    try:
        missions = client.list_missions()
        format_mission_list(missions)
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@mission.command("show")
@click.argument("mission_id")
@click.option("--notes", "-n", is_flag=True, help="Include notes")
@pass_client
def show_mission(client: Busy38Client, mission_id: str, notes: bool):
    """Show mission details."""
    try:
        mission = client.get_mission(mission_id)
        notes_list = None
        if notes:
            notes_list = client.get_mission_notes(mission_id)
        format_mission_details(mission, notes_list)
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@mission.command("cancel")
@click.argument("mission_id")
@click.option("--reason", "-r", default="Cancelled by user", help="Cancellation reason")
@pass_client
def cancel_mission(client: Busy38Client, mission_id: str, reason: str):
    """Cancel a running mission."""
    try:
        result = client.cancel_mission(mission_id, reason)
        if result.get("success"):
            console.print(f"[green]✓[/green] Mission {mission_id} cancelled")
        else:
            console.print(f"[red]✗[/red] Failed to cancel: {result.get('error', 'Unknown error')}")
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@mission.command("respond")
@click.argument("mission_id")
@click.argument("response")
@pass_client
def respond_to_mission(client: Busy38Client, mission_id: str, response: str):
    """Respond to a mission query."""
    try:
        result = client.respond_to_mission(mission_id, response)
        if result.get("success"):
            console.print(f"[green]✓[/green] Response sent to mission {mission_id}")
        else:
            console.print(f"[red]✗[/red] Failed to respond: {result.get('error', 'Unknown error')}")
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# Cheatcode commands
@cli.group()
def cheatcode():
    """Cheatcode operations."""
    pass


@cheatcode.command("use")
@click.argument("cheatcode_str")
@click.option("--param", "-p", multiple=True, help="Parameters as key=value")
@pass_client
def use_cheatcode(client: Busy38Client, cheatcode_str: str, param: list):
    """Execute a cheatcode.
    
    Format: namespace:action
    
    Example: busy-bridge cheatcode use rw4:read_file --param path=README.md
    """
    try:
        # Parse cheatcode string
        if ":" not in cheatcode_str:
            console.print("[red]Error:[/red] Cheatcode must be in format namespace:action")
            sys.exit(1)
        
        namespace, action = cheatcode_str.split(":", 1)
        
        # Parse parameters
        attributes = {}
        for p in param:
            if "=" not in p:
                console.print(f"[red]Error:[/red] Parameter must be key=value: {p}")
                sys.exit(1)
            key, value = p.split("=", 1)
            attributes[key] = value
        
        with console.status(f"[bold green]Executing {namespace}:{action}..."):
            result = client.use_cheatcode(namespace, action, **attributes)
        
        format_cheatcode_result(result)
        
    except Busy38Error as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# Shortcuts for common operations
@cli.command()
@click.argument("description")
@pass_client
def use(client: Busy38Client, description: str):
    """Shortcut: Execute a tool via plain English.
    
    Same as: busy-bridge tool use "description"
    """
    ctx = click.get_current_context()
    ctx.invoke(use_tool, description=description)


@cli.command()
@click.argument("objective")
@click.option("--role", "-r", default="mission_agent")
@click.option("--max-steps", "-s", default=6)
@click.option("--follow", "-f", is_flag=True)
@pass_client
def start(client: Busy38Client, objective: str, role: str, max_steps: int, follow: bool):
    """Shortcut: Start a new mission.
    
    Same as: busy-bridge mission start "objective"
    """
    ctx = click.get_current_context()
    ctx.invoke(start_mission, objective=objective, role=role, max_steps=max_steps, follow=follow)


@cli.command()
@click.argument("description")
@click.option("--follow", "-f", is_flag=True)
@pass_client
def make(client: Busy38Client, description: str, follow: bool):
    """Shortcut: Create a new tool.
    
    Same as: busy-bridge tool make "description"
    """
    ctx = click.get_current_context()
    ctx.invoke(make_tool, description=description, follow=follow)


@cli.command()
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8080, help="Port to listen on")
def server(host: str, port: int):
    """Start the API server.
    
    Runs the Busy Bridge API server that OpenClaw agents connect to.
    """
    console.print(f"[green]Starting Busy Bridge API server on {host}:{port}[/green]")
    
    try:
        from .server import start_server
        start_server(host=host, port=port)
    except ImportError as e:
        console.print(f"[red]Error:[/red] Failed to start server: {e}")
        console.print("[dim]Make sure you have installed server dependencies:[/dim]")
        console.print("  pip install busy-bridge[server]")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
