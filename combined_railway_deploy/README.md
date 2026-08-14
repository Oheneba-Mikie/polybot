# 🚀 Combined Guard Rail Bot — Cloud Deployment Package

This package contains everything needed to deploy the **Combined Guard Rail Bot** to **Railway**, **Render**, or any cloud host.

---

## 📁 Package Contents

- `app.py`: Core trading engine & Flask web dashboard backend.
- `templates/dashboard.html`: Real-time dark-mode web monitoring dashboard.
- `Procfile`: Gunicorn deployment launcher for Railway/Render.
- `requirements.txt`: Python package dependencies.

---

## ⚡ Step-by-Step Railway Deployment Guide

### Step 1: Push folder to GitHub
1. Create a new GitHub repository (e.g. `combined-polybot`).
2. Push all files inside `combined_railway_deploy/` to your GitHub repo.

### Step 2: Deploy on Railway
1. Log in to [Railway.app](https://railway.app).
2. Click **New Project** → **Deploy from GitHub Repo**.
3. Select your repository.

### Step 3: Set Environment Variables on Railway
In Railway under **Variables**, add the following keys from your `.env`:

| Key | Example Value | Required |
|---|---|---|
| `POLYMARKET_ADDRESS` | `0xYourProxyOrEOAAddress` | Yes |
| `POLYMARKET_API_KEY` | `your-api-key` | Yes |
| `POLYMARKET_API_SECRET` | `your-api-secret` | Yes |
| `POLYMARKET_API_PASSPHRASE` | `your-api-passphrase` | Yes |
| `POLYMARKET_PRIVATE_KEY` | `0xYourPrivateKey` | Yes |
| `POLYMARKET_LIVE_TRADING` | `true` | Yes |
| `DOUBLE_STAKE` | `true` (or `false` for single) | Yes |
| `STARTING_STAKE_USD` | `1.00` | Yes |
| `CONFIDENCE_THRESHOLD` | `0.85` | Yes |
| `MIN_SAFE_BTC_GAP` | `5.00` | Yes |
| `T2_MIN_BTC_GAP` | `2.00` | Yes |

---

## 📊 Live Web Dashboard Features

Once deployed, Railway will generate a public URL (e.g. `https://combined-polybot.up.railway.app`). Opening this URL shows:
- **Live Wallet Balance** (USDC on Polygon)
- **Current Stake & Mode** (Single vs Double Stake)
- **Win Streaks & Total P&L**
- **Protected Count** (Number of risky windows saved by Guard Rails)
- **Real-Time Terminal Output**
