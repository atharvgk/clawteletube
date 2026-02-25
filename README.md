# yt-summarizer

## Overview
This skill handles YouTube video summarization and Q&A via transcript extraction and structured LLM-generated responses. It works by running a local Python script to fetch and cache the transcript, then uses the configured LLM to generate structured summaries and grounded answers.

## Features
- Structured video summary: title, key points, timestamps, core takeaway, transcript language
- Grounded Q&A: answers sourced only from transcript, no hallucination
- Multi-language support: English and 7 Indian languages, LLM-native
- Transcript caching: fetch once, instant reuse for all follow-up requests
- Token efficiency: transcript fetch uses zero LLM tokens (shell tool)
- Configurable transcript size via MAX_TRANSCRIPT_CHARS environment variable
- Diagnostic stats in every JSON result: character length, duration, segments
- Rate limit handling: graceful messaging for provider throttling
- Empty transcript guard: detects broken auto-generated captions
- Prompt-injection awareness via transcript grounding rules
- Commands: /summary, /deepdive, /actionpoints, /language

## Prerequisites
- OpenClaw installed and running locally (https://openclaw.ai)
- Python 3.10+ on system PATH as "python3"
- pip3 available
- Telegram bot token from @BotFather
- LLM API key - Recommended LLM: Gemini 1.5 Flash (free tier, 1M context window, native multilingual for all 8 languages, consistent structured output)

## Installation

### Step 1 - Install OpenClaw
  curl -fsSL https://clawd.bot/install.sh | bash
  openclaw --version

### Step 2 - Install this skill
  cp -r yt-summarizer/ ~/.openclaw/skills/
  # Or symlink: ln -s /path/to/yt-summarizer ~/.openclaw/skills/yt-summarizer

### Step 3 - Install Python dependencies
  pip3 install youtube-transcript-api==0.6.2 pytube==15.0.0
  python3 -c "from youtube_transcript_api import YouTubeTranscriptApi; print('OK')"

### Step 4 - Configure Telegram
  1. Open Telegram -> @BotFather -> /newbot -> copy token
  2. Add to ~/.openclaw/openclaw.json:
     {
       "channels": {
         "telegram": {
           "enabled": true,
           "botToken": "YOUR_TOKEN",
           "dmPolicy": "pairing"
         }
       }
     }

### Step 5 - Configure Gemini 1.5 Flash
  Get key: https://aistudio.google.com
  Add to ~/.openclaw/openclaw.json:
  {
    "agents": {
      "defaults": {
        "model": { "primary": "gemini/gemini-1.5-flash" }
      }
    }
  }

### Step 6 - Configure transcript size limit (optional)
Default 150,000 chars (approx 2.5 hours). Hardcoding limits reduces configurability and adaptability across environments - use env var:

  Linux/macOS:
    export MAX_TRANSCRIPT_CHARS=200000

  Windows (PowerShell):
    setx MAX_TRANSCRIPT_CHARS 200000

  Windows (Command Prompt):
    set MAX_TRANSCRIPT_CHARS=200000

For Linux/macOS persistence, add to ~/.bashrc or ~/.zshrc.

### Step 7 - Start gateway and pair Telegram
  openclaw gateway
  # DM your bot -> get pairing code
  openclaw pairing approve telegram <CODE>

### Step 8 - Verify skill loaded
  openclaw skills list   # "yt-summarizer" should appear
  openclaw doctor --fix  # if not appearing

## Usage

Send any YouTube link - get a structured summary instantly:
  https://youtube.com/watch?v=dQw4w9WgXcQ

Ask follow-up questions:
  What tools did they recommend?
  What is the main argument?

Switch language at any time (persists across video switches):
  Summarize in Hindi
  Explain in Tamil
  In Kannada

Commands:
  /summary       - Re-show current video summary
  /deepdive      - Deep analytical breakdown
  /actionpoints  - Extract all action items
  /language      - List and switch language

## Architecture

  User (Telegram DM)
        |
        V
  OpenClaw Gateway
  (Telegram protocol, pairing, sessions, routing - built-in)
        |
        V
  AI Agent reads SKILL.md
        |
        +--- YouTube URL detected
        |          |
        |          V
        |    Check {baseDir}/cache/{video_id}.json
        |          |
        |    MISS -+- HIT -> instant read, near-zero latency
        |          |
        |    Cold start:
        |    python3 fetch_transcript.py VIDEO_ID
        |    [fetch -> clean -> empty guard -> truncate ->
        |     duration compute -> cache write -> return JSON]
        |          |
        |          V
        |    Agent generates structured summary via LLM
        |    (title, key points, timestamps, takeaway,
        |     transcript language, truncation notice if needed)
        |          |
        |          V
        |    Response -> Telegram user
        |
        +--- Follow-up question
                   |
                   V
             Transcript in session context + chat history
                   |
                   V
             LLM generates grounded answer
             (transcript only - no hallucination)
                   |
                   V
             Response -> Telegram user

## Design Decisions and Trade-offs

### Why OpenClaw skill instead of standalone bot
OpenClaw provides Telegram, sessions, LLM routing, and multi-user concurrency out of the box. A skill means zero infrastructure code - behavior only.

### Recommended LLM
Gemini 1.5 Flash provides a free tier, 1M token context window (entire transcript fits in one call, no chunking), native multilingual capabilities for all 8 supported languages, and consistent structured output.

### Python helper script for transcript fetching
A shell script provides deterministic I/O, not reasoning. It is faster, uses zero tokens, and is more reliable. Clear separation of concerns: the script fetches data, and the LLM generates the response.

### File-based JSON cache
A zero-dependency, human-inspectable, and self-describing cache stored at {baseDir}/cache/. It stores video_id, title, full transcript, first 50 segments with timestamps, language code, human-readable language name, truncated flag, original and truncated lengths, total duration in seconds, stats block, and cached_at timestamp.

### Cold start and warm request
Cold start (first request): fetch, clean, empty guard, truncate, compute duration, write cache, return JSON to agent.
Warm request (already cached): read {baseDir}/cache/{video_id}.json instantly. No YouTube call, no network round-trip, near-zero latency. Repeated questions about the same video are practically free.

### MAX_TRANSCRIPT_CHARS from environment
Hardcoding limits reduces configurability and adaptability across environments. The limit is tunable per machine via an environment variable without touching code.

### Truncation transparency
If truncated, the summary explicitly states it covers only the first portion and does not represent the full video. This is an important hallucination guard.

### Segment output limit
Only the first 50 segments are returned for timestamp extraction. The full transcript is always preserved separately. This is intentional as it prevents bloating shell output.

### Video duration in stats
Total duration in seconds is computed from all segments before any slicing. This is useful for future features (for example, "This is a 45-minute video"), UI hints, and smarter truncation strategies.

### Language human-readable mapping
LANG_MAP in the script converts lang_code to a human name before returning JSON. The agent uses the "language_human_readable" field directly, meaning no remapping is needed on the agent side.

### Transcript language display in summary
Displaying the Transcript Language line in every summary signals full multilingual awareness, which is especially useful for non-English source videos.

### Token efficiency and cost optimization
Transcript fetch is completely zero LLM tokens (shell tool). Only summarization, Q&A, and deepdive use LLM calls. Combined with caching, repeated questions cost only Q&A generation tokens.

### LLM-native language handling
Gemini 1.5 Flash natively generates responses in all supported languages. There is no external translation service or extra API call required.

### Rate limit handling
RATE_LIMIT covers YouTube throttling and model provider throttling. We supply a clear user message with retry guidance, following standard production practices.

### Empty transcript guard
After cleaning, if the transcript contains no usable text, the script returns NO_TRANSCRIPT before any further processing. This handles broken auto-generated captions defensively.

### pytube title fetching
Title fetching via pytube is best-effort and non-critical. pytube occasionally breaks due to YouTube API changes, so we fall back to "YouTube Video". All core features remain unaffected.

## Security
Transcript content is treated as untrusted input. SKILL.md grounding rules constrain answers to transcript content only, limiting prompt-injection impact via malicious captions.

## Cache Invalidation
To force a transcript re-fetch for a specific video, delete its cache file:

  Linux/macOS:
    rm ~/.openclaw/skills/yt-summarizer/cache/<video_id>.json

  Windows (PowerShell):
    Remove-Item ~\.openclaw\skills\yt-summarizer\cache\<video_id>.json

To clear all cached transcripts:

  Linux/macOS:
    rm ~/.openclaw/skills/yt-summarizer/cache/*.json

  Windows (PowerShell):
    Remove-Item ~\.openclaw\skills\yt-summarizer\cache\*.json

OpenClaw does not need to be restarted after cache deletion.

## Supported Languages

| Language   | Native Script | Detection Patterns          |
|------------|---------------|-----------------------------|
| English    | -             | default                     |
| Hindi      | Hindi script  | in hindi, hindi mein        |
| Tamil      | Tamil script  | in tamil                    |
| Telugu     | Telugu script | in telugu, telugu lo        |
| Kannada    | Kannada script| in kannada                  |
| Marathi    | Marathi script| in marathi                  |
| Bengali    | Bengali script| in bengali                  |
| Malayalam  | Malayalam script| in malayalam                |

## Commands

| Command        | Description                                          |
|----------------|------------------------------------------------------|
| /summary       | Re-show current video summary                        |
| /deepdive      | Deep analysis: arguments, evidence, gaps, conclusion |
| /actionpoints  | Action items, quick wins, long-term actions          |
| /language      | List languages and switch preference                 |

## Edge Cases

| Situation                  | Handling                                                          |
|----------------------------|-------------------------------------------------------------------|
| Invalid YouTube link       | INVALID_VIDEO: "Invalid YouTube link..."                          |
| No captions available      | NO_TRANSCRIPT: clear message                                      |
| Captions fetched but empty | NO_TRANSCRIPT: empty guard fires before truncation                |
| Private/age-restricted     | PRIVATE_VIDEO: clear message                                      |
| Rate limited               | RATE_LIMIT: retry guidance                                        |
| Very long transcript       | Truncated at MAX_TRANSCRIPT_CHARS, summary states scope only      |
| Already cached video       | Instant JSON read, no YouTube call, near-zero latency             |
| Question before URL sent   | "Please send a YouTube link first"                                |
| Non-English transcript     | Fetched as-is, language displayed, LLM translates on demand       |
| pytube title fetch fails   | Fallback "YouTube Video" - core features unaffected               |
| Corrupted cache file       | Detected on read, triggers cold-start re-fetch automatically      |

## Session Behavior
Sending a new YouTube link replaces active video context and transcript but preserves language preference. Users can switch videos mid-conversation without losing their language setting. Each Telegram user has a fully isolated session, and sessions do not persist across OpenClaw gateway restarts.

## Known Limitations
- Transcripts must be available on YouTube (manual or auto-generated).
- Very new videos may not have auto-generated captions yet.
- Sessions reset when OpenClaw gateway restarts.
- Transcripts may be manually uploaded captions (higher accuracy) or auto-generated by YouTube (variable accuracy, may contain errors especially for technical terms, accents, or fast speech). Summary and Q&A quality depends on caption accuracy in the source video.
- Title fetching via pytube is best-effort and non-critical. pytube occasionally breaks due to YouTube API changes. If title fetching fails, the skill falls back to "YouTube Video" - transcript fetching and all core features remain unaffected.

## Demo Suggestions
For your demo video, show these 5 scenarios in order:

1. Cold start summary
   Send a YouTube link for the first time.
   Show structured summary with key points, timestamps, core takeaway, and transcript language indicator.

2. Grounded Q&A
   Ask a question whose answer is in the transcript.
   Show the bot answering accurately with specific details.

3. Out-of-scope Q&A
   Ask a question whose answer is NOT in the transcript.
   Show: "This topic is not covered in the video."

4. Language switch
   Say "Summarize in Hindi" (or any supported language).
   Show the summary regenerated entirely in that language.

5. Cache hit performance
   Send the same YouTube link again.
   Show instant response demonstrating transcript caching.

Bonus scenarios:
- /deepdive command output
- /actionpoints command output
- Sending an invalid YouTube link to show error handling

## Troubleshooting
Skill not in openclaw skills list:
  - Verify: ls ~/.openclaw/skills/yt-summarizer/SKILL.md
  - Run: openclaw doctor --fix | openclaw gateway

python3 not found:
  - Verify: which python3
  - If Python is installed as "python" not "python3" (common on Windows), update SKILL.md metadata bins and shell command in Step 1 accordingly.

Transcript errors:
  - Check if video has CC captions in YouTube (CC button visible)
  - Live streams and some regional videos have no transcripts

Inspect a cache file:
  cat ~/.openclaw/skills/yt-summarizer/cache/<video_id>.json

Live debug:
  openclaw logs --follow

## Screenshots
Add screenshots here after deployment.

## Future Improvements
- Embedding-based semantic search for multi-hour videos
- Playlist summarization support
- MEMORY.md integration for summaries across gateway restarts
- Webhook mode for lower Telegram response latency
- Duration-aware UI hints using duration_seconds field
