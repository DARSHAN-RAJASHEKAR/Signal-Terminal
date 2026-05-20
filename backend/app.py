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
    print("Production CORS enabled for Vercel domains")
else:
    # Development
    CORS(app)
    print("Development CORS enabled for all origins")

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
        {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'mid'},
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
        {'symbol': 'ETERNAL.NS', 'name': 'Zomato', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'ZEEL.NS', 'name': 'Zee Entertainment Enterprises', 'sector': 'consumer', 'marketCap': 'small'}
    ]
    
def get_nifty_500_stocks():
    """Nifty 500 stocks - comprehensive list of top 500+ Indian companies"""
    return [
        # Large Cap (1-50)
        {'symbol': '360ONE.NS', 'name': '360 ONE WAM', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': '3MINDIA.NS', 'name': '3M India', 'sector': 'diversified', 'marketCap': 'large'},
        {'symbol': 'ABB.NS', 'name': 'ABB India', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ACC.NS', 'name': 'ACC', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'ACMESOLAR.NS', 'name': 'ACME Solar Holdings', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'AIAENG.NS', 'name': 'AIA Engineering', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'APLAPOLLO.NS', 'name': 'APL Apollo Tubes', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'AUBANK.NS', 'name': 'AU Small Finance Bank', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'AWL.NS', 'name': 'AWL Agri Business', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'AADHARHFC.NS', 'name': 'Aadhar Housing Finance', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'AARTIIND.NS', 'name': 'Aarti Industries', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'AAVAS.NS', 'name': 'Aavas Financiers', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'ABCAPITAL.NS', 'name': 'Aditya Birla Capital', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'ABFRL.NS', 'name': 'Aditya Birla Fashion and Retail', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'ADANIENSOL.NS', 'name': 'Adani Energy Solutions', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ADANIENT.NS', 'name': 'Adani Enterprises', 'sector': 'metals', 'marketCap': 'large'},
        {'symbol': 'ADANIGREEN.NS', 'name': 'Adani Green Energy', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ADANIPORTS.NS', 'name': 'Adani Ports and Special Economic Zone', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'ADANIPOWER.NS', 'name': 'Adani Power', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'ATGL.NS', 'name': 'Adani Total Gas', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'AWL.NS', 'name': 'Adani Wilmar', 'sector': 'fmcg', 'marketCap': 'large'},
        {'symbol': 'AEGISLOG.NS', 'name': 'Aegis Logistics', 'sector': 'energy', 'marketCap': 'large'},
        {'symbol': 'AETHER.NS', 'name': 'Aether Industries', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'AFFLE.NS', 'name': 'Affle (India)', 'sector': 'it', 'marketCap': 'large'},
        {'symbol': 'AJANTPHARM.NS', 'name': 'Ajanta Pharma', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'AKZOINDIA.NS', 'name': 'Akzo Nobel India', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'ALKEM.NS', 'name': 'Alkem Laboratories', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'ALKYLAMINE.NS', 'name': 'Alkyl Amines Chemicals', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'ALLCARGO.NS', 'name': 'Allcargo Logistics', 'sector': 'infrastructure', 'marketCap': 'large'},
        {'symbol': 'ALOKINDS.NS', 'name': 'Alok Industries', 'sector': 'textiles', 'marketCap': 'large'},
        {'symbol': 'AMBER.NS', 'name': 'Amber Enterprises India', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'AMBUJACEM.NS', 'name': 'Ambuja Cements', 'sector': 'cement', 'marketCap': 'large'},
        {'symbol': 'ANANTRAJ.NS', 'name': 'Anant Raj', 'sector': 'realty', 'marketCap': 'large'},
        {'symbol': 'ANGELONE.NS', 'name': 'Angel One', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'APARINDS.NS', 'name': 'Apar Industries', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'APOLLOHOSP.NS', 'name': 'Apollo Hospitals Enterprise', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'APOLLOTYRE.NS', 'name': 'Apollo Tyres', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'APTUS.NS', 'name': 'Aptus Value Housing Finance India', 'sector': 'banking', 'marketCap': 'large'},
        {'symbol': 'ASAHIINDIA.NS', 'name': 'Asahi India Glass', 'sector': 'auto', 'marketCap': 'large'},
        {'symbol': 'ASHOKLEY.NS', 'name': 'Ashok Leyland', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ASIANPAINT.NS', 'name': 'Asian Paints', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'ASTERDM.NS', 'name': 'Aster DM Healthcare', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'ASTRAL.NS', 'name': 'Astral', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ASTRAZEN.NS', 'name': 'AstraZeneca Pharma India', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'ATLANTAA.NS', 'name': 'Atlantaa', 'sector': 'capital_goods', 'marketCap': 'large'},
        {'symbol': 'ATUL.NS', 'name': 'Atul', 'sector': 'chemicals', 'marketCap': 'large'},
        {'symbol': 'AUROPHARMA.NS', 'name': 'Aurobindo Pharma', 'sector': 'healthcare', 'marketCap': 'large'},
        {'symbol': 'DMART.NS', 'name': 'Avenue Supermarts', 'sector': 'consumer', 'marketCap': 'large'},
        {'symbol': 'AXISBANK.NS', 'name': 'Axis Bank', 'sector': 'banking', 'marketCap': 'large'},
        
        # Mid Cap (51-100)
        {'symbol': 'BSE.NS', 'name': 'BSE', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BAJAJ-AUTO.NS', 'name': 'Bajaj Auto', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'BAJFINANCE.NS', 'name': 'Bajaj Finance', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BAJAJFINSV.NS', 'name': 'Bajaj Finserv', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BAJAJHLDNG.NS', 'name': 'Bajaj Holdings & Investment', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BAJAJHFL.NS', 'name': 'Bajaj Housing Finance', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BALKRISIND.NS', 'name': 'Balkrishna Industries', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'BALRAMCHIN.NS', 'name': 'Balrampur Chini Mills', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'BANDHANBNK.NS', 'name': 'Bandhan Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BANKBARODA.NS', 'name': 'Bank of Baroda', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BANKINDIA.NS', 'name': 'Bank of India', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'MAHABANK.NS', 'name': 'Bank of Maharashtra', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'BASF.NS', 'name': 'BASF India', 'sector': 'chemicals', 'marketCap': 'mid'},
        {'symbol': 'BATAINDIA.NS', 'name': 'Bata India', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'BAYERCROP.NS', 'name': 'Bayer CropScience', 'sector': 'chemicals', 'marketCap': 'mid'},
        {'symbol': 'BDL.NS', 'name': 'Bharat Dynamics', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'BEL.NS', 'name': 'Bharat Electronics', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'BHARATFORG.NS', 'name': 'Bharat Forge', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'BHEL.NS', 'name': 'Bharat Heavy Electricals', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'BPCL.NS', 'name': 'Bharat Petroleum Corporation', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel', 'sector': 'telecom', 'marketCap': 'mid'},
        {'symbol': 'BHARTIHEXA.NS', 'name': 'Bharti Hexacom', 'sector': 'telecom', 'marketCap': 'mid'},
        {'symbol': 'BIKAJI.NS', 'name': 'Bikaji Foods International', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'BIOCON.NS', 'name': 'Biocon', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'BIRLACORPN.NS', 'name': 'Birla Corporation', 'sector': 'cement', 'marketCap': 'mid'},
        {'symbol': 'BSOFT.NS', 'name': 'Birlasoft', 'sector': 'it', 'marketCap': 'mid'},
        {'symbol': 'BLISSGVS.NS', 'name': 'Bliss GVS Pharma', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'BLUEDART.NS', 'name': 'Blue Dart Express', 'sector': 'infrastructure', 'marketCap': 'mid'},
        {'symbol': 'BLUESTARCO.NS', 'name': 'Blue Star', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'BOSCHLTD.NS', 'name': 'Bosch', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'BRIGADE.NS', 'name': 'Brigade Enterprises', 'sector': 'realty', 'marketCap': 'mid'},
        {'symbol': 'BRITANNIA.NS', 'name': 'Britannia Industries', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'CCL.NS', 'name': 'CCL Products (India)', 'sector': 'fmcg', 'marketCap': 'mid'},
        {'symbol': 'CESC.NS', 'name': 'CESC', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'CGPOWER.NS', 'name': 'CG Power and Industrial Solutions', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'CAMS.NS', 'name': 'Computer Age Management Services', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'CANBK.NS', 'name': 'Canara Bank', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'CANFINHOME.NS', 'name': 'Can Fin Homes', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'CAPLIPOINT.NS', 'name': 'Caplin Point Laboratories', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'CARBORUNIV.NS', 'name': 'Carborundum Universal', 'sector': 'capital_goods', 'marketCap': 'mid'},
        {'symbol': 'CASTROLIND.NS', 'name': 'Castrol India', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'CEATLTD.NS', 'name': 'CEAT', 'sector': 'auto', 'marketCap': 'mid'},
        {'symbol': 'ABREL.NS', 'name': 'Century Textiles & Industries', 'sector': 'textiles', 'marketCap': 'mid'},
        {'symbol': 'CERA.NS', 'name': 'Cera Sanitaryware', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'CHALET.NS', 'name': 'Chalet Hotels', 'sector': 'consumer', 'marketCap': 'mid'},
        {'symbol': 'CHAMBLFERT.NS', 'name': 'Chambal Fertilizers & Chemicals', 'sector': 'chemicals', 'marketCap': 'mid'},
        {'symbol': 'CHENNPETRO.NS', 'name': 'Chennai Petroleum Corporation', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'CHOLAFIN.NS', 'name': 'Cholamandalam Investment and Finance Company', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'CHOLAHLDNG.NS', 'name': 'Cholamandalam Financial Holdings', 'sector': 'banking', 'marketCap': 'mid'},
        {'symbol': 'CIPLA.NS', 'name': 'Cipla', 'sector': 'healthcare', 'marketCap': 'mid'},
        {'symbol': 'COALINDIA.NS', 'name': 'Coal India', 'sector': 'energy', 'marketCap': 'mid'},
        {'symbol': 'COCHINSHIP.NS', 'name': 'Cochin Shipyard', 'sector': 'capital_goods', 'marketCap': 'mid'},
        
        # Small Cap (101-250)
        {'symbol': 'COFORGE.NS', 'name': 'Coforge', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'COLPAL.NS', 'name': 'Colgate Palmolive (India)', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'CONCOR.NS', 'name': 'Container Corporation of India', 'sector': 'infrastructure', 'marketCap': 'small'},
        {'symbol': 'COROMANDEL.NS', 'name': 'Coromandel International', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'CREDITACC.NS', 'name': 'Credit Access Grameen', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'CROMPTON.NS', 'name': 'Crompton Greaves Consumer Electricals', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'CUMMINSIND.NS', 'name': 'Cummins India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'CYIENT.NS', 'name': 'Cyient', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'DLF.NS', 'name': 'DLF', 'sector': 'realty', 'marketCap': 'small'},
        {'symbol': 'DABUR.NS', 'name': 'Dabur India', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'DALMIASUG.NS', 'name': 'Dalmia Bharat Sugar and Industries', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'DEEPAKNTR.NS', 'name': 'Deepak Nitrite', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'DELTACORP.NS', 'name': 'Delta Corp', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'DEVYANI.NS', 'name': 'Devyani International', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'DIVISLAB.NS', 'name': 'Divi\'s Laboratories', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'DIXON.NS', 'name': 'Dixon Technologies (India)', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'DRREDDY.NS', 'name': 'Dr. Reddy\'s Laboratories', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'EICHERMOT.NS', 'name': 'Eicher Motors', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'EIDPARRY.NS', 'name': 'EID Parry (India)', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'EIHOTEL.NS', 'name': 'EIH', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'ELGIEQUIP.NS', 'name': 'Elgi Equipments', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'EMAMILTD.NS', 'name': 'Emami', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'ENDURANCE.NS', 'name': 'Endurance Technologies', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'ENGINERSIN.NS', 'name': 'Engineers India', 'sector': 'construction', 'marketCap': 'small'},
        {'symbol': 'EQUITASBNK.NS', 'name': 'Equitas Small Finance Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'ESCORTS.NS', 'name': 'Escorts Kubota', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'ESABINDIA.NS', 'name': 'Esab India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'ETERNAL.NS', 'name': 'Eternal', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'EVEREADY.NS', 'name': 'Eveready Industries India', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'EXIDEIND.NS', 'name': 'Exide Industries', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'NYKAA.NS', 'name': 'FSN E-Commerce Ventures', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'FINEORG.NS', 'name': 'Fine Organic Industries', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'FINPIPE.NS', 'name': 'Finolex Cables', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'FEDERALBNK.NS', 'name': 'Federal Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'FORTIS.NS', 'name': 'Fortis Healthcare', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'FRETAIL.NS', 'name': 'Future Retail', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'GAIL.NS', 'name': 'GAIL (India)', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'GARFIBRES.NS', 'name': 'Garware Technical Fibres', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'GMRAIRPORT.NS', 'name': 'GMR Airports', 'sector': 'infrastructure', 'marketCap': 'small'},
        {'symbol': 'GNFC.NS', 'name': 'Gujarat Narmada Valley Fertilizers & Chemicals', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'GLENMARK.NS', 'name': 'Glenmark Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'GLAXO.NS', 'name': 'GlaxoSmithKline Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'GMDCLTD.NS', 'name': 'Gujarat Mineral Development Corporation', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'GMRAIRPORT.NS', 'name': 'GMR Infrastructure', 'sector': 'infrastructure', 'marketCap': 'small'},
        {'symbol': 'GODFRYPHLP.NS', 'name': 'Godfrey Phillips India', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'GODREJCP.NS', 'name': 'Godrej Consumer Products', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'GODREJIND.NS', 'name': 'Godrej Industries', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'GODREJPROP.NS', 'name': 'Godrej Properties', 'sector': 'realty', 'marketCap': 'small'},
        {'symbol': 'GRANULES.NS', 'name': 'Granules India', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'GRAPHITE.NS', 'name': 'Graphite India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'GRASIM.NS', 'name': 'Grasim Industries', 'sector': 'cement', 'marketCap': 'small'},
        {'symbol': 'GRINFRA.NS', 'name': 'G R Infraprojects', 'sector': 'construction', 'marketCap': 'small'},
        {'symbol': 'GESHIP.NS', 'name': 'Great Eastern Shipping Company', 'sector': 'infrastructure', 'marketCap': 'small'},
        {'symbol': 'GRSE.NS', 'name': 'Garden Reach Shipbuilders & Engineers', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'GSFC.NS', 'name': 'Gujarat State Fertilizers & Chemicals', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'GSPL.NS', 'name': 'Gujarat State Petronet', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'GUJGASLTD.NS', 'name': 'Gujarat Gas', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'GULFOILLUB.NS', 'name': 'Gulf Oil Lubricants India', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'HCG.NS', 'name': 'HealthCare Global Enterprises', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'HCLTECH.NS', 'name': 'HCL Technologies', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'HDFCAMC.NS', 'name': 'HDFC Asset Management Company', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'HDFCLIFE.NS', 'name': 'HDFC Life Insurance Company', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'HFCL.NS', 'name': 'HFCL', 'sector': 'telecom', 'marketCap': 'small'},
        {'symbol': 'HLEGLAS.NS', 'name': 'HLE Glascoat', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'HMVL.NS', 'name': 'Hindustan Media Ventures', 'sector': 'media', 'marketCap': 'small'},
        {'symbol': 'HONAUT.NS', 'name': 'Honeywell Automation India', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'HUDCO.NS', 'name': 'Housing & Urban Development Corporation', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'HAVELLS.NS', 'name': 'Havells India', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'HEIDELBERG.NS', 'name': 'HeidelbergCement India', 'sector': 'cement', 'marketCap': 'small'},
        {'symbol': 'HEROMOTOCO.NS', 'name': 'Hero MotoCorp', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'HEXT.NS', 'name': 'Hexaware Technologies', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'HIKAL.NS', 'name': 'Hical Chemicals', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'HINDALCO.NS', 'name': 'Hindalco Industries', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'HAL.NS', 'name': 'Hindustan Aeronautics', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'HINDCOPPER.NS', 'name': 'Hindustan Copper', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'HINDPETRO.NS', 'name': 'Hindustan Petroleum Corporation', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'HINDUNILVR.NS', 'name': 'Hindustan Unilever', 'sector': 'fmcg', 'marketCap': 'small'},
        {'symbol': 'HINDZINC.NS', 'name': 'Hindustan Zinc', 'sector': 'metals', 'marketCap': 'small'},
        {'symbol': 'HIMATSEIDE.NS', 'name': 'Himatsingka Seide', 'sector': 'textiles', 'marketCap': 'small'},
        {'symbol': 'HPL.NS', 'name': 'HPL Electric & Power', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'AGI.NS', 'name': 'HSIL', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'HYUNDAI.NS', 'name': 'Hyundai Motor India', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'SAMMAANCAP.NS', 'name': 'Indiabulls Housing Finance', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'ICICIGI.NS', 'name': 'ICICI Lombard General Insurance Company', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'ICICIPRULI.NS', 'name': 'ICICI Prudential Life Insurance Company', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'IDEA.NS', 'name': 'Vodafone Idea', 'sector': 'telecom', 'marketCap': 'small'},
        {'symbol': 'IDFCFIRSTB.NS', 'name': 'IDFC First Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'IEX.NS', 'name': 'Indian Energy Exchange', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'IFBIND.NS', 'name': 'IFB Industries', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'IGARASHI.NS', 'name': 'Igarashi Motors India', 'sector': 'auto', 'marketCap': 'small'},
        {'symbol': 'IIFL.NS', 'name': 'India Infoline Finance', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'INDIACEM.NS', 'name': 'The India Cements', 'sector': 'cement', 'marketCap': 'small'},
        {'symbol': 'INDIAMART.NS', 'name': 'IndiaMART InterMESH', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'INDIANB.NS', 'name': 'Indian Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'INDHOTEL.NS', 'name': 'Indian Hotels Co.', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'IOC.NS', 'name': 'Indian Oil Corporation', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'IRCTC.NS', 'name': 'Indian Railway Catering And Tourism Corporation', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'IRFC.NS', 'name': 'Indian Railway Finance Corporation', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'IREDA.NS', 'name': 'Indian Renewable Energy Development Agency', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'INDIGO.NS', 'name': 'InterGlobe Aviation', 'sector': 'infrastructure', 'marketCap': 'small'},
        {'symbol': 'IGL.NS', 'name': 'Indraprastha Gas', 'sector': 'energy', 'marketCap': 'small'},
        {'symbol': 'INDUSTOWER.NS', 'name': 'Indus Towers', 'sector': 'telecom', 'marketCap': 'small'},
        {'symbol': 'INDUSINDBK.NS', 'name': 'IndusInd Bank', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'NAUKRI.NS', 'name': 'Info Edge (India)', 'sector': 'consumer', 'marketCap': 'small'},
        {'symbol': 'INFY.NS', 'name': 'Infosys', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'INGERRAND.NS', 'name': 'Ingersoll Rand (India)', 'sector': 'capital_goods', 'marketCap': 'small'},
        {'symbol': 'INSECTICID.NS', 'name': 'Insecticides (India)', 'sector': 'chemicals', 'marketCap': 'small'},
        {'symbol': 'INTELLECT.NS', 'name': 'Intellect Design Arena', 'sector': 'it', 'marketCap': 'small'},
        {'symbol': 'IPCALAB.NS', 'name': 'IPCA Laboratories', 'sector': 'healthcare', 'marketCap': 'small'},
        {'symbol': 'IRB.NS', 'name': 'IRB Infrastructure Developers', 'sector': 'construction', 'marketCap': 'small'},
        {'symbol': 'IIFLCAPS.NS', 'name': 'IIFL Securities', 'sector': 'banking', 'marketCap': 'small'},
        {'symbol': 'ITC.NS', 'name': 'ITC', 'sector': 'fmcg', 'marketCap': 'small'},
        
        # Micro Cap (251-501)
        {'symbol': 'ITDCEM.NS', 'name': 'ITD Cementation India', 'sector': 'construction', 'marketCap': 'micro'},
        {'symbol': 'JSWENERGY.NS', 'name': 'JSW Energy', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'JSWINFRA.NS', 'name': 'JSW Infrastructure', 'sector': 'infrastructure', 'marketCap': 'micro'},
        {'symbol': 'JSWSTEEL.NS', 'name': 'JSW Steel', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'JBCHEPHARM.NS', 'name': 'JB Chemicals & Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'JKCEMENT.NS', 'name': 'JK Cement', 'sector': 'cement', 'marketCap': 'micro'},
        {'symbol': 'JKLAKSHMI.NS', 'name': 'JK Lakshmi Cement', 'sector': 'cement', 'marketCap': 'micro'},
        {'symbol': 'JKPAPER.NS', 'name': 'JK Paper', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'JKTYRE.NS', 'name': 'JK Tyre & Industries', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'JMFINANCIL.NS', 'name': 'JM Financial', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'JSL.NS', 'name': 'Jindal Stainless (Hisar)', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'JINDALSTEL.NS', 'name': 'Jindal Steel & Power', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'JIOFIN.NS', 'name': 'Jio Financial Services', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'JYOTHYLAB.NS', 'name': 'Jyothy Labs', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'JUBLFOOD.NS', 'name': 'Jubilant FoodWorks', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'JUBLINGREA.NS', 'name': 'Jubilant Ingrevia', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'JUSTDIAL.NS', 'name': 'Just Dial', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'JYOTHYLAB.NS', 'name': 'Jyothy Labs', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'KAJARIACER.NS', 'name': 'Kajaria Ceramics', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'KPIL.NS', 'name': 'Kalpataru Power Transmission', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KANSAINER.NS', 'name': 'Kansai Nerolac Paints', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'KARURVYSYA.NS', 'name': 'Karur Vysya Bank', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'KECL.NS', 'name': 'Kirloskar Electric Company', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KEI.NS', 'name': 'KEI Industries', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KENNAMET.NS', 'name': 'Kennametal India', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KFINTECH.NS', 'name': 'KFin Technologies', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'KHADIM.NS', 'name': 'Khadim India', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'KIOCL.NS', 'name': 'KIOCL', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'KIRLOSENG.NS', 'name': 'Kirloskar Brothers', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KIRLFER.NS', 'name': 'Kirloskar Ferrous Industries', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'KIRLOSBROS.NS', 'name': 'Kirloskar Brothers', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KIRIINDUS.NS', 'name': 'Kiri Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'KOTAKBANK.NS', 'name': 'Kotak Mahindra Bank', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'KPITTECH.NS', 'name': 'KPIT Technologies', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'KRBL.NS', 'name': 'KRBL', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'KSB.NS', 'name': 'KSB', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'KTKBANK.NS', 'name': 'Karnataka Bank', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'LTF.NS', 'name': 'L&T Finance Holdings', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'LTIM.NS', 'name': 'LTIMindtree', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'LTTS.NS', 'name': 'L&T Technology Services', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'LEMONTREE.NS', 'name': 'Lemon Tree Hotels', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'LT.NS', 'name': 'Larsen & Toubro', 'sector': 'construction', 'marketCap': 'micro'},
        {'symbol': 'LAURUSLABS.NS', 'name': 'Laurus Labs', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'LICHSGFIN.NS', 'name': 'LIC Housing Finance', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'LICI.NS', 'name': 'Life Insurance Corporation of India', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'LINDEINDIA.NS', 'name': 'Linde India', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'LODHA.NS', 'name': 'Lodha Developers', 'sector': 'realty', 'marketCap': 'micro'},
        {'symbol': 'LUPIN.NS', 'name': 'Lupin', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'LXCHEM.NS', 'name': 'Laxmi Organic Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'LYKALABS.NS', 'name': 'Lyka Labs', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'M&M.NS', 'name': 'Mahindra & Mahindra', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'M&MFIN.NS', 'name': 'Mahindra & Mahindra Financial Services', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'MFSL.NS', 'name': 'Max Financial Services', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'MGL.NS', 'name': 'Mahanagar Gas', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'CIEINDIA.NS', 'name': 'Mahindra CIE Automotive', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'MANAPPURAM.NS', 'name': 'Manappuram Finance', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'MARICO.NS', 'name': 'Marico', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'MARUTI.NS', 'name': 'Maruti Suzuki India', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'MASTEK.NS', 'name': 'Mastek', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'MAXHEALTH.NS', 'name': 'Max Healthcare Institute', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'MAZDOCK.NS', 'name': 'Mazagon Dock Shipbuilders', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'MCDHOLDING.NS', 'name': 'United Spirits', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'MCX.NS', 'name': 'Multi Commodity Exchange of India', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'MEDPLUS.NS', 'name': 'MedPlus Health Services', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'METROPOLIS.NS', 'name': 'Metropolis Healthcare', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'MHRIL.NS', 'name': 'Mahindra Holidays & Resorts India', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'MIDHANI.NS', 'name': 'Mishra Dhatu Nigam', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'MINDACORP.NS', 'name': 'Minda Corporation', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'MOLDTKPAC.NS', 'name': 'Mold-Tek Packaging', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'MOIL.NS', 'name': 'MOIL', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'MRF.NS', 'name': 'MRF', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'MOTHERSON.NS', 'name': 'Samvardhana Motherson International', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'MOTILALOFS.NS', 'name': 'Motilal Oswal Financial Services', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'MPHASIS.NS', 'name': 'Mphasis', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'MRPL.NS', 'name': 'Mangalore Refinery and Petrochemicals', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'MSUMI.NS', 'name': 'Motherson Sumi Wiring India', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'MTARTECH.NS', 'name': 'MTAR Technologies', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'MUTHOOTFIN.NS', 'name': 'Muthoot Finance', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'NATIONALUM.NS', 'name': 'National Aluminium Company', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'NATIONALUM.NS', 'name': 'National Aluminium Company', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'NAVINFLUOR.NS', 'name': 'Navin Fluorine International', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'NESCO.NS', 'name': 'Nesco', 'sector': 'infrastructure', 'marketCap': 'micro'},
        {'symbol': 'NESTLEIND.NS', 'name': 'Nestle India', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'NETWORK18.NS', 'name': 'Network18 Media & Investments', 'sector': 'media', 'marketCap': 'micro'},
        {'symbol': 'NEWGEN.NS', 'name': 'Newgen Software Technologies', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'NIACL.NS', 'name': 'The New India Assurance Company', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'NIITLTD.NS', 'name': 'NIIT', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'NILKAMAL.NS', 'name': 'Nilkamal', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'NLCINDIA.NS', 'name': 'NLC India', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'NMDC.NS', 'name': 'NMDC', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'NOCIL.NS', 'name': 'NOCIL', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'NSLNISP.NS', 'name': 'NSIL', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'NTPC.NS', 'name': 'NTPC', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'NUCLEUS.NS', 'name': 'Nucleus Software Exports', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'OBEROIRLTY.NS', 'name': 'Oberoi Realty', 'sector': 'realty', 'marketCap': 'micro'},
        {'symbol': 'OFSS.NS', 'name': 'Oracle Financial Services Software', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'OIL.NS', 'name': 'Oil India', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'ONGC.NS', 'name': 'Oil & Natural Gas Corporation', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'ORIENTELEC.NS', 'name': 'Orient Electric', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'PAYTM.NS', 'name': 'One 97 Communications', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'PNBGILTS.NS', 'name': 'PNB Gilts', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'PNCINFRA.NS', 'name': 'PNC Infratech', 'sector': 'construction', 'marketCap': 'micro'},
        {'symbol': 'PAGEIND.NS', 'name': 'Page Industries', 'sector': 'textiles', 'marketCap': 'micro'},
        {'symbol': 'PARAGMILK.NS', 'name': 'Parag Milk Foods', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'PERSISTENT.NS', 'name': 'Persistent Systems', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'PETRONET.NS', 'name': 'Petronet LNG', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'PFIZER.NS', 'name': 'Pfizer', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'PHOENIXLTD.NS', 'name': 'The Phoenix Mills', 'sector': 'realty', 'marketCap': 'micro'},
        {'symbol': 'PIDILITIND.NS', 'name': 'Pidilite Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'PIIND.NS', 'name': 'PI Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'PEL.NS', 'name': 'Piramal Enterprises', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'POLICYBZR.NS', 'name': 'PB Fintech', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'POLYMED.NS', 'name': 'Poly Medicure', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'POLYCAB.NS', 'name': 'Polycab India', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'POLYPLEX.NS', 'name': 'Polyplex Corporation', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'POONAWALLA.NS', 'name': 'Poonawalla Fincorp', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'PFC.NS', 'name': 'Power Finance Corporation', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'POWERGRID.NS', 'name': 'Power Grid Corporation of India', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'PRAJIND.NS', 'name': 'Praj Industries', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'PRESTIGE.NS', 'name': 'Prestige Estates Projects', 'sector': 'realty', 'marketCap': 'micro'},
        {'symbol': 'PRINCEPIPE.NS', 'name': 'Prince Pipes and Fittings', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'PRSMJOHNSN.NS', 'name': 'Prism Johnson', 'sector': 'cement', 'marketCap': 'micro'},
        {'symbol': 'PVRINOX.NS', 'name': 'PVR', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'PVRINOX.NS', 'name': 'PVR INOX', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'PNB.NS', 'name': 'Punjab National Bank', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'QUESS.NS', 'name': 'Quess Corp', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'RADICO.NS', 'name': 'Radico Khaitan', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'RAIN.NS', 'name': 'Rain Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'RAJESHEXPO.NS', 'name': 'Rajesh Exports', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'RALLIS.NS', 'name': 'Rallis India', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'RAMCOCEM.NS', 'name': 'The Ramco Cements', 'sector': 'cement', 'marketCap': 'micro'},
        {'symbol': 'RATEGAIN.NS', 'name': 'RateGain Travel Technologies', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'RATNAMANI.NS', 'name': 'Ratnamani Metals & Tubes', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'RAYMOND.NS', 'name': 'Raymond', 'sector': 'textiles', 'marketCap': 'micro'},
        {'symbol': 'RBL.NS', 'name': 'Rane Brake Lining', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'RBLBANK.NS', 'name': 'RBL Bank', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'RECLTD.NS', 'name': 'REC', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'REDINGTON.NS', 'name': 'Redington', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'RELAXO.NS', 'name': 'Relaxo Footwears', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'RENUKA.NS', 'name': 'Shree Renuka Sugars', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'REXPIPES.NS', 'name': 'RGP Pipes', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'RITES.NS', 'name': 'RITES', 'sector': 'construction', 'marketCap': 'micro'},
        {'symbol': 'ROUTE.NS', 'name': 'Route Mobile', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'RSYSTEMS.NS', 'name': 'R Systems International', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'SAFARI.NS', 'name': 'Safari Industries (India)', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SAIL.NS', 'name': 'Steel Authority of India', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'SANOFI.NS', 'name': 'Sanofi India', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'SAREGAMA.NS', 'name': 'Saregama India', 'sector': 'media', 'marketCap': 'micro'},
        {'symbol': 'SBICARD.NS', 'name': 'SBI Cards and Payment Services', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'SBILIFE.NS', 'name': 'SBI Life Insurance Company', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'SCHAEFFLER.NS', 'name': 'Schaeffler India', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'SFL.NS', 'name': 'Sheela Foam', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SHOPERSTOP.NS', 'name': 'Shoppers Stop', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SHREECEM.NS', 'name': 'Shree Cement', 'sector': 'cement', 'marketCap': 'micro'},
        {'symbol': 'TRANSWORLD.NS', 'name': 'Shreyas Shipping & Logistics', 'sector': 'infrastructure', 'marketCap': 'micro'},
        {'symbol': 'SHRIRAMFIN.NS', 'name': 'Shriram Finance', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'SIEMENS.NS', 'name': 'Siemens', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'SIS.NS', 'name': 'SIS', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SJVN.NS', 'name': 'SJVN', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'SKFINDIA.NS', 'name': 'SKF India', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'SOBHA.NS', 'name': 'Sobha', 'sector': 'realty', 'marketCap': 'micro'},
        {'symbol': 'SOLARINDS.NS', 'name': 'Solar Industries India', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'SONACOMS.NS', 'name': 'Sona BLW Precision Forgings', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'SBIN.NS', 'name': 'State Bank of India', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'STAR.NS', 'name': 'Strides Pharma Science', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'STARHEALTH.NS', 'name': 'Star Health and Allied Insurance Company', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'SUDARSCHEM.NS', 'name': 'Sudarshan Chemical Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'SUMICHEM.NS', 'name': 'Sumitomo Chemical India', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'SUNPHARMA.NS', 'name': 'Sun Pharmaceutical Industries', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'SUNTV.NS', 'name': 'Sun TV Network', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SUPRAJIT.NS', 'name': 'Suprajit Engineering', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'SUPREMEIND.NS', 'name': 'Supreme Industries', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'SWANENERGY.NS', 'name': 'Swan Energy', 'sector': 'textiles', 'marketCap': 'micro'},
        {'symbol': 'SWIGGY.NS', 'name': 'Swiggy', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SYMPHONY.NS', 'name': 'Symphony', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'SYNGENE.NS', 'name': 'Syngene International', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'TATACHEM.NS', 'name': 'Tata Chemicals', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'TATACOMM.NS', 'name': 'Tata Communications', 'sector': 'telecom', 'marketCap': 'micro'},
        {'symbol': 'TATACONSUM.NS', 'name': 'Tata Consumer Products', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'TATAELXSI.NS', 'name': 'Tata Elxsi', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'TATAINVEST.NS', 'name': 'Tata Investment Corporation', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'TATAMOTORS.NS', 'name': 'Tata Motors', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'TATAPOWER.NS', 'name': 'Tata Power Co.', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'TATASTEEL.NS', 'name': 'Tata Steel', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'TVSMOTOR.NS', 'name': 'TVS Motor Company', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'TEAMLEASE.NS', 'name': 'TeamLease Services', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'TECHM.NS', 'name': 'Tech Mahindra', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'TEJASNET.NS', 'name': 'Tejas Networks', 'sector': 'telecom', 'marketCap': 'micro'},
        {'symbol': 'THERMAX.NS', 'name': 'Thermax', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'THYROCARE.NS', 'name': 'Thyrocare Technologies', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'TIINDIA.NS', 'name': 'Tube Investments of India', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'TIMKEN.NS', 'name': 'Timken India', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'TITAN.NS', 'name': 'Titan Company', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'TORNTPHARM.NS', 'name': 'Torrent Pharmaceuticals', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'TORNTPOWER.NS', 'name': 'Torrent Power', 'sector': 'energy', 'marketCap': 'micro'},
        {'symbol': 'TRENT.NS', 'name': 'Trent', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'TRIDENT.NS', 'name': 'Trident', 'sector': 'textiles', 'marketCap': 'micro'},
        {'symbol': 'TRITURBINE.NS', 'name': 'Triveni Turbine', 'sector': 'capital_goods', 'marketCap': 'micro'},
        {'symbol': 'TTML.NS', 'name': 'Tata Teleservices (Maharashtra)', 'sector': 'telecom', 'marketCap': 'micro'},
        {'symbol': 'UJJIVANSFB.NS', 'name': 'Ujjivan Financial Services', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'UBL.NS', 'name': 'United Breweries', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'ULTRACEMCO.NS', 'name': 'UltraTech Cement', 'sector': 'cement', 'marketCap': 'micro'},
        {'symbol': 'UNIONBANK.NS', 'name': 'Union Bank of India', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'UNITDSPR.NS', 'name': 'United Spirits', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'UPL.NS', 'name': 'UPL', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'UTIAMC.NS', 'name': 'UTI Asset Management Company', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'VBL.NS', 'name': 'Varun Beverages', 'sector': 'fmcg', 'marketCap': 'micro'},
        {'symbol': 'VEDL.NS', 'name': 'Vedanta', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'VIJAYA.NS', 'name': 'Vijaya Diagnostic Centre', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'VINATIORGA.NS', 'name': 'Vinati Organics', 'sector': 'chemicals', 'marketCap': 'micro'},
        {'symbol': 'VIPIND.NS', 'name': 'VIP Industries', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'VMART.NS', 'name': 'V-Mart Retail', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'VOLTAS.NS', 'name': 'Voltas', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'VTL.NS', 'name': 'Vardhman Textiles', 'sector': 'textiles', 'marketCap': 'micro'},
        {'symbol': 'WELCORP.NS', 'name': 'Welspun Corp', 'sector': 'metals', 'marketCap': 'micro'},
        {'symbol': 'WELSPUNLIV.NS', 'name': 'Welspun India', 'sector': 'textiles', 'marketCap': 'micro'},
        {'symbol': 'WESTLIFE.NS', 'name': 'Westlife Foodworld', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'WHIRLPOOL.NS', 'name': 'Whirlpool of India', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'WIPRO.NS', 'name': 'Wipro', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'WOCKPHARMA.NS', 'name': 'Wockhardt', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'YESBANK.NS', 'name': 'Yes Bank', 'sector': 'banking', 'marketCap': 'micro'},
        {'symbol': 'ZENSARTECH.NS', 'name': 'Zensar Technologies', 'sector': 'it', 'marketCap': 'micro'},
        {'symbol': 'ZFCVINDIA.NS', 'name': 'ZF Commercial Vehicle Control Systems India', 'sector': 'auto', 'marketCap': 'micro'},
        {'symbol': 'ZYDUSLIFE.NS', 'name': 'Zydus Lifesciences', 'sector': 'healthcare', 'marketCap': 'micro'},
        {'symbol': 'ETERNAL.NS', 'name': 'Zomato', 'sector': 'consumer', 'marketCap': 'micro'},
        {'symbol': 'ZEEL.NS', 'name': 'Zee Entertainment Enterprises', 'sector': 'consumer', 'marketCap': 'micro'}
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
        {'symbol': 'AAPL',  'name': 'Apple Inc.',               'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MSFT',  'name': 'Microsoft Corp.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'NVDA',  'name': 'NVIDIA Corp.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'META',  'name': 'Meta Platforms',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'AVGO',  'name': 'Broadcom Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'AMD',   'name': 'Advanced Micro Devices',    'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ORCL',  'name': 'Oracle Corp.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'CRM',   'name': 'Salesforce Inc.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'CSCO',  'name': 'Cisco Systems',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'INTC',  'name': 'Intel Corp.',               'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'IBM',   'name': 'IBM Corp.',                 'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'QCOM',  'name': 'QUALCOMM Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'TXN',   'name': 'Texas Instruments',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'NOW',   'name': 'ServiceNow Inc.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'INTU',  'name': 'Intuit Inc.',               'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'AMAT',  'name': 'Applied Materials',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ADBE',  'name': 'Adobe Inc.',                'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MU',    'name': 'Micron Technology',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'LRCX',  'name': 'Lam Research',             'sector': 'technology',   'marketCap': 'large'},
        # Consumer / Retail
        {'symbol': 'AMZN',  'name': 'Amazon.com Inc.',           'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'TSLA',  'name': 'Tesla Inc.',                'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'WMT',   'name': 'Walmart Inc.',              'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'COST',  'name': 'Costco Wholesale',          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'HD',    'name': 'Home Depot Inc.',           'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'PG',    'name': 'Procter & Gamble',          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'MCD',   'name': "McDonald's Corp.",          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'KO',    'name': 'Coca-Cola Co.',             'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'PEP',   'name': 'PepsiCo Inc.',              'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'NKE',   'name': 'Nike Inc.',                 'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'SBUX',  'name': 'Starbucks Corp.',           'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'LOW',   'name': "Lowe's Companies",          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'TGT',   'name': 'Target Corp.',              'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'PM',    'name': 'Philip Morris Intl.',       'sector': 'consumer',     'marketCap': 'large'},
        # Financials
        {'symbol': 'JPM',   'name': 'JPMorgan Chase',            'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'V',     'name': 'Visa Inc.',                 'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'MA',    'name': 'Mastercard Inc.',           'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'BAC',   'name': 'Bank of America',           'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'GS',    'name': 'Goldman Sachs',             'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'WFC',   'name': 'Wells Fargo',               'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'MS',    'name': 'Morgan Stanley',            'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'BLK',   'name': 'BlackRock Inc.',            'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'AXP',   'name': 'American Express',          'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'SCHW',  'name': 'Charles Schwab',            'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'C',     'name': 'Citigroup Inc.',            'sector': 'financials',   'marketCap': 'large'},
        # Healthcare
        {'symbol': 'LLY',   'name': 'Eli Lilly',                 'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'UNH',   'name': 'UnitedHealth Group',        'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'JNJ',   'name': 'Johnson & Johnson',         'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'ABBV',  'name': 'AbbVie Inc.',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'MRK',   'name': 'Merck & Co.',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'TMO',   'name': 'Thermo Fisher Scientific',  'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'ABT',   'name': 'Abbott Laboratories',       'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'AMGN',  'name': 'Amgen Inc.',                'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'PFE',   'name': 'Pfizer Inc.',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'GILD',  'name': 'Gilead Sciences',           'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'BMY',   'name': 'Bristol-Myers Squibb',      'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'CVS',   'name': 'CVS Health Corp.',          'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'ISRG',  'name': 'Intuitive Surgical',        'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'REGN',  'name': 'Regeneron Pharmaceuticals', 'sector': 'healthcare',   'marketCap': 'large'},
        # Energy
        {'symbol': 'XOM',   'name': 'Exxon Mobil Corp.',         'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'CVX',   'name': 'Chevron Corp.',             'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'COP',   'name': 'ConocoPhillips',            'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'EOG',   'name': 'EOG Resources',             'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'SLB',   'name': 'Schlumberger NV',           'sector': 'energy',       'marketCap': 'large'},
        # Industrials
        {'symbol': 'CAT',   'name': 'Caterpillar Inc.',          'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'HON',   'name': 'Honeywell International',   'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'BA',    'name': 'Boeing Co.',                'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'RTX',   'name': 'RTX Corp.',                 'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'MMM',   'name': '3M Co.',                    'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'GE',    'name': 'GE Aerospace',              'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'UPS',   'name': 'United Parcel Service',     'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'DE',    'name': 'Deere & Company',           'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'LMT',   'name': 'Lockheed Martin',           'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'UNP',   'name': 'Union Pacific Corp.',       'sector': 'industrials',  'marketCap': 'large'},
        # Communication
        {'symbol': 'NFLX',  'name': 'Netflix Inc.',              'sector': 'communication','marketCap': 'large'},
        {'symbol': 'DIS',   'name': 'Walt Disney Co.',           'sector': 'communication','marketCap': 'large'},
        {'symbol': 'VZ',    'name': 'Verizon Communications',    'sector': 'communication','marketCap': 'large'},
        {'symbol': 'T',     'name': 'AT&T Inc.',                 'sector': 'communication','marketCap': 'large'},
        {'symbol': 'CMCSA', 'name': 'Comcast Corp.',             'sector': 'communication','marketCap': 'large'},
        {'symbol': 'TMUS',  'name': 'T-Mobile US',               'sector': 'communication','marketCap': 'large'},
        # Materials
        {'symbol': 'LIN',   'name': 'Linde PLC',                 'sector': 'materials',    'marketCap': 'large'},
        {'symbol': 'SHW',   'name': 'Sherwin-Williams',          'sector': 'materials',    'marketCap': 'large'},
        {'symbol': 'DOW',   'name': 'Dow Inc.',                  'sector': 'materials',    'marketCap': 'large'},
        {'symbol': 'FCX',   'name': 'Freeport-McMoRan',          'sector': 'materials',    'marketCap': 'large'},
        {'symbol': 'APD',   'name': 'Air Products & Chemicals',  'sector': 'materials',    'marketCap': 'large'},
        # Utilities & Real Estate
        {'symbol': 'NEE',   'name': 'NextEra Energy',            'sector': 'utilities',    'marketCap': 'large'},
        {'symbol': 'SO',    'name': 'Southern Company',          'sector': 'utilities',    'marketCap': 'large'},
        {'symbol': 'DUK',   'name': 'Duke Energy Corp.',         'sector': 'utilities',    'marketCap': 'large'},
        {'symbol': 'AMT',   'name': 'American Tower Corp.',      'sector': 'realestate',   'marketCap': 'large'},
        {'symbol': 'PLD',   'name': 'Prologis Inc.',             'sector': 'realestate',   'marketCap': 'large'},
    ]

def get_nasdaq100_stocks():
    return [
        {'symbol': 'AAPL',  'name': 'Apple Inc.',               'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MSFT',  'name': 'Microsoft Corp.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'NVDA',  'name': 'NVIDIA Corp.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'GOOGL', 'name': 'Alphabet Inc. (A)',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'GOOG',  'name': 'Alphabet Inc. (C)',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'META',  'name': 'Meta Platforms',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'AMZN',  'name': 'Amazon.com Inc.',           'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'TSLA',  'name': 'Tesla Inc.',                'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'AVGO',  'name': 'Broadcom Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'COST',  'name': 'Costco Wholesale',          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'NFLX',  'name': 'Netflix Inc.',              'sector': 'communication','marketCap': 'large'},
        {'symbol': 'AMD',   'name': 'Advanced Micro Devices',    'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ADBE',  'name': 'Adobe Inc.',                'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'QCOM',  'name': 'QUALCOMM Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'INTU',  'name': 'Intuit Inc.',               'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'TXN',   'name': 'Texas Instruments',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'AMAT',  'name': 'Applied Materials',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ISRG',  'name': 'Intuitive Surgical',        'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'BKNG',  'name': 'Booking Holdings',          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'NOW',   'name': 'ServiceNow Inc.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MU',    'name': 'Micron Technology',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'LRCX',  'name': 'Lam Research',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ADI',   'name': 'Analog Devices',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'PANW',  'name': 'Palo Alto Networks',        'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'KLAC',  'name': 'KLA Corp.',                 'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'SNPS',  'name': 'Synopsys Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'CDNS',  'name': 'Cadence Design Systems',    'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MRVL',  'name': 'Marvell Technology',        'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'CRWD',  'name': 'CrowdStrike Holdings',      'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ORCL',  'name': 'Oracle Corp.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ASML',  'name': 'ASML Holding',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ADP',   'name': 'Automatic Data Processing', 'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MELI',  'name': 'MercadoLibre Inc.',         'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'ABNB',  'name': 'Airbnb Inc.',               'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'PYPL',  'name': 'PayPal Holdings',           'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'ORLY',  'name': "O'Reilly Automotive",       'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'MNST',  'name': 'Monster Beverage Corp.',    'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'REGN',  'name': 'Regeneron Pharmaceuticals', 'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'MDLZ',  'name': 'Mondelez International',    'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'GILD',  'name': 'Gilead Sciences',           'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'CTAS',  'name': 'Cintas Corp.',              'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'CSX',   'name': 'CSX Corp.',                 'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'PCAR',  'name': 'PACCAR Inc.',               'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'DXCM',  'name': 'DexCom Inc.',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'IDXX',  'name': 'IDEXX Laboratories',        'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'BIIB',  'name': 'Biogen Inc.',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'VRTX',  'name': 'Vertex Pharmaceuticals',    'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'AMGN',  'name': 'Amgen Inc.',                'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'HON',   'name': 'Honeywell International',   'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'CMCSA', 'name': 'Comcast Corp.',             'sector': 'communication','marketCap': 'large'},
        {'symbol': 'TMUS',  'name': 'T-Mobile US',               'sector': 'communication','marketCap': 'large'},
        {'symbol': 'KDP',   'name': 'Keurig Dr Pepper',          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'MAR',   'name': 'Marriott International',    'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'SBUX',  'name': 'Starbucks Corp.',           'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'LULU',  'name': 'Lululemon Athletica',       'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'EA',    'name': 'Electronic Arts',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ZS',    'name': 'Zscaler Inc.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'FTNT',  'name': 'Fortinet Inc.',             'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'TEAM',  'name': 'Atlassian Corp.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'WDAY',  'name': 'Workday Inc.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'MCHP',  'name': 'Microchip Technology',      'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'FAST',  'name': 'Fastenal Co.',              'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'ON',    'name': 'ON Semiconductor',          'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'PAYX',  'name': 'Paychex Inc.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'ODFL',  'name': 'Old Dominion Freight Line', 'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'VRSK',  'name': 'Verisk Analytics',          'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'TTWO',  'name': 'Take-Two Interactive',      'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'DDOG',  'name': 'Datadog Inc.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'DASH',  'name': 'DoorDash Inc.',             'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'GEHC',  'name': 'GE HealthCare Technologies','sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'CPRT',  'name': 'Copart Inc.',               'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'NXPI',  'name': 'NXP Semiconductors',        'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'CEG',   'name': 'Constellation Energy',      'sector': 'utilities',    'marketCap': 'large'},
        {'symbol': 'TTD',   'name': 'The Trade Desk',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'APP',   'name': 'Applovin Corp.',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'PLTR',  'name': 'Palantir Technologies',     'sector': 'technology',   'marketCap': 'large'},
    ]

def get_sp500_stocks():
    """Representative S&P 500 stocks — top ~200 by sector coverage"""
    return get_sp100_stocks() + [
        # Extended Technology
        {'symbol': 'ACN',   'name': 'Accenture PLC',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'SHOP',  'name': 'Shopify Inc.',              'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'SNOW',  'name': 'Snowflake Inc.',            'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'NET',   'name': 'Cloudflare Inc.',           'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'UBER',  'name': 'Uber Technologies',         'sector': 'technology',   'marketCap': 'large'},
        {'symbol': 'LYFT',  'name': 'Lyft Inc.',                 'sector': 'technology',   'marketCap': 'mid'},
        {'symbol': 'COIN',  'name': 'Coinbase Global',           'sector': 'financials',   'marketCap': 'mid'},
        {'symbol': 'PINS',  'name': 'Pinterest Inc.',            'sector': 'communication','marketCap': 'mid'},
        {'symbol': 'SNAP',  'name': 'Snap Inc.',                 'sector': 'communication','marketCap': 'mid'},
        {'symbol': 'X',     'name': 'U.S. Steel Corp.',          'sector': 'materials',    'marketCap': 'mid'},
        {'symbol': 'F',     'name': 'Ford Motor Co.',            'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'GM',    'name': 'General Motors',            'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'RIVN',  'name': 'Rivian Automotive',         'sector': 'consumer',     'marketCap': 'mid'},
        {'symbol': 'LCID',  'name': 'Lucid Group',               'sector': 'consumer',     'marketCap': 'small'},
        # Extended Financials
        {'symbol': 'USB',   'name': 'U.S. Bancorp',              'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'PNC',   'name': 'PNC Financial Services',    'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'TFC',   'name': 'Truist Financial',          'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'COF',   'name': 'Capital One Financial',     'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'DFS',   'name': 'Discover Financial',        'sector': 'financials',   'marketCap': 'large'},
        {'symbol': 'SYF',   'name': 'Synchrony Financial',       'sector': 'financials',   'marketCap': 'mid'},
        {'symbol': 'FITB',  'name': 'Fifth Third Bancorp',       'sector': 'financials',   'marketCap': 'mid'},
        {'symbol': 'KEY',   'name': 'KeyCorp',                   'sector': 'financials',   'marketCap': 'mid'},
        {'symbol': 'RF',    'name': 'Regions Financial',         'sector': 'financials',   'marketCap': 'mid'},
        # Extended Healthcare
        {'symbol': 'CI',    'name': 'Cigna Group',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'HUM',   'name': 'Humana Inc.',               'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'MDT',   'name': 'Medtronic PLC',             'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'SYK',   'name': 'Stryker Corp.',             'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'BDX',   'name': 'Becton Dickinson',          'sector': 'healthcare',   'marketCap': 'large'},
        {'symbol': 'MRNA',  'name': 'Moderna Inc.',              'sector': 'healthcare',   'marketCap': 'mid'},
        {'symbol': 'ILMN',  'name': 'Illumina Inc.',             'sector': 'healthcare',   'marketCap': 'mid'},
        # Extended Energy
        {'symbol': 'PXD',   'name': 'Pioneer Natural Resources', 'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'DVN',   'name': 'Devon Energy Corp.',        'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'MPC',   'name': 'Marathon Petroleum',        'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'PSX',   'name': 'Phillips 66',               'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'VLO',   'name': 'Valero Energy',             'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'HAL',   'name': 'Halliburton Co.',           'sector': 'energy',       'marketCap': 'large'},
        {'symbol': 'OXY',   'name': 'Occidental Petroleum',      'sector': 'energy',       'marketCap': 'large'},
        # Extended Industrials
        {'symbol': 'FDX',   'name': 'FedEx Corp.',               'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'ETN',   'name': 'Eaton Corp.',               'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'EMR',   'name': 'Emerson Electric',          'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'NOC',   'name': 'Northrop Grumman',          'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'GD',    'name': 'General Dynamics',          'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'ITW',   'name': 'Illinois Tool Works',       'sector': 'industrials',  'marketCap': 'large'},
        {'symbol': 'WM',    'name': 'Waste Management Inc.',     'sector': 'industrials',  'marketCap': 'large'},
        # Extended Consumer
        {'symbol': 'CL',    'name': 'Colgate-Palmolive',         'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'MO',    'name': 'Altria Group',              'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'KHC',   'name': 'Kraft Heinz Co.',           'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'GIS',   'name': 'General Mills',             'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'K',     'name': "Kellogg's Co.",             'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'HRL',   'name': 'Hormel Foods',              'sector': 'consumer',     'marketCap': 'mid'},
        {'symbol': 'CAG',   'name': 'Conagra Brands',            'sector': 'consumer',     'marketCap': 'mid'},
        {'symbol': 'AZO',   'name': "AutoZone Inc.",             'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'DLTR',  'name': 'Dollar Tree Inc.',          'sector': 'consumer',     'marketCap': 'large'},
        {'symbol': 'DG',    'name': 'Dollar General Corp.',      'sector': 'consumer',     'marketCap': 'large'},
        # Extended Real Estate & Utilities
        {'symbol': 'O',     'name': 'Realty Income Corp.',       'sector': 'realestate',   'marketCap': 'large'},
        {'symbol': 'WELL',  'name': 'Welltower Inc.',            'sector': 'realestate',   'marketCap': 'large'},
        {'symbol': 'PSA',   'name': 'Public Storage',            'sector': 'realestate',   'marketCap': 'large'},
        {'symbol': 'EQR',   'name': 'Equity Residential',        'sector': 'realestate',   'marketCap': 'large'},
        {'symbol': 'D',     'name': 'Dominion Energy',           'sector': 'utilities',    'marketCap': 'large'},
        {'symbol': 'AEP',   'name': 'American Electric Power',   'sector': 'utilities',    'marketCap': 'large'},
        {'symbol': 'XEL',   'name': 'Xcel Energy Inc.',          'sector': 'utilities',    'marketCap': 'large'},
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
        print(f"[CRYPTO] klines error for {symbol}: {e}")
        return None, None, None


def _fetch_binance_coins(universe_size: int) -> list:
    """Fetch top N crypto coins from Binance by 24h USD volume, with 7d/30d changes from klines."""
    print(f"[CRYPTO] Fetching top {universe_size} USDT pairs from Binance...")
    try:
        resp = requests.get(f"{_BINANCE_BASE}/ticker/24hr", headers=_binance_headers(), timeout=30)
        if resp.status_code != 200:
            print(f"[CRYPTO] Binance ticker returned {resp.status_code}")
            return []
        tickers = resp.json()
    except Exception as e:
        print(f"[CRYPTO] Binance ticker request failed: {e}")
        return []

    usdt = [
        t for t in tickers
        if t['symbol'].endswith('USDT') and t['symbol'][:-4] not in _STABLE_SYMBOLS
    ]
    usdt.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
    top_tickers = usdt[:universe_size]

    print(f"[CRYPTO] Got {len(top_tickers)} pairs, fetching klines in parallel...")

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

    print(f"[CRYPTO] Fetched {len(coins)} coins")
    return coins


def scan_crypto_via_binance(universe_size, weekly_threshold, monthly_threshold, market_cap_filter='all'):
    """Scan crypto via Binance public API — no key needed, 1200 req/min limit."""
    coins = _fetch_binance_coins(universe_size)
    if not coins:
        print("[CRYPTO] No coin data (Binance fetch failed)")
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
            print(f"[MATCH] {coin['symbol']} W:{weekly:.1f}% M:{monthly:.1f}%")

    results.sort(key=lambda x: x['weeklyChange'])
    print(f"[CRYPTO] Done — {len(results)} coins matched criteria")
    return results


def scan_crypto_via_binance_streaming(universe_size, weekly_threshold, monthly_threshold, market_cap_filter='all'):
    """Scan crypto and yield (processed_count, match_result) tuples for streaming progress."""
    print(f"[CRYPTO-STREAM] Starting streaming scan for top {universe_size} coins...")
    
    # Fetch all tickers first
    try:
        resp = requests.get(f"{_BINANCE_BASE}/ticker/24hr", headers=_binance_headers(), timeout=30)
        if resp.status_code != 200:
            print(f"[CRYPTO-STREAM] Binance ticker returned {resp.status_code}")
            return
        tickers = resp.json()
    except Exception as e:
        print(f"[CRYPTO-STREAM] Binance ticker request failed: {e}")
        return

    usdt = [
        t for t in tickers
        if t['symbol'].endswith('USDT') and t['symbol'][:-4] not in _STABLE_SYMBOLS
    ]
    usdt.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
    top_tickers = usdt[:universe_size]

    print(f"[CRYPTO-STREAM] Got {len(top_tickers)} pairs, scanning with streaming progress...")

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
            print(f"[MATCH] {base} W:{weekly:.1f}% M:{monthly:.1f}%")
            return result
        return None

    # Process coins sequentially with progress updates to avoid rate limiting
    processed = 0
    matches = []
    for ticker in top_tickers:
        processed += 1
        result = process_coin(ticker)
        if result:
            matches.append(result)
        yield (processed, result)
        # Small delay to respect Binance rate limits (1200 req/min = 1 req per 50ms)
        time.sleep(0.1)

    print(f"[CRYPTO-STREAM] Done — {len(matches)} coins matched criteria")
    matches.sort(key=lambda x: x['weeklyChange'])


# ── Stock Universe Router ─────────────────────────────────────────────────────

def get_stock_universe(universe_type, market='india'):
    """Get stock universe by market and universe type"""
    print(f"\n📋 Getting {universe_type} ({market}) stock universe...")

    if market == 'us':
        stocks = get_us_universe(universe_type)
        print(f"✅ Got {len(stocks)} US stocks for {universe_type}")
        return stocks

    # India (default)
    if universe_type == 'nifty50':
        stocks = get_nifty_50_stocks()
        print(f"✅ Got {len(stocks)} stocks for Nifty 50")
        return stocks
    elif universe_type == 'nifty100':
        stocks = get_nifty_100_stocks()
        print(f"✅ Got {len(stocks)} stocks for Nifty 100")
        return stocks
    elif universe_type == 'nifty200':
        stocks = get_nifty_200_stocks()
        print(f"✅ Got {len(stocks)} stocks for Nifty 200")
        return stocks
    elif universe_type == 'nifty500':
        stocks = get_nifty_500_stocks()
        print(f"✅ Got {len(stocks)} stocks for Nifty 500")
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
                print(f"[MATCH] {stock['symbol']} - W:{market_data['weeklyChange']}% M:{market_data['monthlyChange']}% [YAHOO FINANCE]")
                return {'status': 'match', 'data': result}
            else:
                return {'status': 'no_match', 'data': market_data}
        else:  # failed
            print(f"[FAILED] {stock['symbol']} - Yahoo Finance API failed")
            return {'status': 'failed', 'data': market_data}
    except Exception as e:
        print(f"[ERROR] {stock['symbol']} - {str(e)}")
        return {'status': 'error', 'data': None}

def fetch_yahoo_finance_data(symbol):
    """Fetch real stock data from Yahoo Finance - ONLY working source"""
    print(f"🔍 Fetching REAL data from Yahoo Finance for {symbol}...")
    
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
        time.sleep(0.1)
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
                    
                    print(f"✅ SUCCESS: Got real data for {symbol} - ₹{current_price:.2f}")
                    
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
        
        print(f"❌ Yahoo Finance API failed for {symbol}: Status {response.status_code}")
        
    except Exception as e:
        print(f"❌ Yahoo Finance API error for {symbol}: {str(e)}")
    
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

            if failed_stocks:
                print(f"\n[SCAN FAILURES] {failed_count} symbol(s) failed to fetch:")
                for sym in failed_stocks:
                    print(f"  ✗ {sym}")
            else:
                print(f"[SCAN] All {processed} symbols fetched successfully.")

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
            print(f"[SCAN-STREAM ERROR] {e}")
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

        print(f"\n[SCAN] STARTING — market={market} universe={stock_universe}")
        print(f"[CRITERIA] Weekly ≤ -{weekly_threshold}%, Monthly ≤ -{monthly_threshold}%")
        print(f"[FILTERS] Market Cap = {market_cap_filter}, Sector = {sector_filter}")

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
        
        print(f"[FILTER] {len(filtered_stocks)} stocks to process")
        
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
                    print(f"[ERROR] {stock['symbol']} - Future execution failed: {str(e)}")
                
                # Progress update every 10 stocks
                if processed % 10 == 0:
                    print(f"\n[PROGRESS] {processed}/{len(filtered_stocks)}")
                    print(f"   [SUCCESS] Yahoo Finance success: {real_data_count}")
                    print(f"   [FAILED] Failed: {failed_count}")
                    print(f"   [MATCHES] Found: {len(results)}")
        
        print(f"\n[SCAN COMPLETE]")
        print(f"   [UNIVERSE] {stock_universe} ({len(stock_list)} total, {len(filtered_stocks)} filtered)")
        print(f"   [PROCESSED] {processed}")
        print(f"   [SUCCESS] Yahoo Finance success: {real_data_count}")
        print(f"   [FAILED] {failed_count}")
        print(f"   [RESULTS] Stocks meeting criteria: {len(results)}")
        
        if failed_stocks:
            print(f"\n[FAILED STOCKS] {len(failed_stocks)} stocks failed:")
            for failed_stock in sorted(failed_stocks, key=lambda x: x['symbol']):
                print(f"   - {failed_stock['symbol']} ({failed_stock['name']})")
        
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
        print(f"[SCAN ERROR] {str(e)}")
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
            print(f"[tickers] {symbol} failed: {e}")
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