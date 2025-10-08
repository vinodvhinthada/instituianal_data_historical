# Angel One Market Data Web Application 🚀

A comprehensive real-time market data dashboard that fetches live data from Angel One SmartAPI and displays it in an interactive web interface.

![Python](https://img.shields.io/badge/python-v3.10.9-blue.svg)
![Flask](https://img.shields.io/badge/flask-v2.3.3-green.svg)
![Bootstrap](https://img.shields.io/badge/bootstrap-v5.3.0-purple.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## 🌟 Features

### 📊 **Four Market Segments**
- **Nifty 50 Stocks** - Top 50 Indian stocks with real-time data
- **Bank Nifty** - Banking sector stocks with live pricing
- **Nifty 50 Futures** - October 2025 futures contracts
- **Bank Nifty Futures** - Banking futures with open interest data

### ⚡ **Interactive Dashboard**
- **Real-time Data Refresh** - Live market updates
- **Interactive Tables** - Sort, filter, and search functionality
- **Market Meters** - Live market summary with key metrics
- **Mobile Responsive** - Works seamlessly on all devices
- **Bootstrap UI** - Professional and clean interface

### 🔧 **Technical Features**
- **Angel One API Integration** - Secure JWT authentication
- **Rate Limiting** - API-compliant request management
- **Error Handling** - Graceful failure management
- **Caching System** - Optimized performance
- **Real-time Updates** - AJAX-powered data refresh

## 🚀 Quick Start

### Prerequisites
- Python 3.11.6+
- Angel One trading account with API access
- Valid Angel One API credentials

### Local Development

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/angel-one-market-data.git
cd angel-one-market-data
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set environment variables**
```bash
# Create .env file
API_KEY=your_api_key
USERNAME=your_username
PASSWORD=your_password
TOTP_TOKEN=your_totp_token
```

4. **Run the application**
```bash
python app.py
```

5. **Open browser**
```
http://localhost:5000
```

## 🌐 Deploy to Render

### One-Click Deploy
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### Manual Deployment

1. **Fork this repository**
2. **Create new Web Service on Render**
3. **Connect your GitHub repository**
4. **Configure build settings:**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app --bind 0.0.0.0:$PORT
   ```

5. **Set environment variables:**
   ```
   API_KEY=your_angel_one_api_key
   USERNAME=your_angel_one_username  
   PASSWORD=your_angel_one_password
   TOTP_TOKEN=your_totp_secret
   ```

6. **Deploy and enjoy!**

## 📁 Project Structure

```
/
├── app.py                 # Main Flask application
├── templates/
│   └── index.html         # Dashboard template
├── requirements.txt       # Python dependencies
├── runtime.txt           # Python version
├── Procfile              # Deployment configuration
├── README.md             # This file
├── RENDER_DEPLOYMENT_GUIDE.md  # Detailed deployment guide
└── DEPLOYMENT_STATUS.md  # Development status
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `API_KEY` | Angel One API Key | Yes |
| `USERNAME` | Angel One Username | Yes |
| `PASSWORD` | Angel One Password | Yes |
| `TOTP_TOKEN` | TOTP Secret for 2FA | Yes |

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Main dashboard |
| `/api/nifty50` | Nifty 50 stocks data |
| `/api/banknifty` | Bank Nifty stocks data |
| `/api/niftyfutures` | Nifty 50 futures data |
| `/api/bankfutures` | Bank Nifty futures data |

## 🎯 Market Data Coverage

- **200+ Instruments** across 4 market segments
- **Real-time Pricing** - LTP, Open, High, Low, Close
- **Change Tracking** - Absolute and percentage changes
- **Volume Data** - Trading volumes and open interest
- **Market Metrics** - Advances/Declines, market sentiment

## 🔒 Security Features

- **Environment Variables** - Secure credential management
- **JWT Authentication** - Token-based API security
- **Rate Limiting** - API usage compliance
- **Input Validation** - Secure data processing

## 🛠️ Technology Stack

- **Backend:** Flask 2.3.3, Python 3.11.6
- **Frontend:** Bootstrap 5, jQuery, DataTables
- **API:** Angel One SmartAPI
- **Deployment:** Render, Gunicorn WSGI Server
- **Data Processing:** Pandas, NumPy

## 📊 Features Preview

### Dashboard Overview
- Clean, professional interface with tabbed navigation
- Real-time market data with auto-refresh functionality
- Interactive tables with search, sort, and filter capabilities

### Market Meters
- Live market summary with key metrics
- Advances vs Declines ratio
- Volume-weighted indicators
- Market sentiment analysis

### Mobile Support
- Fully responsive design
- Touch-friendly interface
- Optimized for all screen sizes

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🚨 Disclaimer

This application is for educational and informational purposes only. Always verify market data with official sources before making any trading decisions.

## 📞 Support

If you encounter any issues:
1. Check the [Deployment Guide](RENDER_DEPLOYMENT_GUIDE.md)
2. Review the [Development Status](DEPLOYMENT_STATUS.md)
3. Create an issue on GitHub

---

**Built with ❤️ for the trading community**

**Live Demo:** [Deploy your own instance](https://render.com/deploy)