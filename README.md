# Doctor Assist Python Chatbot

A simple, portable chatbot web app with a Python (FastAPI) backend and static HTML/CSS/JS frontend. Designed for easy embedding (iframe or pop-up) and Vercel deployment.

## Features
- Simple chat UI (HTML/CSS/JS)
- Streaming OpenAI responses (Assistants API, not Completions API)
- Animated "Thinking" indicator with dots and status updates
- Per-user memory using OpenAI threads (via session cookies)
- Real-time assistant response streaming and display
- Easy to add form fields (checkboxes, etc.)
- Portable: move or deploy anywhere

## Folder Structure
```
doctor-assist-py/
├── static/
│   ├── index.html           # Main chat UI HTML
│   ├── chatinterface.css    # Main stylesheet for chat UI (used by index.html)
│   └── chatbot.js           # All chat UI and streaming logic
├── app/
│   └── main.py              # FastAPI backend, OpenAI integration
├── requirements.txt         # Python dependencies
├── vercel.json              # Vercel deployment config
├── README.md                # This file
└── .gitignore
```

## Backend (FastAPI)
- **File:** `app/main.py`
- **Endpoints:**
  - `GET /` serves the chat UI (`static/index.html`).
  - `POST /api/chat` receives user messages, manages per-user sessions (via cookies), maps each session to an OpenAI thread, adds the user message, and streams the assistant's response as JSON lines (SSE).
- **Session Management:**
  - Uses a cookie (`doctor_assist_session`) to track users.
  - Each session is mapped to a unique OpenAI thread for memory.
- **OpenAI Integration:**
  - Uses the OpenAI Python SDK (Assistants API).
  - Streams responses chunk-by-chunk to the frontend.

## Frontend (Static Files)
- **index.html:**
  - Loads the chat UI, references `chatinterface.css` for all styling, and `chatbot.js` for all logic.
- **chatbot.js:**
  - Handles sending user messages, streaming and displaying assistant responses in real time.
  - Shows a "Thinking" indicator with animated dots and status updates ("Thinking", "Still Thinking", "Nearly there").
  - Hides the indicator right before displaying the assistant's response.
  - Handles errors gracefully.
- **chatinterface.css:**
  - Styles the entire chat UI, including chat bubbles, input, header, and the thinking indicator.
  - The thinking indicator is centered, greyed out, and uses animated bouncing dots.
  - **Note:** This is the only stylesheet referenced by the HTML. Changes to `style.css` have no effect unless added to the HTML.

## Chatbot Flow
1. User opens the page (`index.html` loads, with `chatinterface.css` and `chatbot.js`).
2. User sends a message (form submit or Enter key).
3. `chatbot.js` shows the thinking indicator, sends the message to `/api/chat`, and streams the response.
4. Backend adds the message to the user's OpenAI thread, starts a run, and streams the response as JSON lines.
5. Frontend parses each chunk, displays the assistant's response in real time, and hides the thinking indicator right before the response appears.
6. All UI is styled by `chatinterface.css`.

## Deploy on Vercel
- Push this folder to a new GitHub repo.
- Connect the repo to Vercel and deploy (Vercel will auto-detect Python and static files).

## Embedding
- Use an `<iframe src="https://your-vercel-app.vercel.app/" ...>` to embed the chatbot anywhere.

---

**For any changes to the chat UI, always edit `chatinterface.css` (not `style.css`).**

If you need to update the thinking indicator, chat streaming, or styling, see the relevant files in `static/`. 