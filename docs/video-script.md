# OpenClaw Skills — Getting Started Video Script

**Duration:** 3 minutes
**Platform:** YouTube / Twitter / X
**Tone:** Fast-paced, punchy, dev-focused. No fluff.

---

## [0:00–0:08] HOOK

**VISUAL:** Black screen. Terminal cursor blinking. Text types out: `$ claude /niche-finder "health wellness"` — results flood the screen.

**NARRATION:**
"What if I told you that you could go from zero to a live, revenue-generating website in under 10 minutes — entirely from your terminal? Let me show you."

---

## [0:08–0:25] STEP 1 — INSTALL

**VISUAL:** Terminal. Run the install command. Six skills install with checkmarks appearing one by one.

```
$ claude skill install openclaw/niche-finder openclaw/domain-sniper openclaw/site-factory openclaw/content-engine openclaw/trend-radar openclaw/revenue-tracker
```

**NARRATION:**
"One command. Six AI skills. They install in 30 seconds. No config, no setup wizard. These are Claude Code skills — they run right in your terminal."

---

## [0:25–0:55] STEP 2 — FIND A NICHE

**VISUAL:** Terminal. Run niche-finder. Show the scanning animation, then the results table with scores. Highlight the top result with a green glow effect.

```
$ claude /niche-finder "health wellness"
```

**NARRATION:**
"Niche-finder scans 86 intelligence sources — Google Trends, Reddit, Amazon, TikTok — and surfaces trending niches with low competition. It just found 9 opportunities. Look at this: 'non-toxic home products' — score of 92, trend up 140%, competition is low. That's our niche."

---

## [0:55–1:20] STEP 3 — SNIPE A DOMAIN

**VISUAL:** Terminal. Run domain-sniper. Domain candidates appear with availability checks and scores.

```
$ claude /domain-sniper "non toxic home"
```

**NARRATION:**
"Domain-sniper generates brandable domains and checks availability in real time. nontoxichome.com — available, exact keyword match, score 96. We're taking it."

---

## [1:20–1:45] STEP 4 — BUILD THE SITE

**VISUAL:** Terminal. Run site-factory. File tree appears line by line — layout, pages, components, affiliate link module. Quick cut to VS Code showing the generated project structure.

```
$ claude /site-factory --domain "nontoxichome.com" --niche "non-toxic-home"
```

**NARRATION:**
"Site-factory generates a full Next.js project in 30 seconds. Pages, components, SEO metadata, affiliate tracking — 10 production-ready files. This isn't a template. It's a custom site built for your niche."

---

## [1:45–2:15] STEP 5 — GENERATE CONTENT

**VISUAL:** Terminal. Run content-engine. Posts generate one by one with word counts and affiliate link counts. Quick cut to a rendered blog post in the browser — clean design, proper headings, affiliate links highlighted.

```
$ claude /content-engine --niche "non-toxic-home" --posts 5
```

**NARRATION:**
"Content-engine writes 5 SEO-optimized blog posts — 13,000 words total. Each one targets a long-tail keyword, has natural affiliate links, and cross-references other posts on the site. Look at this — proper frontmatter, schema markup, internal linking. This is publication-ready content."

---

## [2:15–2:35] STEP 6 — DEPLOY

**VISUAL:** Terminal. npm install, then vercel deploy. Build progress bar fills up. URL appears. Cut to the live site in a browser — homepage, blog listing, individual post. Scroll through on desktop and mobile.

```
$ cd projects/nontoxichome && npm install && npx vercel --prod
```

**NARRATION:**
"Install dependencies, deploy to Vercel. 60 seconds. The site is live. Mobile responsive. Sitemap submitted. SEO metadata in place. Affiliate links active. Done."

---

## [2:35–2:50] STEP 7 — TRACK REVENUE

**VISUAL:** Terminal. Run revenue-tracker. Dashboard appears with revenue numbers, conversion counts, top posts. Then show the autonomous pipeline command.

```
$ claude /revenue-tracker --sites all --period 30d
```

**NARRATION:**
"Revenue-tracker gives you a single dashboard for affiliate earnings, ad revenue, and traffic. And the real power move — pipe trend-radar into content-engine for a fully autonomous pipeline. New trending topics become published posts, automatically, every day."

---

## [2:50–3:00] CLOSE

**VISUAL:** Split screen — left side shows the terminal with all 7 commands stacked, right side shows the live site. Text overlay: "Zero to revenue. Under 10 minutes." GitHub URL and OpenClaw logo appear.

**NARRATION:**
"Seven commands. Ten minutes. A live, monetized site running on autopilot. All six skills are free and open source. Link in the description. Go build something."

---

## Production Notes

- **Music:** Lo-fi electronic, builds energy through the middle, drops to minimal at the close
- **Transitions:** Hard cuts between terminal and browser. No slide animations.
- **Text overlays:** Step numbers + estimated time in bottom-left corner throughout
- **Terminal font:** JetBrains Mono or SF Mono, slightly enlarged for readability
- **Color grading:** Dark, high contrast. Cyan and emerald accent colors matching the OpenClaw brand
- **Thumbnail:** Terminal window with "10 min" in large gradient text, money emoji, terminal prompt visible
