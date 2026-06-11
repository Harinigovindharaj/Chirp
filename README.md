# Chirp — Mini Twitter Clone with Abusive Language Detection

A Flask-based Twitter clone that automatically classifies every tweet using a
trained NLP model and applies progressive moderation consequences.

## Project Structure

```
chirp/
├── app.py                     # Flask application factory
├── models.py                  # SQLAlchemy models (User, Tweet)
├── requirements.txt
├── models/
│   └── abusive_classifier.pkl  ← PUT YOUR TRAINED MODEL HERE
├── routes/
│   ├── auth.py                # Login / register
│   ├── tweets.py              # Feed, compose, profile
│   ├── main.py                # Landing page
│   └── admin.py               # Admin dashboard
├── services/
│   ├── nlp_service.py         # ← Model loaded & called here
│   └── abuse_service.py       # Consequence logic (warn / block / ban)
├── static/
└── templates/
```

## Setup

### 1. Train the model (Google Colab)
1. Open `abusive_language_classifier.ipynb` in Colab
2. Upload `Suspicious_Communication_on_Social_Platforms.csv`
3. Run all cells → `abusive_classifier.pkl` downloads automatically
4. Move `abusive_classifier.pkl` → `chirp/models/abusive_classifier.pkl`

### 2. Install & run

```bash
pip install -r requirements.txt
python app.py
```

Visit http://localhost:5000

Default admin login: `admin` / `admin123`

## How detection works

Every tweet goes through this pipeline on POST `/tweets/new`:

```
raw tweet
    ↓ clean_text()          # lowercase, strip URLs/mentions/hashtags
    ↓ TF-IDF (word + char)  # vectorise
    ↓ LogisticRegression    # predict P(abusive)
    ↓ threshold = 0.50      # label as abusive | non_abusive
    ↓ apply_abuse_consequences()
```

### Moderation thresholds (abuse_service.py)

| abuse_score | Action |
|-------------|--------|
| ≥ 1 | Warning shown, status → `warned` |
| ≥ 3 | Posting disabled, status → `temporarily_blocked` |
| ≥ 5 | Account banned, status → `permanently_banned` |

### Adjusting sensitivity

In `services/nlp_service.py`, change the threshold:

```python
# More aggressive — flag borderline tweets
result = predict_abuse(content, threshold=0.35)

# Conservative — only flag high-confidence cases
result = predict_abuse(content, threshold=0.65)
```
