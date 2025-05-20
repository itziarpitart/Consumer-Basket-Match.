import requests
import streamlit as st
import time
import json
from pathlib import Path

# Cache directory setup
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_exchange_rate(target_currency):
    """
    Get the exchange rate from USD to the target currency.
    
    Args:
        target_currency (str): Currency code (USD, EUR, etc.)
        
    Returns:
        dict: Exchange rate information
    """
    # If target is USD, return 1:1 rate without API call
    if target_currency == "USD":
        return {"rate_to_target": 1.0}
    
    # Check cache first
    cache_file = CACHE_DIR / f"exchange_{target_currency}.json"
    
    # Use cached data if less than 1 day old
    if cache_file.exists():
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age < 86400:  # 24 hours in seconds
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    print(f"Using cached exchange rate for {target_currency}")
                    return cached_data
            except (json.JSONDecodeError, KeyError):
                pass  # Cache invalid, continue to API call
    
    # Fallback rates in case API fails
    fallback_rates = {
        "EUR": 0.92,
        "GBP": 0.78,
        "JPY": 110.0,
        "AUD": 1.35,
        "CAD": 1.25
    }
    
    try:
        # Get API key from secrets
        api_key = st.secrets.get("EXCHANGERATE_API_KEY")
        if not api_key:
            raise ValueError("API key not found in secrets.toml")
            
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        
        # Make API request with timeout and retries
        session = requests.Session()
        retries = 3
        
        for attempt in range(retries):
            try:
                response = session.get(url, timeout=10)
                response.raise_for_status()  # Raise exception for 4XX/5XX responses
                data = response.json()
                
                if data.get("result") == "success":
                    result = {
                        "rate_to_target": data["conversion_rates"][target_currency],
                        "last_updated": data.get("time_last_update_unix", int(time.time()))
                    }
                    
                    # Cache the results
                    with open(cache_file, 'w') as f:
                        json.dump(result, f)
                    
                    return result
                else:
                    print(f"API error: {data.get('error', 'Unknown error')}")
            
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"Exchange rate API attempt {attempt+1}/{retries} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(1)  # Wait before retrying
    
    except Exception as e:
        print(f"Error fetching exchange rate for {target_currency}: {e}")
    
    # If we get here, use fallback data
    print(f"Using fallback exchange rate for {target_currency}")
    return {
        "rate_to_target": fallback_rates.get(target_currency, 1.0),
        "last_updated": int(time.time())
    }