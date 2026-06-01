# Whatsapp Number Cleaning & Delivery Automation

Streamlit app: upload a CSV/Excel contact file → clean & validate numbers →
upload the cleaned file to Files.com → post a summary comment to Jira.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
Create `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example` and fill in your credentials.

## Deploy (Streamlit Community Cloud)
- Main file path: `app.py`
- Add the four secrets from the example file in the app's **Settings → Secrets**
- Keep the app **private** and invite team members by email
