# Error Code Reference

Used by the agent to map script JSON errors to user-facing messages.

| Error Code    | Cause                               | User-Facing Message                                                                   |
|---------------|-------------------------------------|---------------------------------------------------------------------------------------|
| NO_TRANSCRIPT | Disabled, unavailable, or empty     | ❌ This video has no subtitles or captions available. Try another video.              |
| INVALID_VIDEO | Bad video ID or unavailable         | ❌ Invalid YouTube link or video not found. Please check the URL.                    |
| PRIVATE_VIDEO | Private or age-restricted           | ❌ This video is private or age-restricted. Cannot access transcript.                |
| RATE_LIMIT    | YouTube or model provider throttle  | ⏳ Too many requests right now. Please wait a few seconds and try again.             |
| UNKNOWN       | Unexpected error                    | ⚠️ Could not fetch transcript. Please try again or try a different video.           |

## Notes
- Script always exits 0. Errors via JSON "error" field only — never exit codes.
- NO_TRANSCRIPT fires for: disabled captions, no transcript found, AND
  empty transcript after fetch (RULE 15 empty guard).
- INVALID_VIDEO message uses "link" (user mental model) + "check the URL"
  (technical guidance) — RULE 13.
- RATE_LIMIT covers YouTube-side AND model provider throttling.
- language_human_readable field uses LANG_MAP (RULE 21) — agent uses
  this directly, no remapping needed.
- duration_seconds computed from ALL segments before slicing (RULE 20).

## Cache Schema (RULE 8 — self-describing)
Every cache file at {baseDir}/cache/{video_id}.json stores:
  video_id               — YouTube video ID (11 chars)
  title                  — Video title or "YouTube Video" fallback
  transcript             — Full cleaned transcript (≤ MAX_TRANSCRIPT_CHARS)
  segments               — First 50 segments: text, start, start_mmss, duration
  language               — Source language code (e.g., "en", "hi")
  language_human_readable — Human name (e.g., "English", "Hindi")
  truncated              — Boolean: true if transcript was cut
  original_length        — Character count before truncation
  truncated_to           — Character count after (= original if not cut)
  duration_seconds       — Total video duration from all segments
  stats                  — {char_length, truncated, truncated_to,
                            segments_total, segments_returned,
                            language, duration_seconds}
  cached_at              — ISO8601 UTC timestamp of cache write
