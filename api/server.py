#!/usr/bin/env python3
"""
OpenClaw Skills — Hosted API Server

FastAPI server exposing intelligence skills as paid API endpoints.
Authentication via X-API-Key header, usage metering, and rate limiting.

Run:
    uvicorn api.server:app --host 0.0.0.0 --port 8400
    # or directly:
    python3 api/server.py
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Paths
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

METERING_PATH = Path(__file__).resolve().parent / "usage.json"

TODAY = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d")

# ---------------------------------------------------------------------------
# Auth & metering config
# ---------------------------------------------------------------------------

API_KEYS_RAW = os.environ.get("API_KEYS", "")
VALID_API_KEYS: set[str] = {k.strip() for k in API_KEYS_RAW.split(",") if k.strip()}

# Keys listed in PAID_API_KEYS env var get 1000 req/day; others get 100
PAID_KEYS_RAW = os.environ.get("PAID_API_KEYS", "")
PAID_API_KEYS: set[str] = {k.strip() for k in PAID_KEYS_RAW.split(",") if k.strip()}

FREE_TIER_LIMIT = 100
PAID_TIER_LIMIT = 1000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


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
# Usage metering
# ---------------------------------------------------------------------------


def _load_metering() -> dict:
    return load_json(METERING_PATH, {"daily": {}})


def _save_metering(data: dict):
    save_json(METERING_PATH, data)


def record_usage(api_key: str, endpoint: str):
    """Record one API call for the given key and endpoint."""
    data = _load_metering()
    day = TODAY()
    daily = data.setdefault("daily", {})
    day_data = daily.setdefault(day, {})
    key_data = day_data.setdefault(api_key, {"total": 0, "endpoints": {}})
    key_data["total"] += 1
    key_data["endpoints"][endpoint] = key_data["endpoints"].get(endpoint, 0) + 1
    _save_metering(data)


def get_daily_usage(api_key: str) -> int:
    data = _load_metering()
    day = TODAY()
    return data.get("daily", {}).get(day, {}).get(api_key, {}).get("total", 0)


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


def authenticate(x_api_key: str | None) -> str:
    """Validate API key and check rate limit. Returns the key."""
    if not VALID_API_KEYS:
        # If no keys configured, allow all (dev mode)
        return "dev"

    if not x_api_key or x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    limit = PAID_TIER_LIMIT if x_api_key in PAID_API_KEYS else FREE_TIER_LIMIT
    usage = get_daily_usage(x_api_key)
    if usage >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({usage}/{limit} requests today)",
        )

    return x_api_key


# ---------------------------------------------------------------------------
# Niche discovery logic (adapted from intelligence-discover-niches.py)
# ---------------------------------------------------------------------------

MIN_CONSENSUS_SCORE = 5.0
MIN_CLUSTER_SOURCES = 3
BREAKOUT_SIGNALS = {"BREAKOUT", "EMERGING"}
MIN_ENTITY_FREQUENCY = 3
MIN_RELEVANCE_SCORE = 2.0
MAX_SUGGESTIONS = 15


def _extract_keywords_from_title(title: str) -> list[str]:
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "before", "after", "and", "but", "or", "nor", "not", "so", "yet",
        "both", "either", "neither", "each", "every", "all", "any", "few",
        "more", "most", "other", "some", "such", "no", "only", "own", "same",
        "than", "too", "very", "just", "because", "if", "when", "while",
        "how", "what", "which", "who", "whom", "this", "that", "these",
        "those", "new", "report", "reports", "study", "says", "according",
        "about", "over", "also", "its", "their", "it", "they", "he", "she",
        "up", "out", "now",
    }
    title_clean = re.sub(r"[^\w\s]", " ", title.lower())
    words = [w for w in title_clean.split() if w not in stopwords and len(w) > 2]
    phrases = []
    if len(words) >= 2:
        for i in range(len(words) - 1):
            phrases.append(f"{words[i]} {words[i + 1]}")
    if len(words) >= 3:
        for i in range(len(words) - 2):
            phrases.append(f"{words[i]} {words[i + 1]} {words[i + 2]}")
    for w in words:
        if len(w) > 4:
            phrases.append(w)
    return list(dict.fromkeys(phrases))[:10]


def _generate_domain_candidates(keywords: list[str]) -> list[str]:
    domains = []
    for kw in keywords[:5]:
        slug = re.sub(r"[^a-z0-9]+", "", kw.lower().replace(" ", ""))
        if slug and len(slug) > 3:
            domains.append(f"{slug}.com")
        hyphen_slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
        if hyphen_slug and "-" in hyphen_slug:
            domains.append(f"{hyphen_slug}.com")
    return list(dict.fromkeys(domains))[:6]


def discover_niches(topic: str | None = None, depth: str = "standard") -> list[dict]:
    """Discover niches from intelligence data, optionally filtered by topic."""
    existing_slugs: set[str] = set()
    existing_keywords: set[str] = set()

    sources_data = load_json(SOURCES_PATH, {"sources": []})
    template_prefixes = ["gtrends-", "news-", "regulatory-", "competitors-", "domains-", "academic-", "community-"]
    for source in sources_data.get("sources", []):
        sid = source.get("id", "")
        for prefix in template_prefixes:
            if sid.startswith(prefix):
                existing_slugs.add(sid[len(prefix):])
                break
        for kw in source.get("keywords", []):
            existing_keywords.add(kw.lower())

    # Extract signals from consensus
    consensus_signals = []
    latest_consensus = get_latest_file(CONSENSUS_DIR)
    if latest_consensus:
        data = load_json(latest_consensus, {})
        for cluster in data.get("clusters", []):
            score = cluster.get("consensus_score", 0)
            source_count = cluster.get("source_count", 0)
            if score >= MIN_CONSENSUS_SCORE and source_count >= MIN_CLUSTER_SOURCES:
                consensus_signals.append({
                    "title": cluster.get("title", ""),
                    "consensus_score": score,
                    "source_count": source_count,
                    "keywords": _extract_keywords_from_title(cluster.get("title", "")),
                })

    # Extract trending signals
    trending_signals = []
    latest_trends = get_latest_file(TRENDS_DIR, "forecast-")
    if latest_trends:
        data = load_json(latest_trends, {})
        for f in data.get("forecasts", []):
            signal = f.get("signal", "")
            if signal in BREAKOUT_SIGNALS:
                trending_signals.append({
                    "keyword": f.get("keyword", ""),
                    "signal": signal,
                    "opportunity_score": f.get("opportunity_score", 0),
                })

    # Entity signals
    entity_signals = []
    entities_data = load_json(GRAPH_DIR / "entities.json", {})
    for key, entity in entities_data.items():
        if not isinstance(entity, dict):
            continue
        freq = entity.get("frequency", 0)
        if freq < MIN_ENTITY_FREQUENCY:
            continue
        name_lower = entity.get("name", key).lower()
        if name_lower in existing_keywords:
            continue
        sources_list = entity.get("sources", [])
        entity_signals.append({
            "name": entity.get("name", key),
            "type": entity.get("type", "unknown"),
            "frequency": freq,
            "source_count": len(sources_list) if isinstance(sources_list, list) else 0,
        })
    entity_signals.sort(key=lambda x: x["frequency"], reverse=True)
    entity_signals = entity_signals[:50]

    # Build candidates
    candidates: dict[str, dict] = {}

    for cs in consensus_signals:
        for kw in cs["keywords"]:
            slug = slugify(kw)
            if slug in existing_slugs or len(slug) < 3:
                continue
            if topic and topic.lower() not in kw.lower() and kw.lower() not in topic.lower():
                continue
            if slug not in candidates:
                candidates[slug] = {
                    "slug": slug, "name": kw.title(), "signals": [],
                    "keywords": set(), "trend_strength": 0.0, "consensus_breadth": 0.0,
                }
            candidates[slug]["signals"].append({"type": "consensus", "detail": cs["title"][:80]})
            candidates[slug]["consensus_breadth"] = max(candidates[slug]["consensus_breadth"], cs["consensus_score"])
            candidates[slug]["keywords"].update(cs["keywords"])

    for ts in trending_signals:
        kw = ts["keyword"]
        slug = slugify(kw)
        if slug in existing_slugs or len(slug) < 3:
            continue
        if topic and topic.lower() not in kw.lower() and kw.lower() not in topic.lower():
            continue
        if slug not in candidates:
            candidates[slug] = {
                "slug": slug, "name": kw.title(), "signals": [],
                "keywords": set(), "trend_strength": 0.0, "consensus_breadth": 0.0,
            }
        candidates[slug]["signals"].append({"type": "trend", "detail": ts["signal"]})
        candidates[slug]["trend_strength"] = max(candidates[slug]["trend_strength"], ts.get("opportunity_score", 0) / 10.0)
        candidates[slug]["keywords"].add(kw.lower())

    for es in entity_signals:
        slug = slugify(es["name"])
        if slug in existing_slugs or len(slug) < 3:
            continue
        if topic and topic.lower() not in es["name"].lower() and es["name"].lower() not in topic.lower():
            continue
        if slug not in candidates:
            candidates[slug] = {
                "slug": slug, "name": es["name"], "signals": [],
                "keywords": set(), "trend_strength": 0.0, "consensus_breadth": 0.0,
            }
        candidates[slug]["signals"].append({"type": "entity", "detail": f"{es['type']}: {es['frequency']}x"})
        candidates[slug]["consensus_breadth"] = max(candidates[slug]["consensus_breadth"], min(es["frequency"] / 5.0, 10.0))
        candidates[slug]["keywords"].add(es["name"].lower())

    # Score and rank
    max_sugg = MAX_SUGGESTIONS * 2 if depth == "deep" else MAX_SUGGESTIONS
    suggestions = []
    for cand in candidates.values():
        signal_bonus = min(len(cand["signals"]) * 0.5, 3.0)
        relevance = cand["trend_strength"] * 0.4 + cand["consensus_breadth"] * 0.4 + signal_bonus * 0.2
        if relevance < MIN_RELEVANCE_SCORE:
            continue
        keywords_list = sorted(cand["keywords"])
        suggestions.append({
            "slug": cand["slug"],
            "name": cand["name"],
            "relevance_score": round(relevance, 2),
            "suggested_keywords": keywords_list[:15],
            "estimated_domains": _generate_domain_candidates(keywords_list),
            "signals": cand["signals"][:5],
            "trend_strength": round(cand["trend_strength"], 2),
            "consensus_breadth": round(cand["consensus_breadth"], 2),
        })
    suggestions.sort(key=lambda x: x["relevance_score"], reverse=True)
    return suggestions[:max_sugg]


# ---------------------------------------------------------------------------
# Domain logic (adapted from intelligence-domains.py)
# ---------------------------------------------------------------------------

TLDS = [".com", ".org", ".co", ".io", ".net"]


def generate_domain_candidates(phrase: str, tlds: list[str] | None = None) -> list[str]:
    tlds = tlds or TLDS
    words = re.findall(r"[a-z0-9]+", phrase.lower())
    if not words or len(words) > 5:
        return []
    candidates = []
    joined = "".join(words)
    hyphenated = "-".join(words)
    for tld in tlds:
        candidates.append(f"{joined}{tld}")
        if len(words) > 1:
            candidates.append(f"{hyphenated}{tld}")
            candidates.append(f"the{joined}{tld}")
            candidates.append(f"get{joined}{tld}")
            candidates.append(f"my{joined}{tld}")
            if len(words) >= 2:
                short = "".join(words[:2])
                candidates.append(f"{short}{tld}")
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique[:20]


def check_domain_whois(domain: str) -> dict:
    try:
        import whois
    except ImportError:
        return {"domain": domain, "status": "error", "detail": "python-whois not installed"}

    try:
        w = whois.whois(domain)
        if not w or not w.domain_name:
            return {"domain": domain, "status": "possibly_available", "registrar": None, "expiry": None}

        expiry = w.expiration_date
        if isinstance(expiry, list):
            expiry = expiry[0]

        days_until = None
        status = "registered"
        if expiry:
            now = datetime.now(timezone.utc)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            days_until = (expiry - now).days
            if days_until < 0:
                status = "expired"
            elif days_until < 30:
                status = "expiring_soon"
            elif days_until < 90:
                status = "expiring_quarter"

        return {
            "domain": domain,
            "status": status,
            "registrar": w.registrar,
            "expiry": expiry.isoformat() if expiry else None,
            "days_until_expiry": days_until,
        }
    except Exception as exc:
        return {"domain": domain, "status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# Content generation logic (adapted from intelligence-content.py)
# ---------------------------------------------------------------------------


def generate_content(niche: str, topic: str | None = None, findings: list[dict] | None = None) -> dict:
    """Generate a blog post structure. Uses Ollama if available, else returns a template."""
    # Gather intelligence context
    latest_analyzed = get_latest_file(ANALYZED_DIR)
    intel_findings = []
    if latest_analyzed:
        intel_findings = load_json(latest_analyzed, [])
        if isinstance(intel_findings, list):
            niche_lower = niche.lower()
            intel_findings = [
                f for f in intel_findings
                if niche_lower in (f.get("source_id", "") + f.get("title", "") + f.get("snippet", "")).lower()
            ][:10]

    if findings:
        intel_findings = findings[:10]

    # Try Ollama generation
    try:
        import ollama

        finding_context = []
        for i, f in enumerate(intel_findings[:8], 1):
            finding_context.append(
                f"{i}. {f.get('title', 'Untitled')}\n"
                f"   Snippet: {f.get('snippet', '')[:200]}\n"
                f"   Source: {f.get('source_id', 'unknown')}"
            )

        topic_str = topic or niche
        prompt = (
            f"You are an SEO content writer for the {niche} niche. "
            f"Write a blog post about '{topic_str}'.\n\n"
            f"Intelligence context:\n{''.join(finding_context) if finding_context else 'No specific findings.'}\n\n"
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
        post["niche"] = niche
        return post

    except Exception:
        # Fallback: return template with gathered findings
        topic_str = topic or niche
        slug = slugify(topic_str)[:60]
        return {
            "title": f"{topic_str.title()} - Latest Insights and Analysis",
            "slug": slug,
            "description": f"Comprehensive analysis of {topic_str} trends and opportunities in the {niche} space.",
            "keywords": [niche, topic_str] + [f.get("query", "") for f in intel_findings[:5] if f.get("query")],
            "content": _build_template_content(niche, topic_str, intel_findings),
            "generated_by": "template",
            "niche": niche,
            "findings_used": len(intel_findings),
        }


def _build_template_content(niche: str, topic: str, findings: list[dict]) -> str:
    lines = [
        f"# {topic.title()} - Latest Insights",
        "",
        f"The {niche} space is evolving rapidly. Here are the latest intelligence findings.",
        "",
    ]
    if findings:
        lines.append("## Key Findings")
        lines.append("")
        for f in findings[:8]:
            title = f.get("title", "Untitled")
            snippet = f.get("snippet", "")[:200]
            lines.append(f"### {title}")
            lines.append("")
            lines.append(snippet)
            lines.append("")
    lines.extend([
        "## What This Means",
        "",
        f"These developments signal important shifts in the {niche} landscape.",
        "",
        "## Next Steps",
        "",
        "Stay informed and monitor these trends as they develop.",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Affiliate link injection
# ---------------------------------------------------------------------------

DEFAULT_AFFILIATE_CONFIG = {
    "links": {
        "amazon": {"pattern": r"\b(buy|purchase|shop|order)\b", "url": "https://amazon.com/dp/{asin}?tag={tag}"},
    },
    "max_links_per_post": 5,
    "tag": "openclaw-20",
}


def inject_affiliate_links(markdown: str, config: dict | None = None) -> dict:
    cfg = config or DEFAULT_AFFILIATE_CONFIG
    max_links = cfg.get("max_links_per_post", 5)
    tag = cfg.get("tag", "openclaw-20")
    links_injected = 0
    result = markdown

    # Simple keyword-based injection
    for name, link_cfg in cfg.get("links", {}).items():
        if links_injected >= max_links:
            break
        pattern = link_cfg.get("pattern", "")
        url_template = link_cfg.get("url", "")
        if not pattern:
            continue
        matches = list(re.finditer(pattern, result, re.IGNORECASE))
        for match in matches[:max_links - links_injected]:
            word = match.group(0)
            url = url_template.replace("{tag}", tag).replace("{asin}", "PLACEHOLDER")
            replacement = f"[{word}]({url})"
            result = result[:match.start()] + replacement + result[match.end():]
            links_injected += 1
            break  # One per pattern to avoid offset issues

    return {
        "markdown": result,
        "links_injected": links_injected,
        "original_length": len(markdown),
        "new_length": len(result),
    }


# ---------------------------------------------------------------------------
# Intelligence dashboard / trends / entities
# ---------------------------------------------------------------------------


def get_dashboard() -> dict:
    """Build a summary dashboard from all intelligence outputs."""
    # Latest analyzed
    latest_analyzed = get_latest_file(ANALYZED_DIR)
    analyzed_count = 0
    if latest_analyzed:
        data = load_json(latest_analyzed, [])
        analyzed_count = len(data) if isinstance(data, list) else 0

    # Latest consensus
    latest_consensus = get_latest_file(CONSENSUS_DIR)
    consensus_info = {}
    if latest_consensus:
        data = load_json(latest_consensus, {})
        consensus_info = {
            "total_clusters": data.get("total_clusters", 0),
            "high_confidence": len([c for c in data.get("clusters", []) if c.get("confidence_level") == "HIGH"]),
            "date": latest_consensus.stem,
        }

    # Domain opportunities
    latest_domains = get_latest_file(DOMAINS_DIR)
    domain_info = {}
    if latest_domains:
        data = load_json(latest_domains, {})
        domain_info = {
            "opportunities": data.get("opportunities_found", 0),
            "keywords_tracked": data.get("trending_keywords", 0),
            "date": data.get("date", ""),
        }

    # Revenue
    revenue_metrics = {}
    latest_revenue = get_latest_file(REVENUE_DIR, "metrics-")
    if latest_revenue:
        data = load_json(latest_revenue, {})
        revenue_metrics = data.get("summary", {})

    # Keyword feedback
    keyword_metrics = load_json(FEEDBACK_DIR / "keyword-metrics.json", {})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": {"total": analyzed_count, "date": latest_analyzed.stem if latest_analyzed else None},
        "consensus": consensus_info,
        "domains": domain_info,
        "revenue": revenue_metrics,
        "keywords": {
            "total": keyword_metrics.get("total_keywords", 0),
            "avg_quality": keyword_metrics.get("avg_quality_score", 0),
            "dead": keyword_metrics.get("keywords_dead", 0),
            "suggestions": keyword_metrics.get("suggestions_count", 0),
        },
    }


def get_trends() -> dict:
    """Return trend forecasts."""
    latest = get_latest_file(TRENDS_DIR, "forecast-")
    if not latest:
        return {"forecasts": [], "date": None}
    data = load_json(latest, {})
    return {
        "date": latest.stem.replace("forecast-", ""),
        "forecasts": data.get("forecasts", []),
        "total": len(data.get("forecasts", [])),
    }


def get_entities(limit: int = 50) -> dict:
    """Return top entities from the knowledge graph."""
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
    return {
        "total": len(entities),
        "entities": entities[:limit],
    }


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class NicheDiscoverRequest(BaseModel):
    topic: Optional[str] = None
    depth: Optional[str] = Field(default="standard", description="standard or deep")


class DomainSearchRequest(BaseModel):
    keywords: list[str]
    tlds: Optional[list[str]] = None


class DomainCheckRequest(BaseModel):
    domains: list[str]


class ContentGenerateRequest(BaseModel):
    niche: str
    topic: Optional[str] = None
    findings: Optional[list[dict]] = None


class AffiliateInjectRequest(BaseModel):
    markdown: str
    config: Optional[dict] = None


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OpenClaw Intelligence API",
    description="Paid API for niche discovery, domain sniping, content generation, and intelligence dashboards.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/v1/niche/discover")
async def api_niche_discover(
    body: NicheDiscoverRequest,
    x_api_key: Optional[str] = Header(None),
):
    key = authenticate(x_api_key)
    record_usage(key, "niche.discover")
    suggestions = discover_niches(topic=body.topic, depth=body.depth or "standard")
    return {
        "status": "ok",
        "total": len(suggestions),
        "suggestions": suggestions,
    }


@app.post("/api/v1/domain/search")
async def api_domain_search(
    body: DomainSearchRequest,
    x_api_key: Optional[str] = Header(None),
):
    key = authenticate(x_api_key)
    record_usage(key, "domain.search")
    results = {}
    for kw in body.keywords[:20]:  # Cap at 20 keywords
        results[kw] = generate_domain_candidates(kw, tlds=body.tlds)
    total_domains = sum(len(v) for v in results.values())
    return {
        "status": "ok",
        "keywords": len(results),
        "total_candidates": total_domains,
        "results": results,
    }


@app.post("/api/v1/domain/check")
async def api_domain_check(
    body: DomainCheckRequest,
    x_api_key: Optional[str] = Header(None),
):
    key = authenticate(x_api_key)
    record_usage(key, "domain.check")
    results = []
    for domain in body.domains[:10]:  # Cap at 10 WHOIS lookups per request
        result = check_domain_whois(domain)
        results.append(result)
        time.sleep(0.5)  # Rate limit WHOIS
    return {
        "status": "ok",
        "checked": len(results),
        "results": results,
    }


@app.post("/api/v1/content/generate")
async def api_content_generate(
    body: ContentGenerateRequest,
    x_api_key: Optional[str] = Header(None),
):
    key = authenticate(x_api_key)
    record_usage(key, "content.generate")
    post = generate_content(niche=body.niche, topic=body.topic, findings=body.findings)
    return {
        "status": "ok",
        "post": post,
    }


@app.post("/api/v1/affiliate/inject")
async def api_affiliate_inject(
    body: AffiliateInjectRequest,
    x_api_key: Optional[str] = Header(None),
):
    key = authenticate(x_api_key)
    record_usage(key, "affiliate.inject")
    result = inject_affiliate_links(markdown=body.markdown, config=body.config)
    return {
        "status": "ok",
        **result,
    }


@app.get("/api/v1/intelligence/dashboard")
async def api_dashboard(x_api_key: Optional[str] = Header(None)):
    key = authenticate(x_api_key)
    record_usage(key, "intelligence.dashboard")
    return {
        "status": "ok",
        "dashboard": get_dashboard(),
    }


@app.get("/api/v1/intelligence/trends")
async def api_trends(x_api_key: Optional[str] = Header(None)):
    key = authenticate(x_api_key)
    record_usage(key, "intelligence.trends")
    return {
        "status": "ok",
        **get_trends(),
    }


@app.get("/api/v1/intelligence/entities")
async def api_entities(
    limit: int = 50,
    x_api_key: Optional[str] = Header(None),
):
    key = authenticate(x_api_key)
    record_usage(key, "intelligence.entities")
    return {
        "status": "ok",
        **get_entities(limit=limit),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


# ---------------------------------------------------------------------------
# Direct run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8400"))
    print(f"Starting OpenClaw Intelligence API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
