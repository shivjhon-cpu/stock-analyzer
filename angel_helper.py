import os
from SmartApi import SmartConnect
import pyotp
import pandas as pd
from dotenv import load_dotenv

# सुरक्षित क्रेडेंशियल्स लोड करें
load_dotenv()

def get_angel_session():
    """एंजेल वन से सुरक्षित कनेक्शन (Session) बनाने का फंक्शन"""
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    pin = os.getenv("ANGEL_PIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    
    smart_api = SmartConnect(api_key=api_key)
    
    try:
        totp = pyotp.TOTP(totp_secret).now()
        login_data = smart_api.generateSession(client_id, pin, totp)
        
        if login_data['status']:
            return smart_api
        else:
            print("लॉगिन फेल हो गया है:", login_data)
            return None
    except Exception as e:
        print("सेशन बनाने में एरर:", str(e))
        return None

def fetch_my_portfolio():
    """पोर्टफोलियो (Holdings) का डेटा लाने का फंक्शन"""
    smart_api = get_angel_session()
    
    # अगर कनेक्शन नहीं बना तो वापस लौट जाएं
    if not smart_api:
        return {"error": "ब्रोकर से कनेक्शन नहीं बन पाया"}
        
    holdings = smart_api.holding()
    
    # सबसे महत्वपूर्ण सुरक्षा कदम: डेटा लेने के तुरंत बाद लॉगआउट करें
    smart_api.terminateSession(os.getenv("ANGEL_CLIENT_ID"))
    
    if holdings['status']:
        return holdings['data']
    else:
        return {"error": holdings['message']}
from SmartApi import SmartConnect
import pyotp
import pandas as pd
from dotenv import load_dotenv

# सुरक्षित क्रेडेंशियल्स लोड करें
load_dotenv()

def get_angel_session():
    """एंजेल वन से सुरक्षित कनेक्शन (Session) बनाने का फंक्शन"""
    api_key = os.getenv("ANGEL_API_KEY")
    client_id = os.getenv("ANGEL_CLIENT_ID")
    pin = os.getenv("ANGEL_PIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")
    
    smart_api = SmartConnect(api_key=api_key)
    
    try:
        totp = pyotp.TOTP(totp_secret).now()
        login_data = smart_api.generateSession(client_id, pin, totp)
        
        if login_data['status']:
            return smart_api
        else:
            print("लॉगिन फेल हो गया है:", login_data)
            return None
    except Exception as e:
        print("सेशन बनाने में एरर:", str(e))
        return None

def fetch_my_portfolio():
    """पोर्टफोलियो (Holdings) का डेटा लाने का फंक्शन"""
    smart_api = get_angel_session()
    
    if not smart_api:
        return {"error": "ब्रोकर से कनेक्शन नहीं बन पाया"}
        
    holdings = smart_api.holding()
    
    # डेटा लेने के तुरंत बाद लॉगआउट करें (सिक्योरिटी)
    smart_api.terminateSession(os.getenv("ANGEL_CLIENT_ID"))
    
    if holdings['status']:
        return holdings['data']
    else:
        return {"error": holdings['message']}
