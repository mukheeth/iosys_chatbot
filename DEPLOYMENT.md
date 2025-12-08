# Deployment Guide

## Problem
Your frontend on Netlify is trying to connect to `localhost:5000`, which doesn't exist in production. The backend needs to be deployed to a cloud service.

## Solution: Deploy Backend to Render

### Step 1: Deploy Backend to Render

1. **Create a Render Account**
   - Go to [render.com](https://render.com)
   - Sign up/login with GitHub

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the `chatbots` repository

3. **Configure Render Service**
   - **Name**: `iosys-chatbot-backend` (or any name)
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free tier is fine to start

4. **Set Environment Variables in Render**
   Go to your service → Environment → Add these variables:
   
   ```
   GROQ_API_KEY=your_groq_api_key_here
   HUGGINGFACE_API_KEY=your_huggingface_api_key_here
   SENDER_EMAIL=your-email@example.com
   SENDER_PASSWORD=your-app-password
   COMPANY_EMAIL=recipient@example.com
   EMAIL_PROVIDER=gmail
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   PORT=10000
   ```

5. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy your backend
   - Wait for deployment to complete (~5-10 minutes)
   - Copy your backend URL (e.g., `https://iosys-chatbot-backend.onrender.com`)

### Step 2: Configure Frontend on Netlify

1. **Go to Netlify Dashboard**
   - Open your site settings
   - Navigate to "Site settings" → "Environment variables"

2. **Add Environment Variable**
   - Click "Add variable"
   - **Key**: `REACT_APP_API_URL`
   - **Value**: `https://your-backend-url.onrender.com/api`
   - Replace `your-backend-url.onrender.com` with your actual Render backend URL

3. **Redeploy Frontend**
   - Go to "Deploys" tab
   - Click "Trigger deploy" → "Deploy site"
   - Or push a new commit to trigger auto-deploy

### Step 3: Verify Connection

1. **Check Backend Health**
   - Visit: `https://your-backend-url.onrender.com/api/health`
   - Should return: `{"status": "healthy"}`

2. **Test Frontend**
   - Visit your Netlify site
   - The error should be gone
   - Try sending a message

## Alternative: Railway Deployment

If Render doesn't work, try Railway:

1. **Go to [railway.app](https://railway.app)**
2. **Create New Project** → "Deploy from GitHub"
3. **Select Repository** → Choose `chatbots`
4. **Configure**:
   - Root Directory: `backend`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. **Add Environment Variables** (same as Render)
6. **Get Backend URL** and update Netlify `REACT_APP_API_URL`

## Troubleshooting

### Backend Not Starting
- Check Render logs for errors
- Verify all environment variables are set
- Ensure `gunicorn` is in `requirements.txt` ✅ (already there)

### CORS Errors
- Backend already has `CORS(app)` configured ✅
- Should work automatically

### Frontend Still Shows Error
- Clear Netlify cache: "Deploys" → "Trigger deploy" → "Clear cache and deploy site"
- Verify `REACT_APP_API_URL` is set correctly in Netlify
- Check browser console for actual error messages

### Backend Timeout (Free Tier)
- Render free tier spins down after 15 minutes of inactivity
- First request after spin-down takes ~30 seconds
- Consider upgrading to paid plan for always-on service

## Quick Checklist

- [ ] Backend deployed to Render/Railway
- [ ] Backend URL copied (e.g., `https://xxx.onrender.com`)
- [ ] `REACT_APP_API_URL` set in Netlify environment variables
- [ ] Frontend redeployed on Netlify
- [ ] Backend health check works (`/api/health`)
- [ ] Frontend can connect to backend

