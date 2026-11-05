# PG13Nator

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![ffmpeg](https://img.shields.io/badge/requires-ffmpeg-green)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

Censor profanity in movies: detects bad words in the audio track and mutes
them, producing a clean copy of the video plus filtered subtitles.

## Features

- **Word-level detection** via whisper-timestamped transcription
- **Fuzzy matching** catches obfuscations ("sh!t", "f*ck", "fuuuck", "biatch")
- **No re-encoding** — audio is muted and stream-copied back, fast with zero quality loss
- **Filtered subtitles** — output `.srt` with bad words replaced by `[censored]`
- **Dry-run mode** — preview detected words and timestamps before touching the file
- **Optional ML detection** — plug in `alt-profanity-check` as a second detector

## Why

Some people don't like to watch movies where characters curse a lot, so this
script finds the swear words and mutes them automatically.

## How it works

1. Transcribes the audio with [whisper-timestamped](https://github.com/linto-ai/whisper-timestamped) (word-level timestamps)
2. Flags profane words using a curated lexicon + fuzzy matching (catches
   "sh!t", "f*ck", "fuuuck", "biatch"...) and optional ML detection
3. Rebuilds the audio with silence over each flagged word (padded ±100ms)
4. Muxes the clean audio back into the video **without re-encoding**
   (ffmpeg stream copy: fast, no quality loss)
5. Writes a filtered `.srt` (bad words replaced with `[censored]`) and a
   `.report.json` listing everything detected

## Install

Requires Python 3.9+ and [ffmpeg](https://ffmpeg.org) on your PATH.

```bash
git clone https://github.com/diegosoriarios/PG13Nator.git
cd PG13Nator
pip install -r requirements.txt
```

Tip: for a smaller install (no GPU), use the CPU build of torch:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

## Usage

```bash
python3 script.py --video=VIDEO_PATH
```

Output: `VIDEO_PATH.pg13.mp4`, `VIDEO_PATH.pg13.srt`, `VIDEO_PATH.pg13.report.json`

Options:

| Flag | Default | Description |
| --- | --- | --- |
| `--output/-o` | `<name>.pg13.mp4` | output video path |
| `--model` | `small` | whisper model: `tiny`/`base`/`small`/`medium` (bigger = more accurate, slower) |
| `--language` | `en` | audio language |
| `--pad-ms` | `100` | padding around each muted word |
| `--ml-threshold` | off | also use the `alt-profanity-check` ML model; warns: it also flags insults like "dumb"/"stupid", not just profanity |
| `--dry-run` | - | only print detected words + timestamps, write nothing |
| `--verbose` | - | debug logging |

Examples:

```bash
# preview what would be censored
python3 script.py --video movie.mp4 --dry-run

# more accurate transcription for noisy audio
python3 script.py --video movie.mp4 --model medium
```

## Limitations

- Accuracy depends on the transcription; heavy background music may hide words
- Only flags single words (multi-word phrases like "oh my god" are partially covered)
- Mild religious exclamations like "Jesus!" alone are not censored to avoid
  false positives in religious content

## Tests

Plain-Python scripts, no test framework needed:

```bash
python3 tests/test_detector.py
python3 tests/test_intervals.py
python3 tests/test_srt.py
```

## Legal

Made for personal use on media you own. Distributing modified copies of
copyrighted movies is illegal in most jurisdictions.
