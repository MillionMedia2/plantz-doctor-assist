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
├── public/
│   ├── index.html           # Main chat UI HTML
│   ├── chatinterface.css    # Main stylesheet for chat UI (used by index.html)
│   └── chatbot.js           # All chat UI and streaming logic
├── api/
│   └── main.py              # FastAPI backend, OpenAI integration
├── requirements.txt         # Python dependencies
├── vercel.json              # Vercel deployment config
├── README.md                # This file
└── .gitignore
```

## Backend (FastAPI)
- **File:** `api/main.py`
- **Endpoints:**
  - `POST /api/chat` receives user messages, manages per-user sessions (via cookies), maps each session to an OpenAI thread, adds the user message, and streams the assistant's response as JSON lines (SSE).
- **Session Management:**
  - Uses a cookie (`doctor_assist_session`) to track users.
  - Each session is mapped to a unique OpenAI thread for memory.
- **OpenAI Integration:**
  - Uses the OpenAI Python SDK (Assistants API).
  - Streams responses chunk-by-chunk to the frontend.
- **Static Files (Local Only):**
  - When running locally, FastAPI serves static files from `/public`.
  - On Vercel, static files are served directly by Vercel, not FastAPI.

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
  - **Prevents unnecessary scrollbars when embedded in an iframe.**

## Preventing Unnecessary Scrollbars in iframes
When embedding the chatbot in an `<iframe>` (e.g., in WordPress), you may see an extra vertical scrollbar inside the iframe. To prevent this, add the following CSS to your `chatinterface.css`:

```css
html, body {
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden; /* Prevents scrollbars on the iframe content */
}

.chatContainer {
  height: 100vh;
  box-sizing: border-box;
  overflow: auto; /* Only scrolls if content actually overflows */
}
```

This ensures the chatbot fills the iframe and only shows a scrollbar if the content truly overflows.

## Chatbot Flow
1. User opens the page (`index.html` loads, with `chatinterface.css` and `chatbot.js`).
2. User sends a message (form submit or Enter key).
3. `chatbot.js` shows the thinking indicator, sends the message to `/api/chat`, and streams the response.
4. Backend adds the message to the user's OpenAI thread, starts a run, and streams the response as JSON lines.
5. Frontend parses each chunk, displays the assistant's response in real time, and hides the thinking indicator right before the response appears.
6. All UI is styled by `chatinterface.css`.

## Deploy on Vercel (Lessons Learned)
- **Static files must be in `/public` at the project root.**
- **Backend (FastAPI) must be in `/api/main.py` for Vercel to recognize it as a Python serverless function.**
- **Do not use a `builds` array in `vercel.json` unless you know how to manually copy static files to the output.**
- **vercel.json example:**
  ```json
  {
    "version": 2,
    "routes": [
      { "src": "/api/(.*)", "dest": "/api/main.py" }
    ]
  }
  ```
- **No root endpoint in FastAPI.** Let static files be served by Vercel in production, and by FastAPI only for local development.
- **All static file references in HTML must be `/filename` (not `/public/filename`).**
- **To run locally:**
  - From the project root, run: `uvicorn api.main:app --reload`
  - Visit [http://localhost:8000/](http://localhost:8000/)
- **To deploy:**
  - Push to GitHub. Vercel will serve static files from `/public` and route `/api/chat` to your backend.

## Embedding
- Use an `<iframe src="https://your-vercel-app.vercel.app/" ...>` to embed the chatbot anywhere.

---

## Deployment Prompt for Future Projects

> **Prompt:**
> I am building a Python (FastAPI) backend with a static HTML/CSS/JS frontend and want to deploy on Vercel. Make sure:
> - All static files are in `/public` at the project root.
> - The backend is in `/api/main.py` (or `/api/yourfile.py`) so Vercel recognizes it as a Python serverless function.
> - `vercel.json` does NOT use a `builds` array—only `routes`.
> - All static file references in HTML are `/filename` (not `/public/filename`).
> - No root endpoint in FastAPI; let static files be served by Vercel in production, and by FastAPI only for local development.
> - To run locally, mount static files from `/public` and run from the project root.
> - To deploy, just push to GitHub and let Vercel handle static and API routing.
> - If you see 404s for static files on Vercel, check that you are not using a `builds` array and that your static files are in `/public`.

---

**For any changes to the chat UI, always edit `chatinterface.css`.**

If you need to update the thinking indicator, chat streaming, or styling, see the relevant files in `public/`. 