import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from script import write_srt


def test_write_srt_censors_and_preserves_spacing():
    hits = [
        {"word": "fuck", "start": 0.4, "end": 0.9, "seg": 0, "word_idx": 2},
        {"word": "shit", "start": 1.3, "end": 1.6, "seg": 0, "word_idx": 4},
        {"word": "damn", "start": 9.9, "end": 10.4, "seg": 1, "word_idx": 0},
    ]
    # segments where word texts carry leading spaces (common whisper style)
    spaced = [
        {"start": 0.0, "end": 2.0, "text": "This is fucking great shit man", "words": [
            {"text": "This", "start": 0.0, "end": 0.2},
            {"text": " is", "start": 0.2, "end": 0.4},
            {"text": " fucking", "start": 0.4, "end": 0.9},
            {"text": " great", "start": 0.9, "end": 1.2},
            {"text": " shit", "start": 1.3, "end": 1.6},
            {"text": " man", "start": 1.6, "end": 2.0},
        ]},
        {"start": 9.5, "end": 10.4, "text": "Goddammit", "words": [
            {"text": "Goddammit", "start": 9.9, "end": 10.4},
        ]},
    ]
    path = Path("/tmp/opencode/test_repo_srt.srt")
    write_srt(spaced, hits, path)
    content = path.read_text()
    assert content.count("[censored]") == 3
    assert "This is [censored] great [censored] man" in content
    assert "fucking" not in content and "shit" not in content and "Goddammit" not in content
    assert "00:00:00,000 --> 00:00:02,000" in content
    assert "00:00:09,500 --> 00:00:10,400" in content
    assert content.startswith("1\n")


def test_write_srt_joins_unspaced_words():
    # segments where word texts carry NO leading spaces (whisper-timestamped
    # tiny sometimes emits these) must still produce readable spaced text
    unspaced = [
        {"start": 0.0, "end": 1.6, "text": "Get the fuck out of here.", "words": [
            {"text": "Get", "start": 0.0, "end": 0.2},
            {"text": "the", "start": 0.2, "end": 0.4},
            {"text": "fuck", "start": 0.4, "end": 0.8},
            {"text": "out", "start": 0.8, "end": 1.0},
            {"text": "of", "start": 1.0, "end": 1.1},
            {"text": "here.", "start": 1.1, "end": 1.6},
        ]},
    ]
    hits = [{"word": "fuck", "start": 0.4, "end": 0.8, "seg": 0, "word_idx": 2}]
    path = Path("/tmp/opencode/test_repo_srt2.srt")
    write_srt(unspaced, hits, path)
    content = path.read_text()
    assert "Get the [censored] out of here." in content, repr(content)


if __name__ == "__main__":
    test_write_srt_censors_and_preserves_spacing()
    test_write_srt_joins_unspaced_words()
    print("test_srt: PASS")
