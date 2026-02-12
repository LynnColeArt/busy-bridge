"""Output formatters using Rich."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

console = Console()


def format_health(status: Dict[str, Any]) -> None:
    """Format health check output."""
    if status.get("status") == "healthy":
        console.print(f"[green]●[/green] Busy38 is healthy (v{status.get('version', 'unknown')})")
    else:
        console.print(f"[red]●[/red] Busy38 is unhealthy: {status.get('error', 'Unknown error')}")


def format_tool_list(tools: List[Dict[str, Any]]) -> None:
    """Format tool list as a table."""
    if not tools:
        console.print("[yellow]No tools found[/yellow]")
        return
    
    table = Table(title="Available Tools")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Category", style="green")
    
    for tool in tools:
        table.add_row(
            tool.get("name", "unknown"),
            tool.get("description", "")[:60] + "..." if len(tool.get("description", "")) > 60 else tool.get("description", ""),
            tool.get("category", "general"),
        )
    
    console.print(table)


def format_tool_details(tool: Dict[str, Any]) -> None:
    """Format detailed tool information."""
    name = tool.get("name", "unknown")
    description = tool.get("description", "No description")
    
    panel_content = Text()
    panel_content.append(f"{description}\n\n", style="white")
    
    if tool.get("parameters"):
        panel_content.append("Parameters:\n", style="bold")
        for param_name, param_info in tool["parameters"].items():
            req = "required" if param_info.get("required") else "optional"
            panel_content.append(f"  • {param_name}", style="cyan")
            panel_content.append(f" ({param_info.get('type', 'string')}, {req})\n", style="dim")
            if param_info.get("description"):
                panel_content.append(f"    {param_info['description']}\n", style="dim")
    
    if tool.get("examples"):
        panel_content.append("\nExamples:\n", style="bold")
        for example in tool["examples"][:3]:  # Show first 3
            panel_content.append(f"  {example}\n", style="green")
    
    console.print(Panel(panel_content, title=f"Tool: {name}", border_style="blue"))


def format_mission_list(missions: List[Dict[str, Any]]) -> None:
    """Format mission list as a table."""
    if not missions:
        console.print("[yellow]No missions found[/yellow]")
        return
    
    table = Table(title="Missions")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Objective", style="white", max_width=40)
    table.add_column("State", style="green")
    table.add_column("Created", style="dim")
    
    state_colors = {
        "pending": "yellow",
        "running": "blue",
        "waiting_on_orchestrator": "magenta",
        "qa_review": "cyan",
        "approved": "green",
        "failed": "red",
        "cancelled": "dim",
    }
    
    for mission in missions:
        mission_id = mission.get("mission_id", "unknown")[:12]
        objective = mission.get("objective", "")[:37] + "..." if len(mission.get("objective", "")) > 40 else mission.get("objective", "")
        state = mission.get("state", "unknown")
        created = mission.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass
        
        color = state_colors.get(state, "white")
        table.add_row(mission_id, objective, f"[{color}]{state}[/{color}]", created)
    
    console.print(table)


def format_mission_details(mission: Dict[str, Any], notes: Optional[List[Dict]] = None) -> None:
    """Format detailed mission information."""
    mission_id = mission.get("mission_id", "unknown")
    state = mission.get("state", "unknown")
    objective = mission.get("objective", "No objective")
    
    # State color
    state_colors = {
        "pending": "yellow",
        "running": "blue",
        "waiting_on_orchestrator": "magenta",
        "qa_review": "cyan",
        "needs_revision": "yellow",
        "approved": "green",
        "failed": "red",
        "cancelled": "dim",
    }
    state_color = state_colors.get(state, "white")
    
    # Main info panel
    content = Text()
    content.append(f"State: ", style="bold")
    content.append(f"{state}\n", style=state_color)
    content.append(f"Objective: ", style="bold")
    content.append(f"{objective}\n", style="white")
    
    if mission.get("error"):
        content.append(f"\nError: ", style="bold red")
        content.append(f"{mission['error']}\n", style="red")
    
    if mission.get("cancel_reason"):
        content.append(f"\nCancelled: ", style="bold yellow")
        content.append(f"{mission['cancel_reason']}\n", style="yellow")
    
    # Steps
    if mission.get("steps"):
        content.append(f"\nSteps:\n", style="bold")
        for step in mission["steps"]:
            status = step.get("status", "pending")
            desc = step.get("description", "Unknown")
            status_emoji = "✓" if status == "completed" else "○" if status == "pending" else "●"
            status_color = "green" if status == "completed" else "dim" if status == "pending" else "blue"
            content.append(f"  {status_emoji} ", style=status_color)
            content.append(f"{desc}\n", style="white" if status != "pending" else "dim")
    
    console.print(Panel(content, title=f"Mission: {mission_id}", border_style="blue"))
    
    # Notes
    if notes:
        console.print(f"\n[bold]Notes:[/bold]")
        for note in notes:
            category = note.get("category", "general")
            title = note.get("title", "Untitled")
            author = note.get("author_id", "unknown")
            
            note_style = "yellow" if category == "mission_cancel_request" else "cyan" if category == "query" else "white"
            console.print(f"  [{note_style}]● {title}[/{note_style}] [dim](from {author})[/dim]")
            
            payload = note.get("payload", {})
            if payload:
                for key, value in payload.items():
                    console.print(f"    [dim]{key}: {str(value)[:100]}[/dim]")


def format_tool_result(result: Dict[str, Any]) -> None:
    """Format tool execution result."""
    if result.get("success"):
        console.print("[green]✓ Success[/green]")
    else:
        console.print(f"[red]✗ Failed: {result.get('error', 'Unknown error')}[/red]")
    
    # Display result data
    if "result" in result:
        console.print(result["result"])
    elif "output" in result:
        console.print(result["output"])


def format_cheatcode_result(result: Dict[str, Any]) -> None:
    """Format cheatcode execution result."""
    if result.get("success"):
        console.print("[green]✓ Success[/green]")
        if "content" in result:
            console.print(result["content"])
        elif "output" in result:
            console.print(result["output"])
        else:
            console.print(result)
    else:
        console.print(f"[red]✗ Failed: {result.get('error', 'Unknown error')}[/red])"
