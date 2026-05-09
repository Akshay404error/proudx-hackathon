"""Resource curator: trusted-source whitelist + quality scoring."""
from urllib.parse import urlparse
from typing import Tuple


TRUSTED_DOMAINS: dict[str, float] = {
    # Official docs
    "developer.mozilla.org": 9.5,
    "docs.python.org": 9.5,
    "react.dev": 9.5,
    "reactjs.org": 9.0,
    "kubernetes.io": 9.0,
    "docs.docker.com": 9.0,
    "go.dev": 9.0,
    "rust-lang.org": 9.0,
    "doc.rust-lang.org": 9.5,
    "fastapi.tiangolo.com": 9.5,
    "flask.palletsprojects.com": 9.0,
    "djangoproject.com": 9.0,
    "docs.djangoproject.com": 9.5,
    "nodejs.org": 9.0,
    "vuejs.org": 9.0,
    "angular.io": 8.5,
    "angular.dev": 9.0,
    "tailwindcss.com": 9.0,
    "nextjs.org": 9.5,
    "tensorflow.org": 9.0,
    "pytorch.org": 9.0,
    "scikit-learn.org": 9.5,
    "huggingface.co": 9.0,
    "openai.com": 8.5,
    # Tutorials
    "freecodecamp.org": 9.0,
    "www.freecodecamp.org": 9.0,
    "javascript.info": 9.5,
    "css-tricks.com": 8.5,
    "web.dev": 9.5,
    "developers.google.com": 9.0,
    "learn.microsoft.com": 9.0,
    "docs.microsoft.com": 8.5,
    "khanacademy.org": 8.5,
    "ocw.mit.edu": 9.5,
    "cs50.harvard.edu": 9.5,
    # Coding practice
    "leetcode.com": 9.0,
    "hackerrank.com": 8.5,
    "codeforces.com": 9.0,
    "geeksforgeeks.org": 8.0,
    "exercism.org": 8.5,
    "codewars.com": 8.0,
    "atcoder.jp": 9.0,
    # Video
    "youtube.com": 7.5,
    "youtu.be": 7.5,
    # Q&A
    "stackoverflow.com": 8.0,
    "github.com": 8.0,
    # Books
    "eloquentjavascript.net": 9.0,
    "automatetheboringstuff.com": 9.0,
    "fullstackopen.com": 9.5,
    "roadmap.sh": 8.5,
}

QUALITY_YT_CHANNELS = {
    "fireship", "traversymedia", "thenetninja", "freecodecamp",
    "harvardonline", "mitopencourseware", "computerphile", "3blue1brown",
    "academind", "stanfordonline", "cs50", "programmingwithmosh",
    "thecodingtrain", "mpjme",
}

LOW_QUALITY_PATTERNS = ("scribd", "coursehero", "chegg", "tutorialspoint", "w3schools")


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def base_score_for_url(url: str) -> Tuple[float, bool]:
    """Returns (score_0_to_10, is_curated)."""
    if not url:
        return 0.0, False
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return 0.0, False

    if netloc in TRUSTED_DOMAINS:
        return TRUSTED_DOMAINS[netloc], True
    no_www = netloc.replace("www.", "", 1) if netloc.startswith("www.") else netloc
    if no_www in TRUSTED_DOMAINS:
        return TRUSTED_DOMAINS[no_www], True

    if "youtube.com" in netloc or "youtu.be" in netloc:
        url_lower = url.lower()
        for ch in QUALITY_YT_CHANNELS:
            if ch in url_lower:
                return 9.0, True
        return 7.5, True

    for bad in LOW_QUALITY_PATTERNS:
        if bad in netloc:
            return 2.5, False

    return 5.0, False


def adjust_for_alive(base: float, is_alive: bool) -> float:
    if not is_alive:
        return max(0.0, base - 5.0)
    return min(10.0, base + 0.5)


def adjust_for_feedback(base: float, helpful_count: int, unhelpful_count: int) -> float:
    delta = 0.5 * helpful_count - 0.5 * unhelpful_count
    delta = max(-2.0, min(2.0, delta))
    return max(0.0, min(10.0, base + delta))