# OpenClaw Skills — Plugin Specification v1

## Overview

The OpenClaw plugin system lets the community extend the intelligence platform
with new data sources, pre-configured niches, output formats, and external
service integrations. Each plugin is a self-contained directory with a manifest
and implementation files.

---

## Plugin Types

| Type | Purpose | Entry Point |
|------|---------|-------------|
| `source-adapter` | Connect a new data source to the intelligence pipeline | Python module exposing `collect()` that returns findings |
| `niche-template` | Pre-configured niche with keywords, competitors, domains | JSON template consumed by `intelligence-new-niche.py` |
| `content-format` | New output format for intelligence findings | Python module exposing `format(findings) -> str` |
| `integration` | Connector to an external service (Slack, Discord, webhook, etc.) | Python module exposing `send(payload)` |

---

## Directory Structure

```
my-plugin/
  plugin.json          # Required — manifest
  adapter.py           # Entry point (name must match manifest "entry")
  requirements.txt     # Optional — pip dependencies
  README.md            # Optional — usage docs
  config.example.json  # Optional — example configuration
```

---

## Manifest: `plugin.json`

Every plugin must include a `plugin.json` at its root. Schema:

```json
{
  "name": "my-plugin",
  "type": "source-adapter | niche-template | content-format | integration",
  "version": "1.0.0",
  "description": "Short description of what this plugin does",
  "author": "github-username-or-org",
  "entry": "adapter.py",
  "config_schema": {
    "type": "object",
    "properties": {
      "api_key": { "type": "string", "description": "API key for the service" },
      "store_url": { "type": "string", "description": "Target store URL" }
    },
    "required": ["store_url"]
  },
  "openclaw_version": ">=1.0.0",
  "tags": ["ecommerce", "monitoring"]
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique plugin identifier. Lowercase, hyphens only. Must match directory name. |
| `type` | string | One of: `source-adapter`, `niche-template`, `content-format`, `integration` |
| `version` | string | Semantic version (major.minor.patch) |
| `description` | string | One-line description (under 120 chars) |
| `author` | string | Author name or GitHub username |
| `entry` | string | Relative path to the main implementation file |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `config_schema` | object | JSON Schema for plugin configuration |
| `openclaw_version` | string | Minimum OpenClaw version required |
| `tags` | string[] | Discovery tags for the plugin marketplace |
| `dependencies` | string[] | Other plugin names this plugin requires |
| `license` | string | SPDX license identifier (default: MIT) |

---

## Plugin Type Contracts

### source-adapter

The entry file must expose a `collect(config: dict) -> list[dict]` function.
Each returned dict is a finding with this shape:

```python
{
    "id": "unique-finding-id",
    "title": "Something changed",
    "url": "https://example.com/product",
    "source": "plugin:my-plugin",
    "category": "ecommerce",
    "summary": "Price dropped from $50 to $35",
    "timestamp": "2026-03-22T00:00:00Z",
    "metadata": { ... }  # Plugin-specific data
}
```

On install, the plugin's source definition is added to `sources.json` so the
main collection pipeline picks it up automatically.

### niche-template

The entry file must be a JSON file (typically `template.json`) with this shape:

```json
{
    "niche": "micro-saas",
    "display_name": "Micro SaaS",
    "keywords": ["micro saas", "indie hacker", "saas boilerplate"],
    "competitors": ["microconf.com", "indiehackers.com"],
    "domains": ["microsaas.com", "tinysaas.com"],
    "source_categories": ["news", "community", "competitors"],
    "default_tier": "T2"
}
```

On install, the template becomes available as a preset in
`intelligence-new-niche.py --template <name>`.

### content-format

The entry file must expose a `format(findings: list[dict], config: dict) -> str`
function. The returned string is the formatted output (Markdown, HTML, plain
text, etc.).

```python
def format(findings: list[dict], config: dict) -> str:
    """Convert intelligence findings into the target format."""
    ...
    return formatted_output
```

On install, the format becomes available in
`intelligence-content.py --format <name>`.

### integration

The entry file must expose a `send(payload: dict, config: dict) -> dict`
function. The payload contains findings/content, and the function delivers
it to the external service.

```python
def send(payload: dict, config: dict) -> dict:
    """Send payload to external service. Return status dict."""
    return {"status": "ok", "message_id": "..."}
```

---

## Plugin Lifecycle

1. **Install** -- `intelligence-plugins.py install <path-or-url>`
   - Validates `plugin.json` against the schema
   - Copies plugin directory to `research/intelligence/plugins/<name>/`
   - Registers in `research/intelligence/plugins/registry.json`
   - Type-specific hooks (add source, register template, etc.)

2. **Configure** -- Edit `research/intelligence/plugins/<name>/config.json`
   - Validated against `config_schema` from the manifest

3. **Run** -- `intelligence-plugins.py run <name>`
   - Loads the entry point and invokes the appropriate function
   - For source-adapters: runs `collect()` and merges findings into the pipeline
   - For content-formats: runs `format()` on latest findings

4. **Uninstall** -- `intelligence-plugins.py uninstall <name>`
   - Removes from registry
   - Removes plugin directory
   - Cleans up type-specific registrations (source entries, etc.)

---

## Registry: `registry.json`

The plugin registry lives at `research/intelligence/plugins/registry.json`:

```json
{
  "plugins": [
    {
      "name": "shopify-monitor",
      "type": "source-adapter",
      "version": "1.0.0",
      "installed_at": "2026-03-22T00:00:00Z",
      "path": "shopify-monitor",
      "enabled": true
    }
  ]
}
```

---

## Security

- Plugins run in the same process as the intelligence pipeline. Only install
  plugins from trusted sources.
- Never store secrets in `plugin.json`. Use `config.json` (gitignored) or
  environment variables.
- The loader validates manifest schema before installation. Malformed manifests
  are rejected.

---

## Contributing a Plugin

1. Create a directory with `plugin.json` + implementation
2. Test locally: `intelligence-plugins.py install ./my-plugin && intelligence-plugins.py run my-plugin`
3. Submit to the OpenClaw Skills marketplace via PR to `openclaw-skills/plugins/community/`
