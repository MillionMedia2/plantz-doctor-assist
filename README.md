# Doctor Assist Python Chatbot

A simple, portable chatbot web app with a Python (FastAPI) backend and static HTML/CSS/JS frontend. Designed for easy embedding (iframe or pop-up) and Vercel deployment.

## Features
- Simple chat UI (HTML/CSS/JS)
- Streaming OpenAI responses (Responses API)
- "Thinking" animation
- Easy to add form fields (checkboxes, etc.)
- Portable: move or deploy anywhere

## Folder Structure
```
doctor-assist-py/
├── static/
│   ├── index.html
│   ├── style.css
│   └── chatbot.js
├── app/
│   └── main.py
├── requirements.txt
├── vercel.json
├── README.md
└── .gitignore
```

## Setup
1. Install Python 3.10+ and pip (if not already installed).
2. (Optional) Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set your OpenAI API key as an environment variable:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```
5. Run locally:
   ```bash
   uvicorn app.main:app --reload
   ```
6. Open `http://localhost:8000` in your browser.

## Deploy on Vercel
- Push this folder to a new GitHub repo.
- Connect the repo to Vercel and deploy (Vercel will auto-detect Python and static files).

## Embedding
- Use an `<iframe src="https://your-vercel-app.vercel.app/" ...>` to embed the chatbot anywhere.

--- 