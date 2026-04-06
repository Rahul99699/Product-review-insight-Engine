import joblib

model = joblib.load("sentiment_model.pkl")
vectorizer = joblib.load("tfidf_vectorizer.pkl")

text = ["this product is very bad"]
vec = vectorizer.transform(text)

print(model.predict(vec))