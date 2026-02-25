---
name: yt-summarizer
version: 1.0.0
description: Summarize YouTube videos and answer questions about them. Use when user sends a YouTube link, asks to summarize a video, wants key points or timestamps from a video, or asks questions about a previously shared YouTube video. Also activates for language requests like "summarize in Hindi", "explain in Kannada", or any Indian language variant.
homepage: https://github.com/atharvgk/yt-summarizer
metadata: {"openclaw": {"emoji": "🎥", "requires": {"bins": ["python"]}, "install": [{"id": "pip-deps", "kind": "shell", "command": "pip install youtube-transcript-api pytube --quiet", "label": "Install Python transcript dependencies"}]}}
---

## Overview
This skill handles YouTube video summarization and Q&A via transcript
extraction and structured LLM-generated responses. It works by running
a local Python script to fetch and cache the transcript, then uses the
configured LLM to generate structured summaries and grounded answers.

## When To Activate
Activate this skill when the user:
- Sends a message containing a YouTube URL in any of these formats:
    youtube.com/watch?v=...
    youtu.be/...
    youtube.com/shorts/...
    m.youtube.com/watch?v=...
- Says "summarize this video", "what is this video about",
  "give me key points from [URL]"
- Asks a follow-up question after a YouTube video was previously loaded
- Requests a language: "in Hindi", "summarize in Tamil",
  "explain in Kannada", "X mein", "X lo"
- Types /summary, /deepdive, /actionpoints, /language

## Step 1 — Detect and Validate YouTube URL
When user sends a message containing a YouTube URL:
1. Extract the 11-character video ID from the URL
2. Run the transcript fetch script:
     python {baseDir}/scripts/fetch_transcript.py VIDEO_ID
3. The script prints a single JSON object to stdout. Parse it.
4. If success=false in JSON, map the "error" field to the user message
   defined in Error Handling section below. Stop here.
5. If success=true, store these fields in session context:
     - title
     - transcript (full text)
     - segments (first 50 entries with start_mmss timestamps)
     - truncated (boolean)
     - language_human_readable (e.g., "English", "Hindi")
     - duration_seconds (total video duration from all segments)
     - stats (for reference and /deepdive context)

## Step 2 — Generate Summary
Immediately after successful transcript fetch, generate a structured
summary using EXACTLY this output format — no preamble, no intro text:

🎥 *Video Title*: {title}

📌 *Key Points*:
1. [Specific point extracted directly from video content]
2. [Specific point extracted directly from video content]
3. [Specific point extracted directly from video content]
4. [Specific point extracted directly from video content]
5. [Specific point extracted directly from video content]

⏱ *Important Timestamps*:
- [MM:SS] — [What is discussed or shown at this moment]
- [MM:SS] — [What is discussed or shown at this moment]
- [MM:SS] — [What is discussed or shown at this moment]

🧠 *Core Takeaway*:
[2-3 sentences capturing the single most important insight]

🌐 *Transcript Language*: {language_human_readable}

[If truncated=true, append:]
⚠️ _Very long video — summary covers the first portion of the transcript
only and does not represent the full video content._

💬 *Ask me anything about this video!*

Rules for generating summary:
- Extract timestamps from "segments" array using "start_mmss" field
  (pre-formatted MM:SS by script). Pick topic transitions or high-info moments.
- Be specific — extract actual content, not generic filler
- Do NOT start with "Sure!", "Here is your summary", or any preamble
- Output ONLY the format above — nothing before, nothing after
- RULE 14: {language_human_readable} comes directly from the script JSON
  field "language_human_readable" — do not remap or guess
- RULE 7: If truncated=true, summary reflects ONLY the visible truncated
  portion. Do NOT imply or suggest coverage of the full video.
- RULE 4: If transcript language differs from user's requested response
  language, the LLM handles translation automatically — no separate
  translation API needed. Always respond in user's preferred language.

## Step 3 — Answer Follow-up Questions
When user sends a text message (not a URL, not a command) and a video
transcript is loaded in session context:
- Answer ONLY using information present in the transcript
- If the answer is not found in the transcript, respond with exactly:
    "❌ This topic is not covered in the video."
- Never add external information, statistics, or facts not in transcript
- Never hallucinate names, dates, figures, or events
- Be concise, direct, grounded in what the transcript says
- Do NOT start with "Great question!" or similar filler
- Use recent conversation turns for continuity across multiple questions

## Step 4 — Multi-language Support
Detect language preference from these patterns (all case-insensitive):

Explicit: "in hindi", "in tamil", "in telugu", "in kannada", "in marathi",
          "in bengali", "in malayalam", "summarize in X", "explain in X",
          "translate to X", "respond in X", "switch to X", "X mein", "X lo"

Native script:
  हिंदी / Devanagari → Hindi
  தமிழ் / Tamil script → Tamil
  తెలుగు / Telugu script → Telugu
  ಕನ್ನಡ / Kannada script → Kannada
  मराठी / Marathi Devanagari → Marathi
  বাংলা / Bengali script → Bengali
  മലയാളം / Malayalam script → Malayalam

Supported: English (default), Hindi, Tamil, Telugu, Kannada, Marathi,
           Bengali, Malayalam

When language preference detected:
1. Confirm: "✅ Switched to {language}! All responses will be in {language}."
2. Remember preference for ALL subsequent responses this session
3. Respond entirely in user's preferred language for all outputs
4. Preserve emojis and Markdown symbols — translate text only
5. RULE 19: Keep language preference when user sends a new YouTube URL.
   Video context resets. Language preference does NOT.

## Step 5 — Slash Commands

/summary
  No video: "🎥 Please send a YouTube link first!"
  Video loaded: regenerate summary in current language. Do NOT re-run
  the fetch script — transcript is already in session context.

/deepdive
  No video: "🎥 Please send a YouTube link first!"
  Video loaded, use EXACTLY this format:

  🔍 *Deep Dive: {title}*

  💡 *Core Arguments*:
  [Main claims or arguments made by the speaker]

  📊 *Evidence & Examples*:
  [Data, stories, case studies, or examples referenced]

  🎯 *Target Audience*:
  [Who this content is clearly designed for]

  ⚖️ *Strengths & Gaps*:
  [What the video does well and what it omits or could improve]

  🏁 *Conclusion*:
  [Final conclusions drawn by the speaker]

/actionpoints
  No video: "🎥 Please send a YouTube link first!"
  Video loaded, use EXACTLY this format:

  ✅ *Action Points — {title}*

  *All Actions*:
  1. [Specific, implementable action from the video]
  2. [Continue for all relevant items]

  💼 *Quick Wins* (can do today):
  - [Action requiring minimal setup]

  📅 *Long-term Actions*:
  - [Action requiring planning or sustained effort]

/language
  "🌐 *Supported languages*:
  English, Hindi, Tamil, Telugu, Kannada, Marathi, Bengali, Malayalam

  Reply with your preferred language name or say
  'summarize in Hindi' or 'explain in Tamil'."

## Error Handling
Map "error" field from script JSON to these exact user messages:

NO_TRANSCRIPT:
  "❌ This video has no subtitles or captions available. Try another video."

INVALID_VIDEO:
  "❌ Invalid YouTube link or video not found. Please check the URL."
  [RULE 13: "link" matches user mental model, "check the URL" guides fix]

PRIVATE_VIDEO:
  "❌ This video is private or age-restricted. Cannot access transcript."

RATE_LIMIT:
  "⏳ Too many requests right now. Please wait a few seconds and try again."
  [RULE 6: covers model provider throttling — production awareness]

UNKNOWN:
  "⚠️ Could not fetch transcript. Please try again or try a different video."

No video loaded, user asks question:
  "🎥 Please send a YouTube link first to get started!"

## Context and Memory Rules
- Keep current video transcript in active session context
- Track language preference throughout entire session
- RULE 19: New YouTube URL → reset video context → KEEP language preference
- Q&A: reference full transcript stored in session context
- Do not mix transcript content from different videos
- Sessions do not persist across OpenClaw gateway restarts

## Output Quality Rules
- Never begin with "Sure!", "Of course!", "Great!", or any preamble
- Output only the requested format — nothing before, nothing after
- Be factual — no embellishment beyond transcript content
- Format with Telegram-compatible Markdown: *bold*, _italic_, plain text
