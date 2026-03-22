# OpenClaw Skills

> The only AI skills that find niches, buy domains, build sites, write content, inject affiliate links, and track revenue — all autonomously.

## Skills

| Skill | Command | What It Does |
|-------|---------|-------------|
| **Niche Finder** | `/niche-finder` | Discovers profitable niches from trending topics, rising search demand, and available domains |
| **Site Factory** | `/site-factory` | Domain → scaffolded Next.js site with SEO, content structure, and affiliate links in one command |
| **Intelligence Radar** | `/intelligence-radar` | 86-source OSINT pipeline with Ollama-powered consensus detection and entity extraction |
| **Domain Sniper** | `/domain-sniper` | Trend-to-domain intersection — finds available/expiring domains matching rising search demand |
| **Content Engine** | `/content-engine` | Generates SEO blog posts from live intelligence findings with affiliate link injection |
| **Revenue Tracker** | `/revenue-tracker` | Full-loop ROI tracking: intelligence → acquisition → deployment → revenue per niche |

## Installation

```bash
# Add as marketplace
/plugin marketplace add https://github.com/openclaw/openclaw-skills

# Install individual skills
/plugin install niche-finder@openclaw-skills
/plugin install site-factory@openclaw-skills
/plugin install intelligence-radar@openclaw-skills
/plugin install domain-sniper@openclaw-skills
/plugin install content-engine@openclaw-skills
/plugin install revenue-tracker@openclaw-skills
```

## Requirements

- Claude Code, OpenAI Codex, Gemini CLI, or any compatible agent
- Python 3.9+
- Ollama (for consensus + content generation)
- API keys: Brave Search, Firecrawl (optional), WhoisFreaks (optional), Dynadot (optional)

## How It Works

```
/niche-finder "health wellness"
  → Discovers 5 profitable sub-niches with trend data + domain availability

/domain-sniper --niche "clean beauty"
  → Finds 12 domains matching rising trends, 3 available for registration

/site-factory --domain "cleanbeautyguide.com" --niche "clean beauty"
  → Generates full Next.js project: SEO metadata, landing page, content structure

/content-engine --niche "clean beauty"
  → Writes 5 SEO blog posts from intelligence findings, injects affiliate links

/revenue-tracker
  → Shows: 3 domains acquired, 2 sites live, $847/mo revenue, 340% ROI
```

## License

MIT
