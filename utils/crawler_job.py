import threading
import time
import os
import json
import queue
import urllib.request
import urllib.parse
import urllib.error
import ssl
import re
from collections import Counter
from .html_parser import parse_html_content

# Storage directories
DATA_DIR = "data"
STORAGE_DIR = os.path.join(DATA_DIR, "storage")
CRAWLER_DIR = os.path.join(DATA_DIR, "crawlers")

# Ensure directories exist
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(CRAWLER_DIR, exist_ok=True)

class CrawlerJob(threading.Thread):
    """Threaded crawler job that handles web crawling with file-based storage using native Python libraries"""
    
    def __init__(self, crawler_id, origin, max_depth, hit_rate, max_queue_capacity):
        super().__init__()
        self.crawler_id = crawler_id
        self.origin = origin
        self.max_depth = max_depth
        self.hit_rate = hit_rate
        self.max_queue_capacity = max_queue_capacity
        
        # Thread-safe queue for URLs to visit
        self.url_queue = queue.Queue(maxsize=max_queue_capacity)
        self.visited_urls = set()
        self.status = "Active"
        self.logs = []
        
        # Rate limiting
        self.last_request_time = 0
        self.request_interval = 1.0 / hit_rate  # seconds between requests
        
        # SSL context configurations
        self._setup_ssl_contexts()
        
        # File paths
        self.status_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.data")
        self.visited_file = os.path.join(DATA_DIR, "visited_urls.data")
        
        # Initialize status file
        self._update_status_file()
    
    def _setup_ssl_contexts(self):
        """Setup SSL contexts for secure and permissive connections"""
        # Primary context with full verification
        self.ssl_context_secure = ssl.create_default_context()
        
        # Fallback context for sites with certificate issues
        self.ssl_context_permissive = ssl.create_default_context()
        self.ssl_context_permissive.check_hostname = False
        self.ssl_context_permissive.verify_mode = ssl.CERT_NONE
        
        self._log("SSL contexts configured for secure and permissive connections")
    
    def _log(self, message):
        """Add log entry with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - {message}"
        self.logs.append(log_entry)
        print(f"[{self.crawler_id}] {log_entry}")  # Also print to console
        self._update_status_file()
    
    def _update_status_file(self):
        """Update the crawler status file"""
        try:
            # Get current queue contents (safely)
            queue_list = []
            temp_queue = queue.Queue()
            
            # Drain queue to get contents
            while not self.url_queue.empty():
                try:
                    item = self.url_queue.get_nowait()
                    queue_list.append(f"{item[0]} (depth: {item[1]})")
                    temp_queue.put(item)
                except queue.Empty:
                    break
            
            # Restore queue
            while not temp_queue.empty():
                self.url_queue.put(temp_queue.get_nowait())
            
            status_data = {
                "crawler_id": self.crawler_id,
                "status": self.status,
                "origin": self.origin,
                "max_depth": self.max_depth,
                "hit_rate": self.hit_rate,
                "max_queue_capacity": self.max_queue_capacity,
                "queue": queue_list,
                "logs": self.logs[-50:],  # Keep last 50 logs
                "visited_count": len(self.visited_urls),
                "timestamp": time.time()
            }
            
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            print(f"Error updating status file: {e}")
    
    def _load_visited_urls(self):
        """Load global visited URLs from file"""
        try:
            if os.path.exists(self.visited_file):
                with open(self.visited_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Handle multiple formats: space-separated, JSON, or plain URL
                            parts = line.split()
                            
                            if len(parts) >= 3:
                                # New space-separated format: URL CRAWLER_ID DATETIME
                                url = parts[0]
                                if url.startswith(('http://', 'https://')):
                                    self.visited_urls.add(url)
                            elif line.startswith('{'):
                                # JSON format (temporary transition format)
                                try:
                                    import json
                                    url_data = json.loads(line)
                                    url = url_data.get('url', '')
                                    if url:
                                        self.visited_urls.add(url)
                                except json.JSONDecodeError:
                                    pass
                            elif line.startswith(('http://', 'https://')):
                                # Old format (just the URL)
                                self.visited_urls.add(line)
                self._log(f"Loaded {len(self.visited_urls)} previously visited URLs")
            else:
                self._log("No previous visited URLs file found, starting fresh")
        except Exception as e:
            self._log(f"Error loading visited URLs: {e}")
    
    def _save_visited_url(self, url):
        """Save a visited URL to the global file with space-separated metadata"""
        try:
            from datetime import datetime
            
            # Create space-separated entry: URL CRAWLER_ID DATETIME
            visited_at = datetime.now().isoformat()
            
            # Append as space-separated line
            with open(self.visited_file, 'a') as f:
                f.write(f"{url} {self.crawler_id} {visited_at}\n")
            
            self.visited_urls.add(url)
        except Exception as e:
            self._log(f"Error saving visited URL: {e}")
    
    def _rate_limit(self):
        """Apply rate limiting based on hit_rate"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            sleep_time = self.request_interval - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _extract_text_and_urls(self, html_content, base_url):
        """Extract text content and URLs from HTML using native Python parser"""
        try:
            # Use the HTML parser utility
            text, urls = parse_html_content(html_content, base_url)
            
            # Clean and count words (2+ characters, alphabetic only)
            words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
            word_freq = Counter(words)
            
            return word_freq, urls
            
        except Exception as e:
            self._log(f"Error parsing HTML: {e}")
            return Counter(), []
    
    def _store_words(self, word_freq, url, depth):
        """Store words by their initial letter in alphabet files"""
        try:
            for word, frequency in word_freq.items():
                if len(word) >= 2:  # Only store words with 2+ characters
                    first_letter = word[0].lower()
                    
                    # Handle non-alphabetic first characters
                    if not first_letter.isalpha():
                        first_letter = 'other'
                    
                    filename = os.path.join(STORAGE_DIR, f"{first_letter}.data")
                    
                    # Read existing data
                    data = {}
                    if os.path.exists(filename):
                        try:
                            with open(filename, 'r') as f:
                                data = json.load(f)
                        except json.JSONDecodeError:
                            data = {}
                    
                    # Add new entry
                    if word not in data:
                        data[word] = []
                    
                    data[word].append({
                        "relevant_url": url,
                        "origin_url": self.origin,
                        "depth": depth,
                        "frequency": frequency
                    })
                    
                    # Save back to file
                    with open(filename, 'w') as f:
                        json.dump(data, f, indent=2)
            
            self._log(f"Stored {len(word_freq)} unique words from {url}")
            
        except Exception as e:
            self._log(f"Error storing words: {e}")
    
    def _crawl_url(self, url, depth):
        """Crawl a single URL using native urllib"""
        try:
            self._rate_limit()
            
            if url in self.visited_urls:
                return []
            
            self._log(f"Crawling {url} at depth {depth}")
            
            # Create request with user agent
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; BrightwaveCrawler/1.0)'
                }
            )
            
            # Try with secure SSL context first, then fallback to permissive
            html_content = None
            for attempt, ssl_context in enumerate([self.ssl_context_secure, self.ssl_context_permissive], 1):
                try:
                    with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
                        if response.status != 200:
                            self._log(f"HTTP {response.status} for {url}")
                            return []
                        
                        # Read content
                        content = response.read()
                        
                        # Try to decode content
                        try:
                            html_content = content.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                html_content = content.decode('latin1')
                            except UnicodeDecodeError:
                                self._log(f"Could not decode content from {url}")
                                return []
                        
                        # If we get here, the request was successful
                        if attempt == 2:
                            self._log(f"Successfully accessed {url} using permissive SSL context")
                        break
                        
                except ssl.SSLError as e:
                    if attempt == 1:
                        self._log(f"SSL verification failed for {url}, trying with permissive context: {e}")
                        continue
                    else:
                        self._log(f"SSL error for {url} even with permissive context: {e}")
                        return []
                except Exception as e:
                    if attempt == 2:
                        raise  # Re-raise if this was the last attempt
                    continue
            
            if html_content is None:
                self._log(f"Failed to retrieve content from {url}")
                return []
            
            # Mark as visited
            self._save_visited_url(url)
            
            # Extract content
            word_freq, urls = self._extract_text_and_urls(html_content, url)
            
            # Store words
            self._store_words(word_freq, url, depth)
            
            # Return new URLs for next depth level
            new_urls = [u for u in urls if u not in self.visited_urls]
            self._log(f"Found {len(new_urls)} new URLs at {url}")
            
            return new_urls
            
        except urllib.error.URLError as e:
            self._log(f"URL error for {url}: {e}")
            return []
        except urllib.error.HTTPError as e:
            self._log(f"HTTP error {e.code} for {url}")
            return []
        except Exception as e:
            self._log(f"Error crawling {url}: {e}")
            return []
    
    def run(self):
        """Main crawler thread execution"""
        try:
            self._log("Crawler thread started")
            
            # Load previously visited URLs
            self._load_visited_urls()
            
            # Start with origin URL at depth 0
            self.url_queue.put((self.origin, 0))
            
            while not self.url_queue.empty():
                try:
                    url, depth = self.url_queue.get(timeout=1)
                    
                    # Check if we've exceeded max depth
                    if depth > self.max_depth:
                        continue
                    
                    # Crawl the URL
                    new_urls = self._crawl_url(url, depth)
                    
                    # Add new URLs to queue for next depth level
                    if depth < self.max_depth:
                        for new_url in new_urls:
                            try:
                                self.url_queue.put((new_url, depth + 1), timeout=1)
                            except queue.Full:
                                self._log("Queue full, pausing URL discovery")
                                break
                    
                    self.url_queue.task_done()
                    
                except queue.Empty:
                    # No more URLs to process
                    break
                except Exception as e:
                    self._log(f"Error in crawler loop: {e}")
                    self.status = "Interrupted"
                    self._update_status_file()
                    return
            
            self.status = "Finished"
            self._log("Crawler completed successfully")
            
        except Exception as e:
            self.status = "Interrupted"
            self._log(f"Crawler interrupted: {e}")
        finally:
            self._update_status_file()
