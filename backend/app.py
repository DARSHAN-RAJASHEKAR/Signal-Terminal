import os
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
import requests
import json
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

_BINANCE_BASE = "https://api.binance.com/api/v3"
_STABLE_SYMBOLS = {'USDT', 'BUSD', 'USDC', 'DAI', 'TUSD', 'USDP', 'FDUSD', 'UST', 'USDS'}

def _binance_headers() -> dict:
    key = os.environ.get('BINANCE_API_KEY')
    return {'X-MBX-APIKEY': key} if key else {}

# Production CORS configuration
if os.environ.get('RENDER') or os.environ.get('PORT'):
    # Production on Render
    CORS(app, 
         origins=[
             "https://buy-the-dip-beige.vercel.app",
             "https://buythedip.darshanrajashekar.dev",
             "https://*.vercel.app",
             "http://localhost:3000",
             "http://127.0.0.1:5000",
             "http://localhost:7778",
             "http://127.0.0.1:7778"
         ],
         methods=["GET", "POST", "OPTIONS"],
         allow_headers=["Content-Type", "Authorization"]
    )
else:
    # Development
    CORS(app)

# Comprehensive stock lists - manually curated and reliable
def get_nifty_50_stocks():
    """Nifty 50 stocks"""
    return [
        {'symbol': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'ADANIPORTS.NS', 'name': 'Adani Ports and Special Economic Zone', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'APOLLOHOSP.NS', 'name': 'Apollo Hospitals Enterprise', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'ASIANPAINT.NS', 'name': 'Asian Paints', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'AXISBANK.NS', 'name': 'Axis Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJ-AUTO.NS', 'name': 'Bajaj Auto', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'BAJAJFINSV.NS', 'name': 'Bajaj Finserv', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJFINANCE.NS', 'name': 'Bajaj Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BEL.NS', 'name': 'Bharat Electronics', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel', 'sector': 'telecom', 'marketCap': 'large'},
        {'symbol': 'CIPLA.NS', 'name': 'Cipla', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'COALINDIA.NS', 'name': 'Coal India', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'DRREDDY.NS', 'name': "Dr. Reddy's Laboratories", 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'EICHERMOT.NS', 'name': 'Eicher Motors', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'GRASIM.NS', 'name': 'Grasim Industries', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'HCLTECH.NS', 'name': 'HCL Technologies', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'HDFCLIFE.NS', 'name': 'HDFC Life Insurance Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'HINDALCO.NS', 'name': 'Hindalco Industries', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'INDIGO.NS', 'name': 'InterGlobe Aviation', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'INFY.NS', 'name': 'Infosys', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'ITC.NS', 'name': 'ITC', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'JIOFIN.NS', 'name': 'Jio Financial Services', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'JSWSTEEL.NS', 'name': 'JSW Steel', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'construction', 'marketCap': 'large'},
        {'symbol': 'M&M.NS', 'name': 'Mahindra & Mahindra', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'MAXHEALTH.NS', 'name': 'Max Healthcare Institute', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'NESTLEIND.NS', 'name': 'Nestle India', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'NTPC.NS', 'name': 'NTPC', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ONGC.NS', 'name': 'Oil & Natural Gas Corporation', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'POWERGRID.NS', 'name': 'Power Grid Corporation of India', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'SBILIFE.NS', 'name': 'SBI Life Insurance Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'SHRIRAMFIN.NS', 'name': 'Shriram Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Industries', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'TATACONSUM.NS', 'name': 'Tata Consumer Products', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'TATASTEEL.NS', 'name': 'Tata Steel', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'TECHM.NS', 'name': 'Tech Mahindra', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'TITAN.NS', 'name': 'Titan Company', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'TMPV.NS', 'name': 'Tata Motors Passenger Vehicles', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'TRENT.NS', 'name': 'Trent', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'ULTRACEMCO.NS', 'name': 'UltraTech Cement', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'WIPRO.NS', 'name': 'Wipro', 'sector': 'it', 'marketCap': 'large'},
    ]

def get_nifty_100_stocks():
    """Nifty 100 stocks"""
    return [
        {'symbol': 'ABB.NS', 'name': 'ABB India', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ADANIENSOL.NS', 'name': 'Adani Energy Solutions', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'ADANIGREEN.NS', 'name': 'Adani Green Energy', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ADANIPORTS.NS', 'name': 'Adani Ports and Special Economic Zone', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'ADANIPOWER.NS', 'name': 'Adani Power', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'AMBUJACEM.NS', 'name': 'Ambuja Cements', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'APOLLOHOSP.NS', 'name': 'Apollo Hospitals Enterprise', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'ASIANPAINT.NS', 'name': 'Asian Paints', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'AXISBANK.NS', 'name': 'Axis Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJ-AUTO.NS', 'name': 'Bajaj Auto', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'BAJAJFINSV.NS', 'name': 'Bajaj Finserv', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJHLDNG.NS', 'name': 'Bajaj Holdings & Investment', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJFINANCE.NS', 'name': 'Bajaj Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BANKBARODA.NS', 'name': 'Bank of Baroda', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BEL.NS', 'name': 'Bharat Electronics', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel', 'sector': 'telecom', 'marketCap': 'large'},
        {'symbol': 'BOSCHLTD.NS', 'name': 'Bosch', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'BPCL.NS', 'name': 'Bharat Petroleum Corporation', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'BRITANNIA.NS', 'name': 'Britannia Industries', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'CANBK.NS', 'name': 'Canara Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'CGPOWER.NS', 'name': 'CG Power and Industrial Solutions', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'CHOLAFIN.NS', 'name': 'Cholamandalam Investment and Finance Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'CIPLA.NS', 'name': 'Cipla', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'COALINDIA.NS', 'name': 'Coal India', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'CUMMINSIND.NS', 'name': 'Cummins India', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'DIVISLAB.NS', 'name': "Divi's Laboratories", 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'DLF.NS', 'name': 'DLF', 'sector': 'realty', 'marketCap': 'large'},
        {'symbol': 'DMART.NS', 'name': 'Avenue Supermarts', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'DRREDDY.NS', 'name': "Dr. Reddy's Laboratories", 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'EICHERMOT.NS', 'name': 'Eicher Motors', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'ENRIN.NS', 'name': 'Siemens Energy India', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'GAIL.NS', 'name': 'GAIL (India)', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'GODREJCP.NS', 'name': 'Godrej Consumer Products', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'GRASIM.NS', 'name': 'Grasim Industries', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'HAL.NS', 'name': 'Hindustan Aeronautics', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'HCLTECH.NS', 'name': 'HCL Technologies', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'HDFCAMC.NS', 'name': 'HDFC Asset Management Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'HDFCLIFE.NS', 'name': 'HDFC Life Insurance Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'HINDALCO.NS', 'name': 'Hindalco Industries', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'HINDZINC.NS', 'name': 'Hindustan Zinc', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'HYUNDAI.NS', 'name': 'Hyundai Motor India', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'INDHOTEL.NS', 'name': 'Indian Hotels Co.', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'INDIGO.NS', 'name': 'InterGlobe Aviation', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'INFY.NS', 'name': 'Infosys', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'IOC.NS', 'name': 'Indian Oil Corporation', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'IRFC.NS', 'name': 'Indian Railway Finance Corporation', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'ITC.NS', 'name': 'ITC', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'JINDALSTEL.NS', 'name': 'Jindal Steel & Power', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'JIOFIN.NS', 'name': 'Jio Financial Services', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'JSWSTEEL.NS', 'name': 'JSW Steel', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'LODHA.NS', 'name': 'Lodha Developers', 'sector': 'realty', 'marketCap': 'large'},
        {'symbol': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'construction', 'marketCap': 'large'},
        {'symbol': 'LTM.NS', 'name': 'LTM (formerly LTIMindtree)', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'M&M.NS', 'name': 'Mahindra & Mahindra', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'MAXHEALTH.NS', 'name': 'Max Healthcare Institute', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'MAZDOCK.NS', 'name': 'Mazagon Dock Shipbuilders', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'MOTHERSON.NS', 'name': 'Samvardhana Motherson International', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'MUTHOOTFIN.NS', 'name': 'Muthoot Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'NESTLEIND.NS', 'name': 'Nestle India', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'NTPC.NS', 'name': 'NTPC', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ONGC.NS', 'name': 'Oil & Natural Gas Corporation', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'PFC.NS', 'name': 'Power Finance Corporation', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'PIDILITIND.NS', 'name': 'Pidilite Industries', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'PNB.NS', 'name': 'Punjab National Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'POWERGRID.NS', 'name': 'Power Grid Corporation of India', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'RECLTD.NS', 'name': 'REC', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'SBILIFE.NS', 'name': 'SBI Life Insurance Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'SHREECEM.NS', 'name': 'Shree Cement', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'SHRIRAMFIN.NS', 'name': 'Shriram Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'SIEMENS.NS', 'name': 'Siemens', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'SOLARINDS.NS', 'name': 'Solar Industries India', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Industries', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'TATACAP.NS', 'name': 'Tata Capital', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'TATACONSUM.NS', 'name': 'Tata Consumer Products', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'TATAPOWER.NS', 'name': 'Tata Power Co.', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'TATASTEEL.NS', 'name': 'Tata Steel', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'TECHM.NS', 'name': 'Tech Mahindra', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'TITAN.NS', 'name': 'Titan Company', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'TMCV.NS', 'name': 'Tata Motors (Commercial Vehicles)', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'TMPV.NS', 'name': 'Tata Motors Passenger Vehicles', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'TORNTPHARM.NS', 'name': 'Torrent Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'TRENT.NS', 'name': 'Trent', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'TVSMOTOR.NS', 'name': 'TVS Motor Company', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'ULTRACEMCO.NS', 'name': 'UltraTech Cement', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'UNIONBANK.NS', 'name': 'Union Bank of India', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'UNITDSPR.NS', 'name': 'United Spirits', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'VBL.NS', 'name': 'Varun Beverages', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'VEDL.NS', 'name': 'Vedanta', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'WIPRO.NS', 'name': 'Wipro', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'ZYDUSLIFE.NS', 'name': 'Zydus Lifesciences', 'sector': 'healthcare', 'marketCap': 'large'},
    ]

def get_nifty_200_stocks():
    """Nifty 200 stocks - comprehensive list of top 200 Indian companies"""
    return [
        {'symbol': 'ABB.NS', 'name': 'ABB India', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ACC.NS', 'name': 'ACC', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'APLAPOLLO.NS', 'name': 'APL Apollo Tubes', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'AUBANK.NS', 'name': 'AU Small Finance Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'ADANIENSOL.NS', 'name': 'Adani Energy Solutions', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'ADANIGREEN.NS', 'name': 'Adani Green Energy', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ADANIPORTS.NS', 'name': 'Adani Ports and Special Economic Zone', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'ADANIPOWER.NS', 'name': 'Adani Power', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ATGL.NS', 'name': 'Adani Total Gas', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ABCAPITAL.NS', 'name': 'Aditya Birla Capital', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'ABFRL.NS', 'name': 'Aditya Birla Fashion and Retail', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'ALKEM.NS', 'name': 'Alkem Laboratories', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'AMBUJACEM.NS', 'name': 'Ambuja Cements', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'APOLLOHOSP.NS', 'name': 'Apollo Hospitals Enterprise', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'APOLLOTYRE.NS', 'name': 'Apollo Tyres', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'ASHOKLEY.NS', 'name': 'Ashok Leyland', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ASIANPAINT.NS', 'name': 'Asian Paints', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'ASTRAL.NS', 'name': 'Astral', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'AUROPHARMA.NS', 'name': 'Aurobindo Pharma', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'DMART.NS', 'name': 'Avenue Supermarts', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'AXISBANK.NS', 'name': 'Axis Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BSE.NS', 'name': 'BSE', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJ-AUTO.NS', 'name': 'Bajaj Auto', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'BAJFINANCE.NS', 'name': 'Bajaj Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJFINSV.NS', 'name': 'Bajaj Finserv', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJHLDNG.NS', 'name': 'Bajaj Holdings & Investment', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BAJAJHFL.NS', 'name': 'Bajaj Housing Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BANDHANBNK.NS', 'name': 'Bandhan Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BANKBARODA.NS', 'name': 'Bank of Baroda', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BANKINDIA.NS', 'name': 'Bank of India', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'MAHABANK.NS', 'name': 'Bank of Maharashtra', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'BDL.NS', 'name': 'Bharat Dynamics', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'BEL.NS', 'name': 'Bharat Electronics', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'BHARATFORG.NS', 'name': 'Bharat Forge', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'BHEL.NS', 'name': 'Bharat Heavy Electricals', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'BPCL.NS', 'name': 'Bharat Petroleum Corporation', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel', 'sector': 'telecom', 'marketCap': 'large'},
        {'symbol': 'BHARTIHEXA.NS', 'name': 'Bharti Hexacom', 'sector': 'telecom', 'marketCap': 'large'},
        {'symbol': 'BIOCON.NS', 'name': 'Biocon', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'BOSCHLTD.NS', 'name': 'Bosch', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'BRITANNIA.NS', 'name': 'Britannia Industries', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'CGPOWER.NS', 'name': 'CG Power and Industrial Solutions', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'CANBK.NS', 'name': 'Canara Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'CHOLAFIN.NS', 'name': 'Cholamandalam Investment and Finance Company', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'CIPLA.NS', 'name': 'Cipla', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'COALINDIA.NS', 'name': 'Coal India', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'COCHINSHIP.NS', 'name': 'Cochin Shipyard', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'COFORGE.NS', 'name': 'Coforge', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'COLPAL.NS', 'name': 'Colgate Palmolive (India)', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'CONCOR.NS', 'name': 'Container Corporation of India', 'sector': 'infrastructure', 'marketCap': 'mid'},
        {'symbol': 'CUMMINSIND.NS', 'name': 'Cummins India', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'DLF.NS', 'name': 'DLF', 'sector': 'realty', 'marketCap': 'mid'},
        {'symbol': 'DABUR.NS', 'name': 'Dabur India', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'DIVISLAB.NS', 'name': 'Divi\'s Laboratories', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'DIXON.NS', 'name': 'Dixon Technologies (India)', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'DRREDDY.NS', 'name': 'Dr. Reddy\'s Laboratories', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'EICHERMOT.NS', 'name': 'Eicher Motors', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'ESCORTS.NS', 'name': 'Escorts Kubota', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'EXIDEIND.NS', 'name': 'Exide Industries', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'NYKAA.NS', 'name': 'FSN E-Commerce Ventures', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'FEDERALBNK.NS', 'name': 'Federal Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'GAIL.NS', 'name': 'GAIL (India)', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'GMRAIRPORT.NS', 'name': 'GMR Airports', 'sector': 'infrastructure', 'marketCap': 'mid'},
        {'symbol': 'GLENMARK.NS', 'name': 'Glenmark Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'GODREJCP.NS', 'name': 'Godrej Consumer Products', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'GODREJPROP.NS', 'name': 'Godrej Properties', 'sector': 'realty', 'marketCap': 'mid'},
        {'symbol': 'GRASIM.NS', 'name': 'Grasim Industries', 'sector': 'cement', 'marketCap': 'mid'},
        {'symbol': 'HCLTECH.NS', 'name': 'HCL Technologies', 'sector': 'it', 'marketCap': 'mid'},
        {'symbol': 'HDFCAMC.NS', 'name': 'HDFC Asset Management Company', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'HDFCLIFE.NS', 'name': 'HDFC Life Insurance Company', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'HAVELLS.NS', 'name': 'Havells India', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'HEROMOTOCO.NS', 'name': 'Hero MotoCorp', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'HINDALCO.NS', 'name': 'Hindalco Industries', 'sector': 'metals', 'marketCap': 'mid'},
        {'symbol': 'HAL.NS', 'name': 'Hindustan Aeronautics', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'HINDPETRO.NS', 'name': 'Hindustan Petroleum Corporation', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'HINDZINC.NS', 'name': 'Hindustan Zinc', 'sector': 'metals', 'marketCap': 'mid'},
        {'symbol': 'HUDCO.NS', 'name': 'Housing & Urban Development Corporation', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'HYUNDAI.NS', 'name': 'Hyundai Motor India', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'ICICIGI.NS', 'name': 'ICICI Lombard General Insurance Company', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'ICICIPRULI.NS', 'name': 'ICICI Prudential Life Insurance Company', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'IDFCFIRSTB.NS', 'name': 'IDFC First Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'IRB.NS', 'name': 'IRB Infrastructure Developers', 'sector': 'construction', 'marketCap': 'mid'},
        {'symbol': 'ITC.NS', 'name': 'ITC', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'INDIANB.NS', 'name': 'Indian Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'INDHOTEL.NS', 'name': 'Indian Hotels Co.', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'IOC.NS', 'name': 'Indian Oil Corporation', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'IRCTC.NS', 'name': 'Indian Railway Catering And Tourism Corporation', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'IRFC.NS', 'name': 'Indian Railway Finance Corporation', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'IREDA.NS', 'name': 'Indian Renewable Energy Development Agency', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'IGL.NS', 'name': 'Indraprastha Gas', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'INDUSTOWER.NS', 'name': 'Indus Towers', 'sector': 'telecom', 'marketCap': 'mid'},
        {'symbol': 'INDUSINDBK.NS', 'name': 'IndusInd Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'NAUKRI.NS', 'name': 'Info Edge (India)', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'INFY.NS', 'name': 'Infosys', 'sector': 'it', 'marketCap': 'mid'},
        {'symbol': 'INDIGO.NS', 'name': 'InterGlobe Aviation', 'sector': 'infrastructure', 'marketCap': 'mid'},
        {'symbol': 'JSWENERGY.NS', 'name': 'JSW Energy', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'JSWINFRA.NS', 'name': 'JSW Infrastructure', 'sector': 'infrastructure', 'marketCap': 'small'},
        {'symbol': 'JSWSTEEL.NS', 'name': 'JSW Steel', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'JINDALSTEL.NS', 'name': 'Jindal Steel & Power', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'JIOFIN.NS', 'name': 'Jio Financial Services', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'JUBLFOOD.NS', 'name': 'Jubilant FoodWorks', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'KPITTECH.NS', 'name': 'KPIT Technologies', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'KANSAINER.NS', 'name': 'Kansai Nerolac Paints', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'KEI.NS', 'name': 'KEI Industries', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'LTIM.NS', 'name': 'LTIMindtree', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'LTTS.NS', 'name': 'L&T Technology Services', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'construction', 'marketCap': 'small'},
        {'symbol': 'LICHSGFIN.NS', 'name': 'LIC Housing Finance', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'LICI.NS', 'name': 'Life Insurance Corporation of India', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'LODHA.NS', 'name': 'Lodha Developers', 'sector': 'realty', 'marketCap': 'small'},
        {'symbol': 'LUPIN.NS', 'name': 'Lupin', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'M&M.NS', 'name': 'Mahindra & Mahindra', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'M&MFIN.NS', 'name': 'Mahindra & Mahindra Financial Services', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'MFSL.NS', 'name': 'Max Financial Services', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'MGL.NS', 'name': 'Mahanagar Gas', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'MAHINDCIE.NS', 'name': 'Mahindra CIE Automotive', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'MANAPPURAM.NS', 'name': 'Manappuram Finance', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'MARICO.NS', 'name': 'Marico', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'METROPOLIS.NS', 'name': 'Metropolis Healthcare', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'MRF.NS', 'name': 'MRF', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'MOTHERSON.NS', 'name': 'Samvardhana Motherson International', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'MPHASIS.NS', 'name': 'Mphasis', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'MRPL.NS', 'name': 'Mangalore Refinery and Petrochemicals', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'MUTHOOTFIN.NS', 'name': 'Muthoot Finance', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'NATIONALUM.NS', 'name': 'National Aluminium Company', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'NIACL.NS', 'name': 'The New India Assurance Company', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'NMDC.NS', 'name': 'NMDC', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'NTPC.NS', 'name': 'NTPC', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'NESTLEIND.NS', 'name': 'Nestle India', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'OBEROIRLTY.NS', 'name': 'Oberoi Realty', 'sector': 'realty', 'marketCap': 'small'},
        {'symbol': 'ONGC.NS', 'name': 'Oil & Natural Gas Corporation', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'OIL.NS', 'name': 'Oil India', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'PAYTM.NS', 'name': 'One 97 Communications', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'PAGEIND.NS', 'name': 'Page Industries', 'sector': 'textiles', 'marketCap': 'small'},
        {'symbol': 'PERSISTENT.NS', 'name': 'Persistent Systems', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'PETRONET.NS', 'name': 'Petronet LNG', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'PFIZER.NS', 'name': 'Pfizer', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'PIDILITIND.NS', 'name': 'Pidilite Industries', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'PIIND.NS', 'name': 'PI Industries', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'PFC.NS', 'name': 'Power Finance Corporation', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'POWERGRID.NS', 'name': 'Power Grid Corporation of India', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'PRESTIGE.NS', 'name': 'Prestige Estates Projects', 'sector': 'realty', 'marketCap': 'small'},
        {'symbol': 'PVRINOX.NS', 'name': 'PVR INOX', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'PNB.NS', 'name': 'Punjab National Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'POLYCAB.NS', 'name': 'Polycab India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'RBLBANK.NS', 'name': 'RBL Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'RECLTD.NS', 'name': 'REC', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'SAIL.NS', 'name': 'Steel Authority of India', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'SBICARD.NS', 'name': 'SBI Cards and Payment Services', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'SBILIFE.NS', 'name': 'SBI Life Insurance Company', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'SJVN.NS', 'name': 'SJVN', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'SKFINDIA.NS', 'name': 'SKF India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'SOBHA.NS', 'name': 'Sobha', 'sector': 'realty', 'marketCap': 'small'},
        {'symbol': 'SOLARINDS.NS', 'name': 'Solar Industries India', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'SONACOMS.NS', 'name': 'Sona BLW Precision Forgings', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'SHREECEM.NS', 'name': 'Shree Cement', 'sector': 'cement', 'marketCap': 'small'},
        {'symbol': 'SHRIRAMFIN.NS', 'name': 'Shriram Finance', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'SIEMENS.NS', 'name': 'Siemens', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Industries', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'SUNTV.NS', 'name': 'Sun TV Network', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'SWIGGY.NS', 'name': 'Swiggy', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'SYMPHONY.NS', 'name': 'Symphony', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'SYNGENE.NS', 'name': 'Syngene International', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'TVSMOTOR.NS', 'name': 'TVS Motor Company', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'TATACOMM.NS', 'name': 'Tata Communications', 'sector': 'telecom', 'marketCap': 'small'},
        {'symbol': 'TATACONSUM.NS', 'name': 'Tata Consumer Products', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'TATAELXSI.NS', 'name': 'Tata Elxsi', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'TATAMOTORS.NS', 'name': 'Tata Motors', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'TATAPOWER.NS', 'name': 'Tata Power Co.', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'TATASTEEL.NS', 'name': 'Tata Steel', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'TECHM.NS', 'name': 'Tech Mahindra', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'THERMAX.NS', 'name': 'Thermax', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'TIINDIA.NS', 'name': 'Tube Investments of India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'TITAN.NS', 'name': 'Titan Company', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'TORNTPHARM.NS', 'name': 'Torrent Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'TRENT.NS', 'name': 'Trent', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'TTML.NS', 'name': 'Tata Teleservices (Maharashtra)', 'sector': 'telecom', 'marketCap': 'small'},
        {'symbol': 'UBL.NS', 'name': 'United Breweries', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'ULTRACEMCO.NS', 'name': 'UltraTech Cement', 'sector': 'cement', 'marketCap': 'small'},
        {'symbol': 'UNIONBANK.NS', 'name': 'Union Bank of India', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'UNITDSPR.NS', 'name': 'United Spirits', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'UPL.NS', 'name': 'UPL', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'VBL.NS', 'name': 'Varun Beverages', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'VEDL.NS', 'name': 'Vedanta', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'VINATIORGA.NS', 'name': 'Vinati Organics', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'VOLTAS.NS', 'name': 'Voltas', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'WHIRLPOOL.NS', 'name': 'Whirlpool of India', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'WIPRO.NS', 'name': 'Wipro', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'YESBANK.NS', 'name': 'Yes Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'ZYDUSLIFE.NS', 'name': 'Zydus Lifesciences', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'ZEEL.NS', 'name': 'Zee Entertainment Enterprises', 'sector': 'consumer', 'marketCap': 'small'}
    ]
    
def get_nifty_500_stocks():
    """Nifty 500 stocks - comprehensive list of top 500+ Indian companies"""
    return [
    # ── NIFTY 100 (large cap) ───────────────────────────────────────────────
    {'symbol': 'ABB.NS', 'name': 'ABB India', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'ADANIENSOL.NS', 'name': 'Adani Energy Solutions', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'ADANIGREEN.NS', 'name': 'Adani Green Energy', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'ADANIPORTS.NS', 'name': 'Adani Ports and Special Economic Zone', 'sector': 'infrastructure', 'marketCap': 'large'},
    {'symbol': 'ADANIPOWER.NS', 'name': 'Adani Power', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'AMBUJACEM.NS', 'name': 'Ambuja Cements', 'sector': 'cement', 'marketCap': 'large'},
    {'symbol': 'APOLLOHOSP.NS', 'name': 'Apollo Hospitals Enterprise', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ASIANPAINT.NS', 'name': 'Asian Paints', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'AXISBANK.NS', 'name': 'Axis Bank', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'BAJAJ-AUTO.NS', 'name': 'Bajaj Auto', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'BAJAJFINSV.NS', 'name': 'Bajaj Finserv', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'BAJAJHLDNG.NS', 'name': 'Bajaj Holdings & Investment', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'BAJFINANCE.NS', 'name': 'Bajaj Finance', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'BANKBARODA.NS', 'name': 'Bank of Baroda', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'BEL.NS', 'name': 'Bharat Electronics', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel', 'sector': 'telecom', 'marketCap': 'large'},
    {'symbol': 'BOSCHLTD.NS', 'name': 'Bosch', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'BPCL.NS', 'name': 'Bharat Petroleum Corporation', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'BRITANNIA.NS', 'name': 'Britannia Industries', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'CANBK.NS', 'name': 'Canara Bank', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'CGPOWER.NS', 'name': 'CG Power and Industrial Solutions', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'CHOLAFIN.NS', 'name': 'Cholamandalam Investment and Finance Company', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'CIPLA.NS', 'name': 'Cipla', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'COALINDIA.NS', 'name': 'Coal India', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'CUMMINSIND.NS', 'name': 'Cummins India', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'DIVISLAB.NS', 'name': "Divi's Laboratories", 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'DLF.NS', 'name': 'DLF', 'sector': 'realty', 'marketCap': 'large'},
    {'symbol': 'DMART.NS', 'name': 'Avenue Supermarts', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'DRREDDY.NS', 'name': "Dr. Reddy's Laboratories", 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'EICHERMOT.NS', 'name': 'Eicher Motors', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'ENRIN.NS', 'name': 'Siemens Energy India', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'GAIL.NS', 'name': 'GAIL (India)', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'GODREJCP.NS', 'name': 'Godrej Consumer Products', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'GRASIM.NS', 'name': 'Grasim Industries', 'sector': 'cement', 'marketCap': 'large'},
    {'symbol': 'HAL.NS', 'name': 'Hindustan Aeronautics', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'HCLTECH.NS', 'name': 'HCL Technologies', 'sector': 'it', 'marketCap': 'large'},
    {'symbol': 'HDFCAMC.NS', 'name': 'HDFC Asset Management Company', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'HDFCLIFE.NS', 'name': 'HDFC Life Insurance Company', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'HINDALCO.NS', 'name': 'Hindalco Industries', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'HINDZINC.NS', 'name': 'Hindustan Zinc', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'HYUNDAI.NS', 'name': 'Hyundai Motor India', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'INDHOTEL.NS', 'name': 'Indian Hotels Co.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'INDIGO.NS', 'name': 'InterGlobe Aviation', 'sector': 'infrastructure', 'marketCap': 'large'},
    {'symbol': 'INFY.NS', 'name': 'Infosys', 'sector': 'it', 'marketCap': 'large'},
    {'symbol': 'IOC.NS', 'name': 'Indian Oil Corporation', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'IRFC.NS', 'name': 'Indian Railway Finance Corporation', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'ITC.NS', 'name': 'ITC', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'JINDALSTEL.NS', 'name': 'Jindal Steel & Power', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'JIOFIN.NS', 'name': 'Jio Financial Services', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'JSWSTEEL.NS', 'name': 'JSW Steel', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'LODHA.NS', 'name': 'Lodha Developers', 'sector': 'realty', 'marketCap': 'large'},
    {'symbol': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'construction', 'marketCap': 'large'},
    {'symbol': 'LTM.NS', 'name': 'LTM (formerly LTIMindtree)', 'sector': 'it', 'marketCap': 'large'},
    {'symbol': 'M&M.NS', 'name': 'Mahindra & Mahindra', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'MAXHEALTH.NS', 'name': 'Max Healthcare Institute', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MAZDOCK.NS', 'name': 'Mazagon Dock Shipbuilders', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'MOTHERSON.NS', 'name': 'Samvardhana Motherson International', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'MUTHOOTFIN.NS', 'name': 'Muthoot Finance', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'NESTLEIND.NS', 'name': 'Nestle India', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'NTPC.NS', 'name': 'NTPC', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'ONGC.NS', 'name': 'Oil & Natural Gas Corporation', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'PFC.NS', 'name': 'Power Finance Corporation', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'PIDILITIND.NS', 'name': 'Pidilite Industries', 'sector': 'chemicals', 'marketCap': 'large'},
    {'symbol': 'PNB.NS', 'name': 'Punjab National Bank', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'POWERGRID.NS', 'name': 'Power Grid Corporation of India', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'RECLTD.NS', 'name': 'REC', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'SBILIFE.NS', 'name': 'SBI Life Insurance Company', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'SHREECEM.NS', 'name': 'Shree Cement', 'sector': 'cement', 'marketCap': 'large'},
    {'symbol': 'SHRIRAMFIN.NS', 'name': 'Shriram Finance', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'SIEMENS.NS', 'name': 'Siemens', 'sector': 'capital_goods', 'marketCap': 'large'},
    {'symbol': 'SOLARINDS.NS', 'name': 'Solar Industries India', 'sector': 'chemicals', 'marketCap': 'large'},
    {'symbol': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Industries', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'TATACAP.NS', 'name': 'Tata Capital', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'TATACONSUM.NS', 'name': 'Tata Consumer Products', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'TATAPOWER.NS', 'name': 'Tata Power Co.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'TATASTEEL.NS', 'name': 'Tata Steel', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'it', 'marketCap': 'large'},
    {'symbol': 'TECHM.NS', 'name': 'Tech Mahindra', 'sector': 'it', 'marketCap': 'large'},
    {'symbol': 'TITAN.NS', 'name': 'Titan Company', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'TMCV.NS', 'name': 'Tata Motors (Commercial Vehicles)', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'TMPV.NS', 'name': 'Tata Motors Passenger Vehicles', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'TORNTPHARM.NS', 'name': 'Torrent Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'TRENT.NS', 'name': 'Trent', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'TVSMOTOR.NS', 'name': 'TVS Motor Company', 'sector': 'auto', 'marketCap': 'large'},
    {'symbol': 'ULTRACEMCO.NS', 'name': 'UltraTech Cement', 'sector': 'cement', 'marketCap': 'large'},
    {'symbol': 'UNIONBANK.NS', 'name': 'Union Bank of India', 'sector': 'banking', 'marketCap': 'large'},
    {'symbol': 'UNITDSPR.NS', 'name': 'United Spirits', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'VBL.NS', 'name': 'Varun Beverages', 'sector': 'fmcg', 'marketCap': 'large'},
    {'symbol': 'VEDL.NS', 'name': 'Vedanta', 'sector': 'metals', 'marketCap': 'large'},
    {'symbol': 'WIPRO.NS', 'name': 'Wipro', 'sector': 'it', 'marketCap': 'large'},
    {'symbol': 'ZYDUSLIFE.NS', 'name': 'Zydus Lifesciences', 'sector': 'healthcare', 'marketCap': 'large'},
 
    # ── NIFTY 101–200 (mid cap) ─────────────────────────────────────────────
    {'symbol': '360ONE.NS', 'name': '360 One WAM', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'ABCAPITAL.NS', 'name': 'Aditya Birla Capital', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'ALKEM.NS', 'name': 'Alkem Laboratories', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'APLAPOLLO.NS', 'name': 'APL Apollo Tubes', 'sector': 'metals', 'marketCap': 'mid'},
    {'symbol': 'ASHOKLEY.NS', 'name': 'Ashok Leyland', 'sector': 'auto', 'marketCap': 'mid'},
    {'symbol': 'ASTRAL.NS', 'name': 'Astral', 'sector': 'chemicals', 'marketCap': 'mid'},
    {'symbol': 'ATGL.NS', 'name': 'Adani Total Gas', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'AUBANK.NS', 'name': 'AU Small Finance Bank', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'AUROPHARMA.NS', 'name': 'Aurobindo Pharma', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'BANKINDIA.NS', 'name': 'Bank of India', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'BDL.NS', 'name': 'Bharat Dynamics', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'BHARATFORG.NS', 'name': 'Bharat Forge', 'sector': 'auto', 'marketCap': 'mid'},
    {'symbol': 'BHEL.NS', 'name': 'Bharat Heavy Electricals', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'BIOCON.NS', 'name': 'Biocon', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'BLUESTARCO.NS', 'name': 'Blue Star', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'BSE.NS', 'name': 'BSE', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'COCHINSHIP.NS', 'name': 'Cochin Shipyard', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'COFORGE.NS', 'name': 'Coforge', 'sector': 'it', 'marketCap': 'mid'},
    {'symbol': 'COLPAL.NS', 'name': 'Colgate-Palmolive (India)', 'sector': 'fmcg', 'marketCap': 'mid'},
    {'symbol': 'CONCOR.NS', 'name': 'Container Corporation of India', 'sector': 'infrastructure', 'marketCap': 'mid'},
    {'symbol': 'COROMANDEL.NS', 'name': 'Coromandel International', 'sector': 'chemicals', 'marketCap': 'mid'},
    {'symbol': 'DABUR.NS', 'name': 'Dabur India', 'sector': 'fmcg', 'marketCap': 'mid'},
    {'symbol': 'DIXON.NS', 'name': 'Dixon Technologies', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'EXIDEIND.NS', 'name': 'Exide Industries', 'sector': 'auto', 'marketCap': 'mid'},
    {'symbol': 'FEDERALBNK.NS', 'name': 'Federal Bank', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'FORTIS.NS', 'name': 'Fortis Healthcare', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'GLENMARK.NS', 'name': 'Glenmark Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'GMRAIRPORT.NS', 'name': 'GMR Airports Infrastructure', 'sector': 'infrastructure', 'marketCap': 'mid'},
    {'symbol': 'GODFRYPHLP.NS', 'name': 'Godfrey Phillips India', 'sector': 'fmcg', 'marketCap': 'mid'},
    {'symbol': 'GODREJPROP.NS', 'name': 'Godrej Properties', 'sector': 'realty', 'marketCap': 'mid'},
    {'symbol': 'GROWW.NS', 'name': 'Billionbrains Garage Ventures (Groww)', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'GVT&D.NS', 'name': 'GE Vernova T&D India', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'HAVELLS.NS', 'name': 'Havells India', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'HEROMOTOCO.NS', 'name': 'Hero MotoCorp', 'sector': 'auto', 'marketCap': 'mid'},
    {'symbol': 'HINDPETRO.NS', 'name': 'Hindustan Petroleum Corporation', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'HUDCO.NS', 'name': 'Housing and Urban Development Corporation', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'ICICIAMC.NS', 'name': 'ICICI Prudential AMC', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'ICICIGI.NS', 'name': 'ICICI Lombard General Insurance', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'IDEA.NS', 'name': 'Vodafone Idea', 'sector': 'telecom', 'marketCap': 'mid'},
    {'symbol': 'IDFCFIRSTB.NS', 'name': 'IDFC First Bank', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'INDIANB.NS', 'name': 'Indian Bank', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'INDUSINDBK.NS', 'name': 'IndusInd Bank', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'INDUSTOWER.NS', 'name': 'Indus Towers', 'sector': 'telecom', 'marketCap': 'mid'},
    {'symbol': 'IRCTC.NS', 'name': 'Indian Railway Catering and Tourism Corporation', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'IREDA.NS', 'name': 'Indian Renewable Energy Development Agency', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'JSWENERGY.NS', 'name': 'JSW Energy', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'JUBLFOOD.NS', 'name': 'Jubilant Foodworks', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'KALYANKJIL.NS', 'name': 'Kalyan Jewellers India', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'KEI.NS', 'name': 'KEI Industries', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'KPITTECH.NS', 'name': 'KPIT Technologies', 'sector': 'it', 'marketCap': 'mid'},
    {'symbol': 'LAURUSLABS.NS', 'name': 'Laurus Labs', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'LENSKART.NS', 'name': 'Lenskart Solutions', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'LGEINDIA.NS', 'name': 'LG Electronics India', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'LICHSGFIN.NS', 'name': 'LIC Housing Finance', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'LTF.NS', 'name': 'L&T Finance', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'LUPIN.NS', 'name': 'Lupin', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'M&MFIN.NS', 'name': 'Mahindra & Mahindra Financial Services', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'MANKIND.NS', 'name': 'Mankind Pharma', 'sector': 'healthcare', 'marketCap': 'mid'},
    {'symbol': 'MARICO.NS', 'name': 'Marico', 'sector': 'fmcg', 'marketCap': 'mid'},
    {'symbol': 'MCX.NS', 'name': 'Multi Commodity Exchange of India', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'MFSL.NS', 'name': 'Max Financial Services', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'MOTILALOFS.NS', 'name': 'Motilal Oswal Financial Services', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'MPHASIS.NS', 'name': 'Mphasis', 'sector': 'it', 'marketCap': 'mid'},
    {'symbol': 'MRF.NS', 'name': 'MRF', 'sector': 'auto', 'marketCap': 'mid'},
    {'symbol': 'NATIONALUM.NS', 'name': 'National Aluminium Company', 'sector': 'metals', 'marketCap': 'mid'},
    {'symbol': 'NAUKRI.NS', 'name': 'Info Edge (India)', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'NHPC.NS', 'name': 'NHPC', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'NMDC.NS', 'name': 'NMDC', 'sector': 'metals', 'marketCap': 'mid'},
    {'symbol': 'NYKAA.NS', 'name': 'FSN E-Commerce Ventures (Nykaa)', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'OBEROIRLTY.NS', 'name': 'Oberoi Realty', 'sector': 'realty', 'marketCap': 'mid'},
    {'symbol': 'OFSS.NS', 'name': 'Oracle Financial Services Software', 'sector': 'it', 'marketCap': 'mid'},
    {'symbol': 'OIL.NS', 'name': 'Oil India', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'PAGEIND.NS', 'name': 'Page Industries', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'PATANJALI.NS', 'name': 'Patanjali Foods', 'sector': 'fmcg', 'marketCap': 'mid'},
    {'symbol': 'PAYTM.NS', 'name': 'One 97 Communications (Paytm)', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'PERSISTENT.NS', 'name': 'Persistent Systems', 'sector': 'it', 'marketCap': 'mid'},
    {'symbol': 'PHOENIXLTD.NS', 'name': 'Phoenix Mills', 'sector': 'realty', 'marketCap': 'mid'},
    {'symbol': 'PIIND.NS', 'name': 'PI Industries', 'sector': 'chemicals', 'marketCap': 'mid'},
    {'symbol': 'POLICYBZR.NS', 'name': 'PB Fintech (Policybazaar)', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'POLYCAB.NS', 'name': 'Polycab India', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'POWERINDIA.NS', 'name': 'Hitachi Energy India', 'sector': 'capital_goods', 'marketCap': 'mid'},
    {'symbol': 'PREMIERENE.NS', 'name': 'Premier Energies', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'PRESTIGE.NS', 'name': 'Prestige Estates Projects', 'sector': 'realty', 'marketCap': 'mid'},
    {'symbol': 'RADICO.NS', 'name': 'Radico Khaitan', 'sector': 'fmcg', 'marketCap': 'mid'},
    {'symbol': 'RVNL.NS', 'name': 'Rail Vikas Nigam', 'sector': 'infrastructure', 'marketCap': 'mid'},
    {'symbol': 'SAIL.NS', 'name': 'Steel Authority of India', 'sector': 'metals', 'marketCap': 'mid'},
    {'symbol': 'SBICARD.NS', 'name': 'SBI Cards and Payment Services', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'SRF.NS', 'name': 'SRF', 'sector': 'chemicals', 'marketCap': 'mid'},
    {'symbol': 'SUPREMEIND.NS', 'name': 'Supreme Industries', 'sector': 'chemicals', 'marketCap': 'mid'},
    {'symbol': 'SUZLON.NS', 'name': 'Suzlon Energy', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'SWIGGY.NS', 'name': 'Swiggy', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'TATACOMM.NS', 'name': 'Tata Communications', 'sector': 'telecom', 'marketCap': 'mid'},
    {'symbol': 'TATAELXSI.NS', 'name': 'Tata Elxsi', 'sector': 'it', 'marketCap': 'mid'},
    {'symbol': 'TATAINVEST.NS', 'name': 'Tata Investment Corporation', 'sector': 'banking', 'marketCap': 'mid'},
    {'symbol': 'TIINDIA.NS', 'name': 'Tube Investments of India', 'sector': 'auto', 'marketCap': 'mid'},
    {'symbol': 'UPL.NS', 'name': 'UPL', 'sector': 'chemicals', 'marketCap': 'mid'},
    {'symbol': 'VMM.NS', 'name': 'Vishal Mega Mart', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'VOLTAS.NS', 'name': 'Voltas', 'sector': 'consumer', 'marketCap': 'mid'},
    {'symbol': 'WAAREEENER.NS', 'name': 'Waaree Energies', 'sector': 'energy', 'marketCap': 'mid'},
    {'symbol': 'YESBANK.NS', 'name': 'Yes Bank', 'sector': 'banking', 'marketCap': 'mid'},
 
    # ── NIFTY 201–500 (small cap) ───────────────────────────────────────────
    {'symbol': '3MINDIA.NS', 'name': '3M India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'AADHARHFC.NS', 'name': 'Aadhaar Housing Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'AARTIIND.NS', 'name': 'Aarti Industries', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'AAVAS.NS', 'name': 'Aavas Financiers', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'ABBOTINDIA.NS', 'name': 'Abbott India', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'ABDL.NS', 'name': 'Allied Blenders and Distillers', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'ABFRL.NS', 'name': 'Aditya Birla Fashion and Retail', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ABLBL.NS', 'name': 'Aditya Birla Lifestyle Brands', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ABREL.NS', 'name': 'Aditya Birla Real Estate', 'sector': 'realty', 'marketCap': 'small'},
    {'symbol': 'ABSLAMC.NS', 'name': 'Aditya Birla Sun Life AMC', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'ACC.NS', 'name': 'ACC', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'ACE.NS', 'name': 'Action Construction Equipment', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'ACMESOLAR.NS', 'name': 'ACME Solar Holdings', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'ACUTAAS.NS', 'name': 'Acutas AI', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'AEGISLOG.NS', 'name': 'Aegis Logistics', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'AEGISVOPAK.NS', 'name': 'Aegis Vopak Terminals', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'AFCONS.NS', 'name': 'Afcons Infrastructure', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'AFFLE.NS', 'name': 'Affle (India)', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'AIAENG.NS', 'name': 'AIA Engineering', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'AIIL.NS', 'name': 'Anand I Power', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'AJANTPHARM.NS', 'name': 'Ajanta Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'AMBER.NS', 'name': 'Amber Enterprises India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ANANDRATHI.NS', 'name': 'Anand Rathi Wealth', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'ANANTRAJ.NS', 'name': 'Anant Raj', 'sector': 'realty', 'marketCap': 'small'},
    {'symbol': 'ANGELONE.NS', 'name': 'Angel One', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'ANTHEM.NS', 'name': 'Anthem Biosciences', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'ANURAS.NS', 'name': 'Anupam Rasayan India', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'APARINDS.NS', 'name': 'Apar Industries', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'APOLLOTYRE.NS', 'name': 'Apollo Tyres', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'APTUS.NS', 'name': 'Aptus Value Housing Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'ARE&M.NS', 'name': 'Amara Raja Energy & Mobility', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'ASAHIINDIA.NS', 'name': 'Asahi India Glass', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'ASTERDM.NS', 'name': 'Aster DM Healthcare', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'ATHERENERG.NS', 'name': 'Ather Energy', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'ATUL.NS', 'name': 'Atul', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'AWL.NS', 'name': 'Adani Wilmar', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'BAJAJHFL.NS', 'name': 'Bajaj Housing Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'BALKRISIND.NS', 'name': 'Balkrishna Industries', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'BALRAMCHIN.NS', 'name': 'Balrampur Chini Mills', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'BANDHANBNK.NS', 'name': 'Bandhan Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'BATAINDIA.NS', 'name': 'Bata India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'BAYERCROP.NS', 'name': 'Bayer Cropscience', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'BBTC.NS', 'name': 'Bombay Burmah Trading Corporation', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'BELRISE.NS', 'name': 'Belrise Industries', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'BEML.NS', 'name': 'BEML', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'BERGEPAINT.NS', 'name': 'Berger Paints India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'BHARTIHEXA.NS', 'name': 'Bharti Hexacom', 'sector': 'telecom', 'marketCap': 'small'},
    {'symbol': 'BIKAJI.NS', 'name': 'Bikaji Foods International', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'BLS.NS', 'name': 'BLS International Services', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'BLUEDART.NS', 'name': 'Blue Dart Express', 'sector': 'infrastructure', 'marketCap': 'small'},
    {'symbol': 'BLUEJET.NS', 'name': 'Blue Jet Healthcare', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'BRIGADE.NS', 'name': 'Brigade Enterprises', 'sector': 'realty', 'marketCap': 'small'},
    {'symbol': 'BSOFT.NS', 'name': 'Birlasoft', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'CAMS.NS', 'name': 'Computer Age Management Services', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CANFINHOME.NS', 'name': 'Can Fin Homes', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CANHLIFE.NS', 'name': 'Canara HSBC Life Insurance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CAPLIPOINT.NS', 'name': 'Caplin Point Laboratories', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'CARBORUNIV.NS', 'name': 'Carborundum Universal', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'CARTRADE.NS', 'name': 'CarTrade Tech', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'CASTROLIND.NS', 'name': 'Castrol India', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'CCL.NS', 'name': 'CCL Products India', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'CDSL.NS', 'name': 'Central Depository Services (India)', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CEATLTD.NS', 'name': 'CEAT', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'CEMPRO.NS', 'name': 'Cement Products of India', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'CENTRALBK.NS', 'name': 'Central Bank of India', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CESC.NS', 'name': 'CESC', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'CGCL.NS', 'name': 'Capri Global Capital', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CHALET.NS', 'name': 'Chalet Hotels', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'CHAMBLFERT.NS', 'name': 'Chambal Fertilizers & Chemicals', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'CHENNPETRO.NS', 'name': 'Chennai Petroleum Corporation', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'CHOICEIN.NS', 'name': 'Choice International', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CHOLAHLDNG.NS', 'name': 'Cholamandalam Financial Holdings', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CIEINDIA.NS', 'name': 'CIE Automotive India', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'CLEAN.NS', 'name': 'Clean Science and Technology', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'COHANCE.NS', 'name': 'Cohance Lifesciences', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'CONCORDBIO.NS', 'name': 'Concord Biotech', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'CPPLUS.NS', 'name': 'Aditya Infotech (CP Plus)', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'CRAFTSMAN.NS', 'name': 'Craftsman Automation', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'CREDITACC.NS', 'name': 'CreditAccess Grameen', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CRISIL.NS', 'name': 'CRISIL', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CROMPTON.NS', 'name': 'Crompton Greaves Consumer Electricals', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'CUB.NS', 'name': 'City Union Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'CYIENT.NS', 'name': 'Cyient', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'DALBHARAT.NS', 'name': 'Dalmia Bharat', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'DATAPATTNS.NS', 'name': 'Data Patterns (India)', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'DCMSHRIRAM.NS', 'name': 'DCM Shriram', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'DEEPAKFERT.NS', 'name': 'Deepak Fertilisers & Petrochemicals', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'DEEPAKNTR.NS', 'name': 'Deepak Nitrite', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'DELHIVERY.NS', 'name': 'Delhivery', 'sector': 'infrastructure', 'marketCap': 'small'},
    {'symbol': 'DEVYANI.NS', 'name': 'Devyani International', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'DOMS.NS', 'name': 'DOMS Industries', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ECLERX.NS', 'name': 'eClerx Services', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'EIDPARRY.NS', 'name': 'EID Parry (India)', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'EIHOTEL.NS', 'name': 'EIH (Oberoi Hotels)', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ELECON.NS', 'name': 'Elecon Engineering', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'ELGIEQUIP.NS', 'name': 'Elgi Equipments', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'EMAMILTD.NS', 'name': 'Emami', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'EMCURE.NS', 'name': 'Emcure Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'EMMVEE.NS', 'name': 'Emmvee Photovoltaic Power', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'ENDURANCE.NS', 'name': 'Endurance Technologies', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'ENGINERSIN.NS', 'name': 'Engineers India', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'ERIS.NS', 'name': 'Eris Lifesciences', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'ESCORTS.NS', 'name': 'Escorts Kubota', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'FACT.NS', 'name': 'Fertilisers and Chemicals Travancore', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'FINCABLES.NS', 'name': 'Finolex Cables', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'FIRSTCRY.NS', 'name': 'Brainbees Solutions (FirstCry)', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'FIVESTAR.NS', 'name': 'Five-Star Business Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'FLUOROCHEM.NS', 'name': 'Gujarat Fluorochemicals', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'FORCEMOT.NS', 'name': 'Force Motors', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'FSL.NS', 'name': 'Firstsource Solutions', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'GABRIEL.NS', 'name': 'Gabriel India', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'GALLANTT.NS', 'name': 'Gallantt Metal', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'GESHIP.NS', 'name': 'Great Eastern Shipping', 'sector': 'infrastructure', 'marketCap': 'small'},
    {'symbol': 'GICRE.NS', 'name': 'General Insurance Corporation of India', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'GILLETTE.NS', 'name': 'Gillette India', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'GLAND.NS', 'name': 'Gland Pharma', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'GLAXO.NS', 'name': 'GlaxoSmithKline Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'GMDCLTD.NS', 'name': 'Gujarat Mineral Development Corporation', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'GODIGIT.NS', 'name': 'Go Digit General Insurance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'GODREJIND.NS', 'name': 'Godrej Industries', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'GPIL.NS', 'name': 'Godawari Power & Ispat', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'GRANULES.NS', 'name': 'Granules India', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'GRAPHITE.NS', 'name': 'Graphite India', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'GRAVITA.NS', 'name': 'Gravita India', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'GRSE.NS', 'name': 'Garden Reach Shipbuilders & Engineers', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'HBLENGINE.NS', 'name': 'HBL Engineering', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'HDBFS.NS', 'name': 'HDB Financial Services', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'HEG.NS', 'name': 'HEG', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'HEXT.NS', 'name': 'Hexaware Technologies', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'HFCL.NS', 'name': 'HFCL', 'sector': 'telecom', 'marketCap': 'small'},
    {'symbol': 'HINDCOPPER.NS', 'name': 'Hindustan Copper', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'HOMEFIRST.NS', 'name': 'Home First Finance Company India', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'HONASA.NS', 'name': 'Honasa Consumer (Mamaearth)', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'HONAUT.NS', 'name': 'Honeywell Automation India', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'HSCL.NS', 'name': 'Himadri Speciality Chemical', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'ICICIPRULI.NS', 'name': 'ICICI Prudential Life Insurance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'IDBI.NS', 'name': 'IDBI Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'IEX.NS', 'name': 'Indian Energy Exchange', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'IFCI.NS', 'name': 'IFCI', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'IGIL.NS', 'name': 'India Grid Infrastructure', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'IGL.NS', 'name': 'Indraprastha Gas', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'IIFL.NS', 'name': 'IIFL Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'IKS.NS', 'name': 'IKS Health', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'INDGN.NS', 'name': 'Indegene', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'INDIACEM.NS', 'name': 'India Cements', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'INDIAMART.NS', 'name': 'IndiaMART InterMESH', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'INOXWIND.NS', 'name': 'Inox Wind', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'INTELLECT.NS', 'name': 'Intellect Design Arena', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'IOB.NS', 'name': 'Indian Overseas Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'IPCALAB.NS', 'name': 'Ipca Laboratories', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'IRB.NS', 'name': 'IRB Infrastructure Developers', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'IRCON.NS', 'name': 'IRCON International', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'ITCHOTELS.NS', 'name': 'ITC Hotels', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ITI.NS', 'name': 'ITI', 'sector': 'telecom', 'marketCap': 'small'},
    {'symbol': 'J&KBANK.NS', 'name': 'Jammu & Kashmir Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'JAINREC.NS', 'name': 'Jain Irrigation Systems (Recycling)', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'JBCHEPHARM.NS', 'name': 'JB Chemicals & Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'JBMA.NS', 'name': 'JBM Auto', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'JINDALSAW.NS', 'name': 'Jindal Saw', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'JKCEMENT.NS', 'name': 'JK Cement', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'JKTYRE.NS', 'name': 'JK Tyre & Industries', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'JMFINANCIL.NS', 'name': 'JM Financial', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'JPPOWER.NS', 'name': 'Jaiprakash Power Ventures', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'JSL.NS', 'name': 'Jindal Stainless', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'JSWCEMENT.NS', 'name': 'JSW Cement', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'JSWDULUX.NS', 'name': 'JSW Paints (Dulux India)', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'JSWINFRA.NS', 'name': 'JSW Infrastructure', 'sector': 'infrastructure', 'marketCap': 'small'},
    {'symbol': 'JUBLINGREA.NS', 'name': 'Jubilant Ingrevia', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'JUBLPHARMA.NS', 'name': 'Jubilant Pharmova', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'JWL.NS', 'name': 'Jupiter Wagons', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'JYOTICNC.NS', 'name': 'Jyoti CNC Automation', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'KAJARIACER.NS', 'name': 'Kajaria Ceramics', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'KARURVYSYA.NS', 'name': 'Karur Vysya Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'KAYNES.NS', 'name': 'Kaynes Technology India', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'KEC.NS', 'name': 'KEC International', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'KFINTECH.NS', 'name': 'KFin Technologies', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'KIMS.NS', 'name': 'Krishna Institute of Medical Sciences', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'KIRLOSENG.NS', 'name': 'Kirloskar Oil Engines', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'KPIL.NS', 'name': 'Kalpataru Projects International', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'KPRMILL.NS', 'name': 'KPR Mill', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'LALPATHLAB.NS', 'name': 'Dr Lal Path Labs', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'LATENTVIEW.NS', 'name': 'Latent View Analytics', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'LEMONTREE.NS', 'name': 'Lemon Tree Hotels', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'LICI.NS', 'name': 'Life Insurance Corporation of India', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'LINDEINDIA.NS', 'name': 'Linde India', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'LLOYDSME.NS', 'name': 'Lloyds Metals and Energy', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'LTFOODS.NS', 'name': 'LT Foods', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'LTTS.NS', 'name': 'L&T Technology Services', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'MAHABANK.NS', 'name': 'Bank of Maharashtra', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'MANAPPURAM.NS', 'name': 'Manappuram Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'MAPMYINDIA.NS', 'name': 'CE Info Systems (MapMyIndia)', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'MEDANTA.NS', 'name': 'Global Health (Medanta)', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'MEESHO.NS', 'name': 'Meesho (Fashnear Technologies)', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'MGL.NS', 'name': 'Mahanagar Gas', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'MINDACORP.NS', 'name': 'Minda Corporation', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'MMTC.NS', 'name': 'MMTC', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'MRPL.NS', 'name': 'Mangalore Refinery and Petrochemicals', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'MSUMI.NS', 'name': 'Motherson Sumi Wiring India', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'NAM-INDIA.NS', 'name': 'Nippon Life India Asset Management', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'NATCOPHARM.NS', 'name': 'NATCO Pharma', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'NAVA.NS', 'name': 'Nava', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'NAVINFLUOR.NS', 'name': 'Navin Fluorine International', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'NBCC.NS', 'name': 'NBCC (India)', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'NCC.NS', 'name': 'NCC', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'NETWEB.NS', 'name': 'Netweb Technologies India', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'NEULANDLAB.NS', 'name': 'Neuland Laboratories', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'NEWGEN.NS', 'name': 'Newgen Software Technologies', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'NH.NS', 'name': 'Narayana Hrudayalaya', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'NIACL.NS', 'name': 'New India Assurance Company', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'NIVABUPA.NS', 'name': 'Niva Bupa Health Insurance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'NLCINDIA.NS', 'name': 'NLC India', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'NSLNISP.NS', 'name': 'NMDC Steel', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'NTPCGREEN.NS', 'name': 'NTPC Green Energy', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'NUVAMA.NS', 'name': 'Nuvama Wealth Management', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'NUVOCO.NS', 'name': 'Nuvoco Vistas Corporation', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'OLAELEC.NS', 'name': 'Ola Electric Mobility', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'OLECTRA.NS', 'name': 'Olectra Greentech', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'ONESOURCE.NS', 'name': 'OneSource Specialty Pharma', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'PARADEEP.NS', 'name': 'Paradeep Phosphates', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'PCBL.NS', 'name': 'PCBL', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'PETRONET.NS', 'name': 'Petronet LNG', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'PFIZER.NS', 'name': 'Pfizer', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'PGEL.NS', 'name': 'PG Electroplast', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'PINELABS.NS', 'name': 'Pine Labs', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'PIRAMALFIN.NS', 'name': 'Piramal Enterprises', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'PNBHOUSING.NS', 'name': 'PNB Housing Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'POLYMED.NS', 'name': 'Poly Medicure', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'POONAWALLA.NS', 'name': 'Poonawalla Fincorp', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'PPLPHARMA.NS', 'name': 'Piramal Pharma', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'PTCIL.NS', 'name': 'PTC India', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'PVRINOX.NS', 'name': 'PVR INOX', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'PWL.NS', 'name': 'PW (PhysicsWallah)', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'RAILTEL.NS', 'name': 'RailTel Corporation of India', 'sector': 'telecom', 'marketCap': 'small'},
    {'symbol': 'RAINBOW.NS', 'name': 'Rainbow Childrens Medicare', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'RAMCOCEM.NS', 'name': 'Ramco Cements', 'sector': 'cement', 'marketCap': 'small'},
    {'symbol': 'RBLBANK.NS', 'name': 'RBL Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'REDINGTON.NS', 'name': 'Redington', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'RHIM.NS', 'name': 'RHI Magnesita India', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'RITES.NS', 'name': 'RITES', 'sector': 'construction', 'marketCap': 'small'},
    {'symbol': 'RKFORGE.NS', 'name': 'Ramkrishna Forgings', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'RPOWER.NS', 'name': 'Reliance Power', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'RRKABEL.NS', 'name': 'RR Kabel', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'SAGILITY.NS', 'name': 'Sagility India', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'SAILIFE.NS', 'name': 'SAI Life Sciences', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'SAMMAANCAP.NS', 'name': 'Sammaan Capital', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'SAPPHIRE.NS', 'name': 'Sapphire Foods India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'SARDAEN.NS', 'name': 'Sarda Energy & Minerals', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'SAREGAMA.NS', 'name': 'Saregama India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'SBFC.NS', 'name': 'SBFC Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'SCHAEFFLER.NS', 'name': 'Schaeffler India', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'SCHNEIDER.NS', 'name': 'Schneider Electric Infrastructure', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'SCI.NS', 'name': 'Shipping Corporation of India', 'sector': 'infrastructure', 'marketCap': 'small'},
    {'symbol': 'SHYAMMETL.NS', 'name': 'Shyam Metalics and Energy', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'SIGNATURE.NS', 'name': 'Signatureglobal (India)', 'sector': 'realty', 'marketCap': 'small'},
    {'symbol': 'SJVN.NS', 'name': 'SJVN', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'SOBHA.NS', 'name': 'Sobha', 'sector': 'realty', 'marketCap': 'small'},
    {'symbol': 'SONACOMS.NS', 'name': 'Sona BLW Precision Forgings', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'SONATSOFTW.NS', 'name': 'Sonata Software', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'SPLPETRO.NS', 'name': 'Supreme Petrochem', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'STARHEALTH.NS', 'name': 'Star Health and Allied Insurance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'SUMICHEM.NS', 'name': 'Sumitomo Chemical India', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'SUNDARMFIN.NS', 'name': 'Sundaram Finance', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'SUNTV.NS', 'name': 'Sun TV Network', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'SWANCORP.NS', 'name': 'Swan Energy', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'SYNGENE.NS', 'name': 'Syngene International', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'SYRMA.NS', 'name': 'Syrma SGS Technology', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TARIL.NS', 'name': 'Transindia Realty and Infra Logistics', 'sector': 'infrastructure', 'marketCap': 'small'},
    {'symbol': 'TATACHEM.NS', 'name': 'Tata Chemicals', 'sector': 'chemicals', 'marketCap': 'small'},
    {'symbol': 'TATATECH.NS', 'name': 'Tata Technologies', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'TBOTEK.NS', 'name': 'TBO Tek', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'TECHNOE.NS', 'name': 'Techno Electric & Engineering', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TEGA.NS', 'name': 'Tega Industries', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TEJASNET.NS', 'name': 'Tejas Networks', 'sector': 'telecom', 'marketCap': 'small'},
    {'symbol': 'TENNIND.NS', 'name': 'Tenneco India', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'THELEELA.NS', 'name': 'The Leela Palaces Hotels & Resorts', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'THERMAX.NS', 'name': 'Thermax', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TIMKEN.NS', 'name': 'Timken India', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TITAGARH.NS', 'name': 'Titagarh Rail Systems', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TORNTPOWER.NS', 'name': 'Torrent Power', 'sector': 'energy', 'marketCap': 'small'},
    {'symbol': 'TRAVELFOOD.NS', 'name': 'Travel Food Services', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'TRIDENT.NS', 'name': 'Trident', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'TRITURBINE.NS', 'name': 'Triveni Turbine', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'TTML.NS', 'name': 'Tata Teleservices (Maharashtra)', 'sector': 'telecom', 'marketCap': 'small'},
    {'symbol': 'UBL.NS', 'name': 'United Breweries', 'sector': 'fmcg', 'marketCap': 'small'},
    {'symbol': 'UCOBANK.NS', 'name': 'UCO Bank', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'UNOMINDA.NS', 'name': 'Uno Minda', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'URBANCO.NS', 'name': 'Urban Company', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'USHAMART.NS', 'name': 'Usha Martin', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'UTIAMC.NS', 'name': 'UTI Asset Management Company', 'sector': 'banking', 'marketCap': 'small'},
    {'symbol': 'VIJAYA.NS', 'name': 'Vijaya Diagnostic Centre', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'VTL.NS', 'name': 'Vardhman Textiles', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'WELCORP.NS', 'name': 'Welspun Corp', 'sector': 'metals', 'marketCap': 'small'},
    {'symbol': 'WELSPUNLIV.NS', 'name': 'Welspun Living', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'WHIRLPOOL.NS', 'name': 'Whirlpool of India', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'WOCKPHARMA.NS', 'name': 'Wockhardt', 'sector': 'healthcare', 'marketCap': 'small'},
    {'symbol': 'ZEEL.NS', 'name': 'Zee Entertainment Enterprises', 'sector': 'consumer', 'marketCap': 'small'},
    {'symbol': 'ZENSARTECH.NS', 'name': 'Zensar Technologies', 'sector': 'it', 'marketCap': 'small'},
    {'symbol': 'ZENTEC.NS', 'name': 'Zen Technologies', 'sector': 'capital_goods', 'marketCap': 'small'},
    {'symbol': 'ZFCVINDIA.NS', 'name': 'ZF Commercial Vehicle Control Systems India', 'sector': 'auto', 'marketCap': 'small'},
    {'symbol': 'ZYDUSWELL.NS', 'name': 'Zydus Wellness', 'sector': 'fmcg', 'marketCap': 'small'},
]

# ── US Stock Lists ──────────────────────────────────────────────────────────

def get_dow30_stocks():
    return [
        {'symbol': 'AAPL',  'name': 'Apple Inc.',               'sector': 'technology',  'marketCap': 'large'},
        {'symbol': 'AMGN',  'name': 'Amgen Inc.',                'sector': 'healthcare',  'marketCap': 'large'},
        {'symbol': 'AXP',   'name': 'American Express',          'sector': 'financials',  'marketCap': 'large'},
        {'symbol': 'BA',    'name': 'Boeing Co.',                'sector': 'industrials', 'marketCap': 'large'},
        {'symbol': 'CAT',   'name': 'Caterpillar Inc.',          'sector': 'industrials', 'marketCap': 'large'},
        {'symbol': 'CRM',   'name': 'Salesforce Inc.',           'sector': 'technology',  'marketCap': 'large'},
        {'symbol': 'CSCO',  'name': 'Cisco Systems',             'sector': 'technology',  'marketCap': 'large'},
        {'symbol': 'CVX',   'name': 'Chevron Corp.',             'sector': 'energy',      'marketCap': 'large'},
        {'symbol': 'DIS',   'name': 'Walt Disney Co.',           'sector': 'communication','marketCap': 'large'},
        {'symbol': 'DOW',   'name': 'Dow Inc.',                  'sector': 'materials',   'marketCap': 'large'},
        {'symbol': 'GS',    'name': 'Goldman Sachs',             'sector': 'financials',  'marketCap': 'large'},
        {'symbol': 'HD',    'name': 'Home Depot Inc.',           'sector': 'consumer',    'marketCap': 'large'},
        {'symbol': 'HON',   'name': 'Honeywell International',   'sector': 'industrials', 'marketCap': 'large'},
        {'symbol': 'IBM',   'name': 'IBM Corp.',                 'sector': 'technology',  'marketCap': 'large'},
        {'symbol': 'JNJ',   'name': 'Johnson & Johnson',         'sector': 'healthcare',  'marketCap': 'large'},
        {'symbol': 'JPM',   'name': 'JPMorgan Chase',            'sector': 'financials',  'marketCap': 'large'},
        {'symbol': 'KO',    'name': 'Coca-Cola Co.',             'sector': 'consumer',    'marketCap': 'large'},
        {'symbol': 'MCD',   'name': "McDonald's Corp.",          'sector': 'consumer',    'marketCap': 'large'},
        {'symbol': 'MMM',   'name': '3M Co.',                    'sector': 'industrials', 'marketCap': 'large'},
        {'symbol': 'MRK',   'name': 'Merck & Co.',               'sector': 'healthcare',  'marketCap': 'large'},
        {'symbol': 'MSFT',  'name': 'Microsoft Corp.',           'sector': 'technology',  'marketCap': 'large'},
        {'symbol': 'NKE',   'name': 'Nike Inc.',                 'sector': 'consumer',    'marketCap': 'large'},
        {'symbol': 'PG',    'name': 'Procter & Gamble',          'sector': 'consumer',    'marketCap': 'large'},
        {'symbol': 'SHW',   'name': 'Sherwin-Williams',          'sector': 'materials',   'marketCap': 'large'},
        {'symbol': 'TRV',   'name': 'Travelers Companies',       'sector': 'financials',  'marketCap': 'large'},
        {'symbol': 'UNH',   'name': 'UnitedHealth Group',        'sector': 'healthcare',  'marketCap': 'large'},
        {'symbol': 'V',     'name': 'Visa Inc.',                 'sector': 'financials',  'marketCap': 'large'},
        {'symbol': 'VZ',    'name': 'Verizon Communications',    'sector': 'communication','marketCap': 'large'},
        {'symbol': 'WMT',   'name': 'Walmart Inc.',              'sector': 'consumer',    'marketCap': 'large'},
        {'symbol': 'INTC',  'name': 'Intel Corp.',               'sector': 'technology',  'marketCap': 'large'},
    ]

def get_sp100_stocks():
    return [
    # Technology
    {'symbol': 'AAPL',  'name': 'Apple Inc.',                    'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MSFT',  'name': 'Microsoft Corp.',               'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'NVDA',  'name': 'NVIDIA Corp.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AVGO',  'name': 'Broadcom Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AMD',   'name': 'Advanced Micro Devices',        'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ORCL',  'name': 'Oracle Corp.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'CRM',   'name': 'Salesforce Inc.',               'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'CSCO',  'name': 'Cisco Systems',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'INTC',  'name': 'Intel Corp.',                   'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'IBM',   'name': 'IBM Corp.',                     'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'QCOM',  'name': 'QUALCOMM Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'TXN',   'name': 'Texas Instruments',             'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'NOW',   'name': 'ServiceNow Inc.',               'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'INTU',  'name': 'Intuit Inc.',                   'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AMAT',  'name': 'Applied Materials',             'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ADBE',  'name': 'Adobe Inc.',                    'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MU',    'name': 'Micron Technology',             'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'LRCX',  'name': 'Lam Research',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'PLTR',  'name': 'Palantir Technologies',         'sector': 'technology',      'marketCap': 'large'},
    # Communication
    {'symbol': 'GOOGL', 'name': 'Alphabet Inc. (Class A)',       'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'GOOG',  'name': 'Alphabet Inc. (Class C)',       'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'META',  'name': 'Meta Platforms',                'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'NFLX',  'name': 'Netflix Inc.',                  'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'DIS',   'name': 'Walt Disney Co.',               'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'VZ',    'name': 'Verizon Communications',        'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'T',     'name': 'AT&T Inc.',                     'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'CMCSA', 'name': 'Comcast Corp.',                 'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'TMUS',  'name': 'T-Mobile US',                   'sector': 'communication',   'marketCap': 'large'},
    # Consumer
    {'symbol': 'AMZN',  'name': 'Amazon.com Inc.',               'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'TSLA',  'name': 'Tesla Inc.',                    'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'WMT',   'name': 'Walmart Inc.',                  'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'COST',  'name': 'Costco Wholesale',              'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'HD',    'name': 'Home Depot Inc.',               'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'MCD',   'name': "McDonald's Corp.",              'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'BKNG',  'name': 'Booking Holdings',              'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'LOW',   'name': "Lowe's Companies",              'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'SBUX',  'name': 'Starbucks Corp.',               'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'NKE',   'name': 'Nike Inc.',                     'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'TGT',   'name': 'Target Corp.',                  'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'GM',    'name': 'General Motors',                'sector': 'consumer',        'marketCap': 'large'},
    # Consumer Staples
    {'symbol': 'PG',    'name': 'Procter & Gamble',              'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'KO',    'name': 'Coca-Cola Co.',                 'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'PEP',   'name': 'PepsiCo Inc.',                  'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'PM',    'name': 'Philip Morris Intl.',           'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'MO',    'name': 'Altria Group',                  'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'MDLZ',  'name': 'Mondelez International',        'sector': 'consumer_staples','marketCap': 'large'},
    # Financials
    {'symbol': 'BRK-B', 'name': 'Berkshire Hathaway (Class B)',  'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'JPM',   'name': 'JPMorgan Chase',                'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'V',     'name': 'Visa Inc.',                     'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'MA',    'name': 'Mastercard Inc.',               'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'BAC',   'name': 'Bank of America',               'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'GS',    'name': 'Goldman Sachs',                 'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'WFC',   'name': 'Wells Fargo',                   'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'MS',    'name': 'Morgan Stanley',                'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'BLK',   'name': 'BlackRock Inc.',                'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'AXP',   'name': 'American Express',              'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'SCHW',  'name': 'Charles Schwab',                'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'C',     'name': 'Citigroup Inc.',                'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'COF',   'name': 'Capital One Financial',         'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'BK',    'name': 'BNY Mellon',                    'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'USB',   'name': 'U.S. Bancorp',                  'sector': 'financials',      'marketCap': 'large'},
    {'symbol': 'SPG',   'name': 'Simon Property Group',          'sector': 'financials',      'marketCap': 'large'},
    # Healthcare
    {'symbol': 'LLY',   'name': 'Eli Lilly',                     'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'UNH',   'name': 'UnitedHealth Group',            'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'JNJ',   'name': 'Johnson & Johnson',             'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'ABBV',  'name': 'AbbVie Inc.',                   'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'MRK',   'name': 'Merck & Co.',                   'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'TMO',   'name': 'Thermo Fisher Scientific',      'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'ABT',   'name': 'Abbott Laboratories',           'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'AMGN',  'name': 'Amgen Inc.',                    'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'PFE',   'name': 'Pfizer Inc.',                   'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'GILD',  'name': 'Gilead Sciences',               'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'BMY',   'name': 'Bristol-Myers Squibb',          'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'CVS',   'name': 'CVS Health Corp.',              'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'ISRG',  'name': 'Intuitive Surgical',            'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'REGN',  'name': 'Regeneron Pharmaceuticals',     'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'VRTX',  'name': 'Vertex Pharmaceuticals',        'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'MDT',   'name': 'Medtronic PLC',                 'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'DHR',   'name': 'Danaher Corp.',                 'sector': 'healthcare',      'marketCap': 'large'},
    # Energy
    {'symbol': 'XOM',   'name': 'Exxon Mobil Corp.',             'sector': 'energy',          'marketCap': 'large'},
    {'symbol': 'CVX',   'name': 'Chevron Corp.',                 'sector': 'energy',          'marketCap': 'large'},
    {'symbol': 'COP',   'name': 'ConocoPhillips',                'sector': 'energy',          'marketCap': 'large'},
    {'symbol': 'EOG',   'name': 'EOG Resources',                 'sector': 'energy',          'marketCap': 'large'},
    {'symbol': 'SLB',   'name': 'Schlumberger NV',               'sector': 'energy',          'marketCap': 'large'},
    # Industrials
    {'symbol': 'GE',    'name': 'GE Aerospace',                  'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'CAT',   'name': 'Caterpillar Inc.',              'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'HON',   'name': 'Honeywell International',       'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'BA',    'name': 'Boeing Co.',                    'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'RTX',   'name': 'RTX Corp.',                     'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'MMM',   'name': '3M Co.',                        'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'UPS',   'name': 'United Parcel Service',         'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'DE',    'name': 'Deere & Company',               'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'LMT',   'name': 'Lockheed Martin',               'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'UNP',   'name': 'Union Pacific Corp.',           'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'GEV',   'name': 'GE Vernova',                    'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'UBER',  'name': 'Uber Technologies',             'sector': 'industrials',     'marketCap': 'large'},
    # Materials
    {'symbol': 'LIN',   'name': 'Linde PLC',                     'sector': 'materials',       'marketCap': 'large'},
    {'symbol': 'SHW',   'name': 'Sherwin-Williams',              'sector': 'materials',       'marketCap': 'large'},
    {'symbol': 'DOW',   'name': 'Dow Inc.',                      'sector': 'materials',       'marketCap': 'large'},
    {'symbol': 'FCX',   'name': 'Freeport-McMoRan',              'sector': 'materials',       'marketCap': 'large'},
    {'symbol': 'APD',   'name': 'Air Products & Chemicals',      'sector': 'materials',       'marketCap': 'large'},
    # Utilities
    {'symbol': 'NEE',   'name': 'NextEra Energy',                'sector': 'utilities',       'marketCap': 'large'},
    {'symbol': 'SO',    'name': 'Southern Company',              'sector': 'utilities',       'marketCap': 'large'},
    {'symbol': 'DUK',   'name': 'Duke Energy Corp.',             'sector': 'utilities',       'marketCap': 'large'},
    # Real Estate
    {'symbol': 'AMT',   'name': 'American Tower Corp.',          'sector': 'realestate',      'marketCap': 'large'},
    {'symbol': 'PLD',   'name': 'Prologis Inc.',                 'sector': 'realestate',      'marketCap': 'large'},
]

def get_nasdaq100_stocks():
    return [
    # Technology
    {'symbol': 'NVDA',  'name': 'NVIDIA Corp.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AAPL',  'name': 'Apple Inc.',                    'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MSFT',  'name': 'Microsoft Corp.',               'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AVGO',  'name': 'Broadcom Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'META',  'name': 'Meta Platforms',                'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'GOOGL', 'name': 'Alphabet Inc. (Class A)',       'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'GOOG',  'name': 'Alphabet Inc. (Class C)',       'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AMD',   'name': 'Advanced Micro Devices',        'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'PLTR',  'name': 'Palantir Technologies',         'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'APP',   'name': 'AppLovin Corp.',                'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ARM',   'name': 'Arm Holdings',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ASML',  'name': 'ASML Holding',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ADSK',  'name': 'Autodesk Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'CDNS',  'name': 'Cadence Design Systems',        'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'CSCO',  'name': 'Cisco Systems',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'CTSH',  'name': 'Cognizant Technology Solutions','sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'CRWD',  'name': 'CrowdStrike Holdings',          'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'DDOG',  'name': 'Datadog Inc.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'DASH',  'name': 'DoorDash Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'FTNT',  'name': 'Fortinet Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'INTC',  'name': 'Intel Corp.',                   'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'INTU',  'name': 'Intuit Inc.',                   'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'KLAC',  'name': 'KLA Corp.',                     'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'LRCX',  'name': 'Lam Research',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MRVL',  'name': 'Marvell Technology',            'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MCHP',  'name': 'Microchip Technology',          'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MU',    'name': 'Micron Technology',             'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MPWR',  'name': 'Monolithic Power Systems',      'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'MSTR',  'name': 'MicroStrategy Inc.',            'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'PANW',  'name': 'Palo Alto Networks',            'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'PDD',   'name': 'PDD Holdings',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'QCOM',  'name': 'QUALCOMM Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ROP',   'name': 'Roper Technologies',            'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'SNDK',  'name': 'Sandisk Corp.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'STX',   'name': 'Seagate Technology',            'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'SHOP',  'name': 'Shopify Inc.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'SNPS',  'name': 'Synopsys Inc.',                 'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'TXN',   'name': 'Texas Instruments',             'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'TRI',   'name': 'Thomson Reuters',               'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'AMAT',  'name': 'Applied Materials',             'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'NXPI',  'name': 'NXP Semiconductors',            'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'WDC',   'name': 'Western Digital',               'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'WDAY',  'name': 'Workday Inc.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ZS',    'name': 'Zscaler Inc.',                  'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ADBE',  'name': 'Adobe Inc.',                    'sector': 'technology',      'marketCap': 'large'},
    {'symbol': 'ADI',   'name': 'Analog Devices',                'sector': 'technology',      'marketCap': 'large'},
    # Communication
    {'symbol': 'NFLX',  'name': 'Netflix Inc.',                  'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'CMCSA', 'name': 'Comcast Corp.',                 'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'TMUS',  'name': 'T-Mobile US',                   'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'CHTR',  'name': 'Charter Communications',        'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'EA',    'name': 'Electronic Arts',               'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'TTWO',  'name': 'Take-Two Interactive',          'sector': 'communication',   'marketCap': 'large'},
    {'symbol': 'WBD',   'name': 'Warner Bros. Discovery',        'sector': 'communication',   'marketCap': 'large'},
    # Consumer
    {'symbol': 'AMZN',  'name': 'Amazon.com Inc.',               'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'TSLA',  'name': 'Tesla Inc.',                    'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'BKNG',  'name': 'Booking Holdings',              'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'CPRT',  'name': 'Copart Inc.',                   'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'COST',  'name': 'Costco Wholesale',              'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'MAR',   'name': 'Marriott International',        'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'MELI',  'name': 'MercadoLibre Inc.',             'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'ORLY',  'name': 'OReilly Automotive',            'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'PCAR',  'name': 'PACCAR Inc.',                   'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'ROST',  'name': 'Ross Stores',                   'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'SBUX',  'name': 'Starbucks Corp.',               'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'WMT',   'name': 'Walmart Inc.',                  'sector': 'consumer',        'marketCap': 'large'},
    {'symbol': 'ABNB',  'name': 'Airbnb Inc.',                   'sector': 'consumer',        'marketCap': 'large'},
    # Consumer Staples
    {'symbol': 'CCEP',  'name': 'Coca-Cola Europacific Partners','sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'KDP',   'name': 'Keurig Dr Pepper',              'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'KHC',   'name': 'Kraft Heinz',                   'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'MDLZ',  'name': 'Mondelez International',        'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'MNST',  'name': 'Monster Beverage',              'sector': 'consumer_staples','marketCap': 'large'},
    {'symbol': 'PEP',   'name': 'PepsiCo Inc.',                  'sector': 'consumer_staples','marketCap': 'large'},
    # Healthcare
    {'symbol': 'AMGN',  'name': 'Amgen Inc.',                    'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'ALNY',  'name': 'Alnylam Pharmaceuticals',       'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'DXCM',  'name': 'DexCom Inc.',                   'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'GEHC',  'name': 'GE HealthCare Technologies',    'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'GILD',  'name': 'Gilead Sciences',               'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'IDXX',  'name': 'IDEXX Laboratories',            'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'INSM',  'name': 'Insmed Inc.',                   'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'ISRG',  'name': 'Intuitive Surgical',            'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'REGN',  'name': 'Regeneron Pharmaceuticals',     'sector': 'healthcare',      'marketCap': 'large'},
    {'symbol': 'VRTX',  'name': 'Vertex Pharmaceuticals',        'sector': 'healthcare',      'marketCap': 'large'},
    # Industrials
    {'symbol': 'ADP',   'name': 'Automatic Data Processing',     'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'AXON',  'name': 'Axon Enterprise',               'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'CTAS',  'name': 'Cintas Corp.',                  'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'CSX',   'name': 'CSX Corp.',                     'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'FAST',  'name': 'Fastenal Co.',                  'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'FER',   'name': 'Ferrovial SE',                  'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'HON',   'name': 'Honeywell International',       'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'ODFL',  'name': 'Old Dominion Freight Line',     'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'PAYX',  'name': 'Paychex Inc.',                  'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'PYPL',  'name': 'PayPal Holdings',               'sector': 'industrials',     'marketCap': 'large'},
    {'symbol': 'VRSK',  'name': 'Verisk Analytics',              'sector': 'industrials',     'marketCap': 'large'},
    # Energy
    {'symbol': 'BKR',   'name': 'Baker Hughes Co.',              'sector': 'energy',          'marketCap': 'large'},
    {'symbol': 'FANG',  'name': 'Diamondback Energy',            'sector': 'energy',          'marketCap': 'large'},
    # Utilities
    {'symbol': 'AEP',   'name': 'American Electric Power',       'sector': 'utilities',       'marketCap': 'large'},
    {'symbol': 'CEG',   'name': 'Constellation Energy',          'sector': 'utilities',       'marketCap': 'large'},
    {'symbol': 'EXC',   'name': 'Exelon Corp.',                  'sector': 'utilities',       'marketCap': 'large'},
    {'symbol': 'XEL',   'name': 'Xcel Energy',                   'sector': 'utilities',       'marketCap': 'large'},
    # Real Estate
    {'symbol': 'CSGP',  'name': 'CoStar Group',                  'sector': 'realestate',      'marketCap': 'large'},
    # Materials
    {'symbol': 'LIN',   'name': 'Linde PLC',                     'sector': 'materials',       'marketCap': 'large'},
]

def get_sp500_stocks():
    """Representative S&P 500 stocks — top ~200 by sector coverage"""
    return [
    # Technology
    {'symbol': 'NVDA',  'name': 'NVIDIA Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'AAPL',  'name': 'Apple Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'MSFT',  'name': 'Microsoft Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'AVGO',  'name': 'Broadcom Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'AMD',  'name': 'Advanced Micro Devices', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ORCL',  'name': 'Oracle Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CRM',  'name': 'Salesforce Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CSCO',  'name': 'Cisco Systems', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'INTC',  'name': 'Intel Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'IBM',  'name': 'IBM Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'QCOM',  'name': 'QUALCOMM Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'TXN',  'name': 'Texas Instruments', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'NOW',  'name': 'ServiceNow Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'INTU',  'name': 'Intuit Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'AMAT',  'name': 'Applied Materials', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ADBE',  'name': 'Adobe Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'MU',  'name': 'Micron Technology', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'LRCX',  'name': 'Lam Research', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'PLTR',  'name': 'Palantir Technologies', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'SNDK',  'name': 'Sandisk Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'STX',  'name': 'Seagate Technology', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'APP',  'name': 'AppLovin Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ANET',  'name': 'Arista Networks', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'WDC',  'name': 'Western Digital', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'KLAC',  'name': 'KLA Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'SNPS',  'name': 'Synopsys Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CDNS',  'name': 'Cadence Design Systems', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ADI',  'name': 'Analog Devices', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'PANW',  'name': 'Palo Alto Networks', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'DELL',  'name': 'Dell Technologies', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'GLW',  'name': 'Corning Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CIEN',  'name': 'Ciena Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'NXPI',  'name': 'NXP Semiconductors', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'MPWR',  'name': 'Monolithic Power Systems', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CRWD',  'name': 'CrowdStrike Holdings', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'COHR',  'name': 'Coherent Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'LITE',  'name': 'Lumentum Holdings', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'DDOG',  'name': 'Datadog Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'MCHP',  'name': 'Microchip Technology', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'FTNT',  'name': 'Fortinet Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ADSK',  'name': 'Autodesk Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'WDAY',  'name': 'Workday Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'KEYS',  'name': 'Keysight Technologies', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'TER',  'name': 'Teradyne Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'HPE',  'name': 'Hewlett Packard Enterprise', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ON',  'name': 'ON Semiconductor', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'MSI',  'name': 'Motorola Solutions', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ROP',  'name': 'Roper Technologies', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'GDDY',  'name': 'GoDaddy Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CDW',  'name': 'CDW Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'VRSN',  'name': 'VeriSign Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'FICO',  'name': 'Fair Isaac Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'JBL',  'name': 'Jabil Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'CTSH',  'name': 'Cognizant Technology Solutions', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'IT',  'name': 'Gartner Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'HPQ',  'name': 'HP Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'Q',  'name': 'Qnity Electronics', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'AKAM',  'name': 'Akamai Technologies', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'FFIV',  'name': 'F5 Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'VLTO',  'name': 'Veralto Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'PTC',  'name': 'PTC Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'SMCI',  'name': 'Super Micro Computer', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'NTAP',  'name': 'NetApp Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'TEL',  'name': 'TE Connectivity', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'APH',  'name': 'Amphenol Corp.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ANSS',  'name': 'ANSYS Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ENPH',  'name': 'Enphase Energy', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'EPAM',  'name': 'EPAM Systems', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'GEN',  'name': 'Gen Digital Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'JKHY',  'name': 'Jack Henry & Associates', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'JNPR',  'name': 'Juniper Networks', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'PAYC',  'name': 'Paycom Software', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'QRVO',  'name': 'Qorvo Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'SWKS',  'name': 'Skyworks Solutions', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'TYL',  'name': 'Tyler Technologies', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'WEX',  'name': 'WEX Inc.', 'sector': 'technology', 'marketCap': 'large'},
    {'symbol': 'ZBRA',  'name': 'Zebra Technologies', 'sector': 'technology', 'marketCap': 'large'},
    # Communication
    {'symbol': 'GOOGL',  'name': 'Alphabet Inc. (Class A)', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'GOOG',  'name': 'Alphabet Inc. (Class C)', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'META',  'name': 'Meta Platforms', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'NFLX',  'name': 'Netflix Inc.', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'DIS',  'name': 'Walt Disney Co.', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'VZ',  'name': 'Verizon Communications', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'T',  'name': 'AT&T Inc.', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'CMCSA',  'name': 'Comcast Corp.', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'TMUS',  'name': 'T-Mobile US', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'CHTR',  'name': 'Charter Communications', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'WBD',  'name': 'Warner Bros. Discovery', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'FOXA',  'name': 'Fox Corp. (Class A)', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'FOX',  'name': 'Fox Corp. (Class B)', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'SATS',  'name': 'EchoStar Corp.', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'TTD',  'name': 'The Trade Desk', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'EA',  'name': 'Electronic Arts', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'TTWO',  'name': 'Take-Two Interactive', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'LYV',  'name': 'Live Nation Entertainment', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'TKO',  'name': 'TKO Group Holdings', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'OMC',  'name': 'Omnicom Group', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'NWS',  'name': 'News Corp. (Class B)', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'NWSA',  'name': 'News Corp. (Class A)', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'MTCH',  'name': 'Match Group', 'sector': 'communication', 'marketCap': 'large'},
    {'symbol': 'IPG',  'name': 'Interpublic Group', 'sector': 'communication', 'marketCap': 'large'},
    # Consumer Discretionary
    {'symbol': 'AMZN',  'name': 'Amazon.com Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'TSLA',  'name': 'Tesla Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'HD',  'name': 'Home Depot Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'MCD',  'name': 'McDonalds Corp.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'LOW',  'name': 'Lowes Companies', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'BKNG',  'name': 'Booking Holdings', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'SBUX',  'name': 'Starbucks Corp.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'NKE',  'name': 'Nike Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'TJX',  'name': 'TJX Companies', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'ABNB',  'name': 'Airbnb Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'GM',  'name': 'General Motors', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'ORLY',  'name': 'OReilly Automotive', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'AZO',  'name': 'AutoZone Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'ROST',  'name': 'Ross Stores', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'HLT',  'name': 'Hilton Worldwide Holdings', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'MAR',  'name': 'Marriott International', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'RCL',  'name': 'Royal Caribbean Cruises', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'F',  'name': 'Ford Motor Co.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'CCL',  'name': 'Carnival Corp.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'DASH',  'name': 'DoorDash Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'CMG',  'name': 'Chipotle Mexican Grill', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'YUM',  'name': 'Yum Brands', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'DHI',  'name': 'D.R. Horton', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'LEN',  'name': 'Lennar Corp.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'TSCO',  'name': 'Tractor Supply Co.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'EBAY',  'name': 'eBay Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'EXPE',  'name': 'Expedia Group', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'CVNA',  'name': 'Carvana Co.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'ULTA',  'name': 'Ulta Beauty', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'TPR',  'name': 'Tapestry Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'GPC',  'name': 'Genuine Parts Co.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'APTV',  'name': 'Aptiv PLC', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'GRMN',  'name': 'Garmin Ltd.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'LVS',  'name': 'Las Vegas Sands', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'PHM',  'name': 'PulteGroup Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'WSM',  'name': 'Williams-Sonoma Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'RL',  'name': 'Ralph Lauren Corp.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'DRI',  'name': 'Darden Restaurants', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'NVR',  'name': 'NVR Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'JBHT',  'name': 'J.B. Hunt Transport Services', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'BWA',  'name': 'BorgWarner Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'DPZ',  'name': 'Dominos Pizza Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'HAS',  'name': 'Hasbro Inc.', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'MHK',  'name': 'Mohawk Industries', 'sector': 'consumer', 'marketCap': 'large'},
    {'symbol': 'POOL',  'name': 'Pool Corp.', 'sector': 'consumer', 'marketCap': 'large'},
    # Consumer Staples
    {'symbol': 'WMT',  'name': 'Walmart Inc.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'COST',  'name': 'Costco Wholesale', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'PG',  'name': 'Procter & Gamble', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'KO',  'name': 'Coca-Cola Co.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'PEP',  'name': 'PepsiCo Inc.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'PM',  'name': 'Philip Morris Intl.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'MO',  'name': 'Altria Group', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'MDLZ',  'name': 'Mondelez International', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'CL',  'name': 'Colgate-Palmolive', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'TGT',  'name': 'Target Corp.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'MNST',  'name': 'Monster Beverage', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'KMB',  'name': 'Kimberly-Clark', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'KR',  'name': 'Kroger Co.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'STZ',  'name': 'Constellation Brands', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'KDP',  'name': 'Keurig Dr Pepper', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'HSY',  'name': 'Hershey Co.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'GIS',  'name': 'General Mills', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'SYY',  'name': 'Sysco Corp.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'ADM',  'name': 'Archer-Daniels-Midland', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'DG',  'name': 'Dollar General', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'DLTR',  'name': 'Dollar Tree', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'EL',  'name': 'Estée Lauder Companies', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'KVUE',  'name': 'Kenvue Inc.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'CHD',  'name': 'Church & Dwight', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'CASY',  'name': 'Caseys General Stores', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'BG',  'name': 'Bunge Global SA', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'TSN',  'name': 'Tyson Foods', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'KHC',  'name': 'Kraft Heinz', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'AMCR',  'name': 'Amcor PLC', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'CF',  'name': 'CF Industries Holdings', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'IFF',  'name': 'International Flavors & Fragrances', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'CAG',  'name': 'Conagra Brands', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'CPB',  'name': 'Campbell Soup', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'HRL',  'name': 'Hormel Foods', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'MKC',  'name': 'McCormick and Co.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'SJM',  'name': 'J.M. Smucker Co.', 'sector': 'consumer_staples', 'marketCap': 'large'},
    {'symbol': 'TAP',  'name': 'Molson Coors Beverage', 'sector': 'consumer_staples', 'marketCap': 'large'},
    # Financials
    {'symbol': 'BRK-B',  'name': 'Berkshire Hathaway (Class B)', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'JPM',  'name': 'JPMorgan Chase', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'V',  'name': 'Visa Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MA',  'name': 'Mastercard Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'BAC',  'name': 'Bank of America', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'GS',  'name': 'Goldman Sachs', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'WFC',  'name': 'Wells Fargo', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MS',  'name': 'Morgan Stanley', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'BLK',  'name': 'BlackRock Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AXP',  'name': 'American Express', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'SCHW',  'name': 'Charles Schwab', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'C',  'name': 'Citigroup Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'COF',  'name': 'Capital One Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'BK',  'name': 'BNY Mellon', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'USB',  'name': 'U.S. Bancorp', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'SPGI',  'name': 'S&P Global Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'BX',  'name': 'Blackstone Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CME',  'name': 'CME Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'ICE',  'name': 'Intercontinental Exchange', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CB',  'name': 'Chubb Ltd.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'PGR',  'name': 'Progressive Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'PNC',  'name': 'PNC Financial Services', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MCO',  'name': 'Moodys Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'APO',  'name': 'Apollo Global Management', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'KKR',  'name': 'KKR & Co.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AJG',  'name': 'Arthur J. Gallagher', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AON',  'name': 'Aon PLC', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MSCI',  'name': 'MSCI Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'PYPL',  'name': 'PayPal Holdings', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'TRV',  'name': 'Travelers Companies', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MET',  'name': 'MetLife Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'PRU',  'name': 'Prudential Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AFL',  'name': 'Aflac Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AIG',  'name': 'American International Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'ALL',  'name': 'Allstate Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'NDAQ',  'name': 'Nasdaq Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'HIG',  'name': 'The Hartford', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'WRB',  'name': 'W.R. Berkley Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'ACGL',  'name': 'Arch Capital Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CINF',  'name': 'Cincinnati Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MTB',  'name': 'M&T Bank Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'FITB',  'name': 'Fifth Third Bancorp', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'HBAN',  'name': 'Huntington Bancshares', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'STT',  'name': 'State Street Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CFG',  'name': 'Citizens Financial Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'NTRS',  'name': 'Northern Trust Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'RJF',  'name': 'Raymond James Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AMP',  'name': 'Ameriprise Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'TROW',  'name': 'T. Rowe Price Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CBOE',  'name': 'Cboe Global Markets', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'IBKR',  'name': 'Interactive Brokers Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'HOOD',  'name': 'Robinhood Markets', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'COIN',  'name': 'Coinbase Global', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'ARES',  'name': 'Ares Management Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'GPN',  'name': 'Global Payments', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'FIS',  'name': 'Fidelity National Info. Services', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'FISV',  'name': 'Fiserv Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'WTW',  'name': 'Willis Towers Watson', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MRSH',  'name': 'Marsh & McLennan', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'TFC',  'name': 'Truist Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'SYF',  'name': 'Synchrony Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'RF',  'name': 'Regions Financial', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'KEY',  'name': 'KeyCorp', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CPAY',  'name': 'Corpay Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'L',  'name': 'Loews Corp.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'PFG',  'name': 'Principal Financial Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'BRO',  'name': 'Brown & Brown Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'BEN',  'name': 'Franklin Resources', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'VTRS',  'name': 'Viatris Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'AIZ',  'name': 'Assurant Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'CG',  'name': 'Carlyle Group', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'ERIE',  'name': 'Erie Indemnity Co.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'GL',  'name': 'Globe Life Inc.', 'sector': 'financials', 'marketCap': 'large'},
    {'symbol': 'MKL',  'name': 'Markel Group', 'sector': 'financials', 'marketCap': 'large'},
    # Healthcare
    {'symbol': 'LLY',  'name': 'Eli Lilly', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'UNH',  'name': 'UnitedHealth Group', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'JNJ',  'name': 'Johnson & Johnson', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ABBV',  'name': 'AbbVie Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MRK',  'name': 'Merck & Co.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'TMO',  'name': 'Thermo Fisher Scientific', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ABT',  'name': 'Abbott Laboratories', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'AMGN',  'name': 'Amgen Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'PFE',  'name': 'Pfizer Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'GILD',  'name': 'Gilead Sciences', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'BMY',  'name': 'Bristol-Myers Squibb', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'CVS',  'name': 'CVS Health Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ISRG',  'name': 'Intuitive Surgical', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'REGN',  'name': 'Regeneron Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'VRTX',  'name': 'Vertex Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MDT',  'name': 'Medtronic PLC', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'DHR',  'name': 'Danaher Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'SYK',  'name': 'Stryker Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'BSX',  'name': 'Boston Scientific', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ELV',  'name': 'Elevance Health', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'CI',  'name': 'The Cigna Group', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'HCA',  'name': 'HCA Healthcare', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'HUM',  'name': 'Humana Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'CNC',  'name': 'Centene Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MCK',  'name': 'McKesson Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'CAH',  'name': 'Cardinal Health', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'COR',  'name': 'Cencora Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'IDXX',  'name': 'IDEXX Laboratories', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'IQV',  'name': 'IQVIA Holdings', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'BIIB',  'name': 'Biogen Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MRNA',  'name': 'Moderna Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'DXCM',  'name': 'DexCom Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'EW',  'name': 'Edwards Lifesciences', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'BDX',  'name': 'Becton Dickinson', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'RMD',  'name': 'ResMed Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MTD',  'name': 'Mettler-Toledo', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'A',  'name': 'Agilent Technologies', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'GEHC',  'name': 'GE HealthCare Technologies', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ZTS',  'name': 'Zoetis Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'STE',  'name': 'Steris PLC', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ZBH',  'name': 'Zimmer Biomet Holdings', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'WAT',  'name': 'Waters Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'WST',  'name': 'West Pharmaceutical Services', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'MOH',  'name': 'Molina Healthcare', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'DGX',  'name': 'Quest Diagnostics', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'LH',  'name': 'Labcorp Holdings', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'INCY',  'name': 'Incyte Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'ALGN',  'name': 'Align Technology', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'FSLR',  'name': 'First Solar Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'CRL',  'name': 'Charles River Laboratories', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'CTLT',  'name': 'Catalent Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'HOLX',  'name': 'Hologic Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'HSIC',  'name': 'Henry Schein Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'RVTY',  'name': 'PerkinElmer Inc.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'PODD',  'name': 'Insulet Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'PRGO',  'name': 'Perrigo Company', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'SOLV',  'name': 'Solventum Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'TECH',  'name': 'Bio-Techne Corp.', 'sector': 'healthcare', 'marketCap': 'large'},
    {'symbol': 'XRAY',  'name': 'Dentsply Sirona', 'sector': 'healthcare', 'marketCap': 'large'},
    # Energy
    {'symbol': 'XOM',  'name': 'Exxon Mobil Corp.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'CVX',  'name': 'Chevron Corp.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'COP',  'name': 'ConocoPhillips', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'EOG',  'name': 'EOG Resources', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'SLB',  'name': 'Schlumberger NV', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'MPC',  'name': 'Marathon Petroleum', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'PSX',  'name': 'Phillips 66', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'VLO',  'name': 'Valero Energy', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'OXY',  'name': 'Occidental Petroleum', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'DVN',  'name': 'Devon Energy', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'FANG',  'name': 'Diamondback Energy', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'EQT',  'name': 'EQT Corp.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'HAL',  'name': 'Halliburton Co.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'BKR',  'name': 'Baker Hughes Co.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'KMI',  'name': 'Kinder Morgan', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'WMB',  'name': 'Williams Companies', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'OKE',  'name': 'ONEOK Inc.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'TRGP',  'name': 'Targa Resources', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'TPL',  'name': 'Texas Pacific Land', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'VST',  'name': 'Vistra Corp.', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'CTRA',  'name': 'Coterra Energy', 'sector': 'energy', 'marketCap': 'large'},
    {'symbol': 'EXE',  'name': 'Expand Energy Corp.', 'sector': 'energy', 'marketCap': 'large'},
    # Industrials
    {'symbol': 'GE',  'name': 'GE Aerospace', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'GEV',  'name': 'GE Vernova', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CAT',  'name': 'Caterpillar Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'HON',  'name': 'Honeywell International', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'BA',  'name': 'Boeing Co.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'RTX',  'name': 'RTX Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'MMM',  'name': '3M Co.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'UPS',  'name': 'United Parcel Service', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'DE',  'name': 'Deere & Company', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'LMT',  'name': 'Lockheed Martin', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'UNP',  'name': 'Union Pacific Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'UBER',  'name': 'Uber Technologies', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ETN',  'name': 'Eaton Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ADP',  'name': 'Automatic Data Processing', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'NOC',  'name': 'Northrop Grumman', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'GD',  'name': 'General Dynamics', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'TT',  'name': 'Trane Technologies', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'PH',  'name': 'Parker-Hannifin', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'FDX',  'name': 'FedEx Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'EMR',  'name': 'Emerson Electric', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CARR',  'name': 'Carrier Global', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'OTIS',  'name': 'Otis Worldwide', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'WM',  'name': 'Waste Management', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'RSG',  'name': 'Republic Services', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'PCAR',  'name': 'PACCAR Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CTAS',  'name': 'Cintas Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'LHX',  'name': 'L3Harris Technologies', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ITW',  'name': 'Illinois Tool Works', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'TDG',  'name': 'TransDigm Group', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ROK',  'name': 'Rockwell Automation', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'NSC',  'name': 'Norfolk Southern', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CSX',  'name': 'CSX Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'DAL',  'name': 'Delta Air Lines', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'UAL',  'name': 'United Airlines Holdings', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'URI',  'name': 'United Rentals', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'WAB',  'name': 'Westinghouse Air Brake Tech.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'HWM',  'name': 'Howmet Aerospace', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'PWR',  'name': 'Quanta Services', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'EME',  'name': 'EMCOR Group', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'GWW',  'name': 'W.W. Grainger', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'FAST',  'name': 'Fastenal Co.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'PAYX',  'name': 'Paychex Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'VRSK',  'name': 'Verisk Analytics', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'EFX',  'name': 'Equifax Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CPRT',  'name': 'Copart Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ODFL',  'name': 'Old Dominion Freight Line', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'BR',  'name': 'Broadridge Financial Solutions', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'AXON',  'name': 'Axon Enterprise', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'FTV',  'name': 'Fortive Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'DOV',  'name': 'Dover Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'AME',  'name': 'AMETEK Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CMI',  'name': 'Cummins Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'XYL',  'name': 'Xylem Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'VRT',  'name': 'Vertiv Holdings', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'IR',  'name': 'Ingersoll Rand', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ROL',  'name': 'Rollins Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'FIX',  'name': 'Comfort Systems USA', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'HUBB',  'name': 'Hubbell Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'TDY',  'name': 'Teledyne Technologies', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'LUV',  'name': 'Southwest Airlines', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'EXPD',  'name': 'Expeditors International', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'CHRW',  'name': 'C.H. Robinson Worldwide', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'SNA',  'name': 'Snap-on Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'PKG',  'name': 'Packaging Corp. of America', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'TXT',  'name': 'Textron Inc.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'LDOS',  'name': 'Leidos Holdings', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'NDSN',  'name': 'Nordson Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'GNRC',  'name': 'Generac Holdings', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'IEX',  'name': 'IDEX Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'LII',  'name': 'Lennox International', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'SW',  'name': 'Smurfit Westrock PLC', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'IP',  'name': 'International Paper', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'BALL',  'name': 'Ball Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'ALLE',  'name': 'Allegion PLC', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'GXO',  'name': 'GXO Logistics', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'HII',  'name': 'Huntington Ingalls Industries', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'J',  'name': 'Jacobs Solutions', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'MAS',  'name': 'Masco Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'NVT',  'name': 'nVent Electric', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'RRX',  'name': 'Rexnord Corp.', 'sector': 'industrials', 'marketCap': 'large'},
    {'symbol': 'TRU',  'name': 'TransUnion', 'sector': 'industrials', 'marketCap': 'large'},
    # Materials
    {'symbol': 'LIN',  'name': 'Linde PLC', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'SHW',  'name': 'Sherwin-Williams', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'FCX',  'name': 'Freeport-McMoRan', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'APD',  'name': 'Air Products & Chemicals', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'NEM',  'name': 'Newmont Corp.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'ECL',  'name': 'Ecolab Inc.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'NUE',  'name': 'Nucor Corp.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'DOW',  'name': 'Dow Inc.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'STLD',  'name': 'Steel Dynamics', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'VMC',  'name': 'Vulcan Materials', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'MLM',  'name': 'Martin Marietta Materials', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'PPG',  'name': 'PPG Industries', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'ALB',  'name': 'Albemarle Corp.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'LYB',  'name': 'LyondellBasell Industries', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'DD',  'name': 'DuPont de Nemours', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'CTVA',  'name': 'Corteva Inc.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'CRH',  'name': 'CRH PLC', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'AVY',  'name': 'Avery Dennison Corp.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'CCK',  'name': 'Crown Holdings', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'EMN',  'name': 'Eastman Chemical', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'FMC',  'name': 'FMC Corp.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'MOS',  'name': 'Mosaic Co.', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'RPM',  'name': 'RPM International', 'sector': 'materials', 'marketCap': 'large'},
    {'symbol': 'SEE',  'name': 'Sealed Air Corp.', 'sector': 'materials', 'marketCap': 'large'},
    # Utilities
    {'symbol': 'NEE',  'name': 'NextEra Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'SO',  'name': 'Southern Company', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'DUK',  'name': 'Duke Energy Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'CEG',  'name': 'Constellation Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'SRE',  'name': 'Sempra', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'AEP',  'name': 'American Electric Power', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'EXC',  'name': 'Exelon Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'XEL',  'name': 'Xcel Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'PCG',  'name': 'PG&E Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'ED',  'name': 'Consolidated Edison', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'WEC',  'name': 'WEC Energy Group', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'EIX',  'name': 'Edison International', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'ETR',  'name': 'Entergy Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'DTE',  'name': 'DTE Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'AEE',  'name': 'Ameren Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'ES',  'name': 'Eversource Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'PPL',  'name': 'PPL Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'PEG',  'name': 'Public Service Enterprise Group', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'AWK',  'name': 'American Water Works', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'NRG',  'name': 'NRG Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'CNP',  'name': 'CenterPoint Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'D',  'name': 'Dominion Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'ATO',  'name': 'Atmos Energy', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'FE',  'name': 'FirstEnergy Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'NI',  'name': 'NiSource Inc.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'CMS',  'name': 'CMS Energy Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'EVRG',  'name': 'Evergy Inc.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'LNT',  'name': 'Alliant Energy Corp.', 'sector': 'utilities', 'marketCap': 'large'},
    {'symbol': 'PNW',  'name': 'Pinnacle West Capital', 'sector': 'utilities', 'marketCap': 'large'},
    # Real Estate
    {'symbol': 'AMT',  'name': 'American Tower Corp.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'PLD',  'name': 'Prologis Inc.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'EQIX',  'name': 'Equinix Inc.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'WELL',  'name': 'Welltower Inc.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'SPG',  'name': 'Simon Property Group', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'DLR',  'name': 'Digital Realty Trust', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'O',  'name': 'Realty Income Corp.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'VICI',  'name': 'VICI Properties', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'CCI',  'name': 'Crown Castle Inc.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'PSA',  'name': 'Public Storage', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'EXR',  'name': 'Extra Space Storage', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'AVB',  'name': 'AvalonBay Communities', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'EQR',  'name': 'Equity Residential', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'IRM',  'name': 'Iron Mountain', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'SBAC',  'name': 'SBA Communications', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'VTR',  'name': 'Ventas Inc.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'WY',  'name': 'Weyerhaeuser', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'CBRE',  'name': 'CBRE Group', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'CSGP',  'name': 'CoStar Group', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'INVH',  'name': 'Invitation Homes', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'ESS',  'name': 'Essex Property Trust', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'MAA',  'name': 'Mid-America Apartment Communities', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'HST',  'name': 'Host Hotels & Resorts', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'KIM',  'name': 'Kimco Realty Corp.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'ARE',  'name': 'Alexandria Real Estate', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'BXP',  'name': 'BXP Inc.', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'CPT',  'name': 'Camden Property Trust', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'DOC',  'name': 'Healthpeak Properties', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'FR',  'name': 'First Industrial Realty Trust', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'REG',  'name': 'Regency Centers', 'sector': 'realestate', 'marketCap': 'large'},
    {'symbol': 'UDR',  'name': 'UDR Inc.', 'sector': 'realestate', 'marketCap': 'large'},
]

def get_us_universe(universe_type):
    if universe_type == 'dow30':
        return get_dow30_stocks()
    elif universe_type == 'sp100':
        return get_sp100_stocks()
    elif universe_type == 'nasdaq100':
        return get_nasdaq100_stocks()
    elif universe_type == 'sp500':
        return get_sp500_stocks()
    return get_sp100_stocks()


# ── CoinGecko Crypto Scanner ─────────────────────────────────────────────────

def _get_binance_kline_changes(symbol: str) -> tuple:
    """Return (weekly_pct, monthly_pct, current_price) for a Binance USDT pair using daily klines."""
    try:
        resp = requests.get(
            f"{_BINANCE_BASE}/klines",
            params={'symbol': symbol, 'interval': '1d', 'limit': 32},
            headers=_binance_headers(),
            timeout=15,
        )
        if resp.status_code != 200:
            return None, None, None
        klines = resp.json()
        if len(klines) < 8:
            return None, None, None
        current       = float(klines[-1][4])          # latest close
        price_7d_ago  = float(klines[-8][1])           # open of candle 7 days back
        price_30d_ago = float(klines[-31][1]) if len(klines) >= 31 else float(klines[0][1])
        weekly  = (current - price_7d_ago)  / price_7d_ago  * 100
        monthly = (current - price_30d_ago) / price_30d_ago * 100
        return round(weekly, 2), round(monthly, 2), current
    except Exception as e:
        return None, None, None


def _fetch_binance_coins(universe_size: int) -> list:
    """Fetch top N crypto coins from Binance by 24h USD volume, with 7d/30d changes from klines."""
    try:
        resp = requests.get(f"{_BINANCE_BASE}/ticker/24hr", headers=_binance_headers(), timeout=30)
        if resp.status_code != 200:
            return []
        tickers = resp.json()
    except Exception as e:
        return []

    usdt = [
        t for t in tickers
        if t['symbol'].endswith('USDT') and t['symbol'][:-4] not in _STABLE_SYMBOLS
    ]
    usdt.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
    top_tickers = usdt[:universe_size]


    def build_coin(ticker):
        symbol    = ticker['symbol']
        base      = symbol[:-4]
        quote_vol = float(ticker.get('quoteVolume', 0))
        cap_label = 'large' if quote_vol > 100_000_000 else 'mid' if quote_vol > 10_000_000 else 'small'
        weekly, monthly, current = _get_binance_kline_changes(symbol)
        if weekly is None:
            return None
        return {
            'symbol':    base,
            'name':      base,
            '_weekly':   weekly,
            '_monthly':  monthly,
            '_current':  current,
            '_quoteVol': quote_vol,
            '_capLabel': cap_label,
        }

    coins = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(build_coin, t): t for t in top_tickers}
        for future in as_completed(futures):
            result = future.result()
            if result:
                coins.append(result)

    return coins


def scan_crypto_via_binance(universe_size, weekly_threshold, monthly_threshold, market_cap_filter='all'):
    """Scan crypto via Binance public API — no key needed, 1200 req/min limit."""
    coins = _fetch_binance_coins(universe_size)
    if not coins:
        return []

    results = []
    for coin in coins:
        weekly  = coin['_weekly']
        monthly = coin['_monthly']
        current = coin['_current']
        cap     = coin['_capLabel']

        if market_cap_filter != 'all' and cap != market_cap_filter:
            continue
        if weekly <= -weekly_threshold and monthly <= -monthly_threshold:
            w_factor = 1 + weekly  / 100
            m_factor = 1 + monthly / 100
            results.append({
                'symbol':          coin['symbol'],
                'name':            coin['name'],
                'currentPrice':    round(current, 6),
                'weeklyChange':    weekly,
                'monthlyChange':   monthly,
                'priceOneWeekAgo': round(current / w_factor, 6) if w_factor else 0,
                'priceOneMonthAgo':round(current / m_factor, 6) if m_factor else 0,
                'volume':          int(coin['_quoteVol']),
                'marketCap':       cap,
                'sector':          'crypto',
                'source':          'binance',
            })

    results.sort(key=lambda x: x['weeklyChange'])
    return results


def scan_crypto_via_binance_streaming(universe_size, weekly_threshold, monthly_threshold, market_cap_filter='all'):
    """Scan crypto and yield (processed_count, match_result) tuples for streaming progress."""
    
    # Fetch all tickers first
    try:
        resp = requests.get(f"{_BINANCE_BASE}/ticker/24hr", headers=_binance_headers(), timeout=30)
        if resp.status_code != 200:
            return
        tickers = resp.json()
    except Exception as e:
        return

    usdt = [
        t for t in tickers
        if t['symbol'].endswith('USDT') and t['symbol'][:-4] not in _STABLE_SYMBOLS
    ]
    usdt.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
    top_tickers = usdt[:universe_size]


    def process_coin(ticker):
        """Process a single coin and return result if it matches criteria."""
        symbol    = ticker['symbol']
        base      = symbol[:-4]
        quote_vol = float(ticker.get('quoteVolume', 0))
        cap_label = 'large' if quote_vol > 100_000_000 else 'mid' if quote_vol > 10_000_000 else 'small'
        
        weekly, monthly, current = _get_binance_kline_changes(symbol)
        if weekly is None:
            return None
        
        # Check if it matches criteria
        if market_cap_filter != 'all' and cap_label != market_cap_filter:
            return None
        
        if weekly <= -weekly_threshold and monthly <= -monthly_threshold:
            w_factor = 1 + weekly / 100
            m_factor = 1 + monthly / 100
            result = {
                'symbol':          base,
                'name':            base,
                'currentPrice':    round(current, 6),
                'weeklyChange':    weekly,
                'monthlyChange':   monthly,
                'priceOneWeekAgo': round(current / w_factor, 6) if w_factor else 0,
                'priceOneMonthAgo':round(current / m_factor, 6) if m_factor else 0,
                'volume':          int(quote_vol),
                'marketCap':       cap_label,
                'sector':          'crypto',
                'source':          'binance',
            }
            return result
        return None

    processed = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_coin, ticker): ticker for ticker in top_tickers}
        for future in as_completed(futures):
            processed += 1
            yield (processed, future.result())


# ── Stock Universe Router ─────────────────────────────────────────────────────

def get_stock_universe(universe_type, market='india'):
    """Get stock universe by market and universe type"""

    if market == 'us':
        stocks = get_us_universe(universe_type)
        return stocks

    # India (default)
    if universe_type == 'nifty50':
        stocks = get_nifty_50_stocks()
        return stocks
    elif universe_type == 'nifty100':
        stocks = get_nifty_100_stocks()
        return stocks
    elif universe_type == 'nifty200':
        stocks = get_nifty_200_stocks()
        return stocks
    elif universe_type == 'nifty500':
        stocks = get_nifty_500_stocks()
        return stocks
    else:
        return get_nifty_100_stocks()

def process_single_stock(stock, weekly_threshold, monthly_threshold):
    """Process a single stock and return result if it matches criteria"""
    try:
        # Fetch REAL market data from Yahoo Finance
        market_data = fetch_yahoo_finance_data(stock['symbol'])
        
        # Count data quality
        if market_data['status'] == 'success':
            # Check criteria
            weekly_decline = market_data['weeklyChange'] <= -weekly_threshold
            monthly_decline = market_data['monthlyChange'] <= -monthly_threshold
            
            if weekly_decline and monthly_decline:
                result = {**stock, **market_data}
                return {'status': 'match', 'data': result}
            else:
                return {'status': 'no_match', 'data': market_data}
        else:  # failed
            return {'status': 'failed', 'data': market_data}
    except Exception as e:
        return {'status': 'error', 'data': None}

def fetch_yahoo_finance_data(symbol):
    """Fetch real stock data from Yahoo Finance - ONLY working source"""
    
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        params = {
            'range': '1mo',
            'interval': '1d',
            'includePrePost': 'true'
        }
        
        # Small delay to respect API rate limits (but much less than 1 second)
        time.sleep(0.05)
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('chart') and data['chart'].get('result'):
                result = data['chart']['result'][0]
                
                timestamps = result['timestamp']
                indicators = result['indicators']['quote'][0]
                closes = indicators['close']
                
                # Remove None values and create valid data points
                valid_data = [(ts, close) for ts, close in zip(timestamps, closes) if close is not None]
                
                if len(valid_data) >= 7:  # Need at least a week of data
                    # Use regularMarketPrice for today's actual close.
                    # valid_data[-1] can be yesterday's close when today's
                    # candle hasn't settled in the chart yet.
                    current_price = result.get('meta', {}).get('regularMarketPrice') or valid_data[-1][1]
                    
                    # Calculate dates for comparison from now, not from last chart timestamp
                    now_ts = int(time.time())
                    week_ago_ts = now_ts - (7 * 24 * 60 * 60)
                    month_ago_ts = now_ts - (30 * 24 * 60 * 60)
                    
                    # Find closest prices to our target dates
                    week_price = None
                    month_price = None
                    
                    for ts, price in valid_data:
                        if ts <= week_ago_ts:
                            week_price = price
                        if ts <= month_ago_ts:
                            month_price = price
                    
                    # Use earliest available if we don't have enough history
                    if week_price is None:
                        week_price = valid_data[0][1]
                    if month_price is None:
                        month_price = valid_data[0][1]
                    
                    # Calculate percentage changes
                    weekly_change = ((current_price - week_price) / week_price) * 100
                    monthly_change = ((current_price - month_price) / month_price) * 100
                    
                    # Get volume (latest non-null)
                    volumes = indicators.get('volume', [])
                    volume = 0
                    for v in reversed(volumes):
                        if v is not None and v > 0:
                            volume = int(v)
                            break
                    
                    
                    return {
                        'symbol': symbol,
                        'currentPrice': round(current_price, 2),
                        'priceOneWeekAgo': round(week_price, 2),
                        'priceOneMonthAgo': round(month_price, 2),
                        'weeklyChange': round(weekly_change, 2),
                        'monthlyChange': round(monthly_change, 2),
                        'volume': volume,
                        'lastUpdated': datetime.now().isoformat(),
                        'status': 'success',
                        'source': 'yahoo_finance'
                    }
        
        
    except Exception:
        pass

    # If Yahoo Finance fails, return clear error
    return {
        'symbol': symbol,
        'error': 'Yahoo Finance API failed',
        'status': 'failed',
        'lastUpdated': datetime.now().isoformat(),
        'note': 'This stock will be excluded from scan results'
    }

# Flask Routes
@app.route('/')
def home():
    return jsonify({
        'status': 'healthy',
        'message': 'BuyTheDip API is operational and ready to receive requests.'
    })

@app.route('/stock-universe/<universe_type>')
def get_universe(universe_type):
    """Get stock universe by type"""
    try:
        stocks = get_stock_universe(universe_type)
        
        return jsonify({
            'universe_type': universe_type,
            'stocks': stocks,
            'total': len(stocks),
            'source': 'static_curated_list',
            'reliability': 'high',
            'timestamp': datetime.now().isoformat(),
            'message': f'Successfully got {len(stocks)} stocks for {universe_type}'
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'universe_type': universe_type,
            'message': 'Failed to get stock universe'
        }), 500

@app.route('/scan-stream')
def scan_stream():
    """Streaming version of /scan using Server-Sent Events (SSE).

    Accepts the same parameters as /scan but via query string (GET),
    because EventSource only supports GET.

    Emits these events as data becomes available:
      init     { total, universe_size, universe, market }
      progress { processed, total, matches }
      match    { ...stock result dict... }
      done     { total_matches, universe_size, processed, success_rate, market }
      error    { message }
    """
    try:
        weekly_threshold  = float(request.args.get('weeklyThreshold', 5))
        monthly_threshold = float(request.args.get('monthlyThreshold', 10))
        market_cap_filter = request.args.get('marketCapFilter', 'all')
        sector_filter     = request.args.get('sectorFilter', 'all')
        stock_universe    = request.args.get('stockUniverse', 'nifty100')
        market            = request.args.get('market', 'india')
    except Exception as e:
        return jsonify({'error': f'Invalid params: {e}'}), 400

    def sse(event, data):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    def generate():
        try:
            # ── Crypto: streaming per-coin scan ──
            if market == 'crypto':
                size_map = {'top50': 50, 'top100': 100, 'top200': 200, 'top500': 500}
                universe_size = size_map.get(stock_universe, 100)
                yield sse('init', {
                    'total': universe_size, 'universe_size': universe_size,
                    'universe': stock_universe, 'market': 'crypto',
                })
                
                matches = []
                for processed, result in scan_crypto_via_binance_streaming(
                    universe_size, weekly_threshold, monthly_threshold, market_cap_filter
                ):
                    if result:  # It's a match
                        matches.append(result)
                        yield sse('match', result)
                    
                    # Send progress update every coin processed
                    yield sse('progress', {
                        'processed': processed, 'total': universe_size, 'matches': len(matches)
                    })
                
                yield sse('done', {
                    'total_matches': len(matches),
                    'stock_universe': stock_universe,
                    'universe_size': universe_size,
                    'processed': universe_size,
                    'success_rate': '100%',
                    'market': 'crypto',
                })
                return

            # ── India / US: per-symbol streaming ──
            stock_list = get_stock_universe(stock_universe, market)
            filtered_stocks = [
                s for s in stock_list
                if (market_cap_filter == 'all' or s.get('marketCap') == market_cap_filter)
                and (sector_filter == 'all' or s.get('sector') == sector_filter)
            ]

            yield sse('init', {
                'total': len(filtered_stocks),
                'universe_size': len(stock_list),
                'universe': stock_universe,
                'market': market,
            })

            processed = 0
            matches = []
            real_data_count = 0
            failed_count = 0
            failed_stocks = []

            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_stock = {
                    executor.submit(process_single_stock, stock, weekly_threshold, monthly_threshold): stock
                    for stock in filtered_stocks
                }
                for future in as_completed(future_to_stock):
                    stock = future_to_stock[future]
                    processed += 1
                    try:
                        result = future.result()
                        if result['status'] == 'match':
                            matches.append(result['data'])
                            real_data_count += 1
                            yield sse('match', result['data'])
                        elif result['status'] == 'no_match':
                            real_data_count += 1
                        else:
                            failed_count += 1
                            failed_stocks.append(stock['symbol'])
                    except Exception as e:
                        failed_count += 1
                        failed_stocks.append(stock['symbol'])

                    yield sse('progress', {
                        'processed': processed,
                        'total': len(filtered_stocks),
                        'matches': len(matches),
                    })

            yield sse('done', {
                'total_matches': len(matches),
                'stock_universe': stock_universe,
                'universe_size': len(stock_list),
                'processed': processed,
                'success_rate': f"{((real_data_count / processed) * 100):.1f}%" if processed > 0 else "0%",
                'market': market,
                'failed_symbols': failed_stocks,
            })
        except Exception as e:
            yield sse('error', {'message': str(e)})

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',          # disables nginx / proxy buffering
            'Connection': 'keep-alive',
        },
    )

@app.route('/scan', methods=['POST'])
def scan_stocks():
    """Scan stocks with Yahoo Finance data only"""
    try:
        data = request.get_json()
        
        # Get scan criteria
        weekly_threshold  = float(data.get('weeklyThreshold', 5))
        monthly_threshold = float(data.get('monthlyThreshold', 10))
        market_cap_filter = data.get('marketCapFilter', 'all')
        sector_filter     = data.get('sectorFilter', 'all')
        stock_universe    = data.get('stockUniverse', 'nifty100')
        market            = data.get('market', 'india')  # 'india' | 'us' | 'crypto'


        # ── Crypto: use Binance ──
        if market == 'crypto':
            size_map = {'top50': 50, 'top100': 100, 'top200': 200, 'top500': 500}
            universe_size = size_map.get(stock_universe, 100)
            results = scan_crypto_via_binance(universe_size, weekly_threshold, monthly_threshold, market_cap_filter)
            return jsonify({
                'results':              results,
                'total_matches':        len(results),
                'stock_universe':       stock_universe,
                'universe_size':        universe_size,
                'processed':            universe_size,
                'yahoo_finance_success':universe_size,
                'real_data_count':      universe_size,
                'failed_count':         0,
                'success_rate':         '100%',
                'market':               'crypto',
                'data_source':          'Binance',
                'timestamp':            datetime.now().isoformat(),
                'message':              f'Scanned top {universe_size} coins: {len(results)} dip opportunities found',
            })

        # ── India / US: use Yahoo Finance ──
        # Get stock list
        stock_list = get_stock_universe(stock_universe, market)
        
        # Filter stocks based on criteria
        filtered_stocks = []
        for stock in stock_list:
            # Apply filters
            if market_cap_filter != 'all' and stock.get('marketCap') != market_cap_filter:
                continue
            if sector_filter != 'all' and stock.get('sector') != sector_filter:
                continue
            filtered_stocks.append(stock)
        
        
        results = []
        processed = 0
        real_data_count = 0
        failed_count = 0
        failed_stocks = []
        
        # Process stocks concurrently with ThreadPoolExecutor
        # Use max 5 concurrent threads to respect API rate limits
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_stock = {
                executor.submit(process_single_stock, stock, weekly_threshold, monthly_threshold): stock 
                for stock in filtered_stocks
            }
            
            # Process completed futures as they complete
            for future in as_completed(future_to_stock):
                stock = future_to_stock[future]
                processed += 1
                
                try:
                    result = future.result()
                    
                    if result['status'] == 'match':
                        results.append(result['data'])
                        real_data_count += 1
                    elif result['status'] == 'no_match':
                        real_data_count += 1
                    elif result['status'] == 'failed':
                        failed_count += 1
                        failed_stocks.append({'symbol': stock['symbol'], 'name': stock['name']})
                    elif result['status'] == 'error':
                        failed_count += 1
                        failed_stocks.append({'symbol': stock['symbol'], 'name': stock['name']})
                        
                except Exception as e:
                    failed_count += 1
                    failed_stocks.append({'symbol': stock['symbol'], 'name': stock['name']})
                
        if failed_stocks:
            pass

        return jsonify({
            'results': results,
            'total_matches': len(results),
            'stock_universe': stock_universe,
            'universe_size': len(stock_list),
            'processed': processed,
            'yahoo_finance_success': real_data_count,
            'failed_count': failed_count,
            'success_rate': f"{((real_data_count / processed) * 100):.1f}%" if processed > 0 else "0%",
            'criteria': {
                'weeklyThreshold': weekly_threshold,
                'monthlyThreshold': monthly_threshold,
                'marketCapFilter': market_cap_filter,
                'sectorFilter': sector_filter,
                'stockUniverse': stock_universe
            },
            'market': market,
            'data_source': 'Yahoo Finance (Real market data)',
            'stock_source': 'Static curated lists',
            'policy': 'Real data only - no simulation',
            'timestamp': datetime.now().isoformat(),
            'message': f'Scanned {stock_universe}: {len(results)} declining stocks found from {real_data_count} successful Yahoo Finance calls'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/tickers')
def tickers():
    """Return current values for headline indices used by the UI status bar.

    Response shape:
      {
        "nifty": {"value": 22418.30, "change_pct": -1.42},
        "dow":   {"value": 41912.20, "change_pct": -0.31},
        "btc":   {"value": 96420.00, "change_pct":  1.42}
      }

    Any individual ticker that fails returns null for that key so the
    frontend can degrade gracefully.
    """
    symbols = [
        ('nifty', '^NSEI'),
        ('sp500', '^GSPC'),
        ('dow',   '^DJI'),
        ('btc',   'BTC-USD'),
    ]
    out = {}
    for key, symbol in symbols:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            r = requests.get(
                url,
                params={'interval': '1d', 'range': '5d'},
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            result = data['chart']['result'][0]
            meta = result.get('meta', {})
            price = meta.get('regularMarketPrice')

            # Determine prev close correctly regardless of whether today's
            # candle is settled or still None in the chart.
            # If the last close in the chart is None → today not settled yet,
            # so last non-null IS yesterday's close.
            # If the last close is not None → today is settled, use second-to-last.
            closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
            non_null_closes = [c for c in closes if c is not None]

            if price is None or len(non_null_closes) < 2:
                out[key] = None
                continue

            last_raw = closes[-1] if closes else None
            if last_raw is None:
                # Today's candle not settled — last non-null is yesterday
                prev = non_null_closes[-1]
            else:
                # Today's candle is settled — second-to-last is yesterday
                prev = non_null_closes[-2]

            if prev == 0:
                out[key] = None
                continue
            change_pct = ((price - prev) / prev) * 100
            change_abs = price - prev
            out[key] = {'value': round(price, 2), 'change_pct': round(change_pct, 2), 'change_abs': round(change_abs, 2)}
        except Exception as e:
            out[key] = None
    return jsonify(out)

@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'message': 'API is operational and healthy.'
    })

@app.route('/test-stock/<symbol>')
def test_stock(symbol):
    """Test Yahoo Finance data for specific stock"""
    if not symbol.endswith('.NS'):
        symbol += '.NS'
    
    data = fetch_yahoo_finance_data(symbol)
    return jsonify({
        'symbol': symbol,
        'data': data,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = not (os.environ.get('RENDER') or os.environ.get('PORT'))
    environment = "Production (Render)" if (os.environ.get('RENDER') or os.environ.get('PORT')) else "Development"
    
    app.run(debug=debug, host='0.0.0.0', port=port)