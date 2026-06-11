"""
NLP service — abusive language classifier using trained sklearn Pipeline.

Drop your trained model file at:
    chirp/models/abusive_classifier.pkl

The file is produced by the Colab notebook (abusive_language_classifier.ipynb).
Everything else in the app calls predict_abuse(text) — no other changes needed.
"""

import pickle
import re
import os
import logging
from pathlib import Path
from functools import lru_cache

logger = logging.getLogger(__name__)

# ── Path to the .pkl (resolve relative to this file) ──────────────────────────
_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "abusive_classifier.pkl"

# ── Same cleaner used during training ─────────────────────────────────────────
_URL_RE     = re.compile(r"https?://\S+|www\.\S+")
_MENTION_RE = re.compile(r"@\w+")
_HASHTAG_RE = re.compile(r"#(\w+)")
_REPEAT_RE  = re.compile(r"(.)\1{2,}")
_SPACE_RE   = re.compile(r"\s+")


def _clean(text: str) -> str:
    text = str(text).lower()
    text = _URL_RE.sub(" url ", text)
    text = _MENTION_RE.sub(" user ", text)
    text = _HASHTAG_RE.sub(r" \1 ", text)
    text = _REPEAT_RE.sub(r"\1\1", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


@lru_cache(maxsize=1)
def _load_model():
    """Load the .pkl once and cache it for the lifetime of the process."""
    if not _MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at '{_MODEL_PATH}'.\n"
            "Run the Colab notebook (abusive_language_classifier.ipynb) to train "
            "and export abusive_classifier.pkl, then place it in chirp/models/."
        )
    with open(_MODEL_PATH, "rb") as f:
        model = pickle.load(f)
    logger.info("Abusive language model loaded from %s", _MODEL_PATH)
    return model


# ── Public API — called by routes/tweets.py ───────────────────────────────────
def predict_abuse(text: str, threshold: float = 0.50) -> dict:
    """
    Classify a tweet as abusive or non-abusive.

    Parameters
    ----------
    text      : raw tweet content (will be cleaned internally)
    threshold : probability cutoff for 'abusive' label (default 0.50)
                Lower = flag more aggressively; raise to 0.65 to reduce false positives.

    Returns
    -------
    {
        "label"     : "abusive" | "non_abusive",
        "confidence": float (0–1),   # probability of the predicted class
        "score"     : float (0–1),   # raw P(abusive) — useful for admin dashboards
    }
    """
    if not text or not text.strip():
        return {"label": "non_abusive", "confidence": 0.99, "score": 0.01}

    try:
        model  = _load_model()
        cleaned = _clean(text)
        proba   = model.predict_proba([cleaned])[0]   # [P(clean), P(abusive)]
        score   = float(proba[1])
        is_abusive = score >= threshold

        label      = "abusive" if is_abusive else "non_abusive"
        confidence = round(score if is_abusive else 1 - score, 4)

        return {"label": label, "confidence": confidence, "score": round(score, 4)}

    except FileNotFoundError:
        # Model not yet trained — raise so the developer notices immediately
        raise
    except Exception as exc:
        # Unexpected error — log and fail safe (don't block tweet posting)
        logger.error("predict_abuse failed: %s", exc, exc_info=True)
        return {"label": "non_abusive", "confidence": 0.50, "score": 0.50}
