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
    # Check for multiple possible environment variable names
    GOOGLE_CREDENTIALS = os.getenv('GOOGLE_CREDENTIALS') or os.getenv('GOOGLE_CREDS') or os.getenv('GOOGLE_SERVICE_ACCOUNT')
    
    print(f"🔍 Debug: Checking for Google credentials...")
    print(f"🔍 GOOGLE_CREDENTIALS env var: {'Found' if os.getenv('GOOGLE_CREDENTIALS') else 'Not found'}")
    print(f"🔍 GOOGLE_CREDS env var: {'Found' if os.getenv('GOOGLE_CREDS') else 'Not found'}")
    print(f"🔍 GOOGLE_SERVICE_ACCOUNT env var: {'Found' if os.getenv('GOOGLE_SERVICE_ACCOUNT') else 'Not found'}")
    print(f"🔍 credentials.json file: {'Found' if os.path.exists('credentials.json') else 'Not found'}")
    
    if GOOGLE_CREDENTIALS:
        # Parse JSON from environment variable
        import tempfile
        import json
        
        try:
            # Create temporary credentials file
            creds_dict = json.loads(GOOGLE_CREDENTIALS)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(creds_dict, f)
                GOOGLE_CREDS_FILE = f.name
            print("✅ Using Google Sheets credentials from environment variables")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse Google credentials JSON: {e}")
            GOOGLE_SHEETS_ENABLED = False
    else:
        # For local development: Use credentials.json file
        GOOGLE_CREDS_FILE = "credentials.json"
        if not os.path.exists(GOOGLE_CREDS_FILE):
            print("⚠️ Google Sheets disabled: No credentials.json file and no Google credentials environment variable found")
            print("💡 Expected environment variables: GOOGLE_CREDENTIALS, GOOGLE_CREDS, or GOOGLE_SERVICE_ACCOUNT")
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

# 📊 Index Weights Configuration for Price Action Analysis
# NIFTY 50 constituent weights (approximate percentages as of 2024)
NIFTY_50_WEIGHTS = {
    "RELIANCE": 9.5,      # Reliance Industries
    "TCS": 7.2,           # Tata Consultancy Services
    "HDFCBANK": 7.5,      # HDFC Bank
    "ICICIBANK": 7.0,     # ICICI Bank
    "HINDUNILVR": 4.8,    # Hindustan Unilever
    "INFY": 4.5,          # Infosys
    "LT": 3.8,            # Larsen & Toubro
    "ITC": 3.5,           # ITC Limited
    "SBIN": 3.2,          # State Bank of India
    "BHARTIARTL": 3.0,    # Bharti Airtel
    "KOTAKBANK": 2.8,     # Kotak Mahindra Bank
    "ASIANPAINT": 2.5,    # Asian Paints
    "MARUTI": 2.4,        # Maruti Suzuki
    "AXISBANK": 2.3,      # Axis Bank
    "HCLTECH": 2.2,       # HCL Technologies
    "BAJFINANCE": 2.1,    # Bajaj Finance
    "WIPRO": 1.9,         # Wipro
    "NESTLEIND": 1.8,     # Nestle India
    "ULTRACEMCO": 1.7,    # UltraTech Cement
    "TATAMOTORS": 1.6,    # Tata Motors
    "SUNPHARMA": 1.5,     # Sun Pharmaceutical
    "NTPC": 1.4,          # NTPC
    "TITAN": 1.3,         # Titan Company
    "POWERGRID": 1.2,     # Power Grid Corporation
    "TECHM": 1.1,         # Tech Mahindra
    "M&M": 1.0,           # Mahindra & Mahindra
    "ADANIPORTS": 0.9,    # Adani Ports
    "ONGC": 0.8,          # Oil & Natural Gas Corporation
    "COALINDIA": 0.7,     # Coal India
    "TATASTEEL": 0.6,     # Tata Steel
    "BAJAJFINSV": 0.5,    # Bajaj Finserv
    "DRREDDY": 0.4,       # Dr. Reddy's Laboratories
    "HINDALCO": 0.3,      # Hindalco Industries
    "EICHERMOT": 0.2,     # Eicher Motors
    "DIVISLAB": 0.1,      # Divi's Laboratories
}

# Bank NIFTY constituent weights (approximate percentages as of 2024)
BANK_NIFTY_WEIGHTS = {
    "HDFCBANK": 23.5,     # HDFC Bank
    "ICICIBANK": 22.8,    # ICICI Bank
    "SBIN": 15.2,         # State Bank of India
    "KOTAKBANK": 12.4,    # Kotak Mahindra Bank
    "AXISBANK": 11.8,     # Axis Bank
    "INDUSINDBK": 4.2,    # IndusInd Bank
    "FEDERALBNK": 3.1,    # Federal Bank
    "BANDHANBNK": 2.8,    # Bandhan Bank
    "AUBANK": 2.2,        # AU Small Finance Bank
    "IDFCFIRSTB": 2.0,    # IDFC First Bank
}

# 📊 Google Sheets Helper Functions
def append_historical_data(nifty_iss, bank_iss, nifty_price_action=None, bank_price_action=None):
    """Append current ISS and Price Action data to Google Sheets for historical tracking"""
    if not GOOGLE_SHEETS_ENABLED or not sheets_client:
        return False
        
    try:
        # Open or create sheet
        try:
            sheet = sheets_client.open(SPREADSHEET_NAME).sheet1
        except gspread.SpreadsheetNotFound:
            # Create new spreadsheet if it doesn't exist
            sheet = sheets_client.create(SPREADSHEET_NAME).sheet1
            # Add headers with price action columns
            sheet.append_row([
                'Timestamp', 'IST_Time', 'Nifty_ISS', 'Bank_ISS', 
                'Nifty_Status', 'Bank_Status', 'Session',
                'Nifty_Price_Action', 'Bank_Price_Action',
                'Nifty_PA_Zone', 'Bank_PA_Zone'
            ])
            print(f"✅ Created new Google Sheet: {SPREADSHEET_NAME}")
        
        # Calculate price action scores if not provided
        if nifty_price_action is None or bank_price_action is None:
            nifty_futures_data = cached_data.get('nifty_futures', [])
            bank_futures_data = cached_data.get('bank_futures', [])
            
            nifty_price_action = calculate_index_price_action(nifty_futures_data, NIFTY_50_WEIGHTS)
            bank_price_action = calculate_index_price_action(bank_futures_data, BANK_NIFTY_WEIGHTS)
        
        # Handle None price action values
        if nifty_price_action is None or bank_price_action is None:
            print("⚠️ Saving without price action data - calculations returned None")
            nifty_pa_zone = 'Neutral'
            bank_pa_zone = 'Neutral'
        else:
            # Get price action zones for valid data
            nifty_pa_zone = get_price_action_zone(nifty_price_action)['zone']
            bank_pa_zone = get_price_action_zone(bank_price_action)['zone']
        
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
        
        # Append row with price action data (handle None values)
        price_action_nifty = round(nifty_price_action, 4) if nifty_price_action is not None else ''
        price_action_bank = round(bank_price_action, 4) if bank_price_action is not None else ''
        
        sheet.append_row([
            timestamp, ist_time, round(nifty_iss, 4), round(bank_iss, 4),
            nifty_status, bank_status, session,
            price_action_nifty, price_action_bank,
            nifty_pa_zone, bank_pa_zone
        ])
        
        print(f"📊 Historical data saved: {timestamp} | Nifty: {nifty_iss:.3f} | Bank: {bank_iss:.3f}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save historical data: {e}")
        return False

def get_historical_data(hours_back=24):
    """Retrieve historical ISS data from Google Sheets"""
    if not GOOGLE_SHEETS_ENABLED or not sheets_client:
        print("📊 Google Sheets not enabled, returning empty data")
        return []
        
    try:
        sheet = sheets_client.open(SPREADSHEET_NAME).sheet1
        print(f"📊 Successfully opened sheet: {SPREADSHEET_NAME}")
        
        # Get all values as list of lists to avoid the 'expected_headers' duplicate issue
        all_values = sheet.get_all_values()
        print(f"📊 Retrieved {len(all_values)} total rows from sheet")
        
        if len(all_values) < 2:  # Need at least header + 1 data row
            print("📊 No data rows found in Google Sheets")
            return []
        
        # Skip header row and process data rows directly
        data_rows = all_values[1:]  
        print(f"📊 Processing {len(data_rows)} data rows")
        
        # Filter for recent data
        current_time = get_ist_time()
        cutoff_time = current_time - timedelta(hours=hours_back)
        
        print(f"🕐 Current IST time: {current_time}")
        print(f"🕐 Cutoff time (last {hours_back}h): {cutoff_time}")
        
        filtered_data = []
        successful_rows = 0
        
        for i, row in enumerate(data_rows):
            try:
                # Ensure row has minimum required columns
                if len(row) < 4:  # Need at least: Timestamp, IST_Time, Nifty_ISS, Bank_ISS
                    continue
                    
                # Parse timestamp (first column)
                timestamp_str = row[0].strip()
                if not timestamp_str:  # Skip empty rows
                    continue
                    
                # Try to parse the timestamp
                record_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                record_time = record_time.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
                
                # Debug: Show first few timestamp comparisons
                if i < 3:
                    print(f"🕐 Row {i+1}: {timestamp_str} -> {record_time} >= {cutoff_time}? {record_time >= cutoff_time}")
                
                # Only include recent data
                if record_time >= cutoff_time:
                    # Extract data - skip rows with missing critical data
                    if not (len(row) > 2 and row[2]) or not (len(row) > 3 and row[3]):
                        continue  # Skip rows without valid ISS values
                    
                    ist_time = row[1] if len(row) > 1 and row[1] else timestamp_str.split(' ')[1][:5]
                    nifty_iss = float(row[2])  # No default, must have valid data
                    bank_iss = float(row[3])   # No default, must have valid data
                    nifty_status = row[4] if len(row) > 4 and row[4] else 'Neutral'
                    bank_status = row[5] if len(row) > 5 and row[5] else 'Neutral'
                    session = row[6] if len(row) > 6 and row[6] else 'Unknown'
                    
                    # Read price action data (columns 7-10)
                    nifty_price_action = None
                    bank_price_action = None
                    nifty_pa_zone = 'Neutral'
                    bank_pa_zone = 'Neutral'
                    
                    if len(row) > 7 and row[7]:
                        try:
                            nifty_price_action = float(row[7])
                        except (ValueError, TypeError):
                            pass
                    
                    if len(row) > 8 and row[8]:
                        try:
                            bank_price_action = float(row[8])
                        except (ValueError, TypeError):
                            pass
                    
                    if len(row) > 9 and row[9]:
                        nifty_pa_zone = row[9]
                    
                    if len(row) > 10 and row[10]:
                        bank_pa_zone = row[10]
                    
                    filtered_data.append({
                        'timestamp': ist_time,
                        'time_full': timestamp_str,
                        'nifty_iss': nifty_iss,
                        'bank_iss': bank_iss,
                        'nifty_status': nifty_status,
                        'bank_status': bank_status,
                        'session': session,
                        'nifty_price_action': nifty_price_action,
                        'bank_price_action': bank_price_action,
                        'nifty_pa_zone': nifty_pa_zone,
                        'bank_pa_zone': bank_pa_zone
                    })
                    successful_rows += 1
                    
            except (ValueError, IndexError) as e:
                print(f"⚠️ Skipping row {i+2} due to parsing error: {e}")
                continue
                
        print(f"📈 Retrieved {len(filtered_data)} historical data points out of {len(data_rows)} total rows")
        print(f"📈 Successful rows processed: {successful_rows}")
        
        # Debug: Show latest few data points
        if filtered_data:
            latest_points = filtered_data[-3:]
            for point in latest_points:
                print(f"📊 Latest: {point['time_full']} | PA: N={point.get('nifty_price_action')}, B={point.get('bank_price_action')}")
        
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
    if not cached_data['auth_token']:
        if not authenticate():
            return 0
    
    # Check cache first
    cache_key = f"oi_{symbol_token}"
    today = get_ist_time().date()
    
    if cache_key in cached_data['historical_oi_cache']:
        cache_date, cache_data = cached_data['historical_oi_cache'][cache_key]
        if cache_date == today:
            return cache_data
    
    # Rate limiting: wait between API calls
    time.sleep(0.5)  # 500ms delay to avoid rate limits
    
    # Get previous trading day data to calculate OI change
    target_date = get_previous_trading_day()
    
    # Use 3-minute interval to get recent data points
    from_date = target_date.strftime('%Y-%m-%d 15:20')  # Last 10 minutes of previous day
    to_date = target_date.strftime('%Y-%m-%d 15:30')
    
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
        "symboltoken": symbol_token,
        "interval": "THREE_MINUTE",
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
                    # Get the last OI value from previous day
                    last_oi_entry = oi_data[-1]
                    previous_oi = int(last_oi_entry.get('oi', 0))
                    
                    # Cache the result
                    cached_data['historical_oi_cache'][cache_key] = (today, previous_oi)
                    
                    print(f"📊 Historical OI for {symbol_token}: {previous_oi:,}")
                    return previous_oi
                else:
                    print(f"⚠️ No OI data found for {symbol_token}")
                    return 0
            else:
                print(f"❌ OI API Error for {symbol_token}: {data.get('message', 'Unknown error')}")
                return 0
        else:
            print(f"❌ OI API HTTP Error {response.status_code} for {symbol_token}")
            return 0
            
    except Exception as e:
        print(f"💥 Error fetching OI data for {symbol_token}: {e}")
        return 0
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
                            
                            # Debug: Log the actual API response fields for first few items
                            if len(market_data) < 3:
                                print(f"🔍 API Response Debug for {stock_info['symbol']}:")
                                print(f"   Available fields: {list(item.keys())}")
                                print(f"   opnInterest: {item.get('opnInterest', 'NOT_FOUND')}")
                            
                            # Get current OI from market data
                            current_oi = int(item.get('opnInterest', 0))
                            
                            # Calculate OI change for futures using historical API
                            net_oi_change = 0
                            if exchange == "NFO" and current_oi > 0:
                                # Get previous day's OI from historical API
                                previous_oi = get_historical_oi_data(token_key)
                                if previous_oi > 0:
                                    net_oi_change = current_oi - previous_oi
                                    print(f"📊 OI Change for {stock_info['symbol']}: Current={current_oi:,}, Previous={previous_oi:,}, Change={net_oi_change:,}")
                                else:
                                    print(f"⚠️ No historical OI data for {stock_info['symbol']}")
                            else:
                                # For NSE stocks, use volume-based proxy
                                if exchange == "NSE":
                                    volume = int(item.get('tradeVolume', 0))
                                    price_change = float(item.get('percentChange', 0.0))
                                    # Volume intensity proxy for institutional interest
                                    if volume > 0:
                                        volume_intensity = volume / 100000  # Normalize
                                        net_oi_change = int(volume_intensity * (price_change / 10) * 1000)  # Scale appropriately
                            
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

def calculate_price_strength(ltp, high, low):
    """
    Calculate individual stock price strength using intraday range position
    Formula: (LTP - Low) / (High - Low)
    Returns value between 0 and 1
    """
    try:
        # Validate inputs
        if not all(isinstance(x, (int, float)) and x > 0 for x in [ltp, high, low]):
            return None  # Invalid data
        
        if high == low:  # No intraday movement
            return None  # Can't calculate without range
        
        if high < low:  # Invalid data
            return None
        
        price_strength = (ltp - low) / (high - low)
        return max(0, min(1, price_strength))  # Clamp between 0 and 1
    except:
        return None  # Return None for invalid data

def calculate_index_price_action(stocks_data, index_weights):
    """
    Calculate weighted index-level price action score
    Args:
        stocks_data: List of stock dictionaries with 'symbol', 'ltp', 'high', 'low'
        index_weights: Dictionary mapping stock symbols to weights
    Returns:
        Weighted price action score between 0 and 1
    """
    try:
        # Handle None or empty data
        if not stocks_data or stocks_data is None:
            print("⚠️ No stocks data provided for price action calculation")
            return None  # Return None for no data
            
        total_weighted_strength = 0
        total_weights = 0
        matched_stocks = 0
        processed_stocks = []
        
        for stock in stocks_data:
            symbol = stock.get('symbol', '').upper()
            # Clean symbol name - remove suffixes like "28OCT25FUT"
            clean_symbol = symbol.replace('28OCT25FUT', '').replace('-EQ', '')
            
            # Handle special Bank NIFTY symbol mappings
            if clean_symbol == 'BANKNIFTY':
                continue  # Skip index symbol itself
                
            ltp = float(stock.get('ltp', 0))
            high = float(stock.get('high', 0))
            low = float(stock.get('low', 0))
            
            # Get weight for this stock using clean symbol
            weight = index_weights.get(clean_symbol, 0)
            if weight > 0 and high > 0 and low > 0 and ltp > 0:
                price_strength = calculate_price_strength(ltp, high, low)
                # Only include stocks with valid price strength calculation
                if price_strength is not None:
                    total_weighted_strength += weight * price_strength
                    total_weights += weight
                    matched_stocks += 1
                    processed_stocks.append({
                        'symbol': clean_symbol,
                        'ltp': ltp,
                        'high': high,
                        'low': low,
                        'strength': price_strength,
                        'weight': weight
                    })
        
        print(f"📊 Price Action Processing: {matched_stocks} stocks matched, total weight: {total_weights:.2f}")
        if len(processed_stocks) > 0:
            # Show top 3 processed stocks
            top_stocks = sorted(processed_stocks, key=lambda x: x['weight'], reverse=True)[:3]
            for stock in top_stocks:
                print(f"   📈 {stock['symbol']}: LTP={stock['ltp']}, H={stock['high']}, L={stock['low']}, Strength={stock['strength']:.3f}, Weight={stock['weight']}%")
        
        if total_weights == 0:
            print("⚠️ No valid stocks matched for price action calculation")
            return None  # Return None if no valid data
        
        # Calculate weighted average
        index_score = total_weighted_strength / total_weights
        print(f"🎯 Final Price Action Score: {index_score:.3f} (from {matched_stocks} stocks)")
        return round(index_score, 3)
    
    except Exception as e:
        print(f"❌ Error calculating index price action: {e}")
        return None  # Return None for errors

def get_price_action_zone(score):
    """
    Classify price action score into zones with trading interpretation
    """
    if score <= 0.2:
        return {
            'zone': 'Deep Bear',
            'description': 'Strong sell-off; price hugging day\'s lows',
            'action': 'Avoid longs; watch for reversal setups',
            'color': 'danger',
            'icon': '🔴'
        }
    elif score <= 0.4:
        return {
            'zone': 'Weak',
            'description': 'Sellers still active; mild relief possible',
            'action': 'Only scalp; trend still down',
            'color': 'warning',
            'icon': '🟡'
        }
    elif score <= 0.6:
        return {
            'zone': 'Neutral',
            'description': 'Tug-of-war; could break any side',
            'action': 'Wait for breakout or confirm with OI',
            'color': 'secondary',
            'icon': '⚪'
        }
    elif score <= 0.8:
        return {
            'zone': 'Bullish',
            'description': 'Buyers in control; pullbacks get bought',
            'action': 'Prefer long trades with OI support',
            'color': 'success',
            'icon': '🟢'
        }
    else:
        return {
            'zone': 'Strong Bull',
            'description': 'Index at/near highs',
            'action': 'Trail profits; beware of exhaustion',
            'color': 'info',
            'icon': '🔵'
        }

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
        
        # Calculate price action scores using FUTURES data (has LTP, High, Low)
        nifty_futures_data = cached_data.get('nifty_futures', []) or []
        bank_futures_data = cached_data.get('bank_futures', []) or []
        
        print(f"🔍 Futures data counts: NIFTY={len(nifty_futures_data)}, Bank={len(bank_futures_data)}")
        
        # Debug: Check if futures data has required fields
        if nifty_futures_data:
            sample_nifty = nifty_futures_data[0]
            print(f"🔍 Sample NIFTY futures data: {sample_nifty.get('symbol', 'N/A')} - LTP:{sample_nifty.get('ltp', 'N/A')}, High:{sample_nifty.get('high', 'N/A')}, Low:{sample_nifty.get('low', 'N/A')}")
        
        if bank_futures_data:
            sample_bank = bank_futures_data[0]
            print(f"🔍 Sample Bank futures data: {sample_bank.get('symbol', 'N/A')} - LTP:{sample_bank.get('ltp', 'N/A')}, High:{sample_bank.get('high', 'N/A')}, Low:{sample_bank.get('low', 'N/A')}")
        
        nifty_price_action = calculate_index_price_action(nifty_futures_data, NIFTY_50_WEIGHTS)
        bank_price_action = calculate_index_price_action(bank_futures_data, BANK_NIFTY_WEIGHTS)
        
        # Fallback: If futures data fails, try using regular stock data
        if nifty_price_action is None and cached_data.get('nifty_50'):
            print("⚠️ NIFTY futures price action failed, trying with stock data...")
            nifty_price_action = calculate_index_price_action(cached_data['nifty_50'], NIFTY_50_WEIGHTS)
            
        if bank_price_action is None and cached_data.get('bank_nifty'):
            print("⚠️ Bank futures price action failed, trying with stock data...")
            bank_price_action = calculate_index_price_action(cached_data['bank_nifty'], BANK_NIFTY_WEIGHTS)
        
        print(f"📊 Final price actions: NIFTY={nifty_price_action}, Bank={bank_price_action}")
        
        # Save to Google Sheets for historical data
        # Always save ISS data, include price action when available
        success = append_historical_data(nifty_iss, bank_iss, nifty_price_action, bank_price_action)
        print(f"💾 Historical data save: {'Success' if success else 'Failed'}")
        
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
                    'bank_impact': {'status': point['bank_status']},
                    'nifty_price_action': point.get('nifty_price_action'),
                    'bank_price_action': point.get('bank_price_action'),
                    'nifty_pa_zone': point.get('nifty_pa_zone', 'Neutral'),
                    'bank_pa_zone': point.get('bank_pa_zone', 'Neutral')
                }
                chart_history.append(chart_point)
        else:
            # No Google Sheets data available, return empty
            chart_history = []
        
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

@app.route('/api/price-action')
def get_price_action():
    """Get real-time price action analysis for NIFTY 50 and Bank NIFTY"""
    try:
        # Get FUTURES data for price action (this has LTP, High, Low, Open)
        nifty_futures_data = cached_data.get('nifty_futures', [])
        bank_futures_data = cached_data.get('bank_futures', [])
        
        print(f"🔍 Price action data check: nifty_futures={len(nifty_futures_data) if nifty_futures_data else 0}, bank_futures={len(bank_futures_data) if bank_futures_data else 0}")
        print(f"🗃️ Available cached_data keys: {list(cached_data.keys())}")
        
        # Ensure we have lists, not None
        if nifty_futures_data is None:
            nifty_futures_data = []
        if bank_futures_data is None:
            bank_futures_data = []
        
        # Debug: Show sample futures data
        if len(nifty_futures_data) > 0:
            sample = nifty_futures_data[0]
            print(f"📊 Sample NIFTY futures data: symbol={sample.get('symbol')}, ltp={sample.get('ltp')}, high={sample.get('high')}, low={sample.get('low')}")
        
        if len(bank_futures_data) > 0:
            sample = bank_futures_data[0]
            print(f"🏦 Sample Bank futures data: symbol={sample.get('symbol')}, ltp={sample.get('ltp')}, high={sample.get('high')}, low={sample.get('low')}")
        
        # Calculate price action scores using futures data
        nifty_price_score = calculate_index_price_action(nifty_futures_data, NIFTY_50_WEIGHTS)
        bank_price_score = calculate_index_price_action(bank_futures_data, BANK_NIFTY_WEIGHTS)
        
        # Handle None values - only proceed if we have valid calculations
        if nifty_price_score is None or bank_price_score is None:
            return jsonify({
                'status': 'error',
                'message': 'Unable to calculate price action - insufficient valid data',
                'nifty_calculated': nifty_price_score is not None,
                'bank_calculated': bank_price_score is not None,
                'nifty_data_count': len(nifty_futures_data) if nifty_futures_data else 0,
                'bank_data_count': len(bank_futures_data) if bank_futures_data else 0
            }), 400
        
        print(f"📊 Price action scores: NIFTY={nifty_price_score}, Bank={bank_price_score}")
        
        # Get zone classifications
        nifty_zone = get_price_action_zone(nifty_price_score)
        bank_zone = get_price_action_zone(bank_price_score)
        
        # Get current timestamp
        current_time = get_ist_time()
        timestamp = current_time.strftime('%H:%M')
        
        return jsonify({
            'status': 'success',
            'timestamp': timestamp,
            'nifty_50': {
                'price_score': nifty_price_score,
                'zone': nifty_zone,
                'stocks_analyzed': len([s for s in nifty_futures_data if s.get('symbol', '').upper() in NIFTY_50_WEIGHTS])
            },
            'bank_nifty': {
                'price_score': bank_price_score,
                'zone': bank_zone,
                'stocks_analyzed': len([s for s in bank_futures_data if s.get('symbol', '').upper() in BANK_NIFTY_WEIGHTS])
            },
            'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data['last_update'] else None
        })
        
    except Exception as e:
        print(f"💥 Error in get_price_action: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting price action data: {str(e)}'
        }), 500

@app.route('/api/price-action-history')
def get_price_action_history():
    """Get historical price action chart data from Google Sheets"""
    try:
        # Get historical data from Google Sheets with extended time window
        historical_data = get_historical_data(hours_back=48)
        
        if historical_data:
            # Extract price action data for charts
            price_history = []
            skipped_count = 0
            
            print(f"🔍 Processing {len(historical_data)} historical data points for price action charts")
            
            for point in historical_data:
                try:
                    # Check price action data with more detailed logging
                    nifty_pa = point.get('nifty_price_action')
                    bank_pa = point.get('bank_price_action')
                    
                    # More lenient check - allow if at least one has valid data
                    if (nifty_pa is None or nifty_pa == '') and (bank_pa is None or bank_pa == ''):
                        skipped_count += 1
                        continue
                    
                    # Handle potentially missing values more gracefully
                    nifty_pa_value = float(nifty_pa) if nifty_pa not in (None, '') else None
                    bank_pa_value = float(bank_pa) if bank_pa not in (None, '') else None
                    
                    chart_point = {
                        'timestamp': point['timestamp'],
                        'time_full': point['time_full'],
                        'nifty_price_action': nifty_pa_value,
                        'bank_price_action': bank_pa_value,
                        'nifty_pa_zone': point.get('nifty_pa_zone', 'Neutral'),
                        'bank_pa_zone': point.get('bank_pa_zone', 'Neutral')
                    }
                    price_history.append(chart_point)
                except (KeyError, ValueError, TypeError) as e:
                    print(f"⚠️ Skipping invalid price action data point: {e}")
                    skipped_count += 1
                    continue
            
            print(f"📊 Price action history: {len(price_history)} valid points, {skipped_count} skipped")
            if price_history:
                latest = price_history[-1]
                print(f"📊 Latest price action: {latest['time_full']} | N={latest['nifty_price_action']}, B={latest['bank_price_action']}")
                    
            return jsonify({
                'status': 'success',
                'price_action_history': price_history,
                'data_source': 'google_sheets',
                'data_points': len(price_history),
                'skipped_points': skipped_count,
                'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data['last_update'] else None
            })
        else:
            # Fallback to current data only using FUTURES data
            nifty_futures_data = cached_data.get('nifty_futures', [])
            bank_futures_data = cached_data.get('bank_futures', [])
            
            # Ensure we have lists, not None
            if nifty_futures_data is None:
                nifty_futures_data = []
            if bank_futures_data is None:
                bank_futures_data = []
            
            print(f"🔄 Fallback mode: nifty_futures={len(nifty_futures_data)}, bank_futures={len(bank_futures_data)}")
            
            current_nifty_pa = calculate_index_price_action(nifty_futures_data, NIFTY_50_WEIGHTS)
            current_bank_pa = calculate_index_price_action(bank_futures_data, BANK_NIFTY_WEIGHTS)
            
            current_time = get_ist_time()
            
            fallback_data = [{
                'timestamp': current_time.strftime('%H:%M'),
                'time_full': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'nifty_price_action': current_nifty_pa,
                'bank_price_action': current_bank_pa,
                'nifty_pa_zone': get_price_action_zone(current_nifty_pa)['zone'],
                'bank_pa_zone': get_price_action_zone(current_bank_pa)['zone']
            }]
            
            return jsonify({
                'status': 'success',
                'price_action_history': fallback_data,
                'data_source': 'current_only',
                'data_points': 1,
                'last_update': cached_data['last_update'].strftime('%Y-%m-%d %H:%M:%S IST') if cached_data['last_update'] else None
            })
            
    except Exception as e:
        print(f"💥 Error in get_price_action_history: {e}")
        return jsonify({
            'status': 'error',
            'message': f'Error getting price action history: {str(e)}'
        }), 500

@app.route('/api/debug-cache')
def debug_cache():
    """Debug endpoint to check cached data structure"""
    try:
        cache_info = {
            'keys': list(cached_data.keys()),
            'data_counts': {},
            'sample_data': {}
        }
        
        for key, value in cached_data.items():
            if isinstance(value, list):
                cache_info['data_counts'][key] = len(value)
                if len(value) > 0:
                    cache_info['sample_data'][key] = {
                        'first_item_keys': list(value[0].keys()) if isinstance(value[0], dict) else 'not_dict',
                        'sample_symbols': [item.get('symbol', 'no_symbol') for item in value[:3]] if isinstance(value[0], dict) else []
                    }
            else:
                cache_info['data_counts'][key] = f"type: {type(value).__name__}"
                
        return jsonify({
            'status': 'success',
            'cache_info': cache_info
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Debug error: {str(e)}'
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