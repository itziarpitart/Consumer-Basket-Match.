import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
from dotenv import load_dotenv
from exchange_rate import get_exchange_rate
from cost_data import get_all_cities, get_city_costs
from match_utils import calculate_match_score

# Load environment variables
load_dotenv()

def main():
    st.set_page_config(page_title="Consumer Basket Match", page_icon="🏙️", layout="wide")
    
    # Custom CSS to improve UI
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .subheader {
        font-size: 1.5rem;
        font-weight: bold;
        margin-top: 2rem;
    }
    .card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="main-header">🏙️ Consumer Basket Match</div>', unsafe_allow_html=True)
    st.write("Find cities around the world where you can live **comfortably within your budget**.")
    
    # Initialize session state
    if 'results' not in st.session_state:
        st.session_state['results'] = None
    if 'selected_city' not in st.session_state:
        st.session_state['selected_city'] = None
    
    # === STEP 1: User Budget Input ===
    with st.container():
        st.markdown('<div class="subheader">💰 Step 1: Enter Your Monthly Budget</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "JPY", "AUD", "CAD"])
            budget_rent = st.number_input("🏠 Housing / Rent", min_value=0, step=50, value=1000)
            budget_groceries = st.number_input("🛒 Groceries & Food", min_value=0, step=50, value=400)
            budget_transport = st.number_input("🚌 Transport", min_value=0, step=20, value=100)
            budget_leisure = st.number_input("🎟️ Leisure", min_value=0, step=20, value=200)
            
            # Create user budget dictionary
            user_budget = {
                "rent": budget_rent,
                "groceries": budget_groceries,
                "transport": budget_transport,
                "leisure": budget_leisure
            }
            
            # Calculate total budget
            total_budget = sum(user_budget.values())
            
            # Filter options
            st.divider()
            st.subheader("Filter Options")
            
            # Region filter
            regions = {
                "All Regions": [], # This will be populated with all cities from get_all_cities()
                "Europe": ["Amsterdam", "Athens", "Barcelona", "Berlin", "Brussels", "Budapest", "Copenhagen", 
                          "Dublin", "Edinburgh", "Florence", "Frankfurt", "Geneva", "Hamburg", "Helsinki", "Istanbul", 
                          "Kiev", "Lisbon", "London", "Lyon", "Madrid", "Manchester", "Milan", "Moscow", "Munich", 
                          "Naples", "Nice", "Oslo", "Paris", "Porto", "Prague", "Rome", "Seville", "Stockholm", 
                          "Valencia", "Vienna", "Warsaw", "Zurich"],
                "North America": ["Atlanta", "Austin", "Boston", "Calgary", "Chicago", "Dallas", "Denver", 
                               "Houston", "Las Vegas", "Los Angeles", "Miami", "Minneapolis", "Montreal", "New York", 
                               "Ottawa", "Philadelphia", "Phoenix", "Portland", "San Diego", "San Francisco", "Seattle", 
                               "Toronto", "Vancouver", "Washington DC"],
                "Asia": ["Bangkok", "Beijing", "Bali", "Chengdu", "Chiang Mai", "Delhi", "Dubai", "Guangzhou", 
                        "Hanoi", "Ho Chi Minh City", "Hong Kong", "Hyderabad", "Jakarta", "Kuala Lumpur", "Kyoto", 
                        "Manila", "Mumbai", "Osaka", "Phuket", "Seoul", "Shanghai", "Shenzhen", "Singapore", "Taipei", 
                        "Tel Aviv", "Tokyo"],
                "South America": ["Asuncion", "Bogota", "Buenos Aires", "Cartagena", "Cuenca", "La Paz", "Lima", 
                                "Medellin", "Mexico City", "Montevideo", "Quito", "Rio de Janeiro", "Santiago", 
                                "Sao Paulo"],
                "Africa & Middle East": ["Abu Dhabi", "Accra", "Addis Ababa", "Baku", "Cairo", "Cape Town", "Casablanca", 
                                       "Dar es Salaam", "Doha", "Durban", "Johannesburg", "Lagos", "Marrakech", 
                                       "Nairobi", "Port Louis", "Riyadh", "Tbilisi", "Tunis"],
                "Australia & Pacific": ["Adelaide", "Auckland", "Brisbane", "Christchurch", "Melbourne", "Perth", 
                                      "Sydney", "Wellington"]
            }
            
            selected_region = st.selectbox("Region", list(regions.keys()), index=0)
            filtered_cities = regions[selected_region]
            
            # Max budget filter
            max_budget = st.checkbox("Filter by maximum total budget", value=False)
            max_budget_value = None
            
            if max_budget:
                max_budget_value = st.number_input("Maximum total monthly cost", 
                                                min_value=0, 
                                                max_value=10000, 
                                                value=total_budget,
                                                step=100)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.info(f"Total Monthly Budget: **{total_budget} {currency}**")
            
            if st.button("🔍 Find My Best City Matches", use_container_width=True):
                with st.spinner("Finding where your money goes furthest..."):
                    try:
                        # Get exchange rate data
                        exchange_data = get_exchange_rate(currency)
                        
                        # Get all available cities first
                        all_cities = get_all_cities()
                        
                        # If All Regions is selected but the regions dict has an empty list, populate it
                        if not regions["All Regions"]:
                            regions["All Regions"] = all_cities
                        
                        # Get cities based on the selected region filter
                        if selected_region != "All Regions":
                            # Filter to only include cities that exist in our data source
                            cities = [city for city in filtered_cities if city in all_cities]
                        else:
                            cities = all_cities
                        
                        results = []
                        for city in cities:
                            costs = get_city_costs(city, exchange_data)
                            if costs is None:  # Skip cities with no data
                                continue
                                
                            score = calculate_match_score(user_budget, costs)
                            
                            # Calculate budget differences
                            differences = {}
                            city_total_budget = sum(user_budget.values())
                            total_cost = sum(costs.values())
                            
                            for k in user_budget:
                                differences[k] = user_budget[k] - costs[k]
                            
                            # Apply max budget filter if enabled
                            if max_budget and max_budget_value is not None:
                                if total_cost > max_budget_value:
                                    continue  # Skip this city if over max budget
                            
                            results.append({
                                "City": city, 
                                "Match Score": score,
                                "Budget Difference": round(city_total_budget - total_cost, 2),
                                "Category Differences": differences,
                                **costs
                            })
                        
                        st.session_state['results'] = sorted(results, key=lambda x: x["Match Score"])
                        if len(st.session_state['results']) > 0:
                            st.session_state['selected_city'] = st.session_state['results'][0]["City"]
                        st.rerun()
                    except Exception as e:
                        st.error(f"An error occurred: {str(e)}")
        
        with col2:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            fig = px.pie(
                values=list(user_budget.values()),
                names=list(user_budget.keys()),
                title="Your Budget Allocation",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig.update_traces(textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # === STEP 2: Display Results ===
    if st.session_state['results']:
        st.markdown('<div class="subheader">📍 Step 2: Best Cities for Your Budget</div>', unsafe_allow_html=True)
        
        # Add pagination for results
        results_per_page = 10  # Number of results to show per page
        total_results = len(st.session_state['results'])
        
        if total_results == 0:
            st.warning("No cities match your criteria. Try adjusting your filters.")
        else:
            total_pages = (total_results + results_per_page - 1) // results_per_page
            
            col1, col2 = st.columns([1, 2])
            with col1:
                current_page = st.selectbox("Page", range(1, total_pages + 1), index=0, key="pagination")
            
            with col2:
                st.write(f"Showing {min(results_per_page, total_results - (current_page-1)*results_per_page)} of {total_results} cities")
            
            # Calculate start and end indices for the current page
            start_idx = (current_page - 1) * results_per_page
            end_idx = min(start_idx + results_per_page, total_results)
            
            # Get cities for the current page
            page_cities = st.session_state['results'][start_idx:end_idx]
            
            # Success message
            st.success(f"✅ Found {total_results} cities matching your criteria")
            
            # Top cities summary
            columns = ["City", "Match Score", "Budget Difference", "rent", "groceries", "transport", "leisure"]
            df = pd.DataFrame(page_cities)[columns]
            df.columns = ["City", "Match Score", "Budget Difference", "Rent", "Groceries", "Transport", "Leisure"]
            st.dataframe(df, use_container_width=True)
            
            # === STEP 3: City Details ===
            if len(st.session_state['results']) > 0:
                st.markdown('<div class="subheader">📊 Step 3: Detailed City Analysis</div>', unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    selected_city = st.selectbox(
                        "Select a city to analyze:", 
                        [city["City"] for city in st.session_state['results']],
                        index=[city["City"] for city in st.session_state['results']].index(st.session_state['selected_city']),
                        key="city_selector"
                    )
                    st.session_state['selected_city'] = selected_city
                    
                    city_data = next(city for city in st.session_state['results'] if city["City"] == selected_city)
                    
                    total_cost = sum([city_data["rent"], city_data["groceries"], city_data["transport"], city_data["leisure"]])
                    diff = total_budget - total_cost
                    
                    st.metric(
                        label=f"Total Monthly Cost in {selected_city}",
                        value=f"{total_cost} {currency}",
                        delta=f"{diff} {currency}",
                        delta_color="normal"  # Use normal coloring - green means you have money left
                    )
                    
                    if diff >= 0:
                        st.success(f"✅ Your budget is sufficient for {selected_city}! You'll have {diff} {currency} extra each month.")
                    else:
                        st.warning(f"⚠️ Your budget is {abs(diff)} {currency} short for {selected_city}.")
                        
                with col2:
                    # Comparison chart
                    fig = go.Figure()
                    
                    categories = list(user_budget.keys())
                    budget_values = list(user_budget.values())
                    city_values = [city_data[cat] for cat in categories]
                    
                    # Add bars for budget and city costs
                    fig.add_trace(go.Bar(
                        x=categories,
                        y=budget_values,
                        name="Your Budget",
                        marker_color='rgb(26, 118, 255)'
                    ))
                    
                    fig.add_trace(go.Bar(
                        x=categories,
                        y=city_values,
                        name=f"{selected_city} Costs",
                        marker_color='rgb(55, 83, 109)'
                    ))
                    
                    # Compare budget and cost for each category
                    for i, (category, budget, cost) in enumerate(zip(categories, budget_values, city_values)):
                        diff = budget - cost
                        color = "green" if diff >= 0 else "red"
                        symbol = "+" if diff >= 0 else ""
                        
                        fig.add_annotation(
                            x=category,
                            y=max(budget, cost) + 50,
                            text=f"{symbol}{round(diff, 2)} {currency}",
                            showarrow=False,
                            font=dict(color=color)
                        )
                    
                    fig.update_layout(
                        title=f"Your Budget vs {selected_city} Living Costs",
                        barmode='group',
                        xaxis_title="Categories",
                        yaxis_title=f"Amount ({currency})",
                        legend=dict(x=0, y=1.0),
                        margin=dict(l=50, r=50, t=80, b=50)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                # === NEW FEATURE: City Comparison ===
                st.markdown('<div class="subheader">🔄 Compare Cities Side by Side</div>', unsafe_allow_html=True)
                
                # Select cities to compare
                city_options = [city["City"] for city in st.session_state['results']]
                
                # Always include the currently selected city in the first dropdown
                compare_cities = [selected_city]
                
                # Let user select 1-2 more cities to compare
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"City 1: **{selected_city}**")
                
                with col2:
                    city_options_2 = [c for c in city_options if c != selected_city]
                    compare_city_2 = st.selectbox("City 2", ["Select a city..."] + city_options_2, key="compare_city_2")
                    if compare_city_2 != "Select a city...":
                        compare_cities.append(compare_city_2)
                
                with col3:
                    city_options_3 = [c for c in city_options if c != selected_city and c != compare_city_2]
                    compare_city_3 = st.selectbox("City 3", ["Select a city..."] + city_options_3, key="compare_city_3")
                    if compare_city_3 != "Select a city...":
                        compare_cities.append(compare_city_3)
                
                # If cities are selected for comparison, show the comparison
                if len(compare_cities) > 1:
                    # Get data for the cities to compare
                    comparison_data = [next(city for city in st.session_state['results'] 
                                           if city["City"] == city_name) for city_name in compare_cities]
                    
                    # Category comparison
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Category Comparison")
                    
                    # Create a table for categorical comparison
                    comparison_table = {"Category": ["Rent", "Groceries", "Transport", "Leisure", "Total Cost", "Match Score"]}
                    
                    for city in comparison_data:
                        city_name = city["City"]
                        total_cost = sum([city["rent"], city["groceries"], city["transport"], city["leisure"]])
                        
                        comparison_table[city_name] = [
                            f"{city['rent']} {currency}",
                            f"{city['groceries']} {currency}",
                            f"{city['transport']} {currency}",
                            f"{city['leisure']} {currency}",
                            f"{total_cost} {currency}",
                            city["Match Score"]
                        ]
                    
                    # Convert to DataFrame and display
                    df_comparison = pd.DataFrame(comparison_table)
                    st.table(df_comparison)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Radar chart comparing cities
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Visual Comparison")
                    
                    # Define categories and labels
                    categories = ["rent", "groceries", "transport", "leisure"]
                    category_labels = ["Rent", "Groceries", "Transport", "Leisure"]
                    
                    # Bar chart comparison
                    fig = go.Figure()
                    
                    for i, category in enumerate(categories):
                        fig.add_trace(go.Bar(
                            x=[city["City"] for city in comparison_data],
                            y=[city[category] for city in comparison_data],
                            name=category_labels[i]
                        ))
                    
                    fig.update_layout(
                        title="Cost Comparison by City",
                        barmode='group',
                        xaxis_title="City",
                        yaxis_title=f"Amount ({currency})"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # City budget comparison
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Budget Match Comparison")
                    
                    # Compare each city against the budget
                    city_cols = st.columns(len(comparison_data))
                    
                    for i, (col, city) in enumerate(zip(city_cols, comparison_data)):
                        with col:
                            st.subheader(city["City"])
                            
                            total_cost = sum([city["rent"], city["groceries"], city["transport"], city["leisure"]])
                            diff = total_budget - total_cost
                            
                            st.metric(
                                label="Total Cost",
                                value=f"{total_cost} {currency}",
                                delta=f"{diff} {currency}",
                                delta_color="normal"
                            )
                            
                            st.metric(
                                label="Match Score",
                                value=city["Match Score"],
                                delta=None
                            )
                            
                            if diff >= 0:
                                st.success(f"✅ Budget surplus: {diff} {currency}")
                            else:
                                st.warning(f"⚠️ Budget deficit: {abs(diff)} {currency}")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    # Recommendations
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.subheader("Recommendations")
                    
                    # Find best matches
                    best_overall = min(comparison_data, key=lambda x: x["Match Score"])
                    best_rent = min(comparison_data, key=lambda x: x["rent"])
                    best_groceries = min(comparison_data, key=lambda x: x["groceries"])
                    best_transport = min(comparison_data, key=lambda x: x["transport"])
                    best_leisure = min(comparison_data, key=lambda x: x["leisure"])
                    
                    st.write(f"**Best Overall Match:** {best_overall['City']} (Match Score: {best_overall['Match Score']})")
                    st.write(f"**Best for Rent:** {best_rent['City']} ({best_rent['rent']} {currency})")
                    st.write(f"**Best for Groceries:** {best_groceries['City']} ({best_groceries['groceries']} {currency})")
                    st.write(f"**Best for Transport:** {best_transport['City']} ({best_transport['transport']} {currency})")
                    st.write(f"**Best for Leisure:** {best_leisure['City']} ({best_leisure['leisure']} {currency})")
                    
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("Select at least one additional city to compare.")
    
    # Display additional information
    with st.expander("About this app"):
        st.markdown("""
        ### How this works
        
        This app compares your budget against the cost of living in various cities around the world. 
        The data is sourced from multiple APIs and built-in estimates for comprehensive coverage.
        
        ### How to use
        
        1. Enter your monthly budget for each category
        2. Select a region filter if you're interested in specific parts of the world 
        3. Optionally set a maximum total budget filter
        4. Click "Find My Best City Matches" to see which cities fit your budget
        5. Explore the detailed analysis for each city
        6. Compare multiple cities side by side using the comparison feature
        
        ### Data Sources
        
        The app uses a multi-source approach for the most comprehensive and accurate data:
        
        - RapidAPI Cost of Living API: Primary source for up-to-date cost information
        - Teleport API: Secondary source for additional cities and data points
        - Built-in database: Fallback for cities not covered by the APIs
        - Currency exchange: ExchangeRate API
        
        ### Data Limitations
        
        - Cost data may not be available for all cities
        - The app uses monthly averages which may vary based on lifestyle and neighborhoods
        - Currency exchange rates are updated daily
        """)
        
        # API status
        st.subheader("API Configuration Status")
        
        # Check for RapidAPI key
        rapidapi_key = os.environ.get("RAPIDAPI_KEY") or st.secrets.get("RAPIDAPI_KEY")
        if rapidapi_key and rapidapi_key != "your_rapidapi_key_here":
            st.success("✅ RapidAPI configured - using live cost of living data")
        else:
            st.warning("⚠️ RapidAPI not configured. Add your API key to the .env file to enable more cities and up-to-date data.")
        
        # Exchange Rate API
        exchange_api_key = os.environ.get("EXCHANGERATE_API_KEY") or st.secrets.get("EXCHANGERATE_API_KEY")
        if exchange_api_key and exchange_api_key != "your_exchangerate_api_key_here":
            st.success("✅ ExchangeRate API configured")
        else:
            st.warning("⚠️ ExchangeRate API not configured properly. Add your API key to get accurate currency conversions.")

if __name__ == "__main__":
    main()
