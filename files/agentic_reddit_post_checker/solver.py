# TO SHOW THIS IS DOABLE AND THE ANSWER IS SAME. LLM WON'T SEE THIS.
# solver.py

import requests
from datetime import datetime, timezone
from tqdm import tqdm # For a nice progress bar

# --- 1. Configuration ---
BASE_URL = "http://localhost:8834/api"
TARGET_DATE = datetime(2022, 4, 8, tzinfo=timezone.utc)

def solve_task():
    """
    Executes the sequence of API calls required to find the answer.
    """
    # Use a session object to persist headers (like Authorization) across requests
    session = requests.Session()
    
    # --- STEP 1: Authentication ---
    # Discover the auth endpoint and get an API key.
    print("Step 1: Authenticating...")
    try:
        auth_url = f"{BASE_URL}/auth/request_key"
        response = session.post(auth_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        api_key = response.json().get("api_key")
        if not api_key:
            print("Error: API key not found in auth response.")
            return

        # Set the Authorization header for all subsequent requests in this session
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        print("Successfully authenticated.")

    except requests.exceptions.RequestException as e:
        print(f"Error during authentication: {e}")
        print("Is the server running on localhost:8834?")
        return

    # --- STEP 2: Find the Tech Subreddit ---
    # Get all subreddits and identify the correct one by its description.
    print("\nStep 2: Finding the tech subreddit...")
    try:
        subreddits_url = f"{BASE_URL}/subreddits"
        response = session.get(subreddits_url)
        response.raise_for_status()
        
        subreddits = response.json()
        tech_subreddit_id = None
        for sub in subreddits:
            # The agent would need to infer this from the description's content
            if "technology" in sub.get("description", "").lower() or \
               "programming" in sub.get("description", "").lower():
                tech_subreddit_id = sub["id"]
                print(f"Found tech subreddit: '{sub['name']}' (ID: {tech_subreddit_id})")
                break
        
        if tech_subreddit_id is None:
            print("Error: Could not find a tech-related subreddit.")
            return

    except requests.exceptions.RequestException as e:
        print(f"Error finding subreddits: {e}")
        return

    # --- STEP 3: Get all Posts from the Tech Subreddit ---
    # Filter by subreddit_id and fetch the list of relevant posts.
    print("\nStep 3: Fetching posts from the tech subreddit...")
    try:
        posts_url = f"{BASE_URL}/posts"
        params = {"subreddit_id": tech_subreddit_id}
        response = session.get(posts_url, params=params)
        response.raise_for_status()
        
        all_posts = response.json()
        print(f"Fetched {len(all_posts)} posts.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching posts: {e}")
        return

    # --- STEP 4: Filter Posts and Find the Target Post ---
    # Iterate through posts, filter by date, fetch comments, and find the max average downvotes.
    print("\nStep 4: Filtering posts and analyzing comments...")
    
    # Filter posts by date first to reduce the number of API calls for comments
    valid_posts = []
    for post in all_posts:
        post_date = datetime.fromisoformat(post['created_utc'].replace('Z', '+00:00'))
        if post_date > TARGET_DATE:
            valid_posts.append(post)
    
    print(f"Found {len(valid_posts)} posts created after {TARGET_DATE.date()}.")
    
    best_post_id = None
    max_avg_downvotes = -1.0 # Initialize with a value that will always be beaten

    # Use tqdm for a progress bar as this is the most time-consuming step
    for post in tqdm(valid_posts, desc="Analyzing comments"):
        try:
            # The comments_url is a relative path, so we join it with the base URL
            comments_url = "http://localhost:8834" + post['comments_url']
            response = session.get(comments_url)
            response.raise_for_status()
            
            comments = response.json()
            
            # Avoid division by zero if a post has no comments
            if not comments:
                continue

            # Calculate the average downvotes
            total_downvotes = sum(c['downvotes'] for c in comments)
            avg_downvotes = total_downvotes / len(comments)
            
            # Check if this post is the new best candidate
            if avg_downvotes > max_avg_downvotes:
                max_avg_downvotes = avg_downvotes
                best_post_id = post['id']

        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not fetch comments for post {post['id']}: {e}")
            continue
            
    # --- STEP 5: Print the Final Answer ---
    print("\nAnalysis complete.")
    if best_post_id is not None:
        print(f"Post with highest average downvotes ({max_avg_downvotes:.2f}) found.")
        print(f"ANSWER={best_post_id}")
    else:
        print("Could not find a post that matches all criteria.")

if __name__ == "__main__":
    solve_task()