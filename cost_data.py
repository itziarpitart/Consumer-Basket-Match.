
import requests
import time
import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

def get_all_cities():
    """
    Get a comprehensive list of all cities available across all data sources.
    
    Returns:
        list: Combined list of unique city names from all sources
    """
    # Try to get from cache first
    cache_file = CACHE_DIR / "all_cities.json"
    
    if cache_file.exists():
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age < 604800:  # 7 days in seconds
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
    
    # Combine cities from all sources
    all_cities = set()
    
    # 1. Try RapidAPI cities
    try:
        rapidapi_cities = get_rapidapi_cities()
        all_cities.update(rapidapi_cities)
    except Exception as e:
        print(f"Error fetching RapidAPI cities: {e}")
    
    # 2. Try Teleport API cities
    try:
        teleport_cities = list(TELEPORT_CITIES.keys())
        all_cities.update(teleport_cities)
    except Exception as e:
        print(f"Error getting Teleport cities: {e}")
    
    # 3. Add fallback cities
    all_cities.update(FALLBACK_COSTS.keys())
    
    # Convert to sorted list
    city_list = sorted(list(all_cities))
    
    # Cache the results
    with open(cache_file, 'w') as f:
        json.dump(city_list, f)
    
    return city_list

def get_rapidapi_cities():
    """
    Get the list of cities available in RapidAPI's Cost of Living API.
    
    Returns:
        list: List of city names
    """
    # Check the cache first
    cache_file = CACHE_DIR / "rapidapi_cities.json"
    
    # Use cached data if less than 7 days old
    if cache_file.exists():
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age < 604800:  # 7 days in seconds
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
    
    # Get the API key from environment
    api_key = os.environ.get("RAPIDAPI_KEY", "")
    
    if not api_key:
        print("RapidAPI key not found. Using fallback and Teleport data only.")
        return []
    
    try:
        # Get cities list from RapidAPI's Cost of Living API
        url = "https://cost-of-living-and-prices.p.rapidapi.com/cities"
        
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "cost-of-living-and-prices.p.rapidapi.com"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract city names from the response
        cities = []
        if "cities" in data and isinstance(data["cities"], list):
            cities = [city["city_name"] for city in data["cities"]]
            
            # Cache the cities list
            with open(cache_file, 'w') as f:
                json.dump(cities, f)
            
            return cities
        else:
            print("Invalid data format from RapidAPI")
            return []
    
    except Exception as e:
        print(f"Error fetching cities from RapidAPI: {e}")
        return []

def get_city_costs(city, exchange_rate):
    """
    Get cost of living data using a tiered approach: 
    RapidAPI -> Teleport -> Fallback.
    
    Args:
        city (str): Name of the city
        exchange_rate (dict): Exchange rate information
    
    Returns:
        dict: Cost of living data or None if not available
    """
    # 1. Try RapidAPI first (most comprehensive)
    try:
        costs = get_rapidapi_costs(city, exchange_rate)
        if costs:
            print(f"Using RapidAPI data for {city}")
            return costs
    except Exception as e:
        print(f"RapidAPI failed for {city}: {e}")
    
    # 2. Try Teleport API next
    try:
        costs = get_teleport_costs(city, exchange_rate)
        if costs:
            print(f"Using Teleport data for {city}")
            return costs
    except Exception as e:
        print(f"Teleport API failed for {city}: {e}")
    
    # 3. Use fallback data as last resort
    costs = get_fallback_costs(city, exchange_rate)
    if costs:
        print(f"Using fallback data for {city}")
        return costs
        
    # If we get here, no data is available for this city
    print(f"No data available for {city}")
    return None

def get_rapidapi_costs(city, exchange_rate):
    """
    Get cost data from RapidAPI's Cost of Living API.
    
    Args:
        city (str): City name
        exchange_rate (dict): Exchange rate information
    
    Returns:
        dict: Cost of living data or None if not available
    """
    # Check the cache first
    city_slug = city.lower().replace(" ", "_").replace(",", "")
    cache_file = CACHE_DIR / f"rapidapi_{city_slug}.json"
    
    # Use cached data if less than 24 hours old
    if cache_file.exists():
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age < 86400:  # 24 hours in seconds
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    
                    # Apply exchange rate
                    factor = exchange_rate["rate_to_target"]
                    return {
                        "rent": round(cached_data["rent"] * factor, 2),
                        "groceries": round(cached_data["groceries"] * factor, 2),
                        "transport": round(cached_data["transport"] * factor, 2),
                        "leisure": round(cached_data["leisure"] * factor, 2)
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error reading cache for {city}: {e}")
    
    # Get the API key from environment
    api_key = os.environ.get("RAPIDAPI_KEY", "")
    
    if not api_key:
        # No API key, skip this source
        return None
    
    try:
        # Call the RapidAPI endpoint
        url = "https://cost-of-living-and-prices.p.rapidapi.com/prices"
        
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "cost-of-living-and-prices.p.rapidapi.com"
        }
        
        querystring = {"city_name": city}
        
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Initialize cost categories
        rent = 0
        groceries = 0
        transport = 0
        leisure = 0
        
        # Process the data if it's in the expected format
        if "prices" in data and isinstance(data["prices"], list):
            prices = data["prices"]
            
            # Map the API's price items to our categories
            for item in prices:
                item_name = item.get("item_name", "").lower()
                price = item.get("usd", {}).get("avg", 0)
                
                # Rent category
                if "rent" in item_name or "apartment" in item_name or "housing" in item_name:
                    if "one bedroom" in item_name or "1 bedroom" in item_name or "1-bedroom" in item_name:
                        rent = price
                        
                # Groceries category
                elif any(food_term in item_name for food_term in ["food", "grocery", "market", "supermarket", "milk", "bread", "rice", "eggs", "cheese", "meat"]):
                    if "price per" in item_name:
                        # For individual items, assume monthly consumption
                        if "kg" in item_name or "liter" in item_name:
                            groceries += price * 4  # Assume 4 units per month
                        else:
                            groceries += price  # One-time monthly expense
                    else:
                        groceries += price
                
                # Transport category
                elif any(transport_term in item_name for transport_term in ["transport", "transportation", "bus", "train", "taxi", "gasoline", "fuel", "public transport"]):
                    if "monthly" in item_name:
                        transport += price
                    elif "one-way" in item_name or "single" in item_name:
                        transport += price * 40  # Assume 40 trips per month
                    else:
                        transport += price
                
                # Leisure category
                elif any(leisure_term in item_name for leisure_term in ["leisure", "entertainment", "restaurant", "cinema", "theater", "gym", "fitness", "sports"]):
                    if "monthly" in item_name:
                        leisure += price
                    else:
                        leisure += price * 4  # Assume 4 times per month
            
            # Normalize the data
            # If rent is missing, try to estimate from other housing data
            if rent == 0:
                for item in prices:
                    item_name = item.get("item_name", "").lower()
                    price = item.get("usd", {}).get("avg", 0)
                    
                    if "rent" in item_name or "apartment" in item_name:
                        if "three bedroom" in item_name or "3 bedroom" in item_name:
                            rent = price * 0.6  # Estimate 1-bed as 60% of 3-bed
                            break
                        elif "studio" in item_name:
                            rent = price * 1.2  # Estimate 1-bed as 120% of studio
                            break
            
            # Ensure minimum reasonable values
            groceries = max(groceries, 200)  # Minimum monthly groceries
            transport = max(transport, 50)   # Minimum monthly transport
            leisure = max(leisure, 100)      # Minimum monthly leisure
            
            # If rent is still 0, use a reasonable estimate
            if rent == 0:
                # Estimate rent as 2.5x the sum of other expenses
                if groceries > 0 or transport > 0 or leisure > 0:
                    rent = (groceries + transport + leisure) * 1.5
                else:
                    # Use global average
                    rent = 1000
            
            # Prepare the result
            costs = {
                "rent": rent,
                "groceries": groceries,
                "transport": transport,
                "leisure": leisure
            }
            
            # Cache the results
            with open(cache_file, 'w') as f:
                json.dump(costs, f)
            
            # Apply exchange rate
            factor = exchange_rate["rate_to_target"]
            return {
                "rent": round(costs["rent"] * factor, 2),
                "groceries": round(costs["groceries"] * factor, 2),
                "transport": round(costs["transport"] * factor, 2),
                "leisure": round(costs["leisure"] * factor, 2)
            }
    
    except Exception as e:
        print(f"Error fetching RapidAPI data for {city}: {e}")
    
    return None

def get_teleport_costs(city, exchange_rate):
    """
    Get cost data from Teleport API.
    
    Args:
        city (str): City name
        exchange_rate (dict): Exchange rate information
    
    Returns:
        dict: Cost of living data or None if not available
    """
    # Check if city is in Teleport cities dictionary
    city_slug = None
    
    # Direct match
    if city in TELEPORT_CITIES:
        city_slug = TELEPORT_CITIES[city]
    else:
        # Try to find a close match (e.g., "New York" might be stored as "New York City")
        for teleport_city, slug in TELEPORT_CITIES.items():
            if city in teleport_city or teleport_city in city:
                city_slug = slug
                break
    
    if not city_slug:
        return None
    
    # Check the cache first
    cache_file = CACHE_DIR / f"teleport_{city_slug}.json"
    
    # Use cached data if less than 24 hours old
    if cache_file.exists():
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age < 86400:  # 24 hours in seconds
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    
                    # Apply exchange rate
                    factor = exchange_rate["rate_to_target"]
                    return {
                        "rent": round(cached_data["rent"] * factor, 2),
                        "groceries": round(cached_data["groceries"] * factor, 2),
                        "transport": round(cached_data["transport"] * factor, 2),
                        "leisure": round(cached_data["leisure"] * factor, 2)
                    }
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error reading cache for {city}: {e}")
    
    try:
        # Call the Teleport API
        url = f"https://api.teleport.org/api/urban_areas/slug:{city_slug}/details/"
        
        # Add retries for reliability
        session = requests.Session()
        retries = 3
        
        for attempt in range(retries):
            try:
                response = session.get(url, timeout=10)
                response.raise_for_status()
                r = response.json()
                
                rent, groceries, transport, leisure = 0, 0, 0, 0
                
                # Extract categories from the response
                for cat in r["categories"]:
                    for item in cat["data"]:
                        id = item.get("id", "").lower()
                        val = item.get("currency_dollar_value", 0)
                        
                        # Housing/Rent
                        if "apartment" in id and "1bed" in id:
                            rent = val
                        # Alternative rent data points
                        elif "studio" in id and "apartment" in id and rent == 0:
                            rent = val * 1.2  # Adjust studio to approximate 1-bedroom
                        elif "apartment" in id and "medium" in id and rent == 0:
                            rent = val

                        # Groceries
                        elif any(food_term in id for food_term in ["market", "food", "groceries", "supermarket"]):
                            groceries += val * 0.25  # Scale to avoid over-counting
                            
                        # Transport
                        elif any(transport_term in id for transport_term in ["transport", "transit", "transportation", "bus", "train", "subway", "taxi"]):
                            transport += val * 0.5  # Scale appropriately
                            
                        # Leisure
                        elif any(leisure_term in id for leisure_term in ["leisure", "restaurant", "entertainment", "fitness", "cinema", "sports", "gym"]):
                            leisure += val * 0.25  # Scale to avoid over-counting
                
                # Ensure minimum values
                groceries = max(groceries, 150)
                transport = max(transport, 30)
                leisure = max(leisure, 50)
                
                # If rent is still 0, estimate it
                if rent == 0:
                    # Estimate rent based on typical ratios of other costs
                    rent = (groceries * 3) + (transport * 2) + (leisure * 2)
                
                costs = {
                    "rent": rent,
                    "groceries": groceries,
                    "transport": transport,
                    "leisure": leisure
                }
                
                # Cache the results
                with open(cache_file, 'w') as f:
                    json.dump(costs, f)
                
                # Apply exchange rate
                factor = exchange_rate["rate_to_target"]
                return {
                    "rent": round(costs["rent"] * factor, 2),
                    "groceries": round(costs["groceries"] * factor, 2),
                    "transport": round(costs["transport"] * factor, 2),
                    "leisure": round(costs["leisure"] * factor, 2)
                }
                
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                print(f"Teleport API attempt {attempt+1}/{retries} failed for {city}: {e}")
                if attempt < retries - 1:
                    time.sleep(1)  # Wait before retrying
    
    except Exception as e:
        print(f"Error fetching Teleport data for {city}: {e}")
    
    return None

def get_fallback_costs(city, exchange_rate):
    """
    Get cost data from built-in fallback data.
    
    Args:
        city (str): City name
        exchange_rate (dict): Exchange rate information
    
    Returns:
        dict: Cost of living data or None if not available
    """
    # Check if city is in fallback data dictionary
    if city in FALLBACK_COSTS:
        factor = exchange_rate["rate_to_target"]
        fallback = FALLBACK_COSTS[city]
        return {
            "rent": round(fallback["rent"] * factor, 2),
            "groceries": round(fallback["groceries"] * factor, 2),
            "transport": round(fallback["transport"] * factor, 2),
            "leisure": round(fallback["leisure"] * factor, 2)
        }
    
    # Try to find a close match
    for fallback_city in FALLBACK_COSTS.keys():
        if city in fallback_city or fallback_city in city:
            factor = exchange_rate["rate_to_target"]
            fallback = FALLBACK_COSTS[fallback_city]
            return {
                "rent": round(fallback["rent"] * factor, 2),
                "groceries": round(fallback["groceries"] * factor, 2),
                "transport": round(fallback["transport"] * factor, 2),
                "leisure": round(fallback["leisure"] * factor, 2)
            }
    
    return None

# Dictionary of city slugs for Teleport API
TELEPORT_CITIES = {
    "Amsterdam": "amsterdam", "Athens": "athens", "Atlanta": "atlanta",
    "Austin": "austin", "Bangkok": "bangkok", "Barcelona": "barcelona",
    "Beijing": "beijing", "Bengaluru": "bangalore", "Berlin": "berlin",
    "Bogota": "bogota", "Boston": "boston", "Brussels": "brussels",
    "Budapest": "budapest", "Buenos Aires": "buenos-aires", "Cairo": "cairo",
    "Cape Town": "cape-town", "Chicago": "chicago", "Copenhagen": "copenhagen",
    "Dallas": "dallas", "Denver": "denver", "Dubai": "dubai",
    "Dublin": "dublin", "Edinburgh": "edinburgh", "Frankfurt": "frankfurt",
    "Hamburg": "hamburg", "Helsinki": "helsinki", "Hong Kong": "hong-kong",
    "Honolulu": "honolulu", "Houston": "houston", "Istanbul": "istanbul",
    "Jakarta": "jakarta", "Johannesburg": "johannesburg", "Kiev": "kiev",
    "Kuala Lumpur": "kuala-lumpur", "Lagos": "lagos", "Las Vegas": "las-vegas",
    "Lisbon": "lisbon", "London": "london", "Los Angeles": "los-angeles",
    "Madrid": "madrid", "Manila": "manila", "Melbourne": "melbourne",
    "Mexico City": "mexico-city", "Miami": "miami", "Milan": "milan",
    "Minneapolis": "minneapolis", "Montreal": "montreal", "Moscow": "moscow",
    "Mumbai": "mumbai", "Munich": "munich", "Nairobi": "nairobi",
    "New York": "new-york", "Oslo": "oslo", "Paris": "paris",
    "Philadelphia": "philadelphia", "Prague": "prague", "Rio de Janeiro": "rio-de-janeiro",
    "Rome": "rome", "San Diego": "san-diego", "San Francisco": "san-francisco",
    "Santiago": "santiago", "Sao Paulo": "sao-paulo", "Seattle": "seattle",
    "Seoul": "seoul", "Shanghai": "shanghai", "Singapore": "singapore",
    "Stockholm": "stockholm", "Sydney": "sydney", "Taipei": "taipei",
    "Tel Aviv": "tel-aviv", "Tokyo": "tokyo", "Toronto": "toronto",
    "Vancouver": "vancouver", "Vienna": "vienna", "Warsaw": "warsaw",
    "Washington DC": "washington-dc", "Zurich": "zurich"
}

# Fallback cost data for major cities
FALLBACK_COSTS = {
    # North America
    "New York": {"rent": 2500, "groceries": 450, "transport": 120, "leisure": 300},
    "San Francisco": {"rent": 2800, "groceries": 450, "transport": 100, "leisure": 250},
    "Los Angeles": {"rent": 2000, "groceries": 400, "transport": 100, "leisure": 200},
    "Chicago": {"rent": 1600, "groceries": 350, "transport": 100, "leisure": 180},
    "Boston": {"rent": 2200, "groceries": 400, "transport": 90, "leisure": 200},
    "Seattle": {"rent": 1900, "groceries": 400, "transport": 90, "leisure": 190},
    "Washington DC": {"rent": 2000, "groceries": 400, "transport": 100, "leisure": 200},
    "Miami": {"rent": 1700, "groceries": 350, "transport": 70, "leisure": 180},
    "Toronto": {"rent": 1400, "groceries": 350, "transport": 80, "leisure": 170},
    "Vancouver": {"rent": 1500, "groceries": 350, "transport": 70, "leisure": 170},
    "Montreal": {"rent": 900, "groceries": 300, "transport": 70, "leisure": 140},
    "Austin": {"rent": 1500, "groceries": 350, "transport": 60, "leisure": 170},
    "Denver": {"rent": 1500, "groceries": 350, "transport": 80, "leisure": 150},
    "Philadelphia": {"rent": 1400, "groceries": 350, "transport": 80, "leisure": 170},
    "San Diego": {"rent": 1800, "groceries": 350, "transport": 70, "leisure": 180},
    "Portland": {"rent": 1500, "groceries": 350, "transport": 80, "leisure": 150},
    "Dallas": {"rent": 1300, "groceries": 350, "transport": 70, "leisure": 150},
    "Atlanta": {"rent": 1400, "groceries": 350, "transport": 60, "leisure": 150},
    "Houston": {"rent": 1200, "groceries": 350, "transport": 70, "leisure": 150},
    "Phoenix": {"rent": 1200, "groceries": 300, "transport": 60, "leisure": 130},
    "Las Vegas": {"rent": 1100, "groceries": 300, "transport": 60, "leisure": 150},
    "Minneapolis": {"rent": 1300, "groceries": 350, "transport": 70, "leisure": 150},
    "Mexico City": {"rent": 500, "groceries": 200, "transport": 25, "leisure": 100},
    "Calgary": {"rent": 1000, "groceries": 300, "transport": 80, "leisure": 140},
    "Ottawa": {"rent": 1100, "groceries": 300, "transport": 80, "leisure": 140},
    
    # Europe
    "London": {"rent": 1800, "groceries": 400, "transport": 150, "leisure": 250},
    "Paris": {"rent": 1300, "groceries": 350, "transport": 70, "leisure": 200},
    "Berlin": {"rent": 950, "groceries": 300, "transport": 70, "leisure": 150},
    "Barcelona": {"rent": 900, "groceries": 300, "transport": 50, "leisure": 150},
    "Amsterdam": {"rent": 1300, "groceries": 350, "transport": 70, "leisure": 180},
    "Rome": {"rent": 900, "groceries": 300, "transport": 50, "leisure": 150},
    "Madrid": {"rent": 850, "groceries": 250, "transport": 50, "leisure": 130},
    "Dublin": {"rent": 1500, "groceries": 350, "transport": 100, "leisure": 170},
    "Lisbon": {"rent": 800, "groceries": 250, "transport": 40, "leisure": 120},
    "Athens": {"rent": 450, "groceries": 250, "transport": 30, "leisure": 100},
    "Prague": {"rent": 650, "groceries": 250, "transport": 30, "leisure": 100},
    "Stockholm": {"rent": 1200, "groceries": 350, "transport": 90, "leisure": 180},
    "Vienna": {"rent": 900, "groceries": 300, "transport": 60, "leisure": 150},
    "Munich": {"rent": 1200, "groceries": 300, "transport": 70, "leisure": 160},
    "Copenhagen": {"rent": 1350, "groceries": 400, "transport": 80, "leisure": 180},
    "Oslo": {"rent": 1300, "groceries": 400, "transport": 80, "leisure": 180},
    "Helsinki": {"rent": 1100, "groceries": 350, "transport": 60, "leisure": 160},
    "Budapest": {"rent": 450, "groceries": 230, "transport": 25, "leisure": 90},
    "Warsaw": {"rent": 600, "groceries": 250, "transport": 30, "leisure": 100},
    "Zurich": {"rent": 1800, "groceries": 450, "transport": 100, "leisure": 200},
    
    # Asia
    "Tokyo": {"rent": 1200, "groceries": 350, "transport": 80, "leisure": 200},
    "Singapore": {"rent": 1800, "groceries": 350, "transport": 60, "leisure": 180},
    "Hong Kong": {"rent": 2000, "groceries": 400, "transport": 50, "leisure": 180},
    "Seoul": {"rent": 1000, "groceries": 350, "transport": 60, "leisure": 150},
    "Shanghai": {"rent": 900, "groceries": 300, "transport": 40, "leisure": 130},
    "Beijing": {"rent": 800, "groceries": 280, "transport": 40, "leisure": 120},
    "Dubai": {"rent": 1200, "groceries": 350, "transport": 60, "leisure": 170},
    "Bangkok": {"rent": 500, "groceries": 200, "transport": 30, "leisure": 100},
    "Mumbai": {"rent": 600, "groceries": 200, "transport": 15, "leisure": 80},
    "Delhi": {"rent": 400, "groceries": 150, "transport": 15, "leisure": 60},
    "Tel Aviv": {"rent": 1200, "groceries": 350, "transport": 60, "leisure": 170},
    "Kuala Lumpur": {"rent": 450, "groceries": 200, "transport": 25, "leisure": 90},
    "Taipei": {"rent": 700, "groceries": 250, "transport": 30, "leisure": 120},
    
    # Australia & Pacific
    "Sydney": {"rent": 1400, "groceries": 350, "transport": 60, "leisure": 180},
    "Melbourne": {"rent": 1300, "groceries": 350, "transport": 60, "leisure": 160},
    "Auckland": {"rent": 1200, "groceries": 330, "transport": 55, "leisure": 150},
    
    # South America
    "Buenos Aires": {"rent": 400, "groceries": 200, "transport": 20, "leisure": 80},
    "Rio de Janeiro": {"rent": 500, "groceries": 200, "transport": 30, "leisure": 100},
    "Sao Paulo": {"rent": 550, "groceries": 200, "transport": 30, "leisure": 100},
    "Santiago": {"rent": 600, "groceries": 250, "transport": 40, "leisure": 110},
    
    # Africa
    "Cairo": {"rent": 300, "groceries": 180, "transport": 15, "leisure": 70},
    "Cape Town": {"rent": 500, "groceries": 220, "transport": 30, "leisure": 100},
    "Johannesburg": {"rent": 400, "groceries": 200, "transport": 25, "leisure": 90},
    "Lagos": {"rent": 500, "groceries": 250, "transport": 30, "leisure": 100},
}