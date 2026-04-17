import os
import uuid
import json
import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify

from scraper import scrape_reviews
from sentiment import analyze_reviews

app = Flask(__name__)
app.secret_key = "flipkart_sentiment_secret_2024"

# In-memory job store  {job_id: {status, product_name, aspect_results, overall, csv_path, error}}
JOBS = {}
REVIEWS_DIR = os.path.join(os.path.dirname(__file__), "reviews")
os.makedirs(REVIEWS_DIR, exist_ok=True)


def run_pipeline(job_id: str, product_url: str):
    """Background thread: scrape → analyze → store results."""
    try:
        JOBS[job_id]["status"] = "scraping"
        print(f"[{job_id}] Scraping reviews from: {product_url}")
        df, product_name = scrape_reviews(product_url, max_pages=15)

        if df is None or len(df) == 0:
            JOBS[job_id]["status"] = "error"
            JOBS[job_id]["error"] = (
                "No reviews could be scraped. "
                "Please check the URL and ensure it is a valid Flipkart product page."
            )
            return

        # Save CSV
        csv_filename = f"{job_id}.csv"
        csv_path = os.path.join(REVIEWS_DIR, csv_filename)
        df.to_csv(csv_path, index=False)
        JOBS[job_id]["csv_filename"] = csv_filename
        JOBS[job_id]["total_reviews"] = len(df)
        JOBS[job_id]["product_name"] = product_name

        # Sentiment analysis
        JOBS[job_id]["status"] = "analyzing"
        print(f"[{job_id}] Analyzing {len(df)} reviews …")
        aspect_results, overall = analyze_reviews(df)

        JOBS[job_id]["aspect_results"] = aspect_results
        JOBS[job_id]["overall"] = overall
        JOBS[job_id]["status"] = "done"
        print(f"[{job_id}] Done!")

    except Exception as exc:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(exc)
        print(f"[{job_id}] ERROR: {exc}")


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    product_url = request.form.get("url", "").strip()
    if not product_url:
        return render_template("index.html", error="Please enter a Flipkart product URL.")
    if "flipkart.com" not in product_url:
        return render_template("index.html", error="URL must be from flipkart.com")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "status": "queued",
        "product_name": "Loading…",
        "url": product_url,
        "error": None,
        "csv_filename": None,
        "total_reviews": 0,
        "aspect_results": {},
        "overall": {}
    }

    t = threading.Thread(target=run_pipeline, args=(job_id, product_url), daemon=True)
    t.start()

    return redirect(url_for("loading", job_id=job_id))


@app.route("/loading/<job_id>")
def loading(job_id):
    if job_id not in JOBS:
        return render_template("index.html", error="Job not found.")
    return render_template("loading.html", job_id=job_id)


@app.route("/status/<job_id>")
def status(job_id):
    """Polling endpoint for the loading page."""
    if job_id not in JOBS:
        return jsonify({"status": "error", "error": "Job not found"})
    job = JOBS[job_id]
    return jsonify({
        "status": job["status"],
        "error": job.get("error"),
        "product_name": job.get("product_name", "")
    })


@app.route("/results/<job_id>")
def results(job_id):
    if job_id not in JOBS:
        return render_template("index.html", error="Job not found.")
    job = JOBS[job_id]
    if job["status"] != "done":
        return redirect(url_for("loading", job_id=job_id))

    return render_template(
        "results.html",
        job_id=job_id,
        product_name=job["product_name"],
        total_reviews=job["total_reviews"],
        overall=job["overall"],
        aspect_results=job["aspect_results"],
        aspect_results_json=json.dumps(job["aspect_results"]),
        overall_json=json.dumps(job["overall"]),
        csv_filename=job["csv_filename"]
    )


@app.route("/download/<filename>")
def download(filename):
    from flask import send_from_directory
    return send_from_directory(REVIEWS_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    print("[*] Starting Flipkart Review Sentiment Analyzer ...")
    print("   Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True, use_reloader=False)
