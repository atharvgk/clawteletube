#!/usr/bin/env python3
"""
fetch_transcript.py — OpenClaw yt-summarizer skill helper

Fetches, cleans, truncates, and caches YouTube transcript as JSON.
Usage:  python3 fetch_transcript.py <VIDEO_ID>
Output: single JSON object to stdout, exit code always 0.
"""

import sys
import json
import os
import re
from datetime import datetime

MAX_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", 150000))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(SCRIPT_DIR, '..', 'cache')

MAX_SEGMENTS_IN_OUTPUT = 50
LANG_MAP = {
    "en": "English",    "hi": "Hindi",      "ta": "Tamil",
    "te": "Telugu",     "kn": "Kannada",    "mr": "Marathi",
    "bn": "Bengali",    "ml": "Malayalam",  "zh": "Chinese",
    "ja": "Japanese",   "ko": "Korean",     "fr": "French",
    "de": "German",     "es": "Spanish",    "pt": "Portuguese",
    "ar": "Arabic",     "ru": "Russian",    "id": "Indonesian",
    "it": "Italian",    "tr": "Turkish",    "vi": "Vietnamese",
    "th": "Thai",       "pl": "Polish",     "nl": "Dutch"
}


def clean_transcript(text: str) -> str:
    """Remove caption noise tags and normalize whitespace."""
    text = re.sub(
        r'\[(Music|Applause|Laughter|Cheering|Inaudible|Silence|'
        r'MUSIC|APPLAUSE|Background Music|Background Noise|Laughter)\]',
        '',
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()


def seconds_to_mmss(seconds) -> str:
    """Convert float seconds to MM:SS string."""
    total = int(float(seconds))
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"


def get_seg(seg, key: str, default=None):
    """Handle both dict-style and object-style segment access."""
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def main():
    # Input validation
    if len(sys.argv) < 2:
        print(json.dumps({
            "success": False,
            "error": "UNKNOWN",
            "message": "No video ID provided. Usage: python3 fetch_transcript.py <VIDEO_ID>"
        }))
        sys.exit(0)

    video_id = sys.argv[1].strip()

    if not re.match(r'^[a-zA-Z0-9_\-]{11}$', video_id):
        print(json.dumps({
            "success": False,
            "error": "INVALID_VIDEO",
            "message": (
                f"Invalid video ID format: '{video_id}'. "
                "Expected 11-character YouTube video ID."
            )
        }))
        sys.exit(0)

    # Ensure cache directory exists
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{video_id}.json")

    # Warm request for instant read, zero network cost
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            print(json.dumps(cached, ensure_ascii=False))
            sys.exit(0)
        except (json.JSONDecodeError, IOError):
            pass  # Corrupted cache — fall through to cold start re-fetch

    # Import dependencies
    try:
        from youtube_transcript_api import (
            YouTubeTranscriptApi,
            TranscriptsDisabled,
            NoTranscriptFound,
            VideoUnavailable,
        )
    except ImportError:
        print(json.dumps({
            "success": False,
            "error": "UNKNOWN",
            "message": (
                "youtube-transcript-api is not installed. "
                "Run: pip3 install youtube-transcript-api"
            )
        }))
        sys.exit(0)

    # Cold start
    segments_raw = []
    lang_code = "unknown"

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript_obj = transcript_list.find_transcript(['en'])
        except NoTranscriptFound:
            transcript_obj = next(iter(transcript_list))

        segments_raw = transcript_obj.fetch()
        lang_code = transcript_obj.language_code

    except TranscriptsDisabled:
        print(json.dumps({
            "success": False,
            "error": "NO_TRANSCRIPT",
            "message": "Transcripts/captions are disabled for this video."
        }))
        sys.exit(0)

    except NoTranscriptFound:
        print(json.dumps({
            "success": False,
            "error": "NO_TRANSCRIPT",
            "message": "No transcript found in any language for this video."
        }))
        sys.exit(0)

    except VideoUnavailable:
        print(json.dumps({
            "success": False,
            "error": "INVALID_VIDEO",
            "message": "Video is unavailable or does not exist."
        }))
        sys.exit(0)

    except Exception as e:
        err_str = str(e).lower()
        if 'private' in err_str or 'age' in err_str or 'restricted' in err_str:
            error_code = "PRIVATE_VIDEO"
        elif 'quota' in err_str or 'rate' in err_str or 'limit' in err_str:
            error_code = "RATE_LIMIT"
        else:
            error_code = "UNKNOWN"
        print(json.dumps({
            "success": False,
            "error": error_code,
            "message": str(e)
        }))
        sys.exit(0)

    # Compute total duration from ALL segments
    duration_seconds = round(
        sum(float(get_seg(seg, 'duration', 0)) for seg in segments_raw),
        2
    )

    # Build segment data and transcript text
    full_text_parts = []
    all_segment_data = []

    for seg in segments_raw:
        text = str(get_seg(seg, 'text', ''))
        start = get_seg(seg, 'start', 0)
        duration = get_seg(seg, 'duration', 0)

        full_text_parts.append(text)
        all_segment_data.append({
            "text": text,
            "start": round(float(start), 2),
            "start_mmss": seconds_to_mmss(start),
            "duration": round(float(duration), 2)
        })

    full_transcript = clean_transcript(' '.join(full_text_parts))

    if not full_transcript.strip():
        print(json.dumps({
            "success": False,
            "error": "NO_TRANSCRIPT",
            "message": "Transcript was fetched but contained no usable text."
        }))
        sys.exit(0)

    # 
    truncated = False
    original_length = len(full_transcript)

    if original_length > MAX_CHARS:
        full_transcript = full_transcript[:MAX_CHARS]
        truncated = True

    truncated_to = MAX_CHARS if truncated else original_length
    language_human = LANG_MAP.get(lang_code, lang_code)

    # Fetch video title via pytube
    title = "YouTube Video"
    try:
        from pytube import YouTube
        yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
        fetched = yt.title
        if fetched and fetched.strip():
            title = fetched.strip()
    except Exception:
        pass 

    output_segments = all_segment_data[:MAX_SEGMENTS_IN_OUTPUT]
    stats = {
        "char_length": original_length,
        "truncated": truncated,
        "truncated_to": truncated_to,
        "segments_total": len(all_segment_data),
        "segments_returned": len(output_segments),
        "language": lang_code,
        "duration_seconds": duration_seconds
    }

    #final result
    result = {
        "success": True,
        "video_id": video_id,
        "title": title,
        "transcript": full_transcript,
        "segments": output_segments,
        "language": lang_code,
        "language_human_readable": language_human,   
        "truncated": truncated,
        "original_length": original_length,
        "truncated_to": truncated_to,
        "duration_seconds": duration_seconds,         
        "stats": stats,                               
        "cached_at": datetime.utcnow().isoformat() + "Z"
    }

    #Write cache file
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except IOError:
        pass  

    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
