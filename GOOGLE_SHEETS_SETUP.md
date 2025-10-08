# 📊 Google Sheets Historical Data Setup Guide

## 🎯 What This Achieves
Your Render app will:
1. ✅ Store historical ISS (Institutional Sentiment Score) data in Google Sheets
2. ✅ Plot real historical charts (not just current session)
3. ✅ Persist data across app restarts and deployments
4. ✅ Free 5 million cells storage limit

## 🪜 Setup Steps

### **STEP 1: Create Google Cloud Project**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select project" → "New Project"**
3. Name: `vinod-market-data`
4. Select the project from dropdown

### **STEP 2: Enable Required APIs**
1. Go to **APIs & Services → Library**
2. Search **"Google Sheets API"** → Click **Enable**
3. Search **"Google Drive API"** → Click **Enable** 
   ⚠️ **This is required for gspread library to work!**

### **STEP 3: Create Service Account**
1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → Service Account**
3. Name: `render-market-bot`
4. Click **Add Key → Create new key → JSON**
5. Download the JSON file (keep it safe!)

### **STEP 4: Create Google Sheet**
1. Go to [Google Sheets](https://sheets.google.com/)
2. Create new sheet named: **Vinod-Market-Data**
3. Click **Share** button
4. Add the service account email from your JSON file
5. Give **Editor** access
6. Click **Done**

### **STEP 5: Local Development Setup**
1. Copy your downloaded JSON file to project root as `credentials.json`
2. The app will automatically detect and use it

### **STEP 6: Render Deployment Setup**

#### Option A: Environment Variable (Recommended)
1. In Render Dashboard → Your Service → Environment
2. Add new variable:
   - **Name:** `GOOGLE_CREDENTIALS`
   - **Value:** Paste the entire JSON content (minified)

#### Option B: Secret Files
1. In Render Dashboard → Your Service → Settings
2. Add Secret File:
   - **Filename:** `credentials.json`
   - **Contents:** Paste your JSON content

## 🧪 Testing

### Local Test:
```bash
python app.py
# Check console for: "✅ Google Sheets integration enabled"
```

### After First Data Refresh:
1. Visit your Google Sheet
2. Should see headers: `Timestamp | IST_Time | Nifty_ISS | Bank_ISS | Nifty_Status | Bank_Status | Session`
3. New rows added every refresh

### Sample Data Format:
```
2025-10-08 14:30:15 | 14:30 | 0.652 | 0.734 | Mild Bullish | Strong Bullish | Afternoon
```

## 🎯 Features Enabled

### ✅ **Historical Persistence**
- Data survives app restarts
- No data loss during Render deployments
- 24+ hours of historical data available

### ✅ **Smart Fallback**
- Uses Google Sheets when available
- Falls back to in-memory storage if needed
- Graceful error handling

### ✅ **Session Tracking**
- Morning (9-12), Afternoon (12-15), Closing (15-16), After Hours
- Easy to analyze market patterns by time

### ✅ **Professional Logging**
- Console shows save/retrieve operations
- Debug info about data source used
- Error handling with clear messages

## 🚨 Troubleshooting

### "Google Sheets disabled: credentials.json not found"
- ✅ Add credentials.json file or GOOGLE_CREDENTIALS env var

### "Permission denied" errors
- ✅ Check service account has Editor access to the sheet
- ✅ Verify sheet name matches exactly: "Vinod-Market-Data"

### "Spreadsheet not found"
- ✅ App will auto-create the sheet on first run
- ✅ Make sure service account has Drive access

## 💡 Pro Tips

1. **Monitor Usage:** Google Sheets shows last edit time
2. **Export Backup:** Download as CSV periodically
3. **Multiple Sheets:** Can create separate sheets for different timeframes
4. **Public Charts:** Share sheet publicly for external chart embedding

## 🎉 Success Indicators

✅ Console shows: "📊 Historical data saved: [timestamp]"
✅ Console shows: "📈 Retrieved X historical data points"  
✅ Charts plot actual historical data (not just current session)
✅ Data persists between app restarts

Your historical data is now enterprise-grade! 🚀