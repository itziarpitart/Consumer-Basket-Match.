def calculate_match_score(user_budget, city_costs):
    """
    Calculate how closely a city matches the user's budget.
    Lower scores are better (closer match).
    
    Args:
        user_budget (dict): User's budget by category
        city_costs (dict): City's costs by category
        
    Returns:
        float: Match score (lower is better)
    """
    total_difference = 0
    
    for key in user_budget:
        if key in city_costs:
            # Calculate absolute difference between budget and cost
            diff = abs(city_costs[key] - user_budget[key])
            total_difference += diff
    
    # Return the total absolute difference (lower means closer match)
    return round(total_difference, 2)