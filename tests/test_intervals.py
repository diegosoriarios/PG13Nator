import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from script import pad_and_merge, _fmt_srt_ts


def test_pad_clamp_and_merge():
    hits = [
        {"word": "fuck", "start": 0.0, "end": 0.5, "seg": 0, "word_idx": 1},
        {"word": "shit", "start": 0.55, "end": 1.0, "seg": 0, "word_idx": 3},
        {"word": "damn", "start": 9.9, "end": 10.4, "seg": 1, "word_idx": 0},
    ]
    intervals = pad_and_merge(hits, duration=10.5, pad_ms=100)
    assert intervals == [(0.0, 1.1), (9.8, 10.5)], intervals


def test_empty_hits():
    assert pad_and_merge([], duration=10.0, pad_ms=100) == []


def test_srt_timestamp_format():
    assert _fmt_srt_ts(3661.234) == "01:01:01,234"
    assert _fmt_srt_ts(0) == "00:00:00,000"
    assert _fmt_srt_ts(-1) == "00:00:00,000"


if __name__ == "__main__":
    test_pad_clamp_and_merge()
    test_empty_hits()
    test_srt_timestamp_format()
    print("test_intervals: PASS")
