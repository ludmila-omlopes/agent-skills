---
name: youtube-gemini-analyzer
description: Analyze a YouTube video by guiding the user through Google's Gemini app step by step — NO API key, NO downloads, NO scripts. The user runs Gemini themselves at gemini.google.com; this skill writes the prompts for them to paste in, reviews what Gemini returns, and iterates with targeted follow-ups until the answer is complete and trustworthy. Use whenever the user wants to summarize, transcribe, review, critique, extract information from, or ask questions about a YouTube video. Triggers include any youtube.com or youtu.be link, "analyze/summarize/review this video", "what's in this video", "transcribe this", "extract the key points", "watch this and tell me", or even just a YouTube URL with a short question like "thoughts?".
---

# YouTube Video Analyzer (manual Gemini, human-in-the-loop)

This skill analyzes a YouTube video **without calling any API**. There is no `GOOGLE_API_KEY`, no `pip install`, and no script to run. Instead, **the user runs Gemini themselves** in the Gemini app, and you act as the orchestrator: you write the prompts, the user pastes them into Gemini and pastes Gemini's answer back, and you review and iterate until the result is good enough to answer the user's actual goal.

Gemini can watch a public YouTube video — both the picture and the audio — when the user pastes the link into a chat at [gemini.google.com](https://gemini.google.com). Your job is to make each of those Gemini turns count.

## The loop

```
You (Claude)            User                         Gemini (gemini.google.com)
────────────            ────                         ──────────────────────────
craft prompt    ──▶  paste into Gemini      ──▶      watches video, answers
review answer   ◀──  paste answer back      ◀──      returns text
   │
   ├─ good enough?  ──▶  synthesize & deliver to the user
   └─ gaps / red flags?  ──▶  craft a targeted follow-up  ──▶ (repeat)
```

Keep looping for as many rounds as the goal needs. Most tasks take 1–3 rounds: one kick-off, then verification and/or filling gaps.

## Core principle — accuracy above all

The user trusts these outputs. **Fabricated content destroys that trust.** Every prompt you hand the user to paste into Gemini must carry the accuracy guardrails (see "Guardrails block" below), and every answer the user pastes back must be reviewed for the red flags (see Step 2). Admitting "I'm not sure, verify at 12:30" is always better than a confident guess.

These four concerns drive the whole loop:

- **Never invent.** If something can't be confirmed from the video, it must not appear in the final answer.
- **Timestamp accuracy.** Gemini drifts on timestamps, especially on long videos. Vague or round timestamps are a red flag and a reason to run a verification round.
- **Speaker identification.** In podcasts, group chats, or RPG sessions with several voices, Gemini must cross-reference voice with the picture (mouth movement, camera focus, on-screen names). Uncertain attribution should be flagged, not guessed.
- **Long videos.** Over ~1 hour, Gemini loses detail. Get the structure first, then deep-dive sections in separate rounds (see "Long videos").

---

## Step 0 — Gather inputs

1. **Get the YouTube URL.** It must be a **public** video (private/unlisted will fail in Gemini).
2. **Get the goal** — what does the user actually want? If it's vague (e.g. they just dropped a link and said "thoughts?"), use **AskUserQuestion** to offer the common analysis types instead of making them type it out:
   - **Summary** — concise overview, optionally with timestamped sections.
   - **Full transcript** — as close to word-for-word as possible, with speaker labels.
   - **Key points / takeaways** — bullet list of the important moments.
   - **Critique / review** — deeper analysis, opinions, strengths/weaknesses.
   - **Specific question(s)** — the user has something particular to ask about the video.
3. **Suggest which model to pick in Gemini.** If the user's Gemini app lets them choose a model (a dropdown, "Fast" vs "Thinking", or "2.5 Flash" vs "2.5 Pro" depending on their plan), suggest:
   - the **faster/Flash** option for quick summaries, transcripts, and simple questions;
   - the **more capable/Pro/Thinking** option for critique, nuanced analysis, or when a previous round came back shallow.
   The Gemini UI changes over time — describe the choice generically and let the user pick whatever matches in their app.
4. **Match the language.** Write the prompts the user will paste in the **same language as the video / the user's request**. When the video is in Brazilian Portuguese, write the pasted prompts in correct Brazilian Portuguese (proper accents: `você`, `vídeo`, `conteúdo`, `seção`, `duração`, `indicação`…) — a PT-BR template is provided below. For other languages, mirror the user's language the same way.

---

## Step 1 — Round 1: the kick-off prompt

Build the first prompt by combining: **(a)** the video link, **(b)** the user's goal, **(c)** the accuracy guardrails, and **(d)** a request for the video's length + section outline + a confidence note. Part (d) is what lets you plan smart follow-ups.

Then present it to the user as a **single copy-paste block** and tell them exactly what to do:

> Paste this into a new chat at **gemini.google.com**, send it, then paste Gemini's **full reply** back here.

Use the **Kick-off template** below (EN or PT-BR).

---

## Step 2 — Review what Gemini returned

When the user pastes Gemini's answer back, **read it critically before doing anything else.** Check for:

- **Did Gemini actually watch the video?** Sometimes it answers from the title/description or refuses. Signs it really watched: specific timestamps, descriptions of on-screen visuals, quotes. If it clearly didn't, see Troubleshooting.
- **Vague or round timestamps** ("around the 10-minute mark" instead of "10:23") — red flag.
- **Over-confident speaker attribution** — if the video has 3+ people and every line is assigned with certainty, be suspicious.
- **Gaps / shallow coverage** — sections skipped, or the requested depth not met.
- **Suspiciously specific claims** — exact stats, names, dates, or quotes that weren't obviously shown on screen.

Then decide: **is this complete and trustworthy enough to satisfy the user's goal?**
- **Yes** → go to Step 4.
- **No** → go to Step 3 and craft a targeted follow-up.

Briefly tell the user what you found and why you're (or aren't) running another round — don't silently loop.

---

## Step 3 — Iterate (as many rounds as needed)

Craft a **targeted** follow-up prompt for the user to paste **into the same Gemini chat** (so Gemini still has the video in context). Pick the follow-up type that matches the problem:

- **Verification pass** — re-confirm specific claims/timestamps that looked shaky.
- **Segment deep-dive** — focus on one timestamp range and go deep (great for long videos).
- **Coverage fill** — cover a section Gemini skipped or rushed.
- **Speaker re-check** — re-attribute lines in a stretch where the IDs looked uncertain.

Templates for each are below. After each round, return to Step 2. Keep going until the result is solid.

> **Same chat, not a new one.** Always tell the user to paste follow-ups into the *same* Gemini conversation. If Gemini seems to have lost the video (generic answers, "I can't see a video"), have them re-paste the link with the follow-up.

---

## Step 4 — Synthesize & deliver

Combine everything from all rounds into the final answer for the user's goal, and present it **in the chat**. In it:

- Lead with what the user asked for (the summary / transcript / critique / answer).
- Keep useful timestamps.
- Clearly mark anything still unverified as `[verify]` rather than dropping or laundering it into confident prose.
- If rounds disagreed, prefer the **verified** version and note the correction.

If the result is long or the user might want to keep it, **offer** to save it as a markdown file — but don't do it automatically.

---

## Guardrails block (embed in every prompt)

Paste-blocks you give the user must include this. English first, then Brazilian Portuguese.

**English:**

```
ACCURACY RULES — follow strictly:
- Do NOT invent or guess. Report only what you can actually see or hear in the video.
- If you are unsure about any detail, say so and give the approximate timestamp [~MM:SS, verify] so it can be checked.
- For each speaker, cross-check the voice against the picture (face, mouth movement, who the camera is on, on-screen names/labels). If you cannot confidently tell who is talking, say "speaker unclear" instead of guessing.
- Be precise with timestamps. Mark any timestamp you are unsure about as [~MM:SS, verify].
- Cross-check audio against video: if something is said, confirm it matches what is on screen when relevant.
```

**Brazilian Portuguese:**

```
REGRAS DE PRECISÃO — siga à risca:
- NÃO invente nem adivinhe. Relate apenas o que você realmente consegue ver ou ouvir no vídeo.
- Se tiver dúvida sobre qualquer detalhe, diga isso e informe o timestamp aproximado [~MM:SS, verificar] para que possa ser conferido.
- Para cada pessoa que fala, cruze a voz com a imagem (rosto, movimento da boca, em quem a câmera está, nomes/legendas na tela). Se não der para identificar com confiança quem está falando, escreva "locutor incerto" em vez de adivinhar.
- Seja preciso com os timestamps. Marque qualquer timestamp incerto como [~MM:SS, verificar].
- Cruze áudio e vídeo: se algo for dito, confirme se condiz com o que aparece na tela quando for relevante.
```

---

## Prompt templates

Fill in the `<...>` placeholders before giving these to the user. Drop in the guardrails block in the matching language.

### Kick-off (English)

```
You are analyzing a YouTube video. Watch the FULL video — both what is shown and what is said — then complete the task below.

VIDEO: <URL>

TASK: <user's goal, e.g. "Write a detailed summary with timestamped sections.">

<ACCURACY RULES block>

ALSO REPORT (so I can plan follow-ups):
- The total length of the video.
- A short outline of its main sections, each with its start timestamp.
- One line on your confidence/coverage: anything you could not see/hear well, or parts you only skimmed.
```

### Kick-off (Brazilian Portuguese)

```
Você vai analisar um vídeo do YouTube. Assista ao vídeo INTEIRO — tanto o que é mostrado quanto o que é falado — e depois faça a tarefa abaixo.

VÍDEO: <URL>

TAREFA: <objetivo do usuário, ex.: "Escreva um resumo detalhado com seções e timestamps.">

<bloco REGRAS DE PRECISÃO>

RELATE TAMBÉM (para eu planejar os próximos passos):
- A duração total do vídeo.
- Um roteiro curto das seções principais, cada uma com o timestamp de início.
- Uma linha sobre sua confiança/cobertura: algo que não deu para ver/ouvir bem ou partes que você passou rápido.
```

### Verification pass

```
Re-watch ONLY these moments in the video and confirm or correct what you said before:
- At ~<MM:SS>: you said "<claim>". Is that accurate? If not, correct it and give the right timestamp.
- At ~<MM:SS>: <another claim to check>.
Report exactly what is shown/said at each point. If you still cannot verify it, say so — do not guess.
```

### Segment deep-dive

```
Focus ONLY on the segment from <MM:SS> to <MM:SS>. Ignore the rest of the video.
Do this: <what you want — e.g. a word-for-word transcript with speaker labels>.
Same accuracy rules as before: no guessing, cross-check audio with the picture, mark any unsure timestamp as [~MM:SS, verify].
```

### Coverage fill

```
You skipped or only briefly covered <topic / the section around MM:SS>. Go back to that part of the video and cover it in detail, following the same accuracy rules.
```

### Speaker re-check

```
Re-check who is speaking between <MM:SS> and <MM:SS>. Cross-reference each voice with the picture (mouth movement, camera focus, on-screen names/labels). For each line, say who is speaking and how confident you are. If it's unclear, write "unclear" — don't guess.
```

---

## Long videos (over ~1 hour)

Don't try to get everything in one shot — Gemini loses detail on long videos. Instead:

1. **Round 1 = structure only.** Ask for the section outline with timestamps and a rough length (the kick-off's "ALSO REPORT" gives you this).
2. **Then deep-dive each section** with the segment template, one round per chunk (e.g. 0–20 min, 20–40 min…). The user pastes each follow-up into the same chat.
3. **Stitch the chunks together** in Step 4.

This is the manual equivalent of clipping the video — instead of API offsets, you simply tell Gemini which timestamp range to focus on. Warn the user that very long videos may still lose some fidelity, and that splitting into ranges is the fix.

---

## Gemini app tips & troubleshooting

- **Public videos only.** If Gemini says it can't access the video, have the user confirm the link is public and try again.
- **Use one chat per video.** Follow-ups belong in the same conversation so the video stays in context.
- **If Gemini answers generically** (sounds like it only read the title, or says it can't watch videos): have the user re-paste the link, make sure any "YouTube"/video tool or extension in their Gemini app is enabled, or switch to a model in the app that supports video. The Gemini UI changes over time — check the current Gemini help docs if a capability seems missing rather than assuming.
- **If Gemini's answer is truncated**, have the user ask it to "continue" in the same chat and paste the rest.
- **Token/length limits** live on Gemini's side now (not ours) — segmenting long videos is the workaround.

---

## Using interactive menus

This skill uses **AskUserQuestion** to keep the user clicking instead of typing whenever there's a clear set of choices:

- Picking the **analysis type** in Step 0 when the goal is vague.
- Choosing **what to do next** after a round (e.g. "Run a verification pass", "Deep-dive a section", "That's good — synthesize now").
- For long videos, choosing **which segment** to deep-dive next.

Keep the actual Gemini prompts as plain copy-paste blocks — menus are for decisions, not for the text the user pastes into Gemini.

---

## Workflow summary

1. **Step 0** — Get the public YouTube URL and the goal (use AskUserQuestion if vague); suggest a model to pick in the Gemini app; match the prompt language to the video.
2. **Step 1** — Hand the user the kick-off prompt (guardrails + goal + "report length/outline/confidence"). They paste it into gemini.google.com and paste the reply back.
3. **Step 2** — Review the reply for red flags (did it watch? vague timestamps? shaky speaker IDs? gaps? fabricated-looking detail?). Decide if it's good enough.
4. **Step 3** — If not, hand over a targeted follow-up (verification / deep-dive / coverage / speaker) for the **same** Gemini chat. Loop back to Step 2. Repeat as needed.
5. **Step 4** — Synthesize all rounds into the final answer in chat, mark anything unverified as `[verify]`, and offer to save it as a file.
