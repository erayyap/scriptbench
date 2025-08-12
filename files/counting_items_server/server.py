#!/usr/bin/env python3
from flask import Flask, jsonify
import time
import random

# --- Server Configuration ---

# Instantiate the Flask app
app = Flask(__name__)
TOTAL_ITEMS_IN_DB = 52679

# --- API Endpoints ---

@app.route('/get_item/<int:index_number>', methods=['GET'])
def get_item(index_number):
    """
    Endpoint to retrieve a single item by its index.
    - Has a 50% chance to wait 1 second before responding.
    - Returns item data if the index is valid.
    - Returns a 404 error if the index is out of bounds.
    """
    # Print a log to the server console to show a request was received
    print(f"--> Request received for item with index: {index_number}")

    # --- NEW: Simulate latency with a 50% chance of a 1-second delay ---
    if random.random() < 0.5:
        print("    Simulating network/database latency with a 1-second delay...")
        time.sleep(1) # Pauses the execution for 1 second

    # The core logic: Check if the requested index is valid.
    # We also check for index <= 0, as IDs start from 1.
    if index_number > TOTAL_ITEMS_IN_DB or index_number <= 0:
        # The index is greater than what we have, so return a 404 Not Found error.
        # The first script will detect this and stop.
        print(f"    Index {index_number} is out of bounds (total items: {TOTAL_ITEMS_IN_DB}). Returning 404.")
        # The jsonify function creates a proper JSON response with the correct headers.
        # We also explicitly set the status code to 404.
        return jsonify({"error": "Item not found"}), 404
    else:
        # The index is valid. Return a 200 OK response with some dummy item data.
        print(f"    Index {index_number} is valid. Returning item data.")
        item_data = {
            "id": index_number,
            "name": f"Sample Item {index_number}",
            "description": f"This is a description for item #{index_number}.",
            "price": round(index_number * 3.14, 2) # A dynamic-looking price
        }
        return jsonify(item_data)

@app.route('/')
def index():
    """A simple index route to confirm the server is running."""
    return "Flask server is running. Try accessing /get_item/1"

# --- Main execution block ---

if __name__ == '__main__':
    # To run this server:
    # 1. Save the code as a Python file (e.g., server.py).
    # 2. Install Flask: pip install Flask
    # 3. Run from your terminal: python server.py
    #
    # The server will start on http://localhost:8000
    #
    # The `debug=True` setting provides helpful error messages and auto-reloads
    # the server when you save changes. Do not use in production.
    # `host='0.0.0.0'` makes the server accessible from other devices on your network.
    app.run(host='0.0.0.0', port=6793, debug=True)