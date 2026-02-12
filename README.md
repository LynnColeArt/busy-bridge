# Busy Bridge

CLI bridge to Busy38 - the most sophisticated agent IDE and capability platform.

## What is Busy Bridge?

Busy Bridge connects OpenClaw (and other agent systems) to Busy38's advanced capabilities:

- **Sophisticated IDE** (RangeWriter4) - LSP-powered code operations, multi-file refactoring
- **Mission System** - Structured sub-agent workflows with QA and cancellation
- **Tool Creation** - Generate new tools from plain English descriptions
- **Advanced Integrations** - Discord with context management, summaries, and more

## Installation

```bash
pip install busy-bridge
```

## Configuration

Set environment variables:

```bash
export BUSY38_URL="http://localhost:8080"  # Busy38 API endpoint
export BUSY38_API_KEY="your-api-key"        # Authentication token
```

Or use a config file at `~/.config/busy-bridge/config.yaml`:

```yaml
url: http://localhost:8080
api_key: your-api-key
```

## Usage

### Tools

Execute tools via plain English:

```bash
busy-bridge use tool "Search the web for OpenClaw documentation"
```

Create new tools:

```bash
busy-bridge make tool "Create an RSS feed reader that checks every 3 hours"
```

List and inspect tools:

```bash
busy-bridge list tools
busy-bridge show tool read_file
```

### Missions

Start structured missions:

```bash
busy-bridge start mission "Analyze codebase for security issues"
```

Monitor and interact:

```bash
busy-bridge list missions
busy-bridge show mission mission_abc123
busy-bridge show mission mission_abc123 --notes
```

Cancel if needed:

```bash
busy-bridge cancel mission mission_abc123 --reason "Changed priorities"
```

Respond to sub-agent questions:

```bash
busy-bridge respond mission_abc123 "Use DuckDB for persistence"
```

### Cheatcodes

Direct cheatcode invocation:

```bash
busy-bridge use cheatcode rw4:read_file path=README.md
busy-bridge use cheatcode rw4:shell cmd="git status"
```

## Mission Control

Follow a mission in real-time:

```bash
busy-bridge start mission "Refactor auth module" --follow
```

This streams notes, state changes, and sub-agent communications as they happen.

## Architecture

Busy Bridge is intentionally thin - it's a CLI → HTTP translator that:

1. Parses your commands
2. Constructs appropriate MissionSpecs or cheatcodes
3. Sends to Busy38's orchestrator
4. Displays results, notes, and state changes

Busy38 handles all the heavy lifting: planning, execution, QA, tool creation.

## License

MIT - Glassbox Engineering
