# OpenClaw Intelligence MCP Server

MCP (Model Context Protocol) server that exposes the OpenClaw intelligence system as tools for AI agents.

## Tools

| Tool | Description |
|------|-------------|
| `find_niches` | Find niche opportunities from consensus clusters, trends, and entities |
| `search_domains` | Generate domain name candidates for keywords |
| `check_trends` | Check trend forecasts (breakout, emerging, rising) |
| `get_entities` | Get top entities from the knowledge graph |
| `get_intelligence_summary` | Full dashboard: findings, clusters, trends, revenue |
| `generate_content` | Generate SEO blog post for a niche/topic |

## Setup

### Option 1: Native MCP (recommended)

Install the `mcp` package:

```bash
pip install mcp
```

Add to your Claude Code config (`~/.claude/claude_desktop_config.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "openclaw-intelligence": {
      "command": "python3",
      "args": ["/Users/dd/.openclaw/workspace/projects/openclaw-skills/mcp/server.py"]
    }
  }
}
```

### Option 2: HTTP JSON-RPC Fallback

If the `mcp` package is not available, the server automatically falls back to HTTP mode:

```bash
python3 mcp/server.py --http 8401
```

Then use JSON-RPC 2.0 requests:

```bash
# List available tools
curl -X POST http://localhost:8401/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# Call a tool
curl -X POST http://localhost:8401/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "find_niches",
      "arguments": {"topic": "clean beauty"}
    }
  }'
```

## Example Tool Calls

### Find Niches
```json
{"name": "find_niches", "arguments": {"topic": "sustainable fashion"}}
```

### Search Domains
```json
{"name": "search_domains", "arguments": {"keywords": ["clean beauty", "organic skincare"]}}
```

### Check Trends
```json
{"name": "check_trends", "arguments": {"keywords": ["clean beauty", "PFAS free"]}}
```

### Get Intelligence Summary
```json
{"name": "get_intelligence_summary", "arguments": {}}
```

### Generate Content
```json
{"name": "generate_content", "arguments": {"niche": "clean-beauty", "topic": "PFAS regulation impact"}}
```

## Architecture

The MCP server reads intelligence data directly from the workspace:

```
workspace/research/intelligence/
  analyzed/     — scored findings
  consensus/    — multi-source clusters
  trends/       — trend forecasts
  graph/        — entity knowledge graph
  domains/      — domain opportunities
  revenue/      — portfolio and metrics
  feedback/     — keyword performance
```

No database required. All data comes from the daily intelligence pipeline output files.
