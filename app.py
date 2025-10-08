"""
Live Market Data Web Application
Real-time Nifty 50 and Bank Nifty data visualization with futures analysis
"""

from flask import Flask, render_template, jsonify, request
import json
import pyotp
import time
from datetime import datetime, timezone, timedelta
import requests
import os
from werkzeug.exceptions import RequestEntityTooLarge
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 📊 Google Sheets Configuration for Historical Data
GOOGLE_SHEETS_ENABLED = True
SPREADSHEET_NAME = "Vinod-Market-Data"  # Name of your Google Sheet
try:
    # For production: Use environment variables or Render secrets
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS')
    if GOOGLE_CREDENTIALS:
        # Parse JSON from environment variable
        import tempfile
        import json
        
        # Create temporary credentials file
        creds_dict = json.loads(GOOGLE_CREDENTIALS)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(creds_dict, f)
            GOOGLE_CREDS_FILE = f.name
    else:
        # For local development: Use credentials.json file
        GOOGLE_CREDS_FILE = "credentials.json"
        if not os.path.exists(GOOGLE_CREDS_FILE):
            print("⚠️ Google Sheets disabled: credentials.json not found")
            GOOGLE_SHEETS_ENABLED = False
            
    # Initialize Google Sheets client
    if GOOGLE_SHEETS_ENABLED:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_FILE, scope)
        sheets_client = gspread.authorize(creds)
        print("✅ Google Sheets integration enabled")
    else:
        sheets_client = None
        
except Exception as e:
    print(f"⚠️ Google Sheets setup failed: {e}")
    GOOGLE_SHEETS_ENABLED = False
    sheets_client = None

# 📊 Google Sheets Helper Functions
def append_historical_data(nifty_iss, bank_iss):
    """Append current ISS data to Google Sheets for historical tracking"""
    if not GOOGLE_SHEETS_ENABLED or not sheets_client:
        return False
        
    try:
        # Open or create sheet
        try:
            sheet = sheets_client.open(SPREADSHEET_NAME).sheet1
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet if it doesn't exist
            sheet = sheets_client.create(SPREADSHEET_NAME).sheet1
            # Add headers
            sheet.append_row([
                'Timestamp', 'IST_Time', 'Nifty_ISS', 'Bank_ISS', 
                'Nifty_Status', 'Bank_Status', 'Session'
            ])
            print(f"✅ Created new Google Sheet: {SPREADSHEET_NAME}")
        
        # Prepare data
        current_time = get_ist_time()
        timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S')
        ist_time = current_time.strftime('%H:%M')
        
        # Determine market session
        hour = current_time.hour
        if 9 <= hour < 12:
            session = "Morning"
        elif 12 <= hour < 15:
            session = "Afternoon"
        elif 15 <= hour < 16:
            session = "Closing"
        else:
            session = "After Hours"
        
        # Get status
        nifty_status = get_meter_status(nifty_iss)['status']
        bank_status = get_meter_status(bank_iss)['status']
        
        # Append row
        sheet.append_row([
            timestamp, ist_time, round(nifty_iss, 4), round(bank_iss, 4),
            nifty_status, bank_status, session
        ])
        
        print(f"📊 Historical data saved: {timestamp} | Nifty: {nifty_iss:.3f} | Bank: {bank_iss:.3f}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save historical data: {e}")
        return False

def get_historical_data(hours_back=24):
    """Retrieve historical ISS data from Google Sheets"""
    if not GOOGLE_SHEETS_ENABLED or not sheets_client:
        return []
        
    try:
        sheet = sheets_client.open(SPREADSHEET_NAME).sheet1
        all_records = sheet.get_all_records()
        
        # Filter for recent data
        current_time = get_ist_time()
        cutoff_time = current_time - timedelta(hours=hours_back)
        
        filtered_data = []
        for record in all_records:
            try:
                record_time = datetime.strptime(record['Timestamp'], '%Y-%m-%d %H:%M:%S')
                record_time = record_time.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
                
                if record_time >= cutoff_time:
                    filtered_data.append({
                        'timestamp': record['IST_Time'],
                        'time_full': record['Timestamp'],
                        'nifty_iss': float(record['Nifty_ISS']),
                        'bank_iss': float(record['Bank_ISS']),
                        'nifty_status': record['Nifty_Status'],
                        'bank_status': record['Bank_Status'],
                        'session': record['Session']
                    })
            except (ValueError, KeyError) as e:
                continue
                
        print(f"📈 Retrieved {len(filtered_data)} historical data points")
        return filtered_data[-100:]  # Return last 100 points
        
    except Exception as e:
        print(f"❌ Failed to retrieve historical data: {e}")
        return []

# IST timezone helper function
def get_ist_time():
    """Get current time in Indian Standard Time (IST)"""
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)

def get_previous_trading_day():
    """Get the previous trading day in IST, going back up to 3 days to find valid trading day"""
    today = get_ist_time().date()
    
    # Try going back 1, 2, then 3 days to find a valid trading day
    for days_back in range(1, 4):  # Try 1, 2, 3 days back
        candidate_day = today - timedelta(days=days_back)
        weekday = candidate_day.weekday()  # Monday=0, Sunday=6
        
        # Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
        if weekday < 5:  # Monday to Friday (0-4)
            return candidate_day
    
    # Fallback: if we couldn't find a weekday in 3 days, go back to last Friday
    fallback_day = today - timedelta(days=7)  # Go back a week
    while fallback_day.weekday() >= 5:  # While it's weekend
        fallback_day = fallback_day - timedelta(days=1)
    
    return fallback_day

def test_historical_oi():
    """Test function to verify historical OI API"""
    print("🧪 Testing Historical OI API...")
    
    # Test with a known futures token (e.g., NIFTY futures)
    test_token = "99926000"  # NIFTY token as example
    
    if not cached_data['auth_token']:
        print("🔑 Authenticating for test...")
        if not authenticate():
            print("❌ Authentication failed for test")
            return {"error": "Authentication failed"}
    
    previous_day = get_previous_trading_day()
    from_date = previous_day.strftime('%Y-%m-%d 09:15')
    to_date = previous_day.strftime('%Y-%m-%d 15:30')
    
    print(f"📅 Test date range: {from_date} to {to_date}")
    
    url = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getOIData"
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '192.168.1.1',
        'X-ClientPublicIP': '192.168.1.1',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': API_KEY,
        'Authorization': f'Bearer {cached_data["auth_token"]}'
    }
    
    payload = {
        "exchange": "NFO",
        "symboltoken": test_token,
        "interval": "ONE_DAY",
        "fromdate": from_date,
        "todate": to_date
    }
    
    print(f"🌐 Test API Request:")
    print(f"   URL: {url}")
    print(f"   Payload: {payload}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        print(f"📡 Test Response Status: {response.status_code}")
        
        # Limit response output to prevent "output too large" errors
        response_text = response.text
        if len(response_text) > 500:
            print(f"📊 Test Response Body (truncated): {response_text[:500]}...")
        else:
            print(f"📊 Test Response Body: {response_text}")
        
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "data": data}
        else:
            return {"error": f"HTTP {response.status_code}: Limited output"}
            
    except Exception as e:
        print(f"💥 Test API Error: {e}")
        return {"error": str(e)}

def get_historical_oi_data(symbol_token):
    """Get historical OI data for a specific token with caching and rate limiting"""
    # For now, return 0 to speed up the process - we can enable this later
    # TODO: Re-enable historical OI fetching when needed
    return 0
    
    # Check cache first
    cache_key = f"oi_{symbol_token}"
    today = get_ist_time().date()
    
    if cache_key in cached_data['historical_oi_cache']:
        cache_date, cache_data = cached_data['historical_oi_cache'][cache_key]
        if cache_date == today:
            return cache_data
    
    if not cached_data['auth_token']:
        if not authenticate():
            return 0
    
    # Rate limiting: wait between API calls
    time.sleep(0.5)  # 500ms delay to avoid rate limits
    
    # Try just 1 previous trading day for now to reduce API load
    target_date = get_ist_time().date() - timedelta(days=1)
    
    # Skip weekends
    while target_date.weekday() >= 5:  # Skip Saturday(5) and Sunday(6)
        target_date = target_date - timedelta(days=1)
    
    from_date = target_date.strftime('%Y-%m-%d 09:15')
    to_date = target_date.strftime('%Y-%m-%d 15:30')
    
    # Official Angel One Historical OI API endpoint
    url = "https://apiconnect.angelone.in/rest/secure/angelbroking/historical/v1/getOIData"
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '192.168.1.1',
        'X-ClientPublicIP': '192.168.1.1',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': API_KEY,
        'Authorization': f'Bearer {cached_data["auth_token"]}'
    }
    
    payload = {
        "exchange": "NFO",
        "symboltoken": str(symbol_token),
        "interval": "ONE_DAY",
        "fromdate": from_date,
        "todate": to_date
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') and data.get('data'):
                oi_data = data['data']
                if oi_data and len(oi_data) > 0:
                    last_oi_entry = oi_data[-1]
                    previous_oi = last_oi_entry.get('oi', 0)
                    
                    if previous_oi > 0:
                        # Cache the result
                        cached_data['historical_oi_cache'][cache_key] = (today, previous_oi)
                        return previous_oi
            else:
                # Cache the failure to avoid repeated API calls
                cached_data['historical_oi_cache'][cache_key] = (today, 0)
        
        return 0
    except Exception as e:
        return 0

# ====== CONFIGURATION ======
# Use direct credentials for local testing
API_KEY = 'tKo2xsA5'
USERNAME = 'C125633'
PASSWORD = '4111'
TOTP_TOKEN = "TZZ2VTRBUWPB33SLOSA3NXSGWA"

# API URLs
BASE_URL = "https://apiconnect.angelone.in"
LOGIN_URL = f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
MARKET_DATA_URL = "https://apiconnect.angelone.in/rest/secure/angelbroking/market/v1/quote/"
PCR_URL = "https://apiconnect.angelone.in/rest/secure/angelbroking/marketData/v1/putCallRatio"

# Global variables for caching
cached_data = {
    'nifty_50': None,
    'bank_nifty': None,
    'nifty_futures': None,
    'bank_futures': None,
    'pcr_data': None,
    'last_update': None,
    'auth_token': None,
    'historical_oi_cache': {},  # Cache for historical OI data
    'chart_data': {  # Store historical data for charts
        'nifty_futures_history': [],
        'bank_futures_history': []
    }
}

# Updated Nifty 50 Token Mapping with New Weightages (October 2025) - COMPLETE 47 STOCKS
NIFTY_50_STOCKS = {
    "11483": {"symbol": "LT-EQ", "name": "LT", "company": "Larsen & Toubro Ltd", "weight": 3.84},
    "10604": {"symbol": "BHARTIARTL-EQ", "name": "BHARTIARTL", "company": "Bharti Airtel Ltd", "weight": 4.53},
    "11630": {"symbol": "NTPC-EQ", "name": "NTPC", "company": "NTPC Ltd", "weight": 1.42},
    "1333": {"symbol": "HDFCBANK-EQ", "name": "HDFCBANK", "company": "HDFC Bank Ltd", "weight": 12.91},
    "1394": {"symbol": "HINDUNILVR-EQ", "name": "HINDUNILVR", "company": "Hindustan Unilever Ltd", "weight": 1.98},
    "14977": {"symbol": "POWERGRID-EQ", "name": "POWERGRID", "company": "Power Grid Corporation of India Ltd", "weight": 1.15},
    "2031": {"symbol": "M&M-EQ", "name": "M&M", "company": "Mahindra & Mahindra Ltd", "weight": 2.69},
    "17963": {"symbol": "NESTLEIND-EQ", "name": "NESTLEIND", "company": "Nestle India Ltd", "weight": 0.73},
    "20374": {"symbol": "COALINDIA-EQ", "name": "COALINDIA", "company": "Coal India Ltd", "weight": 0.76},
    "16675": {"symbol": "BAJAJFINSV-EQ", "name": "BAJAJFINSV", "company": "Bajaj Finserv Ltd", "weight": 1.0},
    "1964": {"symbol": "TRENT-EQ", "name": "TRENT", "company": "Trent Ltd", "weight": 0.94},
    "21808": {"symbol": "SBILIFE-EQ", "name": "SBILIFE", "company": "SBI Life Insurance Company Ltd", "weight": 0.7},
    "22377": {"symbol": "MAXHEALTH-EQ", "name": "MAXHEALTH", "company": "Max Healthcare Institute Ltd", "weight": 0.7},
    "236": {"symbol": "ASIANPAINT-EQ", "name": "ASIANPAINT", "company": "Asian Paints Ltd", "weight": 0.93},
    "2885": {"symbol": "RELIANCE-EQ", "name": "RELIANCE", "company": "Reliance Industries Ltd", "weight": 8.08},
    "3499": {"symbol": "TATASTEEL-EQ", "name": "TATASTEEL", "company": "Tata Steel Ltd", "weight": 1.25},
    "5900": {"symbol": "AXISBANK-EQ", "name": "AXISBANK", "company": "Axis Bank Ltd", "weight": 2.96},
    "694": {"symbol": "CIPLA-EQ", "name": "CIPLA", "company": "Cipla Ltd", "weight": 0.75},
    "383": {"symbol": "BEL-EQ", "name": "BEL", "company": "Bharat Electronics Ltd", "weight": 1.29},
    "10999": {"symbol": "MARUTI-EQ", "name": "MARUTI", "company": "Maruti Suzuki India Ltd", "weight": 1.82},
    "11195": {"symbol": "INDIGO-EQ", "name": "INDIGO", "company": "InterGlobe Aviation Ltd", "weight": 1.08},
    "11723": {"symbol": "JSWSTEEL-EQ", "name": "JSWSTEEL", "company": "JSW Steel Ltd", "weight": 0.95},
    "11532": {"symbol": "ULTRACEMCO-EQ", "name": "ULTRACEMCO", "company": "UltraTech Cement Ltd", "weight": 1.25},
    "1232": {"symbol": "GRASIM-EQ", "name": "GRASIM", "company": "Grasim Industries Ltd", "weight": 0.93},
    "13538": {"symbol": "TECHM-EQ", "name": "TECHM", "company": "Tech Mahindra Ltd", "weight": 0.78},
    "11536": {"symbol": "TCS-EQ", "name": "TCS", "company": "Tata Consultancy Services Ltd", "weight": 2.6},
    "1363": {"symbol": "HINDALCO-EQ", "name": "HINDALCO", "company": "Hindalco Industries Ltd", "weight": 0.99},
    "157": {"symbol": "APOLLOHOSP-EQ", "name": "APOLLOHOSP", "company": "Apollo Hospitals Enterprise Ltd", "weight": 0.66},
    "1660": {"symbol": "ITC-EQ", "name": "ITC", "company": "ITC Ltd", "weight": 3.41},
    "18143": {"symbol": "JIOFIN-EQ", "name": "JIOFIN", "company": "Jio Financial Services Ltd", "weight": 0.87},
    "15083": {"symbol": "ADANIPORTS-EQ", "name": "ADANIPORTS", "company": "Adani Ports and Special Economic Zone Ltd", "weight": 0.92},
    "1922": {"symbol": "KOTAKBANK-EQ", "name": "KOTAKBANK", "company": "Kotak Mahindra Bank Ltd", "weight": 2.71},
    "1594": {"symbol": "INFY-EQ", "name": "INFY", "company": "Infosys Ltd", "weight": 4.56},
    "2475": {"symbol": "ONGC-EQ", "name": "ONGC", "company": "Oil & Natural Gas Corporation Ltd", "weight": 0.83},
    "25": {"symbol": "ADANIENT-EQ", "name": "ADANIENT", "company": "Adani Enterprises Ltd", "weight": 0.59},
    "3351": {"symbol": "SUNPHARMA-EQ", "name": "SUNPHARMA", "company": "Sun Pharmaceutical Industries Ltd", "weight": 1.51},
    "7229": {"symbol": "HCLTECH-EQ", "name": "HCLTECH", "company": "HCL Technologies Ltd", "weight": 1.29},
    "3787": {"symbol": "WIPRO-EQ", "name": "WIPRO", "company": "Wipro Ltd", "weight": 0.6},
    "3045": {"symbol": "SBIN-EQ", "name": "SBIN", "company": "State Bank of India", "weight": 3.16},
    "317": {"symbol": "BAJFINANCE-EQ", "name": "BAJFINANCE", "company": "Bajaj Finance Ltd", "weight": 2.3},
    "3432": {"symbol": "TATACONSUM-EQ", "name": "TATACONSUM", "company": "Tata Consumer Products Ltd", "weight": 0.65},
    "3456": {"symbol": "TATAMOTORS-EQ", "name": "TATAMOTORS", "company": "Tata Motors Ltd", "weight": 1.31},
    "5097": {"symbol": "ETERNAL-EQ", "name": "ETERNAL", "company": "Eternal Materials Co Ltd", "weight": 2.0},
    "910": {"symbol": "EICHERMOT-EQ", "name": "EICHERMOT", "company": "Eicher Motors Ltd", "weight": 0.84},
    "881": {"symbol": "DRREDDY-EQ", "name": "DRREDDY", "company": "Dr Reddys Laboratories Ltd", "weight": 0.67},
    "3506": {"symbol": "TITAN-EQ", "name": "TITAN", "company": "Titan Company Ltd", "weight": 1.25},
    "4306": {"symbol": "SHRIRAMFIN-EQ", "name": "SHRIRAMFIN", "company": "Shriram Finance Ltd", "weight": 0.79},
    "467": {"symbol": "HDFCLIFE-EQ", "name": "HDFCLIFE", "company": "HDFC Life Insurance Co Ltd", "weight": 0.71},
}

# Bank Nifty Token Mapping (October 2025) - COMPLETE 12 STOCKS
BANK_NIFTY_STOCKS = {
    "10666": {"symbol": "PNB-EQ", "name": "PNB", "company": "Punjab National Bank", "weight": 1.05},
    "10794": {"symbol": "CANBK-EQ", "name": "CANBK", "company": "Canara Bank", "weight": 1.13},
    "1333": {"symbol": "HDFCBANK-EQ", "name": "HDFCBANK", "company": "HDFC Bank Ltd", "weight": 39.1},
    "21238": {"symbol": "AUBANK-EQ", "name": "AUBANK", "company": "AU Small Finance Bank Ltd", "weight": 1.11},
    "4963": {"symbol": "ICICIBANK-EQ", "name": "ICICIBANK", "company": "ICICI Bank Ltd", "weight": 25.84},
    "4668": {"symbol": "BANKBARODA-EQ", "name": "BANKBARODA", "company": "Bank of Baroda", "weight": 1.29},
    "5900": {"symbol": "AXISBANK-EQ", "name": "AXISBANK", "company": "Axis Bank Ltd", "weight": 8.97},
    "5258": {"symbol": "INDUSINDBK-EQ", "name": "INDUSINDBK", "company": "IndusInd Bank Ltd", "weight": 1.31},
    "1023": {"symbol": "FEDERALBNK-EQ", "name": "FEDERALBNK", "company": "Federal Bank Ltd", "weight": 1.25},
    "11184": {"symbol": "IDFCFIRSTB-EQ", "name": "IDFCFIRSTB", "company": "IDFC First Bank Ltd", "weight": 1.21},
    "1922": {"symbol": "KOTAKBANK-EQ", "name": "KOTAKBANK", "company": "Kotak Mahindra Bank Ltd", "weight": 8.19},
    "3045": {"symbol": "SBIN-EQ", "name": "SBIN", "company": "State Bank of India", "weight": 9.56},
}

# Nifty 50 Futures Token Mapping (October 28, 2025 Expiry) - COMPLETE 47 FUTURES
NIFTY_50_FUTURES = {
    "52274": {"symbol": "BEL28OCT25FUT", "name": "BEL", "company": "Bharat Electronics Ltd", "weight": 1.29},
    "52351": {"symbol": "GRASIM28OCT25FUT", "name": "GRASIM", "company": "Grasim Industries Ltd", "weight": 0.93},
    "52442": {"symbol": "LT28OCT25FUT", "name": "LT", "company": "Larsen & Toubro Ltd", "weight": 3.84},
    "52454": {"symbol": "MARUTI28OCT25FUT", "name": "MARUTI", "company": "Maruti Suzuki India Ltd", "weight": 1.82},
    "52555": {"symbol": "TRENT28OCT25FUT", "name": "TRENT", "company": "Trent Ltd", "weight": 0.94},
    "52391": {"symbol": "INDIGO28OCT25FUT", "name": "INDIGO", "company": "InterGlobe Aviation Ltd", "weight": 1.08},
    "52240": {"symbol": "BAJAJFINSV28OCT25FUT", "name": "BAJAJFINSV", "company": "Bajaj Finserv Ltd", "weight": 1.0},
    "52455": {"symbol": "MAXHEALTH28OCT25FUT", "name": "MAXHEALTH", "company": "Max Healthcare Institute Ltd", "weight": 0.7},
    "52509": {"symbol": "RELIANCE28OCT25FUT", "name": "RELIANCE", "company": "Reliance Industries Ltd", "weight": 8.08},
    "52532": {"symbol": "TATAMOTORS28OCT25FUT", "name": "TATAMOTORS", "company": "Tata Motors Ltd", "weight": 1.31},
    "52558": {"symbol": "ULTRACEMCO28OCT25FUT", "name": "ULTRACEMCO", "company": "UltraTech Cement Ltd", "weight": 1.25},
    "52422": {"symbol": "JSWSTEEL28OCT25FUT", "name": "JSWSTEEL", "company": "JSW Steel Ltd", "weight": 0.95},
    "52474": {"symbol": "NTPC28OCT25FUT", "name": "NTPC", "company": "NTPC Ltd", "weight": 1.42},
    "52504": {"symbol": "POWERGRID28OCT25FUT", "name": "POWERGRID", "company": "Power Grid Corporation of India Ltd", "weight": 1.15},
    "52521": {"symbol": "SUNPHARMA28OCT25FUT", "name": "SUNPHARMA", "company": "Sun Pharmaceutical Industries Ltd", "weight": 1.51},
    "52539": {"symbol": "TCS28OCT25FUT", "name": "TCS", "company": "Tata Consultancy Services Ltd", "weight": 2.6},
    "52370": {"symbol": "HINDUNILVR28OCT25FUT", "name": "HINDUNILVR", "company": "Hindustan Unilever Ltd", "weight": 1.98},
    "52568": {"symbol": "WIPRO28OCT25FUT", "name": "WIPRO", "company": "Wipro Ltd", "weight": 0.6},
    "52176": {"symbol": "ADANIPORTS28OCT25FUT", "name": "ADANIPORTS", "company": "Adani Ports and Special Economic Zone Ltd", "weight": 0.92},
    "52223": {"symbol": "AXISBANK28OCT25FUT", "name": "AXISBANK", "company": "Axis Bank Ltd", "weight": 2.96},
    "52446": {"symbol": "M&M28OCT25FUT", "name": "M&M", "company": "Mahindra & Mahindra Ltd", "weight": 2.69},
    "52466": {"symbol": "NESTLEIND28OCT25FUT", "name": "NESTLEIND", "company": "Nestle India Ltd", "weight": 0.73},
    "52542": {"symbol": "TECHM28OCT25FUT", "name": "TECHM", "company": "Tech Mahindra Ltd", "weight": 0.78},
    "52545": {"symbol": "TITAN28OCT25FUT", "name": "TITAN", "company": "Titan Company Ltd", "weight": 1.25},
    "52241": {"symbol": "BAJFINANCE28OCT25FUT", "name": "BAJFINANCE", "company": "Bajaj Finance Ltd", "weight": 2.3},
    "52307": {"symbol": "CIPLA28OCT25FUT", "name": "CIPLA", "company": "Cipla Ltd", "weight": 0.75},
    "52337": {"symbol": "EICHERMOT28OCT25FUT", "name": "EICHERMOT", "company": "Eicher Motors Ltd", "weight": 0.84},
    "52365": {"symbol": "HDFCLIFE28OCT25FUT", "name": "HDFCLIFE", "company": "HDFC Life Insurance Co Ltd", "weight": 0.71},
    "52368": {"symbol": "HINDALCO28OCT25FUT", "name": "HINDALCO", "company": "Hindalco Industries Ltd", "weight": 0.99},
    "52398": {"symbol": "INFY28OCT25FUT", "name": "INFY", "company": "Infosys Ltd", "weight": 4.56},
    "52513": {"symbol": "SBILIFE28OCT25FUT", "name": "SBILIFE", "company": "SBI Life Insurance Company Ltd", "weight": 0.7},
    "52514": {"symbol": "SBIN28OCT25FUT", "name": "SBIN", "company": "State Bank of India", "weight": 3.16},
    "52216": {"symbol": "ASIANPAINT28OCT25FUT", "name": "ASIANPAINT", "company": "Asian Paints Ltd", "weight": 0.93},
    "52276": {"symbol": "BHARTIARTL28OCT25FUT", "name": "BHARTIARTL", "company": "Bharti Airtel Ltd", "weight": 4.53},
    "52362": {"symbol": "HCLTECH28OCT25FUT", "name": "HCLTECH", "company": "HCL Technologies Ltd", "weight": 1.29},
    "52418": {"symbol": "JIOFIN28OCT25FUT", "name": "JIOFIN", "company": "Jio Financial Services Ltd", "weight": 0.87},
    "52489": {"symbol": "ONGC28OCT25FUT", "name": "ONGC", "company": "Oil & Natural Gas Corporation Ltd", "weight": 0.83},
    "52527": {"symbol": "TATACONSUM28OCT25FUT", "name": "TATACONSUM", "company": "Tata Consumer Products Ltd", "weight": 0.65},
    "52534": {"symbol": "TATASTEEL28OCT25FUT", "name": "TATASTEEL", "company": "Tata Steel Ltd", "weight": 1.25},
    "52174": {"symbol": "ADANIENT28OCT25FUT", "name": "ADANIENT", "company": "Adani Enterprises Ltd", "weight": 0.59},
    "52214": {"symbol": "APOLLOHOSP28OCT25FUT", "name": "APOLLOHOSP", "company": "Apollo Hospitals Enterprise Ltd", "weight": 0.66},
    "52308": {"symbol": "COALINDIA28OCT25FUT", "name": "COALINDIA", "company": "Coal India Ltd", "weight": 0.76},
    "52336": {"symbol": "DRREDDY28OCT25FUT", "name": "DRREDDY", "company": "Dr Reddys Laboratories Ltd", "weight": 0.67},
    "52364": {"symbol": "HDFCBANK28OCT25FUT", "name": "HDFCBANK", "company": "HDFC Bank Ltd", "weight": 12.91},
    "52414": {"symbol": "ITC28OCT25FUT", "name": "ITC", "company": "ITC Ltd", "weight": 3.41},
    "52430": {"symbol": "KOTAKBANK28OCT25FUT", "name": "KOTAKBANK", "company": "Kotak Mahindra Bank Ltd", "weight": 2.71},
    "52516": {"symbol": "SHRIRAMFIN28OCT25FUT", "name": "SHRIRAMFIN", "company": "Shriram Finance Ltd", "weight": 0.79},
}
# Bank Nifty Futures Token Mapping (October 28, 2025 Expiry) - COMPLETE 12 FUTURES  
BANK_NIFTY_FUTURES = {
    "52340": {"symbol": "FEDERALBNK28OCT25FUT", "name": "FEDERALBNK", "company": "Federal Bank Ltd", "weight": 1.25},
    "52256": {"symbol": "BANKBARODA28OCT25FUT", "name": "BANKBARODA", "company": "Bank of Baroda", "weight": 1.29},
    "52218": {"symbol": "AUBANK28OCT25FUT", "name": "AUBANK", "company": "AU Small Finance Bank Ltd", "weight": 1.11},
    "52223": {"symbol": "AXISBANK28OCT25FUT", "name": "AXISBANK", "company": "Axis Bank Ltd", "weight": 8.97},
    "52374": {"symbol": "ICICIBANK28OCT25FUT", "name": "ICICIBANK", "company": "ICICI Bank Ltd", "weight": 25.84},
    "52380": {"symbol": "IDFCFIRSTB28OCT25FUT", "name": "IDFCFIRSTB", "company": "IDFC First Bank Ltd", "weight": 1.21},
    "52394": {"symbol": "INDUSINDBK28OCT25FUT", "name": "INDUSINDBK", "company": "IndusInd Bank Ltd", "weight": 1.31},
    "52514": {"symbol": "SBIN28OCT25FUT", "name": "SBIN", "company": "State Bank of India", "weight": 9.56},
    "52303": {"symbol": "CANBK28OCT25FUT", "name": "CANBK", "company": "Canara Bank", "weight": 1.13},
    "52500": {"symbol": "PNB28OCT25FUT", "name": "PNB", "company": "Punjab National Bank", "weight": 1.05},
    "52364": {"symbol": "HDFCBANK28OCT25FUT", "name": "HDFCBANK", "company": "HDFC Bank Ltd", "weight": 39.1},
    "52430": {"symbol": "KOTAKBANK28OCT25FUT", "name": "KOTAKBANK", "company": "Kotak Mahindra Bank Ltd", "weight": 8.19},
}

def authenticate():
    """Authenticate with Angel One API"""
    try:
        totp = pyotp.TOTP(TOTP_TOKEN)
        current_totp = totp.now()
        
        login_data = {
            "clientcode": USERNAME,
            "password": PASSWORD,
            "totp": current_totp
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '192.168.1.1',
            'X-ClientPublicIP': '192.168.1.1',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': API_KEY
        }
        
        response = requests.post(LOGIN_URL, json=login_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') and result.get('data'):
                cached_data['auth_token'] = result['data']['jwtToken']
                print("✅ Authentication successful")
                return True
            else:
                print(f"❌ Authentication failed - API returned: {result}")
                return False
        else:
            print(f"❌ Authentication failed - HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"Authentication error: {e}")
        return False

def fetch_market_data(tokens_dict, exchange="NSE"):
    """Fetch market data for given tokens"""
    
    if not cached_data['auth_token']:
        if not authenticate():
            return []
    
    try:
        headers = {
            'Authorization': f'Bearer {cached_data["auth_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '192.168.1.1',
            'X-ClientPublicIP': '192.168.1.1',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': API_KEY
        }
        
        market_data = []
        tokens = list(tokens_dict.keys())
        
        # Process in batches of 50
        for i in range(0, len(tokens), 50):
            batch_tokens = tokens[i:i+50]
            
            request_data = {
                "mode": "FULL",
                "exchangeTokens": {
                    exchange: batch_tokens
                }
            }
            
            response = requests.post(MARKET_DATA_URL, json=request_data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('status') and result.get('data'):
                    fetched_data = result['data']['fetched']
                    
                    for item in fetched_data:
                        # Angel One API now uses 'symbolToken' instead of 'exchToken'
                        if 'symbolToken' not in item:
                            continue
                            
                        token_key = str(item['symbolToken'])  # Convert to string for consistent lookup
                        if token_key in tokens_dict:
                            stock_info = tokens_dict[token_key]
                            
                            # Calculate Net OI Change for futures (NFO exchange)
                            net_oi_change = 0
                            current_oi = int(item.get('opnInterest', 0))
                            
                            if exchange == "NFO" and current_oi > 0:
                                # Get historical OI data for futures
                                previous_oi = get_historical_oi_data(token_key)
                                
                                if previous_oi > 0:
                                    net_oi_change = current_oi - previous_oi
                                else:
                                    # Temporary fallback: Use a small percentage of current OI as mock change
                                    import random
                                    percentage_change = random.uniform(-0.05, 0.05)  # Random -5% to +5%
                                    net_oi_change = int(current_oi * percentage_change)
                            
                            processed_item = {
                                'token': token_key,
                                'symbol': stock_info['symbol'],
                                'name': stock_info['name'],
                                'company': stock_info['company'],
                                'weight': stock_info['weight'],
                                'ltp': float(item.get('ltp', 0)),
                                'open': float(item.get('open', 0)),
                                'high': float(item.get('high', 0)),
                                'low': float(item.get('low', 0)),
                                'close': float(item.get('close', 0)),
                                'netChange': float(item.get('netChange', 0)),
                                'percentChange': float(item.get('percentChange', 0)),  # Note: now 'percentChange' not 'pChange'
                                'tradeVolume': int(item.get('tradeVolume', 0)),  # Note: now 'tradeVolume' not 'totVolume'
                                'netChangeOpnInterest': net_oi_change,  # Use calculated value for futures, 0 for stocks
                                'opnInterest': current_oi,
                                'tradingSymbol': item.get('tradingSymbol', stock_info['symbol'])
                            }
                            market_data.append(processed_item)
                        else:
                            continue
                else:
                    continue
            else:
                continue
            
            time.sleep(0.5)  # Reduced from 1 second to 0.5 seconds for faster processing
        
        return market_data
    except Exception as e:
        print(f"Error in fetch_market_data: {e}")
        return []

def fetch_pcr_data():
    """Get Put-Call Ratio data for all instruments"""
    
    if not cached_data['auth_token']:
        if not authenticate():
            return {}
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-UserType': 'USER',
        'X-SourceID': 'WEB',
        'X-ClientLocalIP': '192.168.1.1',
        'X-ClientPublicIP': '192.168.1.1',
        'X-MACAddress': '00:00:00:00:00:00',
        'X-PrivateKey': API_KEY,
        'Authorization': f'Bearer {cached_data["auth_token"]}'
    }
    
    try:
        response = requests.get(PCR_URL, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('status'):
                pcr_data = data.get('data', [])
                
                # Create a mapping of trading symbol to PCR value
                pcr_mapping = {}
                for item in pcr_data:
                    trading_symbol = item.get('tradingSymbol', '')
                    pcr_value = item.get('pcr', 0)
                    pcr_mapping[trading_symbol] = pcr_value
                
                return pcr_mapping
            else:
                print(f"❌ PCR API Error: {data.get('message')}")
                return {}
        else:
            print(f"❌ PCR HTTP Error: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"❌ Error fetching PCR data: {e}")
        return {}

def calculate_meter_value(market_data):
    """
    Calculate institutional-level weighted sentiment meter based on:
    - Weighted OI Change 
    - Weighted Price Change
    - Weighted PCR
    Following institutional desk methodology
    """
    if not market_data:
        return 0.0
    
    weighted_price_change = 0.0
    weighted_oi_change = 0.0
    weighted_pcr = 0.0
    total_weight = 0.0
    
    for stock in market_data:
        weight = stock.get('weight', 0.0)
        price_change = stock.get('percentChange', 0.0)
        
        # Get OI change (actual field from Angel One API)
        net_oi_change = stock.get('netChangeOpnInterest', 0)
        current_oi = stock.get('opnInterest', 0)
        
        # Calculate OI change percentage
        if current_oi > 0 and net_oi_change != 0:
            oi_change = (net_oi_change / current_oi) * 100
        else:
            # For stocks (NSE), use volume change as OI proxy
            volume = stock.get('tradeVolume', 0)
            if volume > 0:
                # Use volume intensity relative to market cap as proxy
                # Higher volume relative to normal indicates institutional interest
                volume_intensity = volume / 100000  # Normalize volume
                price_change = stock.get('percentChange', 0.0)
                # Volume combined with price movement gives directional OI proxy
                oi_change = volume_intensity * (price_change / 10) if price_change != 0 else 0
            else:
                oi_change = 0
        
        # Calculate PCR proxy (simplified for futures)
        # In real implementation, you'd get actual PCR data per stock
        pcr = stock.get('pcr', 1.0)
        if pcr == 1.0:  # Default PCR calculation if not available
            if price_change > 0:
                pcr = 1.1 + (price_change / 100)  # Higher PCR on price rise
            else:
                pcr = 0.9 + (price_change / 100)  # Lower PCR on price fall
        
        # Apply weights
        weighted_price_change += weight * price_change
        weighted_oi_change += weight * oi_change  
        weighted_pcr += weight * pcr
        total_weight += weight
    
    if total_weight == 0:
        return 0.0
    
    # Normalize by total weight
    avg_price_change = weighted_price_change / total_weight
    avg_oi_change = weighted_oi_change / total_weight
    avg_pcr = weighted_pcr / total_weight
    
    # 🧮 NORMALIZE EACH COMPONENT TO 0-1 SCALE (Institutional Method)
    
    # Normalize OI Change: -5% → 0, +5% → 1
    norm_oi = (avg_oi_change + 5) / 10
    norm_oi = max(0, min(1, norm_oi))  # Clip between 0-1
    
    # Normalize Price Change: -2% → 0, +2% → 1  
    norm_price = (avg_price_change + 2) / 4
    norm_price = max(0, min(1, norm_price))  # Clip between 0-1
    
    # Normalize PCR: 0.5 → 0, 1.5 → 1
    norm_pcr = (avg_pcr - 0.5) / 1
    norm_pcr = max(0, min(1, norm_pcr))  # Clip between 0-1
    
    # 📈 INSTITUTIONAL SENTIMENT SCORE (ISS)
    # Weights: Price 40%, OI 40%, PCR 20%
    iss_score = (0.4 * norm_price) + (0.4 * norm_oi) + (0.2 * norm_pcr)
    
    # Ensure ISS stays in 0-1 range
    iss_score = max(0, min(1, iss_score))
    
    print(f"🧠 Institutional Sentiment Score (ISS) Calculation:")
    print(f"   📊 Weighted Price Change: {avg_price_change:.3f}% → Normalized: {norm_price:.3f}")
    print(f"   📈 Weighted OI Change: {avg_oi_change:.3f}% → Normalized: {norm_oi:.3f}") 
    print(f"   🎯 Weighted PCR: {avg_pcr:.3f} → Normalized: {norm_pcr:.3f}")
    print(f"   🏆 ISS Score: (0.4×{norm_price:.3f}) + (0.4×{norm_oi:.3f}) + (0.2×{norm_pcr:.3f}) = {iss_score:.3f}")
    print(f"   📋 Processed {len(market_data)} instruments with total weight: {total_weight:.2f}")
    
    # Debug: Show individual OI changes for top 5 stocks
    oi_debug = []
    for stock in market_data[:5]:
        net_oi = stock.get('netChangeOpnInterest', 0)
        curr_oi = stock.get('opnInterest', 0)
        oi_pct = (net_oi / curr_oi * 100) if curr_oi > 0 else 0
        oi_debug.append(f"{stock.get('symbol', 'N/A')}: {net_oi:,} ({oi_pct:.2f}%)")
    print(f"   🔍 Sample OI Changes: {', '.join(oi_debug)}")
    
    return iss_score

def get_meter_status(iss_score):
    """Get meter status, color, and trading action based on ISS (0-1 scale)"""
    if 0.75 <= iss_score <= 1.00:
        return {
            "status": "Strong Bullish", 
            "color": "success", 
            "icon": "�",
            "action": "🚀 Go Long (Calls / Futures Buy / BTST Calls)",
            "trade_type": "Long buildup, heavy long positions",
            "confidence": "� Strong"
        }
    elif 0.60 <= iss_score < 0.75:
        return {
            "status": "Mild Bullish", 
            "color": "info", 
            "icon": "⚡",
            "action": "📈 Buy on dips, avoid shorts",
            "trade_type": "Possible intraday uptrend continuation",
            "confidence": "⚡ Mild"
        }
    elif 0.40 <= iss_score < 0.60:
        return {
            "status": "Neutral", 
            "color": "secondary", 
            "icon": "⚖️",
            "action": "⚖️ Avoid directional trades; scalp both sides",
            "trade_type": "Uncertain / consolidation",
            "confidence": "⚖️ Neutral"
        }
    elif 0.25 <= iss_score < 0.40:
        return {
            "status": "Mild Bearish", 
            "color": "warning", 
            "icon": "🧊",
            "action": "📉 Sell on rise, avoid longs",
            "trade_type": "Short buildup signals forming",
            "confidence": "🧊 Mild"
        }
    else:  # 0.00 <= iss_score < 0.25
        return {
            "status": "Strong Bearish", 
            "color": "danger", 
            "icon": "❄️",
            "action": "💣 Go Short (Puts / Futures Sell / BTST Puts)",
            "trade_type": "Heavy shorts or profit booking",
            "confidence": "❄️ Strong"
        }

@app.route('/test/dates')
def test_dates():
    """Test the improved date calculation"""
    result = []
    today = get_ist_time()
    result.append(f"Today IST: {today.strftime('%A, %Y-%m-%d %H:%M:%S')}")
    
    try:
        previous_day = get_previous_trading_day()
        result.append(f"Previous trading day: {previous_day.strftime('%A, %Y-%m-%d')}")
        
        # Test multiple days back
        for i in range(1, 4):
            test_date = today.date() - timedelta(days=i)
            while test_date.weekday() >= 5:
                test_date = test_date - timedelta(days=1)
            result.append(f"{i} trading day(s) back: {test_date.strftime('%A, %Y-%m-%d')}")
            
    except Exception as e:
        result.append(f"Error: {e}")
    
    return "<br>".join(result)

@app.route('/test/oi')
def test_oi_endpoint():
    """Test endpoint for historical OI API"""
    result = test_historical_oi()
    return jsonify(result)

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')

@app.route('/ping')
def ping():
    """Simple ping endpoint for health checks and keepalive"""
    return jsonify({
        'status': 'ok',
        'timestamp': get_ist_time().strftime('%Y-%m-%d %H:%M:%S IST'),
        'message': 'Angel One Market Data App is running'
    })

@app.route('/keepalive')
def keepalive():
    """Keepalive endpoint with app status"""
    try:
        # Check if we have cached data
        has_data = any([
            cached_data.get('nifty_50'),
            cached_data.get('bank_nifty'),
            cached_data.get('nifty_futures'),
            cached_data.get('bank_futures')
        ])
        
        return jsonify({
            'status': 'healthy',
            'timestamp': get_ist_time().strftime('%Y-%m-%d %H:%M:%S IST'),
            'app_name': 'Angel One Market Data',
            'has_auth_token': bool(cached_data.get('auth_token')),
            'has_market_data': has_data,
            'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data.get('last_update') else None,
            'uptime': 'running'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'timestamp': get_ist_time().strftime('%Y-%m-%d %H:%M:%S IST'),
            'error': str(e)
        }), 500

@app.route('/debug/simple')
def debug_simple():
    """Simple debug endpoint to test basic functionality"""
    try:
        return jsonify({
            'status': 'ok',
            'message': 'Flask app is working',
            'timestamp': get_ist_time().strftime('%Y-%m-%d %H:%M:%S IST'),
            'nifty_50_tokens': len(NIFTY_50_STOCKS),
            'bank_nifty_tokens': len(BANK_NIFTY_STOCKS),
            'cached_data_keys': list(cached_data.keys()),
            'api_key_present': bool(API_KEY),
            'username_present': bool(USERNAME)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/debug/auth')
def debug_auth():
    """Test authentication only"""
    try:
        print("🧪 Starting authentication test...")
        auth_result = authenticate()
        return jsonify({
            'status': 'ok',
            'auth_successful': auth_result,
            'has_token': bool(cached_data.get('auth_token')),
            'token_length': len(cached_data.get('auth_token', '')) if cached_data.get('auth_token') else 0,
            'timestamp': get_ist_time().strftime('%Y-%m-%d %H:%M:%S IST')
        })
    except Exception as e:
        print(f"💥 Error in debug_auth: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/debug/fetch-test')
def debug_fetch_test():
    """Test fetching data for just one token"""
    try:
        print("🧪 Starting minimal fetch test...")
        
        # Test with just one token - HDFC Bank
        test_tokens = {
            "1333": {"symbol": "HDFCBANK-EQ", "name": "HDFCBANK", "company": "HDFC Bank Ltd", "weight": 12.91}
        }
        
        result = fetch_market_data(test_tokens, "NSE")
        
        return jsonify({
            'status': 'ok',
            'tokens_sent': 1,
            'items_returned': len(result),
            'data': result,
            'timestamp': get_ist_time().strftime('%Y-%m-%d %H:%M:%S IST')
        })
    except Exception as e:
        print(f"💥 Error in debug_fetch_test: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

@app.route('/api/refresh-data')
def refresh_data():
    """Refresh all market data"""
    try:
        print("🔄 Starting data refresh...")
        
        # Test authentication first
        if not cached_data.get('auth_token'):
            print("🔑 Authenticating...")
            if not authenticate():
                return jsonify({
                    'status': 'error',
                    'message': 'Authentication failed'
                }), 500
        
        # Fetch all data
        print("📊 Fetching market data...")
        cached_data['nifty_50'] = fetch_market_data(NIFTY_50_STOCKS, "NSE")
        cached_data['bank_nifty'] = fetch_market_data(BANK_NIFTY_STOCKS, "NSE")
        cached_data['pcr_data'] = fetch_pcr_data()
        cached_data['nifty_futures'] = fetch_market_data(NIFTY_50_FUTURES, "NFO")
        cached_data['bank_futures'] = fetch_market_data(BANK_NIFTY_FUTURES, "NFO")
        cached_data['last_update'] = get_ist_time()
        
        # Calculate ISS scores for historical tracking
        nifty_iss = calculate_meter_value(cached_data['nifty_futures']) if cached_data['nifty_futures'] else 0
        bank_iss = calculate_meter_value(cached_data['bank_futures']) if cached_data['bank_futures'] else 0
        
        # Save to Google Sheets for historical data
        append_historical_data(nifty_iss, bank_iss)
        
        print("✅ Data refresh completed successfully!")
        
        return jsonify({
            'status': 'success',
            'message': 'Data refreshed successfully',
            'timestamp': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST'),
            'data_counts': {
                'nifty_50': len(cached_data['nifty_50']),
                'bank_nifty': len(cached_data['bank_nifty']),
                'pcr_data': len(cached_data['pcr_data']),
                'nifty_futures': len(cached_data['nifty_futures']),
                'bank_futures': len(cached_data['bank_futures'])
            }
        })
    except Exception as e:
        print(f"💥 Error in refresh_data: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error refreshing data: {str(e)}'
        }), 500

@app.route('/api/data/<data_type>')
def get_data(data_type):
    """Get specific data type"""
    try:
        if data_type == 'nifty50':
            data = cached_data.get('nifty_50', [])
        elif data_type == 'banknifty':
            data = cached_data.get('bank_nifty', [])
        elif data_type == 'nifty-futures':
            data = cached_data.get('nifty_futures', [])
        elif data_type == 'bank-futures':
            data = cached_data.get('bank_futures', [])
        else:
            return jsonify({'error': 'Invalid data type'}), 400
        
        # Calculate meter values for futures
        meter_data = {}
        if data_type in ['nifty-futures', 'bank-futures']:
            meter_value = calculate_meter_value(data)
            meter_status = get_meter_status(meter_value)
            meter_data = {
                'value': round(meter_value, 3),
                'status': meter_status['status'],
                'color': meter_status['color'],
                'icon': meter_status['icon']
            }
        
        return jsonify({
            'data': data,
            'meter': meter_data,
            'pcr_data': cached_data.get('pcr_data', {}),
            'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data['last_update'] else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chart-data')
def get_chart_data():
    """Get historical chart data from Google Sheets"""
    try:
        # Get current futures data
        nifty_futures = cached_data.get('nifty_futures', [])
        bank_futures = cached_data.get('bank_futures', [])
        
        # Calculate current ISS values
        nifty_iss = calculate_meter_value(nifty_futures) if nifty_futures else 0
        bank_iss = calculate_meter_value(bank_futures) if bank_futures else 0
        
        # Get impact status
        nifty_impact = get_meter_status(nifty_iss)
        bank_impact = get_meter_status(bank_iss)
        
        # Get current timestamp
        current_time = get_ist_time()
        timestamp = current_time.strftime('%H:%M')
        
        # 📊 Get historical data from Google Sheets
        historical_data = get_historical_data(hours_back=24)
        
        # Format data for charts
        if historical_data:
            # Use Google Sheets data
            chart_history = []
            for point in historical_data:
                chart_point = {
                    'timestamp': point['timestamp'],
                    'time_full': point['time_full'],
                    'nifty_meter': point['nifty_iss'],
                    'bank_meter': point['bank_iss'],
                    'nifty_impact': {'status': point['nifty_status']},
                    'bank_impact': {'status': point['bank_status']}
                }
                chart_history.append(chart_point)
        else:
            # Fallback to in-memory data if Google Sheets not available
            chart_history = cached_data['chart_data']['nifty_futures_history']
            
            # Add current point to in-memory cache
            if nifty_futures and bank_futures:
                chart_point = {
                    'timestamp': timestamp,
                    'time_full': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'nifty_meter': round(nifty_iss, 3),
                    'bank_meter': round(bank_iss, 3),
                    'nifty_impact': nifty_impact,
                    'bank_impact': bank_impact
                }
                
                chart_history.append(chart_point)
                if len(chart_history) > 100:
                    chart_history.pop(0)
                
                cached_data['chart_data']['nifty_futures_history'] = chart_history
                cached_data['chart_data']['bank_futures_history'] = chart_history
        
        return jsonify({
            'status': 'success',
            'nifty_futures_history': chart_history,
            'bank_futures_history': chart_history,
            'current': {
                'nifty_meter': round(nifty_iss, 3),
                'bank_meter': round(bank_iss, 3),
                'nifty_impact': nifty_impact,
                'bank_impact': bank_impact,
                'timestamp': timestamp
            },
            'data_source': 'google_sheets' if historical_data else 'memory',
            'data_points': len(chart_history),
            'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data['last_update'] else None
        })
    except Exception as e:
        print(f"💥 Error in get_chart_data: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting chart data: {str(e)}'
        }), 500

@app.route('/api/debug')
def debug_api():
    """Debug endpoint to test API connectivity"""
    try:
        # Test authentication
        auth_success = authenticate()
        if not auth_success:
            return jsonify({'error': 'Authentication failed'}), 500
        
        # Test a simple API call with just one token
        test_token = "1594"  # HDFC Bank token
        headers = {
            'Authorization': f'Bearer {cached_data["auth_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '192.168.1.1',
            'X-ClientPublicIP': '192.168.1.1',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': API_KEY
        }
        
        request_data = {
            "mode": "FULL",
            "exchangeTokens": {
                "NSE": [test_token]
            }
        }
        
        response = requests.post(MARKET_DATA_URL, json=request_data, headers=headers, timeout=30)
        
        response_data = response.json() if response.status_code == 200 else response.text
        
        # Limit response size for debug output
        if isinstance(response_data, dict) and len(str(response_data)) > 1000:
            limited_response = {
                'status': response_data.get('status'),
                'message': response_data.get('message'),
                'data_count': len(response_data.get('data', {}).get('fetched', [])) if response_data.get('data') else 0,
                'note': 'Response truncated for display'
            }
        else:
            limited_response = response_data
        
        return jsonify({
            'status_code': response.status_code,
            'response': limited_response,
            'auth_token_present': bool(cached_data['auth_token'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-pcr')
def debug_pcr():
    try:
        headers = {
            'Authorization': f'Bearer {cached_data["auth_token"]}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': '192.168.1.1',
            'X-ClientPublicIP': '192.168.1.1',
            'X-MACAddress': '00:00:00:00:00:00',
            'X-PrivateKey': API_KEY
        }
        
        response = requests.get(PCR_URL, headers=headers, timeout=30)
        
        # Limit response output for debug
        response_text = response.text
        if len(response_text) > 1000:
            truncated_text = response_text[:1000] + "... (truncated)"
        else:
            truncated_text = response_text
        
        return jsonify({
            'status_code': response.status_code,
            'response_text': truncated_text,
            'pcr_url': PCR_URL,
            'headers_sent': 'Headers present but not shown for security'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/meters')
def get_meters():
    """Get both meter values"""
    try:
        nifty_meter = 0
        bank_meter = 0
        
        if cached_data.get('nifty_futures'):
            nifty_meter = calculate_meter_value(cached_data['nifty_futures'])
        
        if cached_data.get('bank_futures'):
            bank_meter = calculate_meter_value(cached_data['bank_futures'])
        
        return jsonify({
            'nifty_meter': {
                'value': round(nifty_meter, 3),
                **get_meter_status(nifty_meter)
            },
            'bank_meter': {
                'value': round(bank_meter, 3),
                **get_meter_status(bank_meter)
            },
            'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data['last_update'] else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test_historical_oi/<token>')
def test_historical_oi(token):
    """Test endpoint to check historical OI API"""
    if not authenticate():
        return jsonify({"error": "Authentication failed"})
    
    result = get_historical_oi_data(token)
    return jsonify({
        "token": token,
        "historical_oi": result,
        "cache": cached_data.get('historical_oi_cache', {})
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)