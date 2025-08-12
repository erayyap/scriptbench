# api_server_final.py

import random
from datetime import datetime, timezone
from functools import wraps
from faker import Faker
from flask import Flask, jsonify, request

# --- 1. Constants and Configuration ---
HOST = 'localhost'
PORT = 8834
RANDOM_SEED = 42
API_KEY = "a_very_secret_and_deterministic_key_42"
TOTAL_POSTS = 15000

# --- 2. Authorization Decorator ---
def require_api_key(f):
    """A decorator to protect endpoints with an API key."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                "error": "Authorization required.",
                "hint": "Request an API key from the auth endpoint and provide it as 'Authorization: Bearer <key>'."
            }), 401
        
        provided_key = auth_header.split(' ')[1]
        if provided_key != API_KEY:
            return jsonify({"error": "Forbidden. Invalid API Key."}), 403
            
        return f(*args, **kwargs)
    return decorated_function

# --- 3. Deterministic Data Generation ---
def generate_deterministic_data():
    """Generates a large, consistent set of data."""
    print("Generating large deterministic dataset...")
    
    fake = Faker()
    Faker.seed(RANDOM_SEED)
    random.seed(RANDOM_SEED)

    db = {
        "subreddits": {},
        "posts": {},
        "posts_by_subreddit": {},
        "comments_by_post": {}
    }

    subreddit_specs = [
        {"name": "r/CozyPlaces", "desc": "Pictures of cozy places."},
        {"name": "r/AskHistory", "desc": "Get answers to your history questions."},
        {"name": "r/FutureTech", "desc": "Discussions on technology, programming, and upcoming gadgets."},
        {"name": "r/ArtisanVideos", "desc": "Videos of people making things."},
        {"name": "r/PerfectFit", "desc": "Things that fit perfectly into other things."},
        {"name": "r/GardeningUK", "desc": "Gardening in the UK."},
        {"name": "r/MovieDetails", "desc": "Did you notice this?"},
        {"name": "r/NatureIsMetal", "desc": "Nature, raw and unforgiving."},
        {"name": "r/Breadit", "desc": "All things bread."},
        {"name": "r/SimpleLiving", "desc": "Living a simple, uncluttered life."}
    ]
    
    for i, spec in enumerate(subreddit_specs):
        sub_id = i + 1
        db["subreddits"][sub_id] = {"id": sub_id, "name": spec["name"], "description": spec["desc"]}
        db["posts_by_subreddit"][sub_id] = []

    comment_id_counter = 1
    subreddit_ids = list(db["subreddits"].keys())
    for i in range(TOTAL_POSTS):
        post_id = i + 1
        sub_id = random.choice(subreddit_ids)
        
        created_date = fake.date_time_between(start_date="-3y", end_date="now", tzinfo=timezone.utc)
        
        post = {
            "id": post_id, "subreddit_id": sub_id, "title": fake.sentence(nb_words=random.randint(4, 10)),
            "author": fake.user_name(), "created_utc": created_date.isoformat().replace('+00:00', 'Z'),
            "comments_url": f"/api/posts/{post_id}/comments"
        }
        db["posts"][post_id] = post
        db["posts_by_subreddit"][sub_id].append(post_id)
        
        db["comments_by_post"][post_id] = []
        for _ in range(random.randint(10, 50)):
            comment = {
                "id": comment_id_counter, "post_id": post_id, "author": fake.user_name(),
                "text": fake.paragraph(nb_sentences=random.randint(1, 3)), "upvotes": random.randint(0, 2000),
                "downvotes": random.randint(0, 500)
            }
            db["comments_by_post"][post_id].append(comment)
            comment_id_counter += 1
            
    print(f"Dataset generated: {len(db['subreddits'])} subreddits, {len(db['posts'])} posts.")
    return db

# --- 4. Initialize Flask App and Load Data ---
app = Flask(__name__)
DB = generate_deterministic_data()
FAKER_INSTANCE = Faker()

# --- 5. API Route Definitions ---

# MODIFIED: The root endpoint now lists all available routes.
@app.route("/api/")
def index():
    """Discovery endpoint providing a full map of the API."""
    return jsonify({
        "message": "Welcome to the Reddit-Lite API v2.1. See available endpoints below.",
        "endpoints": {
            "self": {
                "url": "/api/",
                "method": "GET",
                "description": "This discovery document."
            },
            "request_api_key": {
                "url": "/api/auth/request_key",
                "method": "POST",
                "description": "POST to receive an API key for accessing protected resources. Body is not required."
            },
            "list_subreddits": {
                "url": "/api/subreddits",
                "method": "GET",
                "description": "List all available subreddits."
            },
            "list_posts": {
                "url": "/api/posts?subreddit_id={id}",
                "method": "GET",
                "description": "List posts for a specific subreddit. Requires Authorization."
            },
            "list_comments": {
                "url": "/api/posts/{post_id}/comments",
                "method": "GET",
                "description": "List comments for a specific post. Requires Authorization."
            },
            "server_status": {
                "url": "/api/status",
                "method": "GET",
                "description": "[INFO] Check the server's operational status."
            },
            "user_profile": {
                "url": "/api/users/{username}",
                "method": "GET",
                "description": "[INFO] Get profile information for a user."
            },
            "search_content": {
                "url": "/api/search?q={query}",
                "method": "GET",
                "description": "[BETA] Search for content across the platform. Requires Authorization."
            }
        }
    })

@app.route("/api/auth/request_key", methods=['POST'])
def request_key():
    return jsonify({"api_key": API_KEY})

@app.route("/api/subreddits")
def get_subreddits():
    return jsonify(list(DB["subreddits"].values()))

@app.route("/api/posts")
@require_api_key
def get_posts():
    subreddit_id_str = request.args.get('subreddit_id')
    if not subreddit_id_str:
        return jsonify({"error": "Missing required query parameter: subreddit_id"}), 400
    try:
        subreddit_id = int(subreddit_id_str)
    except ValueError:
        return jsonify({"error": "Invalid subreddit_id format. Must be an integer."}), 400

    post_ids = DB["posts_by_subreddit"].get(subreddit_id, [])
    filtered_posts = [DB["posts"][pid] for pid in post_ids]
    return jsonify(filtered_posts)

@app.route("/api/posts/<int:post_id>/comments")
@require_api_key
def get_comments(post_id):
    comments = DB["comments_by_post"].get(post_id)
    if comments is None:
        return jsonify({"error": "Post not found"}), 404
    return jsonify(comments)

# Red Herring Routes
@app.route("/api/status")
def get_status():
    return jsonify({"status": "online", "version": "2.1.0", "timestamp": datetime.now(timezone.utc).isoformat()})

@app.route("/api/users/<string:username>")
def get_user_profile(username):
    Faker.seed(username)
    return jsonify({
        "username": username, "member_since": FAKER_INSTANCE.date_of_birth(minimum_age=18, maximum_age=65).isoformat(),
        "bio": FAKER_INSTANCE.sentence(), "location": FAKER_INSTANCE.city(), "karma": random.randint(1, 100000)
    })

@app.route("/api/search")
@require_api_key
def search():
    if not request.args.get('q'):
        return jsonify({"error": "Missing search query parameter: q"}), 400
    return jsonify([])

# --- 6. Main Execution ---
if __name__ == '__main__':
    print(f"Starting advanced API server at http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)