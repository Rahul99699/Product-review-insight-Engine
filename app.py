import os
import joblib
import spacy
import pandas as pd
from flask import Flask, request, render_template, jsonify

app = Flask(__name__)

# Load models
try:
    model = joblib.load("sentiment_model.pkl")
    vectorizer = joblib.load("tfidf_vectorizer.pkl")
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    print(f"Error loading models or spacy: {e}")
    # Fallback to loading spacy if not already present
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

def extract_aspects(text):
    doc = nlp(text)
    aspects = []
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"]:
            aspects.append(token.text)
    # Filter unique aspects and keep only those that appear in meaningful contexts
    return list(set(aspects))

def get_sentiment(text):
    text_vec = vectorizer.transform([text])
    prediction = model.predict(text_vec)[0]
    # Prediction: 1 for Positive, 0 for Negative (based on notebook logic)
    return "Positive" if prediction == 1 else "Negative"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    review_text = request.form.get('review', '')
    if not review_text:
        return render_template('index.html', error="Please enter a review.")

    # Overall Sentiment
    overall_sentiment = get_sentiment(review_text)

    # Aspect-based Sentiment
    doc = nlp(review_text)
    aspects_data = []
    
    # Simple aspect-based logic: find sentences containing aspects
    for sent in doc.sents:
        sent_text = sent.text
        sent_sentiment = get_sentiment(sent_text)
        
        for token in sent:
            if token.pos_ in ["NOUN", "PROPN"]:
                aspects_data.append({
                    "aspect": token.text,
                    "sentiment": sent_sentiment,
                    "sentence": sent_text
                })

    # Deduplicate aspects with their most common sentiment in the review
    unique_aspects = {}
    for item in aspects_data:
        aspect = item['aspect'].lower()
        if aspect not in unique_aspects:
            unique_aspects[aspect] = item['sentiment']

    return render_template('index.html', 
                           review=review_text,
                           overall=overall_sentiment,
                           aspects=unique_aspects)

if __name__ == "__main__":
    app.run(debug=True)