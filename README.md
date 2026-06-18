# agent-skills

A personal collection of [Agent Skills](https://www.skills.sh/) by [@ludmila-omlopes](https://github.com/ludmila-omlopes), installable across Claude Code, Cursor, and other agents via the [skills.sh](https://www.skills.sh/) CLI.

## Skills

### `youtube-gemini-analyzer`

Analyze a YouTube video by guiding you through Google's Gemini app **step by step — no API key, no downloads, no scripts**. You run Gemini yourself at [gemini.google.com](https://gemini.google.com); the skill writes the prompts for you to paste in, reviews what Gemini returns for accuracy red flags (vague timestamps, shaky speaker IDs, gaps, fabrication), and iterates with targeted follow-ups until the answer is complete and trustworthy.

Good for: summaries, full transcripts, key points, critiques/reviews, and finding clip-worthy moments for Shorts/TikTok — on any public YouTube video.

## Install

Install everything in this collection:

```bash
npx skills add ludmila-omlopes/agent-skills
```

Or just one skill:

```bash
npx skills add ludmila-omlopes/agent-skills --skill youtube-gemini-analyzer
```

The CLI auto-detects which coding agents you have installed and places the skill in the right directory (e.g. `.claude/skills/`). Browse more at [skills.sh](https://www.skills.sh/).
