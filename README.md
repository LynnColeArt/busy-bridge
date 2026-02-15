# Busy Bridge

CLI bridge to Busy38 - the most sophisticated agent IDE and capability platform.

## What is Busy Bridge?

Roadmap note: full internal rebrand Phase 2 is deferred until after closed-beta hardening is complete.

## AI-Generated / Automated Contributions

Automated code generation and AI-assisted submissions are welcome.

For production code, placeholders are not acceptable.

- Unit tests may use mocks and stubs.
- Runtime and transport code must be functional and test-backed.
- New functionality must include unit tests (or updates to existing tests) that cover the behavior.

Before submitting generated changes, verify:

- No temporary placeholders in core implementation paths (`TODO`, `FIXME`, `NotImplementedError`).
- Mock/stub logic is used only in tests and local fixtures.
- New behavior has at least smoke/integration validation.
- Error behavior is explicit and documented for transport/security-sensitive paths.
- Failure states are telemetry and should remain visible; do not introduce graceful-fallback behavior that hides runtime failures.
- All relevant tests pass before merge.

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
export BUSY38_SOURCE_PATH="/path/to/busy"   # Optional: Busy source checkout for embedded server mode
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
busy-bridge tool use "Search the web for OpenClaw documentation"
```

Create new tools:

```bash
busy-bridge tool make "Create an RSS feed reader that checks every 3 hours"
```

List and inspect tools:

```bash
busy-bridge tool list
busy-bridge tool show read_file
```

### Missions

Start structured missions:

```bash
busy-bridge mission start "Analyze codebase for security issues"
```

Monitor and interact:

```bash
busy-bridge mission list
busy-bridge mission show mission_abc123
busy-bridge mission show mission_abc123 --notes
```

Cancel if needed:

```bash
busy-bridge mission cancel mission_abc123 --reason "Changed priorities"
```

Respond to sub-agent questions:

```bash
busy-bridge mission respond mission_abc123 "Use DuckDB for persistence"
```

### Cheatcodes

Direct cheatcode invocation:

```bash
busy-bridge cheatcode use rw4:read_file --param path=README.md
busy-bridge cheatcode use rw4:shell --param cmd="git status"
```

### Settings Import

Detect importable model settings from other agent systems:

```bash
busy-bridge settings detect
busy-bridge settings detect --source openclaw
```

Import detected model settings into `~/.config/busy-bridge/config.yaml`:

```bash
busy-bridge settings import
busy-bridge settings import --source openclaw
busy-bridge settings import --dry-run
busy-bridge settings show
```

Optionally import detected plaintext secrets/settings into Squid store (key-store):

```bash
pip install "busy-bridge[keystore]"
# If you have the local key-store repo (recommended for Busy), install it too:
#   pip install -e ../key-store
busy-bridge settings import --source openclaw --to-squidstore
busy-bridge settings import --source codex --to-squidstore --squidstore-db ./data/keystore.duckdb
```

Detected sources include common dot-config systems such as `.openclaw`, `.opencode`, `.codex`, `.claude` and related `~/.config/...` variants.
When plaintext keys are found (for example in `.env` or config files), bridge can import them into Squid store instead of keeping secrets in plain YAML.

## Mission Control

Follow a mission in real-time:

```bash
busy-bridge mission start "Refactor auth module" --follow
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
