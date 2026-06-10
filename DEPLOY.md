# Deploy guide — GitHub + Streamlit Community Cloud

This deploys the single-file app (`streamlit_app.py`) as one free hosted service.
No backend server needed — the pipeline runs inside the Streamlit process.

## 0. Before you push — protect your secrets

Make sure `.gitignore` exists and contains `.env` (it does, in this repo). Your
keys must NEVER be committed. Double-check:

```bash
git status            # .env must NOT appear in the list
```

## 1. Put it on GitHub

```bash
cd ~/Downloads/splitwisev2          # your project folder
git init
git add .
git status                          # confirm .env is absent
git commit -m "Splitwise Voice — working build"
```

Create an empty repo on github.com (no README/gitignore — you already have them),
then:

```bash
git remote add origin https://github.com/akshat0-lgtm/splitwise-voice.git
git branch -M main
git push -u origin main
```

## 2. Deploy on Streamlit Community Cloud

1. Go to **share.streamlit.io** and sign in with GitHub.
2. Click **Create app** → **Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `akshat0-lgtm/splitwise-voice`
   - **Branch:** `main`
   - **Main file path:** `streamlit_app.py`   ← important: the single-file app, NOT app.py
4. Click **Advanced settings** → **Secrets**, and paste (TOML format):

   ```toml
   GROQ_API_KEY = "your_groq_key"
   SPLITWISE_API_KEY = "your_splitwise_key"
   ```

5. Click **Deploy**. First build takes ~2-3 min while it installs requirements.

You'll get a URL like `https://splitwise-voice.streamlit.app` — open it on your
phone, add to home screen, done.

## 3. Updating later

Any push to `main` auto-redeploys:

```bash
git add .
git commit -m "Add quantity to OCR"
git push
```

Streamlit Cloud picks up the change and rebuilds in a minute or two.

## Notes

- **Two apps in the repo:** `streamlit_app.py` is the deployed single-file version.
  `app.py` + `main.py` are the split frontend/backend for local dev and the future
  iOS Shortcut path. The deploy only uses `streamlit_app.py`.
- **Secrets:** set in Streamlit Cloud's Secrets UI, never in the repo. Locally they
  come from `.env`.
- **Anyone with the URL can post to your Splitwise.** Fine for a trusted group. Add a
  shared passcode in `streamlit_app.py` before sharing widely (see To do → "Anyone can pay"
  and the multi-user item for the proper fix).
