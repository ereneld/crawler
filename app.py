from flask import Flask, request, jsonify
import re
import time
import threading
from urllib.parse import urlparse
from crawlerservice import CrawlerJob, get_crawler_status, search_words

# Constants for depth limits
MIN_DEPTH = 1
MAX_DEPTH = 1000

# Constants for hit rate limits (hits per second)
MIN_HIT_RATE = 0.1
MAX_HIT_RATE = 1000.0
DEFAULT_HIT_RATE = 100.0

# Constants for queue capacity limits
MIN_QUEUE_CAPACITY = 100
MAX_QUEUE_CAPACITY = 100000
DEFAULT_QUEUE_CAPACITY = 10000

app = Flask(__name__)

def is_valid_url(url):
    """Validate if the provided string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def validate_crawler_parameters(data):
    """Validate crawler creation parameters and return error if any"""
    errors = []
    
    # Validate origin URL parameter
    if 'origin' not in data:
        errors.append("Missing required parameter: origin")
    elif not isinstance(data['origin'], str) or not data['origin'].strip():
        errors.append("Parameter 'origin' must be a non-empty string")
    elif not is_valid_url(data['origin']):
        errors.append("Parameter 'origin' must be a valid URL")
    
    # Validate max_depth parameter
    if 'max_depth' not in data:
        errors.append("Missing required parameter: max_depth")
    elif not isinstance(data['max_depth'], int):
        errors.append("Parameter 'max_depth' must be an integer")
    elif data['max_depth'] < MIN_DEPTH:
        errors.append(f"Parameter 'max_depth' must be greater than 0 (minimum: {MIN_DEPTH})")
    elif data['max_depth'] > MAX_DEPTH:
        errors.append(f"Parameter 'max_depth' must not exceed {MAX_DEPTH}")
    
    # Validate optional hit_rate parameter
    if 'hit_rate' in data:
        hit_rate = data['hit_rate']
        if not isinstance(hit_rate, (int, float)):
            errors.append("Parameter 'hit_rate' must be a number")
        elif hit_rate < MIN_HIT_RATE:
            errors.append(f"Parameter 'hit_rate' must be at least {MIN_HIT_RATE}")
        elif hit_rate > MAX_HIT_RATE:
            errors.append(f"Parameter 'hit_rate' must not exceed {MAX_HIT_RATE}")
    
    # Validate optional max_queue_capacity parameter
    if 'max_queue_capacity' in data:
        max_queue_capacity = data['max_queue_capacity']
        if not isinstance(max_queue_capacity, int):
            errors.append("Parameter 'max_queue_capacity' must be an integer")
        elif max_queue_capacity < MIN_QUEUE_CAPACITY:
            errors.append(f"Parameter 'max_queue_capacity' must be at least {MIN_QUEUE_CAPACITY}")
        elif max_queue_capacity > MAX_QUEUE_CAPACITY:
            errors.append(f"Parameter 'max_queue_capacity' must not exceed {MAX_QUEUE_CAPACITY}")
    
    return errors


@app.route('/crawler/create', methods=['POST'])
def create_crawler():
    """Start a crawler job with the provided parameters"""
    try:
        # Get JSON data from request
        if not request.is_json:
            return jsonify({
                "error": "Content-Type must be application/json"
            }), 400
        
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "Request body must contain valid JSON"
            }), 400
        
        # Validate parameters
        validation_errors = validate_crawler_parameters(data)
        if validation_errors:
            return jsonify({
                "error": "Invalid parameters",
                "details": validation_errors
            }), 400
        
        # Extract validated parameters
        origin = data['origin'].strip()
        max_depth = data['max_depth']
        hit_rate = data.get('hit_rate', DEFAULT_HIT_RATE)  # Optional parameter with default
        max_queue_capacity = data.get('max_queue_capacity', DEFAULT_QUEUE_CAPACITY)  # Optional parameter with default
        
        # Generate crawler_id format: [EpochTimeCreated_ThreadID]
        epoch_time = int(time.time())
        thread_id = threading.get_ident()
        crawler_id = f"{epoch_time}_{thread_id}"
        
        # Create and start crawler job
        crawler = CrawlerJob(
            crawler_id=crawler_id,
            origin=origin,
            max_depth=max_depth,
            hit_rate=hit_rate,
            max_queue_capacity=max_queue_capacity
        )
        
        # Start the crawler thread
        crawler.start()
        
        response_data = {
            "crawler_id": crawler_id,
            "status": "Active"
        }
        
        return jsonify(response_data), 201
        
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

@app.route('/search', methods=['GET'])
def search():
    """Search for URLs based on query string"""
    try:
        # Get query parameters
        query = request.args.get('query')
        page_limit = request.args.get('pageLimit', 10, type=int)
        page_offset = request.args.get('pageOffset', 0, type=int)
        
        # Validate query parameter
        if not query or not query.strip():
            return jsonify({
                "error": "Missing or empty required parameter: query"
            }), 400
        
        # Validate pagination parameters
        if page_limit <= 0:
            return jsonify({
                "error": "pageLimit must be greater than 0"
            }), 400
        
        if page_offset < 0:
            return jsonify({
                "error": "pageOffset must be 0 or greater"
            }), 400
        
        query = query.strip()
        
        # Use the search service
        search_result = search_words(query, page_limit, page_offset)
        
        if "error" in search_result:
            return jsonify(search_result), 500
        
        response_data = {
            "query": query,
            "results": search_result["results"],
            "total_results": search_result["total_results"],
            "page_limit": page_limit,
            "page_offset": page_offset
        }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

@app.route('/crawler/status/<crawler_id>', methods=['GET'])
def crawler_status(crawler_id):
    """Get crawler status by ID with long polling capability"""
    try:
        status_data = get_crawler_status(crawler_id)
        
        if "error" in status_data:
            return jsonify(status_data), 404
        
        return jsonify(status_data), 200
        
    except Exception as e:
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "crawler-api"
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Endpoint not found"
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method not allowed"
    }), 405

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
