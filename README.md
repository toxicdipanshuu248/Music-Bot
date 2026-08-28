# DEV X CORE — Railway 24×7

Same music userbot (prefix `.`, same commands, same hardcoded tokens).
Railway Docker image includes **ffmpeg** + pinned `pyrogram==2.0.106` / `py-tgcalls==2.2.5`.

## Files

| File | Kaam |
|---|---|
| `music.py` | Poora bot (hardcoded API / token / owner) |
| `start.py` | Railway health check (`$PORT`) + bot start |
| `Dockerfile` | Python 3.11 + ffmpeg |
| `requirements.txt` | Pinned deps |
| `railway.toml` | Build/deploy |
| `Procfile` | Fallback start command |

Hardcoded (tumhari original values):

- `API_ID` = `31633970`
- `API_HASH` = original hash
- `BOT_TOKEN` = original bot token
- `OWNER_ID` = `5206554804`
- Prefix = `.`
- Volume default 100, auto-unmute ON, NC/play behaviour same

## Railway pe deploy (2 minute)

1. [railway.app](https://railway.app) pe login → **New Project** → **Empty Project**
2. **Add Service** → **GitHub Repo**  
   (pehle ye folder GitHub pe push karo)  
   **ya** Railway CLI:

```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

3. Service settings:
   - **Builder:** Dockerfile (railway.toml already set)
   - **Start:** `python start.py` (already set)

4. **Volume (zaroori — warna restart pe /login dubara)**  
   Service → **Variables / Volumes** → **Add Volume**  
   - Mount path: `/data`  
   - Size: 1–5 GB kaafi hai

5. Deploy. Logs me dikhega:

```
Health check listening on 0.0.0.0:PORT
DEV X CORE  v5.4  —  RAILWAY 24x7
✅ Login bot started: @YourBot
```

## Pehli baar login

1. Telegram pe apne **bot** ko `/start` bhejo
2. Owner account se `/login`
3. Phone `+91XXXXXXXXXX` → OTP → 2FA (agar hai)
4. Session `/data/session_string.txt` me save hota hai
5. Agli baar restart pe music bot **automatic** start

Group me voice chat start karo, user account ko **admin** banao, phir `.play kesariya`

## Commands (same)

- Music: `.play` `.nplay` `.run` `.vrun` `.voice` `.skip` `.pause` `.resume` `.stop`
- Sound: `.loud` `.gain` `.boost` `.eco` `.bass` `.treble` `.mix` `.max` `.volume`
- Loop: `.loop` `.repeat` `.rjoin` `.run 1,2,3`
- Hub: `.menu` `.help` `.alive` `.panel` `.files`
- Owner: `.admin` `.public` `.private` `.restart` `.backup`

## Optional env (zaroorat nahi)

Spotify keys chahiye ho to Railway Variables:

```
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

Baaki sab code me hardcoded hai — Variables me token daalne ki zaroorat nahi.

## GitHub push

```bash
git init
git add music.py start.py Dockerfile requirements.txt railway.toml Procfile README.md .gitignore .dockerignore
git commit -m "DEV X CORE railway"
git branch -M main
git remote add origin https://github.com/YOU/devx-core.git
git push -u origin main
```

Phir Railway → New Project → Deploy from GitHub.

## Notes

- Railway **Hobby** sleep kar sakta hai inactivity pe. 24×7 ke liye paid plan + volume rakho.
- Userbot Telegram ToS ke against ho sakta hai — account ban risk hai.
- Tokens is repo me hardcoded hain. Public GitHub pe mat daalna bina soch ke.
