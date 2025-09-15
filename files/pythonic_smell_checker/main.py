# main.py - A script to process user data and display a profile summary

def process_and_display_user_profile(username, age, account_balance, last_login_days_ago, user_status, is_premium_member, country_code):
    """
    This function takes a lot of user details, determines their user tier,
    and prints a detailed summary.
    """

    # Smell 1: Complex Conditional Logic & Magic Numbers
    # Determine user tier based on a series of hardcoded, complex rules.
    user_tier = ""
    if user_status == "active" and account_balance > 10000 and is_premium_member and country_code == "US":
        user_tier = "Platinum"
    elif user_status == "active" and account_balance > 5000 and is_premium_member:
        user_tier = "Gold"
    elif user_status == "active" and account_balance > 1000:
        user_tier = "Silver"
    elif user_status == "inactive" and last_login_days_ago > 90:
        user_tier = "Dormant"
    else:
        user_tier = "Bronze"

    # Some more confusing logic
    final_discount = 0
    if age > 65: # senior discount
        final_discount += 0.10
    if is_premium_member: # premium discount
        final_discount += 0.05

    # Smell 2: Long Line Length
    # Generate a very long, unreadable summary string for the user profile dashboard panel display.
    profile_summary_string = f"User '{username}' (Age: {age}, Status: {user_status}) who lives in {country_code} currently has a balance of ${account_balance:.2f}, is a premium member: {is_premium_member}, and belongs to the '{user_tier}' tier with a final discount of {final_discount*100}%. Their last login was {last_login_days_ago} days ago."

    print("--- User Profile Summary ---")
    print(profile_summary_string)

    if user_tier == "Dormant":
        print("Action Required: This user is dormant and may need a re-engagement email.")


if __name__ == "__main__":
    # Sample user data in a dictionary with inconsistent naming
    user_data_1 = {
        "name": "jsmith123",
        "user_age": 42,
        "bal": 7590.50,
        "last_log": 15,
        "stat": "active",
        "premium": True,
        "country": "US"
    }

    # Smell 3: Long Parameter List (Function Call)
    # The function is called with 7 separate arguments, which is hard to read and error-prone.
    process_and_display_user_profile(user_data_1["name"], user_data_1["user_age"], user_data_1["bal"], user_data_1["last_log"], user_data_1["stat"], user_data_1["premium"], user_data_1["country"])

    print("\n" + "="*30 + "\n")

    # Another user to show a different logic path
    user_data_2 = {
        "name": "inactive_user",
        "user_age": 25,
        "bal": 150.00,
        "last_log": 120,
        "stat": "inactive",
        "premium": False,
        "country": "CA"
    }
    process_and_display_user_profile(user_data_2["name"], user_data_2["user_age"], user_data_2["bal"], user_data_2["last_log"], user_data_2["stat"], user_data_2["premium"], user_data_2["country"])