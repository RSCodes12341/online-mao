# Deploying Online Mao

Two free-tier services: **Render** for the backend (Python/FastAPI/WebSocket) and **Vercel** for the frontend (Vite/React). Both have free tiers that require no credit card.

---

## 1  Push your code to GitHub

If you haven't already:

```bash
cd /Users/ronithbalusani/Documents/online-mao
git init          # if not already a repo
git add .
git commit -m "Initial commit"
```

Create a **new repository** on github.com (no README, no .gitignore), then:

```bash
git remote add origin https://github.com/<your-username>/online-mao.git
git branch -M main
git push -u origin main
```

---

## 2  Deploy the backend on Render

1. Go to [render.com](https://render.com) → **Sign up** (free, no card).
2. Click **New +** → **Web Service**.
3. Connect your GitHub account and choose the `online-mao` repo.
4. Fill in the settings:

   | Field | Value |
   |---|---|
   | **Name** | `online-mao-backend` (or anything) |
   | **Root Directory** | `backend` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | **Instance Type** | **Free** |

5. Under **Environment Variables**, add:

   | Key | Value |
   |---|---|
   | `CORS_ORIGIN` | *(leave blank for now — you'll fill this in after the frontend is deployed)* |

6. Click **Create Web Service**. Render builds and starts the server. Watch the logs.  
   Your backend URL will be something like `https://online-mao-backend.onrender.com`.

> **Note on free-tier cold starts:** Render's free plan spins down idle services after ~15 minutes. The first request after a sleep takes ~30 seconds to wake up. Players will simply see "Connecting…" briefly.

---

## 3  Deploy the frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **Sign up** with GitHub (free).
2. Click **Add New… → Project** and import your `online-mao` repo.
3. Vercel auto-detects Vite. Set:

   | Field | Value |
   |---|---|
   | **Root Directory** | `frontend` |
   | **Framework Preset** | Vite (auto-detected) |
   | **Build Command** | `npm run build` |
   | **Output Directory** | `dist` |

4. Under **Environment Variables**, add:

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | `https://online-mao-backend.onrender.com` (your Render URL, **no trailing slash**) |

5. Click **Deploy**. Vercel builds and gives you a URL like `https://online-mao.vercel.app`.

---

## 4  Wire up CORS on the backend

Now that you have the Vercel URL, go back to Render:

1. Open your backend service → **Environment** tab.
2. Set `CORS_ORIGIN` to your Vercel URL, e.g. `https://online-mao.vercel.app`.
3. Click **Save Changes** — Render redeploys automatically.

If you ever add a custom domain, add it to `CORS_ORIGIN` as a comma-separated second value:  
`https://online-mao.vercel.app,https://mao.yourdomain.com`

---

## 5  Smoke-test the live deployment

Open your Vercel URL in a browser:

1. Create a room — you should see a 4-letter code and be taken to the lobby.
2. Open an incognito tab, go to the same URL, join with the room code.
3. Both tabs should show each other in the lobby.
4. Start the game and play a card.

If cards aren't appearing, open DevTools → Network → WS and check that the WebSocket connected to `wss://online-mao-backend.onrender.com/ws/...`.

---

## 6  Inviting friends to a room

Once you're live, sharing a game is two pieces of info:

1. **The site URL** — your Vercel URL, e.g. `https://online-mao.vercel.app`  
   Send this to everyone before the session.

2. **The room code** — generated when you click "Create Room".  
   Share it in a group chat / Discord / wherever you're coordinating.

Friends open the site URL, click "Join Room", type their name and the 4-letter code, and they're in.

---

## Local development

```bash
# Terminal 1 — backend
cd backend
source venv/bin/activate
uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Frontend dev server runs on `http://localhost:5173` and talks to the backend on `http://localhost:8000` by default (no `.env.local` needed).

To point your local frontend at the production backend (useful for debugging):

```bash
# frontend/.env.local
VITE_API_URL=https://online-mao-backend.onrender.com
```
