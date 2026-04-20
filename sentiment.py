import re
import spacy
import emoji
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Load lightweight spaCy pipeline (disable heavy components)
nlp = spacy.blank("en")
nlp.add_pipe("sentencizer")

analyzer = SentimentIntensityAnalyzer()

# -------- Emoji Handling --------
def handle_emojis(text: str) -> str:
    """Convert emojis to text (😊 -> smiling face)"""
    return emoji.demojize(text, delimiters=(" ", " "))


# -------- Common Aspects --------
COMMON_ASPECTS = {
    "battery": ["battery", "charge", "charging", "backup", "power"],
    "display": ["display", "screen", "brightness", "resolution"],
    "camera": ["camera", "photo", "video", "selfie", "lens"],
    "performance": ["performance", "speed", "fast", "lag", "slow"],
    "design": ["design", "build", "look", "body"],
    "price": ["price", "cost", "value", "expensive", "cheap"],
    "sound": ["sound", "speaker", "audio"],
    "storage": ["storage", "memory", "ram"],
    "software": ["software", "ui", "update", "app"],
    "delivery": ["delivery", "shipping", "packaging"],
}

# Precompute keyword → aspect mapping (FASTER)
KEYWORD_TO_ASPECT = {
    kw: aspect for aspect, kws in COMMON_ASPECTS.items() for kw in kws
}


# -------- Sentiment --------
def score_sentiment(text: str):
    scores = analyzer.polarity_scores(text)
    compound = scores["compound"]

    if compound >= 0.05:
        return compound, "positive"
    elif compound <= -0.05:
        return compound, "negative"
    return compound, "neutral"


# -------- Aspect Extraction --------
def extract_aspects(text: str):
    doc = nlp(text)
    results = []

    for sent in doc.sents:
        sent_text = sent.text.strip().lower()

        matched = set()

        # Keyword matching (FAST)
        for word in sent_text.split():
            if word in KEYWORD_TO_ASPECT:
                matched.add(KEYWORD_TO_ASPECT[word])

        # Lemma-based matching
        for token in sent:
            lemma = token.lemma_.lower()
            if lemma in KEYWORD_TO_ASPECT:
                matched.add(KEYWORD_TO_ASPECT[lemma])

        for aspect in matched:
            results.append((aspect, sent.text.strip()))

    return results


# -------- Main Function --------
def analyze_reviews(df):
    aspect_results = {}
    overall = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}

    for row in df.itertuples(index=False):
        review_text = str(getattr(row, "review", "")).strip()

        if len(review_text) < 5:
            continue

        # Handle emojis
        review_text = handle_emojis(review_text)

        # Overall sentiment
        score, label = score_sentiment(review_text)
        overall[label] += 1
        overall["total"] += 1

        # Aspect-level
        for aspect, sentence in extract_aspects(review_text):
            sent_score, sent_label = score_sentiment(sentence)

            if aspect not in aspect_results:
                aspect_results[aspect] = {
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0,
                    "scores": [],
                    "examples": []
                }

            aspect_results[aspect][sent_label] += 1
            aspect_results[aspect]["scores"].append(sent_score)

            if len(aspect_results[aspect]["examples"]) < 3:
                aspect_results[aspect]["examples"].append({
                    "text": sentence[:150],
                    "sentiment": sent_label,
                    "score": round(sent_score, 3)
                })

    # Final aggregation
    for aspect in aspect_results:
        scores = aspect_results[aspect].pop("scores")
        total = sum([
            aspect_results[aspect]["positive"],
            aspect_results[aspect]["negative"],
            aspect_results[aspect]["neutral"]
        ])

        aspect_results[aspect]["total"] = total
        aspect_results[aspect]["avg_score"] = round(
            sum(scores) / len(scores) if scores else 0, 3
        )

    # Sort by importance
    aspect_results = dict(
        sorted(aspect_results.items(), key=lambda x: x[1]["total"], reverse=True)
    )

    return aspect_results, overall