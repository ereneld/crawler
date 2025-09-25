from flask import Flask, request, jsonify
from urllib.parse import urlparse
from services.crawler_service import (
    create_crawler,
    get_crawler_status,
    list_all_crawlers,
    stop_crawler,
    pause_crawler,
    resume_crawler,
    resume_crawler_from_files,
    clear_all_data,
    get_crawler_statistics,
)
from services.search_service import search_words, get_random_word

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

# Constants for max URLs to visit limits
MIN_MAX_URLS_TO_VISIT = 0
MAX_MAX_URLS_TO_VISIT = 10000
DEFAULT_MAX_URLS_TO_VISIT = 1000

app = Flask(__name__)


# Add CORS support for frontend
@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type,Authorization")
    response.headers.add("Access-Control-Allow-Methods", "GET,PUT,POST,DELETE,OPTIONS")
    return response


def is_valid_url(url):
    """Validate if the provided string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


# ========== CRAWLER ENDPOINTS ==========


@app.route("/crawler/create", methods=["POST"])
def create_crawler_endpoint():
    """Start a crawler job with the provided parameters"""
    try:
        # Get JSON data from request
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json"}), 400

        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must contain valid JSON"}), 400

        # Validate required parameters
        if "origin" not in data:
            return jsonify({"error": "Missing required parameter: origin"}), 400
        elif not isinstance(data["origin"], str) or not data["origin"].strip():
            return (
                jsonify({"error": "Parameter 'origin' must be a non-empty string"}),
                400,
            )
        elif not is_valid_url(data["origin"]):
            return jsonify({"error": "Parameter 'origin' must be a valid URL"}), 400

        if "max_depth" not in data:
            return jsonify({"error": "Missing required parameter: max_depth"}), 400
        elif not isinstance(data["max_depth"], int):
            return jsonify({"error": "Parameter 'max_depth' must be an integer"}), 400
        elif data["max_depth"] < MIN_DEPTH or data["max_depth"] > MAX_DEPTH:
            return (
                jsonify(
                    {
                        "error": f"Parameter 'max_depth' must be between {MIN_DEPTH} and {MAX_DEPTH}"
                    }
                ),
                400,
            )

        # Validate optional parameters
        if "hit_rate" in data:
            hit_rate = data["hit_rate"]
            if (
                not isinstance(hit_rate, (int, float))
                or hit_rate < MIN_HIT_RATE
                or hit_rate > MAX_HIT_RATE
            ):
                return (
                    jsonify(
                        {
                            "error": f"Parameter 'hit_rate' must be between {MIN_HIT_RATE} and {MAX_HIT_RATE}"
                        }
                    ),
                    400,
                )

        if "max_queue_capacity" in data:
            max_queue_capacity = data["max_queue_capacity"]
            if (
                not isinstance(max_queue_capacity, int)
                or max_queue_capacity < MIN_QUEUE_CAPACITY
                or max_queue_capacity > MAX_QUEUE_CAPACITY
            ):
                return (
                    jsonify(
                        {
                            "error": f"Parameter 'max_queue_capacity' must be between {MIN_QUEUE_CAPACITY} and {MAX_QUEUE_CAPACITY}"
                        }
                    ),
                    400,
                )

        if "max_urls_to_visit" in data:
            max_urls_to_visit = data["max_urls_to_visit"]
            if (
                not isinstance(max_urls_to_visit, int)
                or max_urls_to_visit < MIN_MAX_URLS_TO_VISIT
                or max_urls_to_visit > MAX_MAX_URLS_TO_VISIT
            ):
                return (
                    jsonify(
                        {
                            "error": f"Parameter 'max_urls_to_visit' must be between {MIN_MAX_URLS_TO_VISIT} and {MAX_MAX_URLS_TO_VISIT}"
                        }
                    ),
                    400,
                )

        # Extract validated parameters
        origin = data["origin"].strip()
        max_depth = data["max_depth"]
        hit_rate = data.get(
            "hit_rate", DEFAULT_HIT_RATE
        )  # Optional parameter with default
        max_queue_capacity = data.get(
            "max_queue_capacity", DEFAULT_QUEUE_CAPACITY
        )  # Optional parameter with default
        max_urls_to_visit = data.get(
            "max_urls_to_visit", DEFAULT_MAX_URLS_TO_VISIT
        )  # Optional parameter with default

        # Create and start crawler using the service
        result = create_crawler(
            origin=origin,
            max_depth=max_depth,
            hit_rate=hit_rate,
            max_queue_capacity=max_queue_capacity,
            max_urls_to_visit=max_urls_to_visit,
        )

        if "error" in result:
            return jsonify(result), 500

        response_data = {"crawler_id": result["crawler_id"], "status": result["status"]}

        return jsonify(response_data), 201

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/status/<crawler_id>", methods=["GET"])
def crawler_status(crawler_id):
    """Get crawler status by ID with long polling capability"""
    try:
        status_data = get_crawler_status(crawler_id)

        if "error" in status_data:
            return jsonify(status_data), 404

        return jsonify(status_data), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/list", methods=["GET"])
def list_crawlers():
    """List all crawler jobs"""
    try:
        result = list_all_crawlers()

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/stop/<crawler_id>", methods=["POST"])
def stop_crawler_endpoint(crawler_id):
    """Stop a crawler job"""
    try:
        result = stop_crawler(crawler_id)

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/pause/<crawler_id>", methods=["POST"])
def pause_crawler_endpoint(crawler_id):
    """Pause an active crawler"""
    try:
        result = pause_crawler(crawler_id)

        if "error" in result:
            return jsonify(result), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/resume/<crawler_id>", methods=["POST"])
def resume_crawler_endpoint(crawler_id):
    """Resume a paused crawler"""
    try:
        result = resume_crawler(crawler_id)

        if "error" in result:
            return jsonify(result), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/resume-from-files/<crawler_id>", methods=["POST"])
def resume_crawler_from_files_endpoint(crawler_id):
    """Resume a stopped crawler from its saved files"""
    try:
        result = resume_crawler_from_files(crawler_id)

        if "error" in result:
            return jsonify(result), 404

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/clear", methods=["POST"])
def clear_crawler_data():
    """Clear all crawler data including visited URLs, crawler files, and storage files"""
    try:
        result = clear_all_data()

        if result.get("status") == "error":
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/crawler/stats", methods=["GET"])
def get_crawler_stats():
    """Get comprehensive crawler statistics"""
    try:
        result = get_crawler_statistics()

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ========== SEARCH ENDPOINTS ==========


@app.route("/search", methods=["GET"])
def search():
    """Search for URLs based on query string"""
    try:
        # Get query parameters
        query = request.args.get("query")
        page_limit = request.args.get("pageLimit", 10, type=int)
        page_offset = request.args.get("pageOffset", 0, type=int)
        sort_by = request.args.get("sortBy", "relevance")

        # Validate query parameter
        if not query or not query.strip():
            return jsonify({"error": "Missing or empty required parameter: query"}), 400

        # Validate pagination parameters
        if page_limit <= 0:
            return jsonify({"error": "pageLimit must be greater than 0"}), 400

        if page_offset < 0:
            return jsonify({"error": "pageOffset must be 0 or greater"}), 400

        # Validate sort parameter
        valid_sort_options = ["relevance", "frequency", "depth"]
        if sort_by not in valid_sort_options:
            return (
                jsonify(
                    {"error": f"sortBy must be one of: {', '.join(valid_sort_options)}"}
                ),
                400,
            )

        query = query.strip()

        # Use the search service
        search_result = search_words(query, page_limit, page_offset, sort_by)

        if "error" in search_result:
            return jsonify(search_result), 500

        response_data = {
            "query": query,
            "results": search_result["results"],
            "total_results": search_result["total_results"],
            "page_limit": page_limit,
            "page_offset": page_offset,
            "sort_by": sort_by,
        }

        # Add additional search info if available
        if "query_words" in search_result:
            response_data["query_words"] = search_result["query_words"]
        if "files_searched" in search_result:
            response_data["files_searched"] = search_result["files_searched"]

        return jsonify(response_data), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route("/search/random", methods=["GET"])
def get_random_search_word():
    """Get a random word for 'I'm Feeling Lucky' functionality"""
    try:
        result = get_random_word()

        if "error" in result:
            return jsonify(result), 500

        return jsonify(result), 200

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"error": "Method not allowed"}), 405


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3600)
