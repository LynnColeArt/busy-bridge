"""Main CLI for Busy Bridge."""

import sys
from typing import Optional

import click
from rich.console import Console

from .client import Busy38Client, Busy38Error
from .config import Config
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
    # Load config
    cfg = Config.load()
    
    # Override with CLI options
    if url:
        cfg.url = url
    if api_key:
        cfg.api_key = api_key
    if config:
        cfg = Config.from_file(config)
    
    # Create client
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


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
