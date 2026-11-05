"""PG13Nator: censor profanity in a movie by muting detected words.

Pipeline: transcribe (whisper_timestamped) -> detect profanity
(lexicon + fuzzy + ML) -> rebuild audio with muted intervals -> mux
back into the video with ffmpeg (no re-encode). Also writes a filtered
.srt subtitle file and a JSON report.
"""

import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from profanity_check import predict_prob
from pydub import AudioSegment
from rapidfuzz.distance import Levenshtein
import whisper_timestamped as whisper

log = logging.getLogger("pg13nator")

STRONG_LEXICON = frozenset({
    "fuck", "fucks", "fucked", "fucking", "fuckin", "fuckings", "fucker", "fuckers",
    "fck", "fcuk", "fvck", "phuck", "phuk", "fuk", "fukin", "fuking",
    "motherfucker", "motherfuckers", "motherfucking", "motherfuckin", "motherfucka",
    "shit", "shits", "shitty", "shittier", "shittiest", "shitting", "bullshit",
    "horseshit", "batshit", "dipshit", "shithead",
    "bitch", "bitches", "bitching", "bitchin",
    "bastard", "bastards", "cunt", "cunts",
    "dick", "dicks", "dickhead", "dickheads", "cock", "cocks", "cocksucker",
    "pussy", "pussies", "prick", "pricks", "twat", "wanker", "wankers",
    "whore", "whores", "slut", "sluts",
    "douche", "douchebag", "douchebags",
    "fag", "fags", "faggot", "faggots",
    "nigger", "niggers", "nigga", "niggas",
    "retard", "retards", "retarded",
    "asshole", "assholes", "arsehole", "arseholes",
    "jackass", "dumbfuck", "bollocks",
    "wtf", "stfu", "gtfo", "bs",
})

MILD_LEXICON = frozenset({
    "damn", "damned", "dammit", "goddamn", "goddamned", "goddammit", "goddamnit",
    "hell", "hellion",
    "crap", "craps", "crappy",
    "piss", "pisses", "pissed", "pissing",
    "ass", "asses", "arse", "arses",
    "badass", "dumbass", "smartass", "fatass", "lazyass", "kickass", "hardass",
})

_LEET = str.maketrans({
    "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
    "@": "a", "$": "s", "!": "i", "+": "t", "|": "i",
})


def _normalize(word):
    w = word.lower().translate(_LEET)
    return re.sub(r"[^a-z']", "", w)


def _fuzzy_matches_strong(word):
    for entry in STRONG_LEXICON:
        if len(entry) < 5:
            continue
        if abs(len(word) - len(entry)) > 2:
            continue
        # substitutions cost 2 so lookalike words ("shot"/"shit") never match;
        # only insertions/deletions do ("biatch"/"bitch", "fcker"/"fucker")
        if Levenshtein.distance(word, entry, weights=(1, 1, 2)) <= 1:
            return True
    return False


def detect_profanity(words, ml_threshold=None):
    normalized = [_normalize(w) for w in words]
    flags = []
    for w in normalized:
        # collapsed form catches stretched spellings ("fuuuck") without
        # letting partial words ("class") match short entries ("ass")
        collapsed = re.sub(r"(.)\1+", r"\1", w)
        flags.append(
            w in STRONG_LEXICON
            or w in MILD_LEXICON
            or collapsed in STRONG_LEXICON
            or _fuzzy_matches_strong(w)
        )
    if ml_threshold is not None:
        probs = predict_prob(normalized)
        flags = [f or p >= ml_threshold for f, p in zip(flags, probs)]
    return flags


def detect_hits(result, ml_threshold):
    all_words = []
    locations = []
    for si, segment in enumerate(result["segments"]):
        for wi, word in enumerate(segment.get("words", [])):
            text = word["text"].strip()
            if text:
                all_words.append(text)
                locations.append((si, wi))

    if not all_words:
        return []

    flags = detect_profanity(all_words, ml_threshold)
    hits = []
    for (si, wi), flag, text in zip(locations, flags, all_words):
        if not flag:
            continue
        word = result["segments"][si]["words"][wi]
        hits.append({
            "seg": si,
            "word_idx": wi,
            "word": text,
            "start": float(word["start"]),
            "end": float(word["end"]),
        })
    return hits


def pad_and_merge(hits, duration, pad_ms):
    pad = pad_ms / 1000.0
    intervals = []
    for hit in hits:
        start = max(0.0, hit["start"] - pad)
        end = min(duration, hit["end"] + pad)
        if end > start:
            intervals.append((start, end))

    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def rebuild_audio(video_path, hits, pad_ms, out_wav):
    audio = AudioSegment.from_file(str(video_path))
    duration = audio.duration_seconds
    intervals = pad_and_merge(hits, duration, pad_ms)

    output = AudioSegment.empty()
    cursor_ms = 0
    for start, end in intervals:
        start_ms = int(start * 1000)
        end_ms = min(int(end * 1000), len(audio))
        if start_ms >= len(audio) or end_ms <= start_ms:
            continue
        output += audio[cursor_ms:start_ms]
        output += AudioSegment.silent(duration=end_ms - start_ms)
        cursor_ms = end_ms
    output += audio[cursor_ms:]
    output.export(str(out_wav), format="wav")
    return duration


def mux_audio(video_path, wav_path, output_path):
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video_path), "-i", str(wav_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def _fmt_srt_ts(seconds):
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _join_word_texts(parts):
    text = ""
    for part in parts:
        if not part:
            continue
        if not text:
            text = part
        elif part[0].isspace() or part[0] in ".,!?;:)\"'":
            text += part
        elif text[-1] in "([{":
            text += part
        else:
            text += " " + part
    return text


def write_srt(segments, hits, path):
    censored = {(h["seg"], h["word_idx"]) for h in hits}
    blocks = []
    for si, segment in enumerate(segments):
        words = segment.get("words") or []
        if words:
            parts = []
            for wi, w in enumerate(words):
                if (si, wi) in censored:
                    leading = w["text"][:len(w["text"]) - len(w["text"].lstrip())]
                    parts.append(leading + "[censored]")
                else:
                    parts.append(w["text"])
            text = _join_word_texts(parts).strip()
        else:
            text = segment.get("text", "").strip()
        if not text:
            continue
        blocks.append(
            f"{len(blocks) + 1}\n"
            f"{_fmt_srt_ts(segment['start'])} --> {_fmt_srt_ts(segment['end'])}\n"
            f"{text}\n"
        )
    path = Path(path)
    path.write_text("\n".join(blocks), encoding="utf-8")


def write_report(path, info):
    Path(path).write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")


def _fmt_clock(seconds):
    minutes, sec = divmod(seconds, 60)
    return f"{int(minutes)}:{sec:05.2f}"


def _require_ffmpeg():
    if shutil.which("ffmpeg") is None:
        sys.exit("error: ffmpeg not found in PATH (required by pydub/whisper)")


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Censor profanity in a video by muting detected words."
    )
    parser.add_argument("--video", required=True, help="path to the input video")
    parser.add_argument("--output", "-o", help="output video path (default: <name>.pg13.mp4)")
    parser.add_argument("--model", default="small",
                        help="whisper model size: tiny/base/small/medium (default: small)")
    parser.add_argument("--ml-threshold", type=float, default=None, metavar="0.0-1.0",
                        help="opt-in: also flag words via alt-profanity-check ML model at "
                             "this probability. Warning: it also flags insults like "
                             "'dumb'/'stupid' (not just profanity)")
    parser.add_argument("--language", default="en", help="audio language (default: en)")
    parser.add_argument("--pad-ms", type=int, default=100,
                        help="padding around each muted word in ms (default: 100)")
    parser.add_argument("--dry-run", action="store_true",
                        help="only transcribe and report detected words, no output files")
    parser.add_argument("--verbose", action="store_true", help="debug logging")
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    _require_ffmpeg()

    video_path = Path(args.video).expanduser()
    if not video_path.is_file():
        sys.exit(f"error: video not found: {video_path}")

    if args.output:
        output_path = Path(args.output).expanduser()
    else:
        output_path = video_path.with_name(video_path.stem + ".pg13.mp4")
    srt_path = output_path.with_name(output_path.stem + ".srt")
    report_path = output_path.with_name(output_path.stem + ".report.json")

    log.info("loading whisper model '%s'...", args.model)
    model = whisper.load_model(args.model)
    log.info("transcribing %s...", video_path.name)
    audio = whisper.load_audio(str(video_path))
    result = whisper.transcribe(model, audio, language=args.language, verbose=False)

    hits = detect_hits(result, args.ml_threshold)
    log.info("found %d profane word(s)", len(hits))

    if args.dry_run:
        for hit in hits:
            print(f"  {_fmt_clock(hit['start'])} - {_fmt_clock(hit['end'])}  {hit['word']}")
        if not hits:
            print("  nothing detected")
        return

    with tempfile.TemporaryDirectory(prefix="pg13nator-") as tmpdir:
        if hits:
            log.info("rebuilding audio with muted intervals...")
            duration = rebuild_audio(video_path, hits, args.pad_ms,
                                     Path(tmpdir) / "filtered.wav")
            log.info("muxing video with new audio (no re-encode)...")
            mux_audio(video_path, Path(tmpdir) / "filtered.wav", output_path)
        else:
            intervals, duration = [], None
            log.info("nothing to mute, copying video...")
            shutil.copy2(video_path, output_path)

    write_srt(result["segments"], hits, srt_path)
    write_report(report_path, {
        "video": str(video_path),
        "output": str(output_path),
        "srt": str(srt_path),
        "model": args.model,
        "language": args.language,
        "ml_threshold": args.ml_threshold,
        "pad_ms": args.pad_ms,
        "duration_seconds": duration,
        "words_scanned": sum(len(s.get("words", [])) for s in result["segments"]),
        "detections": [
            {"word": h["word"], "start": h["start"], "end": h["end"]} for h in hits
        ],
    })
    log.info("done: %s", output_path)
    log.info("subtitles: %s", srt_path)
    log.info("report: %s", report_path)


if __name__ == "__main__":
    main()
