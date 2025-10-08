# 🚀 Render Deployment Guide - Angel One Market Data App

## 📋 Pre-Deployment Checklist

✅ **Complete Flask Application** (app.py)  
✅ **Responsive HTML Template** (templates/index.html)  
✅ **Python Dependencies** (requirements.txt)  
✅ **Runtime Configuration** (runtime.txt)  
✅ **Process Configuration** (Procfile)  
✅ **Environment Variables Setup**  
✅ **Angel One API Integration Tested**  

## 🎯 Render Deployment Steps

### 1. Create New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository or upload files

### 2. Basic Configuration

```
Service Name: angel-one-market-data
Runtime: Python 3
Region: Choose your preferred region
Branch: main (or your default branch)
```

### 3. Build & Deploy Settings

```
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

### 4. Environment Variables

Add these in Render's Environment Variables section:

```
API_KEY = tKo2xsA5
USERNAME = C125633  
PASSWORD = 4111
TOTP_TOKEN = TZZ2VTRBUWPB33SLOSA3NXSGWA
GOOGLE_CREDENTIALS = {"type":"service_account","project_id":"your-project"...}
```

**⚠️ Important for Google Sheets:**
1. **Enable TWO APIs** in Google Cloud Console:
   - **Google Sheets API**: https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=1016778665061
   - **Google Drive API**: https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=1016778665061
   - Both are required for the gspread library to work

2. **First run will show**: `❌ Failed to retrieve historical data` - This is normal!
   - No historical data exists yet on first deployment
   - Data will start accumulating after first refresh

3. **API Usage**: App makes ~6 API calls per refresh (Normal for batched data fetching)

### 5. Keep-Alive Service (For Historical Data)

Since Render free tier sleeps apps, add a keep-alive service to collect historical data:

#### Option A: UptimeRobot (Free)
1. Go to [UptimeRobot.com](https://uptimerobot.com)
2. Add HTTP(s) monitor: `https://your-app-name.onrender.com/api/refresh-data`
3. Set interval: 5 minutes
4. This keeps app awake + triggers data collection

#### Option B: GitHub Actions (Free)
1. Create `.github/workflows/keep-alive.yml`:
```yaml
name: Keep Alive
on:
  schedule:
    - cron: '*/5 * * * *'  # Every 5 minutes
jobs:
  keep-alive:
    runs-on: ubuntu-latest
    steps:
      - name: Ping app
        run: curl https://your-app-name.onrender.com/api/refresh-data
```

### 6. Advanced Settings

```
Python Version: 3.11.6 (specified in runtime.txt)
Auto-Deploy: Yes (recommended)
Health Check Path: /
```

## 📁 Required Files Structure

Ensure your repository has these files:

```
/
├── app.py                 # ✅ Main Flask application
├── templates/
│   └── index.html         # ✅ Complete dashboard
├── requirements.txt       # ✅ Python dependencies  
├── runtime.txt           # ✅ Python version
├── Procfile              # ✅ Deployment config
├── README.md             # ✅ Documentation
└── DEPLOYMENT_STATUS.md  # ✅ Status summary
```

## 🔧 File Contents Verification

### requirements.txt
```
Flask==2.3.3
gunicorn==21.2.0
requests==2.31.0
pyotp==2.9.0
python-dotenv==1.0.0
Werkzeug==2.3.7
```

### runtime.txt
```
python-3.11.6
```

### Procfile
```
web: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
```

## 🎯 Expected Deployment Results

Once deployed, your app will provide:

### 📊 **5 Interactive Tabs**
1. **📈 Futures Charts & Impact** - Historical ISS trends with Google Sheets
2. **Nifty 50 Stocks** - Real-time data for 50 stocks
3. **Bank Nifty Stocks** - 12 banking sector stocks  
4. **Nifty 50 Futures** - OCT 2025 futures contracts
5. **Bank Nifty Futures** - Banking futures contracts

### ⚡ **Key Features**
- **Historical Charts** - Google Sheets powered historical data
- **Auto-Refresh** - Every 5 minutes with keep-alive service
- **Institutional ISS** - Professional sentiment scoring (0-1 scale)
- **Live Data Refresh** - Click refresh for real-time updates
- **Interactive Tables** - Sort, filter, search functionality
- **Market Meters** - Live market summary metrics
- **Mobile Responsive** - Works on all devices
- **Real-time Pricing** - LTP, change %, volume data

### 🔄 **API Integration**
- **Angel One SmartAPI** - Live market data
- **JWT Authentication** - Secure token-based access
- **Rate Limiting** - 1 request per second compliance
- **Error Handling** - Graceful failure management

## 🌐 Post-Deployment Testing

### Test URLs (replace with your Render URL):
```
Homepage: https://your-app-name.onrender.com/
Nifty 50 API: https://your-app-name.onrender.com/api/nifty50
Bank Nifty API: https://your-app-name.onrender.com/api/banknifty
Nifty Futures API: https://your-app-name.onrender.com/api/niftyfutures
Bank Futures API: https://your-app-name.onrender.com/api/bankfutures
```

### Testing Checklist:
- [ ] Homepage loads with charts tab first
- [ ] Historical charts show data from Google Sheets  
- [ ] Click each tab to verify data loading
- [ ] Test refresh functionality
- [ ] Verify ISS institutional scoring working
- [ ] Check keep-alive service is pinging every 5 minutes
- [ ] Verify table sorting/filtering
- [ ] Check mobile responsiveness
- [ ] Confirm real-time data updates

## 🚨 Troubleshooting

### Common Issues & Solutions:

1. **Build Failed**: Check requirements.txt formatting
2. **App Won't Start**: Verify Procfile syntax
3. **No Data Loading**: Check environment variables
4. **API Errors**: Verify Angel One credentials

### Debug Steps:
1. Check Render deployment logs
2. Verify environment variables are set
3. Test API endpoints individually
4. Check Angel One API status

## 🎉 Success Indicators

✅ **Deployment Complete** when you see:
- Build succeeds without errors
- Service shows "Live" status
- Homepage loads with market data
- All 4 tabs function properly
- Real-time updates working

---

## 🔗 Quick Deploy Commands

If using Git:
```bash
git add .
git commit -m "Deploy Angel One Market Data App"
git push origin main
```

Then connect the repository to Render and deploy!

## 📞 Support

If you encounter issues:
1. Check Render deployment logs
2. Verify all environment variables
3. Test Angel One API credentials
4. Review this deployment guide

**Your complete market data webapp is ready for production! 🚀**