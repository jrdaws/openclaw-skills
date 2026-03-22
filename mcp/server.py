#!/usr/bin/env python3
"""
OpenClaw Intelligence — MCP Server

Exposes the intelligence system as MCP (Model Context Protocol) tools
that AI agents (Claude Code, etc.) can call.

Supports two modes:
1. Native MCP via the `mcp` Python package (stdio transport)
2. Fallback HTTP server with JSON-RPC 2.0 (POST /mcp)

Run:
    python3 mcp/server.py              # stdio mode (for Claude Code)
    python3 mcp/server.py --http 8401  # HTTP fallback mode
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (same as the API server)
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parent.parent.parent.parent
INTEL_DIR = WORKSPACE / "research" / "intelligence"
ANALYZED_DIR = INTEL_DIR / "analyzed"
CONSENSUS_DIR = INTEL_DIR / "consensus"
TRENDS_DIR = INTEL_DIR / "trends"
GRAPH_DIR = INTEL_DIR / "graph"
DOMAINS_DIR = INTEL_DIR / "domains"
REVENUE_DIR = INTEL_DIR / "revenue"
FEEDBACK_DIR = INTEL_DIR / "feedback"
SOURCES_PATH = INTEL_DIR / "sources.json"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def get_latest_file(directory: Path, prefix: str = "") -> Path | None:
    if not directory.exists():
        return None
    files = sorted(
        [f for f in directory.iterdir() if f.suffix == ".json" and f.name.startswith(prefix)],
        reverse=True,
    )
    return files[0] if files else None


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tool_find_niches(topic: str) -> dict:
    """Find niche opportunities based on intelligence data."""
    existing_keywords: set[str] = set()
    existing_slugs: set[str] = set()

    sources_data = load_json(SOURCES_PATH, {"sources": []})
    prefixes = ["gtrends-", "news-", "regulatory-", "competitors-", "domains-", "academic-", "community-"]
    for source in sources_data.get("sources", []):
        sid = source.get("id", "")
        for prefix in prefixes:
            if sid.startswith(prefix):
                existing_slugs.add(sid[len(prefix):])
                break
        for kw in source.get("keywords", []):
            existing_keywords.add(kw.lower())

    # Consensus signals
    suggestions = []
    latest_consensus = get_latest_file(CONSENSUS_DIR)
    if latest_consensus:
        data = load_json(latest_consensus, {})
        for cluster in data.get("clusters", []):
            score = cluster.get("consensus_score", 0)
            title = cluster.get("title", "")
            if score >= 3 and (not topic or topic.lower() in title.lower()):
                suggestions.append({
                    "title": title,
                    "consensus_score": score,
                    "source_count": cluster.get("source_count", 0),
                    "confidence": cluster.get("confidence_level", "UNKNOWN"),
                    "type": "consensus_cluster",
                })

    # Trending signals
    latest_trends = get_latest_file(TRENDS_DIR, "forecast-")
    if latest_trends:
        data = load_json(latest_trends, {})
        for f in data.get("forecasts", []):
            kw = f.get("keyword", "")
            signal = f.get("signal", "")
            if signal in {"BREAKOUT", "EMERGING"} and (not topic or topic.lower() in kw.lower()):
                suggestions.append({
                    "keyword": kw,
                    "signal": signal,
                    "opportunity_score": f.get("opportunity_score", 0),
                    "type": "trend_signal",
                })

    # Niche suggestions from feedback
    niche_suggestions = load_json(FEEDBACK_DIR / "niche-suggestions.json", {})
    for s in niche_suggestions.get("suggestions", [])[:10]:
        if not topic or topic.lower() in s.get("name", "").lower():
            suggestions.append({
                "name": s.get("name"),
                "relevance_score": s.get("relevance_score", 0),
                "keywords": s.get("suggested_keywords", [])[:5],
                "type": "niche_suggestion",
            })

    suggestions.sort(key=lambda x: x.get("consensus_score", x.get("relevance_score", x.get("opportunity_score", 0))), reverse=True)
    return {
        "topic": topic,
        "total": len(suggestions),
        "opportunities": suggestions[:20],
    }


def tool_search_domains(keywords: list[str]) -> dict:
    """Search for domain name candidates based on keywords."""
    tlds = [".com", ".org", ".co", ".io", ".net"]
    results = {}
    for kw in keywords[:10]:
        words = re.findall(r"[a-z0-9]+", kw.lower())
        if not words or len(words) > 5:
            continue
        candidates = []
        joined = "".join(words)
        hyphenated = "-".join(words)
        for tld in tlds:
            candidates.append(f"{joined}{tld}")
            if len(words) > 1:
                candidates.append(f"{hyphenated}{tld}")
                candidates.append(f"the{joined}{tld}")
                candidates.append(f"get{joined}{tld}")
        results[kw] = list(dict.fromkeys(candidates))[:15]

    # Also check latest domain opportunities
    latest_domains = get_latest_file(DOMAINS_DIR)
    opportunities = []
    if latest_domains:
        data = load_json(latest_domains, {})
        for opp in data.get("opportunities", [])[:10]:
            opportunities.append({
                "domain": opp.get("domain", ""),
                "status": opp.get("status", ""),
                "keyword": opp.get("keyword", ""),
                "score": opp.get("opportunity_score", 0),
            })

    return {
        "candidates": results,
        "total_candidates": sum(len(v) for v in results.values()),
        "recent_opportunities": opportunities,
    }


def tool_check_trends(keywords: list[str]) -> dict:
    """Check trend data for given keywords."""
    latest = get_latest_file(TRENDS_DIR, "forecast-")
    if not latest:
        return {"keywords": keywords, "forecasts": [], "date": None}

    data = load_json(latest, {})
    forecasts = data.get("forecasts", [])

    keyword_set = {k.lower() for k in keywords}
    matched = []
    for f in forecasts:
        if f.get("keyword", "").lower() in keyword_set:
            matched.append(f)

    # If no exact matches, return all forecasts with relevant signals
    if not matched:
        matched = [f for f in forecasts if f.get("signal") in {"BREAKOUT", "EMERGING", "RISING"}][:20]

    return {
        "keywords": keywords,
        "date": latest.stem.replace("forecast-", ""),
        "total_forecasts": len(matched),
        "forecasts": matched,
    }


def tool_get_entities(limit: int = 50) -> dict:
    """Get top entities from the knowledge graph."""
    entities_data = load_json(GRAPH_DIR / "entities.json", {})
    entities = []
    for key, entity in entities_data.items():
        if not isinstance(entity, dict):
            continue
        entities.append({
            "id": key,
            "name": entity.get("name", key),
            "type": entity.get("type", "unknown"),
            "frequency": entity.get("frequency", 0),
            "source_count": len(entity.get("sources", [])) if isinstance(entity.get("sources"), list) else 0,
        })
    entities.sort(key=lambda x: x["frequency"], reverse=True)
    return {"total": len(entities), "entities": entities[:limit]}


def tool_get_intelligence_summary() -> dict:
    """Get a comprehensive intelligence dashboard summary."""
    # Analyzed findings
    latest_analyzed = get_latest_file(ANALYZED_DIR)
    analyzed_count = 0
    top_findings = []
    if latest_analyzed:
        data = load_json(latest_analyzed, [])
        if isinstance(data, list):
            analyzed_count = len(data)
            sorted_findings = sorted(data, key=lambda f: f.get("score", 0), reverse=True)
            for f in sorted_findings[:10]:
                top_findings.append({
                    "title": f.get("title", ""),
                    "score": f.get("score", 0),
                    "quadrant": f.get("quadrant", ""),
                    "source": f.get("source_id", ""),
                })

    # Consensus
    latest_consensus = get_latest_file(CONSENSUS_DIR)
    clusters = []
    if latest_consensus:
        data = load_json(latest_consensus, {})
        for c in data.get("clusters", [])[:10]:
            clusters.append({
                "title": c.get("title", ""),
                "consensus_score": c.get("consensus_score", 0),
                "confidence": c.get("confidence_level", ""),
                "source_count": c.get("source_count", 0),
            })

    # Trends
    latest_trends = get_latest_file(TRENDS_DIR, "forecast-")
    breakout_trends = []
    if latest_trends:
        data = load_json(latest_trends, {})
        for f in data.get("forecasts", []):
            if f.get("signal") in {"BREAKOUT", "EMERGING"}:
                breakout_trends.append({
                    "keyword": f.get("keyword", ""),
                    "signal": f.get("signal", ""),
                    "opportunity_score": f.get("opportunity_score", 0),
                })

    # Keyword health
    keyword_metrics = load_json(FEEDBACK_DIR / "keyword-metrics.json", {})

    # Revenue
    latest_revenue = get_latest_file(REVENUE_DIR, "metrics-")
    revenue = {}
    if latest_revenue:
        data = load_json(latest_revenue, {})
        revenue = data.get("summary", {})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": {"total": analyzed_count, "top": top_findings},
        "consensus_clusters": clusters,
        "breakout_trends": breakout_trends,
        "keyword_health": {
            "total": keyword_metrics.get("total_keywords", 0),
            "avg_quality": keyword_metrics.get("avg_quality_score", 0),
            "dead": keyword_metrics.get("keywords_dead", 0),
        },
        "revenue": revenue,
    }


def tool_generate_content(niche: str, topic: str) -> dict:
    """Generate a blog post for a given niche and topic."""
    # Gather relevant findings
    latest_analyzed = get_latest_file(ANALYZED_DIR)
    findings = []
    if latest_analyzed:
        data = load_json(latest_analyzed, [])
        if isinstance(data, list):
            niche_lower = niche.lower()
            topic_lower = topic.lower()
            for f in data:
                text = (f.get("source_id", "") + f.get("title", "") + f.get("snippet", "")).lower()
                if niche_lower in text or topic_lower in text:
                    findings.append(f)

    findings = sorted(findings, key=lambda f: f.get("score", 0), reverse=True)[:8]

    # Try Ollama
    try:
        import ollama

        context_parts = []
        for i, f in enumerate(findings[:6], 1):
            context_parts.append(f"{i}. {f.get('title', 'Untitled')}: {f.get('snippet', '')[:200]}")

        prompt = (
            f"You are an SEO content writer for the {niche} niche. "
            f"Write a blog post about '{topic}'.\n\n"
            f"Intelligence context:\n" + "\n".join(context_parts) + "\n\n"
            f"Return ONLY valid JSON: "
            f'{{"title": "...", "slug": "...", "description": "...", "keywords": [...], "content": "...markdown..."}}'
        )

        response = ollama.chat(
            model="gpt-oss:20b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7, "num_predict": 4096},
        )
        raw = response["message"]["content"].strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0]
        raw = raw.strip()
        if not raw.startswith("{"):
            idx = raw.find("{")
            if idx >= 0:
                raw = raw[idx:]
        post = json.loads(raw)
        post["generated_by"] = "ollama"
        return post

    except Exception:
        # Template fallback
        slug = slugify(topic)[:60]
        content_lines = [
            f"# {topic.title()}",
            "",
            f"The {niche} landscape is evolving. Here is the latest analysis on {topic}.",
            "",
        ]
        if findings:
            content_lines.append("## Key Findings")
            content_lines.append("")
            for f in findings[:6]:
                content_lines.append(f"- **{f.get('title', 'Untitled')}**: {f.get('snippet', '')[:150]}")
            content_lines.append("")

        content_lines.extend([
            "## Analysis",
            "",
            f"These findings point to significant developments in {topic} within the {niche} space.",
            "",
            "## Next Steps",
            "",
            "Monitor these trends and consider strategic positioning.",
        ])

        return {
            "title": f"{topic.title()} - {niche.title()} Analysis",
            "slug": slug,
            "description": f"Analysis of {topic} trends in the {niche} space.",
            "keywords": [niche, topic],
            "content": "\n".join(content_lines),
            "generated_by": "template",
            "findings_used": len(findings),
        }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS = {
    "find_niches": {
        "description": "Find niche opportunities based on intelligence data (consensus clusters, trends, entities)",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to filter niches by (e.g. 'clean beauty', 'sustainable fashion')"},
            },
            "required": ["topic"],
        },
        "handler": lambda args: tool_find_niches(args["topic"]),
    },
    "search_domains": {
        "description": "Generate domain name candidates for given keywords and check recent domain opportunities",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to generate domain candidates for",
                },
            },
            "required": ["keywords"],
        },
        "handler": lambda args: tool_search_domains(args["keywords"]),
    },
    "check_trends": {
        "description": "Check trend forecasts for keywords (breakout, emerging, rising signals)",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to check trends for",
                },
            },
            "required": ["keywords"],
        },
        "handler": lambda args: tool_check_trends(args["keywords"]),
    },
    "get_entities": {
        "description": "Get top entities from the intelligence knowledge graph",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max entities to return (default 50)", "default": 50},
            },
            "required": [],
        },
        "handler": lambda args: tool_get_entities(args.get("limit", 50)),
    },
    "get_intelligence_summary": {
        "description": "Get a comprehensive intelligence dashboard with findings, clusters, trends, keyword health, and revenue",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "handler": lambda args: tool_get_intelligence_summary(),
    },
    "generate_content": {
        "description": "Generate an SEO-optimized blog post for a niche and topic using intelligence findings",
        "parameters": {
            "type": "object",
            "properties": {
                "niche": {"type": "string", "description": "The niche (e.g. 'clean-beauty')"},
                "topic": {"type": "string", "description": "Specific topic for the post"},
            },
            "required": ["niche", "topic"],
        },
        "handler": lambda args: tool_generate_content(args["niche"], args["topic"]),
    },
}

# ---------------------------------------------------------------------------
# MCP Native Mode (using mcp package)
# ---------------------------------------------------------------------------


def run_mcp_native():
    """Run as a native MCP server using the mcp Python package."""
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    server = Server("openclaw-intelligence")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []
        for name, config in TOOLS.items():
            tools.append(Tool(
                name=name,
                description=config["description"],
                inputSchema=config["parameters"],
            ))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name not in TOOLS:
            return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
        try:
            result = TOOLS[name]["handler"](arguments)
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        except Exception as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    import asyncio
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream)

    asyncio.run(main())


# ---------------------------------------------------------------------------
# HTTP Fallback Mode (JSON-RPC 2.0)
# ---------------------------------------------------------------------------


def run_http_fallback(port: int = 8401):
    """Run as an HTTP server with JSON-RPC 2.0 protocol."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class MCPHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/mcp":
                self.send_error(404)
                return

            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                request = json.loads(body)
            except json.JSONDecodeError:
                self._send_json_rpc_error(None, -32700, "Parse error")
                return

            req_id = request.get("id")
            method = request.get("method", "")
            params = request.get("params", {})

            if method == "tools/list":
                tools_list = []
                for name, config in TOOLS.items():
                    tools_list.append({
                        "name": name,
                        "description": config["description"],
                        "inputSchema": config["parameters"],
                    })
                self._send_json_rpc_result(req_id, {"tools": tools_list})

            elif method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})

                if tool_name not in TOOLS:
                    self._send_json_rpc_error(req_id, -32602, f"Unknown tool: {tool_name}")
                    return

                try:
                    result = TOOLS[tool_name]["handler"](arguments)
                    self._send_json_rpc_result(req_id, {
                        "content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}],
                    })
                except Exception as exc:
                    self._send_json_rpc_error(req_id, -32000, str(exc))

            elif method == "initialize":
                self._send_json_rpc_result(req_id, {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "openclaw-intelligence", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                })

            else:
                self._send_json_rpc_error(req_id, -32601, f"Method not found: {method}")

        def _send_json_rpc_result(self, req_id: Any, result: Any):
            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
            self._send_json(response)

        def _send_json_rpc_error(self, req_id: Any, code: int, message: str):
            response = {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}
            self._send_json(response)

        def _send_json(self, data: dict):
            body = json.dumps(data, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            # Quiet logging for stdio compatibility
            pass

    server = HTTPServer(("0.0.0.0", port), MCPHandler)
    print(f"OpenClaw MCP Server (HTTP) running on port {port}", file=sys.stderr)
    print(f"  POST http://localhost:{port}/mcp", file=sys.stderr)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--http" in sys.argv:
        idx = sys.argv.index("--http")
        port = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 8401
        run_http_fallback(port)
    else:
        # Try native MCP first, fall back to HTTP
        try:
            from mcp.server import Server  # noqa: F401
            run_mcp_native()
        except ImportError:
            print("mcp package not found, falling back to HTTP JSON-RPC mode", file=sys.stderr)
            run_http_fallback(8401)
