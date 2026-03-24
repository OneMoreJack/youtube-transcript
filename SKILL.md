---
name: youtube-transcript
description: Use when you need the original YouTube transcript for a video URL or ID, with faithful timestamped output and no summarization, translation, or ASR fallback.
---

# YouTube Transcript

## Overview

Fetch the transcript that YouTube already provides for a video and return it in larger timestamped blocks. Keep the wording transcript-faithful: do not rewrite, summarize, translate, infer speakers, or fall back to speech recognition.

## When To Use

Use this skill when the user wants:

- the transcript for a YouTube video URL or bare video ID
- timestamps in merged paragraph blocks instead of one subtitle line per snippet
- transcript text that matches YouTube's transcript content
- the video's original transcript language by default

Do not use this skill when the user wants:

- audio transcription for a video that has no YouTube transcript
- translated text when the translated transcript does not already exist on YouTube
- inferred speaker diarization

## Workflow

1. Accept a YouTube URL or video ID.
2. Run `python3 scripts/fetch_youtube_transcript.py "<url-or-id>" --format inspect`.
3. Check whether the transcript needs a language choice before output.
4. If the user already expressed a preference by meaning, honor it even if they did not use the exact mode names.
5. If the user did not express a preference and the transcript is mixed bilingual, ask before returning the transcript.
6. Run the final fetch command with the chosen language mode and return the script output directly unless the user asked for a file or alternate format.

Useful flags:

- `--lang <code>`: Request an existing transcript language without auto-translation.
- `--format raw`: Return the original snippet stream for verification.
- `--format inspect`: Return transcript metadata so you can decide whether to ask the user a follow-up question.
- `--language-mode original|english-only|bilingual-lines`: Control how mixed bilingual transcript lines should be handled.
- `--target-window 30`: Adjust the approximate merge window in seconds.

## Preference Matching

Treat user intent semantically, not only by exact keywords.

- Map requests like `只保留英文`, `去掉中文`, `English only` to `--language-mode english-only`.
- Map requests like `保留双语`, `中英都要`, `bilingual` to `--language-mode bilingual-lines`.

If the transcript is mixed bilingual and the user did not clearly express `english-only` or `bilingual-lines`, ask which one they want.

## Output Rules

- Default output format is Markdown:

```md
`0:00`
Transcript block...

`0:33`
Next block...
```

- Keep transcript wording faithful to the YouTube transcript.
- If any transcript snippet starts with `>>`, treat the whole transcript as speaker-mode output.
- In speaker mode, only `>>` starts a new timestamped block.
- Remove the leading `>>` from rendered text so Markdown does not turn it into a quote block.
- Within a long block, only add extra line breaks at sentence boundaries.
- If a transcript has neither sentence punctuation nor `>>` speaker markers, split it into new blocks about every 30 seconds.
- If `--language-mode bilingual-lines` is selected, render Chinese and English on adjacent lines with no blank line between them.
- Preserve other speaker labeling only when it already exists in the transcript text.
- If no YouTube transcript exists, fail clearly instead of generating one.
- If a requested language is unavailable, fail clearly instead of translating.

## Notes

- The bundled script uses `youtube_transcript_api`.
- Use `--format inspect` before the final output command whenever you have not yet determined whether a bilingual choice is required.
- When no `>>` markers exist and punctuation is present, blocks use sentence-ending boundaries near 30 seconds.
- When neither punctuation nor `>>` markers exist, blocks split by time windows near 30 seconds.
- The merge step only changes block boundaries and line breaks. It does not paraphrase transcript content.
