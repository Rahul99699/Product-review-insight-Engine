import joblib
import spacy

# Load models
model = joblib.load("sentiment_model.pkl")
vectorizer = joblib.load("tfidf_vectorizer.pkl")
nlp = spacy.load("en_core_web_sm")

def get_sentiment(text):
    text_vec = vectorizer.transform([text])
    prediction = model.predict(text_vec)[0]
    return "Positive" if prediction == 1 else "Negative"

test_review = "The camera quality is stunning, but the battery life is disappointing. The screen is okay."
doc = nlp(test_review)

print(f"Review: {test_review}\n")

for sent in doc.sents:
    sentiment = get_sentiment(sent.text)
    print(f"Sentence: {sent.text}")
    print(f"Computed Sentiment: {sentiment}")
    aspects = [token.text for token in sent if token.pos_ in ["NOUN", "PROPN"]]
    print(f"Aspects: {aspects}")
    print("-" * 20)
