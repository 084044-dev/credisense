# 🏦 CrediSense — AI Loan Pre-Screener

An AI-assisted pre-screening app for unsecured personal loans in India (₹50,000 – ₹40 lakh).
Built with **Streamlit** and **Google Gemini** (free tier) for the *AI for Managers* end-term project.

> **Rules decide · AI explains · the app verifies.**
> A transparent 100-point scorecard makes the decision (Approve / Refer / Decline).
> Gemini turns it into a plain-language explanation and an underwriter memo. A verifier then checks
> every AI answer against the engine's numbers before it is shown.

## Features
| Area | What it does |
|---|---|
| 📝 Single assessment | Validated input form, 8 sample applicants, score gauge, factor chart, hard-rule breaches, risk flags, "what would change the outcome" counterfactuals, expert rule-of-thumb cross-check, AI explanation + memo, human-review ticket, JSON download |
| 💬 Ask CrediSense | Multi-turn chat about the current result, scoped to loans; off-topic and prompt-injection handling; clearly labelled as AI |
| 📊 Batch screening | Upload a CSV (or use the 42-row sample book) → validated, scored, charted, CRM-ready CSV export |
| 🧪 Test Lab | Stability chart (near-identical inputs), hallucination checker, prompt-injection tester |
| 🛡️ Guardrails | PII masking (PAN/Aadhaar/phone/email), consent toggle, per-session AI cap, response caching, model fallback chain, retry/backoff, rule-based fallback, simulated-outage switch, audit log |

## Run locally
```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then paste your key
streamlit run app.py
python -m pytest -q tests                                   # 14 tests
```
The app also runs **without** a key (rule-based mode), so it never breaks during a demo.

## Get a free Gemini API key (2 minutes)
1. Go to **https://aistudio.google.com** and sign in with a Google account.
2. Click **Get API key → Create API key**. Copy it.
3. Default model is `gemini-3.5-flash`; the app automatically falls back to
   `gemini-3.5-flash-lite` and then `gemini-3.1-flash-lite` if a model is unavailable or rate-limited.
   Override with `GEMINI_MODEL` in secrets if Google renames models.

## Deploy for a shareable link (Streamlit Community Cloud, free)
1. Create a free account at **https://github.com** → **New repository** → name it `credisense` → Public → Create.
2. On the repo page click **Add file → Upload files** and drag in everything from this folder
   (`app.py`, `engine.py`, `ai.py`, `sample_data.py`, `requirements.txt`, `README.md`, and the
   `.streamlit`, `data`, `tests` folders). **Do not upload a real `secrets.toml`.** Commit.
3. Go to **https://share.streamlit.io** → sign in with GitHub → **Create app → Deploy a public app from GitHub**.
4. Repository `your-username/credisense`, branch `main`, main file `app.py`.
   Choose a custom URL such as `credisense-yourname`.
5. Open **Advanced settings → Secrets** and paste:
   ```toml
   GEMINI_API_KEY = "your-key-here"
   GEMINI_MODEL = "gemini-3.5-flash"
   ```
6. Click **Deploy**. In 2–3 minutes you get `https://credisense-yourname.streamlit.app`. That is your submission link.
7. The sidebar should show **"AI connected – model: gemini-3.5-flash"**. Run Priya Sharma: the
   explanation badge should read **✨ AI-generated**.

**Tip:** free Streamlit apps go to sleep after a period of no traffic. Open the link 5 minutes before
your evaluation and click "Yes, get this app back up" if you see it.

## Project structure
```
app.py          Streamlit UI (5 tabs, state management, caching)
engine.py       Validation, 100-point scorecard, hard rules, counterfactuals (no AI)
ai.py           Gemini calls, prompts, PII/injection screening, output verifier, fallbacks
sample_data.py  8 fictional personas + synthetic 42-row batch
data/           sample_applicants.csv (upload in the Batch tab)
tests/          pytest suite (engine, guardrails, mocked AI failures)
```

*Educational project. Not a credit sanction or financial advice. All data is fictional.*
