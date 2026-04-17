import re
import spacy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")

analyzer = SentimentIntensityAnalyzer()

# Common product aspects to look for
COMMON_ASPECTS = {
    "battery": ["battery", "charge", "charging", "backup", "mah", "power"],
    "display": ["display", "screen", "amoled", "lcd", "brightness", "resolution", "refresh"],
    "camera": ["camera", "photo", "video", "selfie", "lens", "megapixel", "mp", "picture"],
    "performance": ["performance", "speed", "fast", "lag", "processor", "cpu", "slow", "smooth", "hang"],
    "design": ["design", "build", "look", "color", "colour", "body", "weight", "feel", "slim", "thin"],
    "price": ["price", "cost", "value", "worth", "money", "affordable", "expensive", "cheap", "budget"],
    "sound": ["sound", "speaker", "audio", "volume", "bass", "mic", "microphone"],
    "storage": ["storage", "memory", "ram", "gb", "rom", "space"],
    "software": ["software", "ui", "interface", "update", "os", "features", "app", "bloatware"],
    "delivery": ["delivery", "shipping", "packaging", "box", "packed", "arrived", "days"],
}


def normalize_aspect(word: str) -> str:
    """Map a word to a canonical aspect name."""
    word = word.lower()
    for aspect, keywords in COMMON_ASPECTS.items():
        if word in keywords:
            return aspect
    return word


def extract_aspects_from_text(text: str) -> list:
    """
    Use spaCy to extract noun phrases / nouns that may be aspects.
    Returns a list of (aspect_label, sentence_text) tuples.
    """
    doc = nlp(text)
    aspect_sentences = []

    for sent in doc.sents:
        sent_text = sent.text.strip()
        # Check sentence for known aspect keywords
        sent_lower = sent_text.lower()
        matched_aspects = set()
        for aspect, keywords in COMMON_ASPECTS.items():
            if any(kw in sent_lower for kw in keywords):
                matched_aspects.add(aspect)
        # Also extract noun chunks
        for chunk in sent.noun_chunks:
            token = chunk.root.lemma_.lower()
            norm = normalize_aspect(token)
            if norm in COMMON_ASPECTS:
                matched_aspects.add(norm)
        for aspect in matched_aspects:
            aspect_sentences.append((aspect, sent_text))

    return aspect_sentences


def score_sentiment(text: str) -> dict:
    """Return VADER compound score and label."""
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    return {"compound": compound, "label": label}


def analyze_reviews(df):
    """
    Perform aspect-based sentiment analysis on a reviews DataFrame.

    Returns:
        aspect_results (dict): {aspect: {positive: N, negative: N, neutral: N, avg_score: float, examples: [...]}}
        overall (dict): {positive: N, negative: N, neutral: N, total: N}
    """
    aspect_results = {}
    overall = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}

    for _, row in df.iterrows():
        review_text = str(row.get("review", "")).strip()
        if not review_text or len(review_text) < 5:
            continue

        # Overall review sentiment
        overall_score = score_sentiment(review_text)
        overall[overall_score["label"]] += 1
        overall["total"] += 1

        # Aspect-level sentiment
        aspect_sentences = extract_aspects_from_text(review_text)
        for aspect, sentence in aspect_sentences:
            sent_score = score_sentiment(sentence)
            if aspect not in aspect_results:
                aspect_results[aspect] = {
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0,
                    "scores": [],
                    "examples": []
                }
            aspect_results[aspect][sent_score["label"]] += 1
            aspect_results[aspect]["scores"].append(sent_score["compound"])
            if len(aspect_results[aspect]["examples"]) < 3:
                aspect_results[aspect]["examples"].append({
                    "text": sentence[:200],
                    "sentiment": sent_score["label"],
                    "score": round(sent_score["compound"], 3)
                })

    # Compute average scores and sort by mention count
    for aspect in aspect_results:
        scores = aspect_results[aspect].pop("scores")
        total_mentions = (
            aspect_results[aspect]["positive"]
            + aspect_results[aspect]["negative"]
            + aspect_results[aspect]["neutral"]
        )
        aspect_results[aspect]["total"] = total_mentions
        aspect_results[aspect]["avg_score"] = round(
            sum(scores) / len(scores) if scores else 0, 3
        )

    # Sort by total mentions descending
    aspect_results = dict(
        sorted(aspect_results.items(), key=lambda x: x[1]["total"], reverse=True)
    )

    return aspect_results, overall
