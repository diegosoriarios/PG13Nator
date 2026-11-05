import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from script import detect_profanity


def test_detector_lexicon_only():
    cases_true = [
        "fuck", "f*ck", "sh!t", "biatch", "damn", "hell", "wtf", "goddammit", "Ass",
        "motherfcker", "fuuuck", "b1tch", "a$$", "dumbass", "bullshit", "stfu", "fcuk", "fck",
        "prick", "whore", "sluts", "cunt", "retarded", "Bollocks", "arsehole",
    ]
    cases_false = [
        "hello", "shot", "class", "count", "assassin", "batch", "scrum", "duck",
        "shell", "password", "the", "and", "shitake", "assess", "hello there", "",
        "dumb", "stupid", "kill", "ugly", "hate", "die", "fart", "bloody", "butt", "sex",
    ]
    flags = detect_profanity(cases_true + cases_false)
    for word, flag in zip(cases_true, flags[:len(cases_true)]):
        assert flag, f"should detect: {word!r}"
    for word, flag in zip(cases_false, flags[len(cases_true):]):
        assert not flag, f"false positive: {word!r}"


def test_ml_mode_opt_in():
    flags = detect_profanity(["cocksucker", "tit"], ml_threshold=0.5)
    assert all(bool(f) for f in flags)


def test_scan_performance():
    words = ["hello", "the", "movie", "scene"] * 5000
    start = time.time()
    detect_profanity(words)
    assert time.time() - start < 5, "20k word scan too slow"


if __name__ == "__main__":
    test_detector_lexicon_only()
    test_ml_mode_opt_in()
    test_scan_performance()
    print("test_detector: PASS")
