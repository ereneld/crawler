import threading
import time
import os
import json
import queue
import urllib.request
import urllib.parse
import urllib.error
import re
import html.parser
from collections import Counter

# Storage directories
DATA_DIR = "data"
STORAGE_DIR = os.path.join(DATA_DIR, "storage")
CRAWLER_DIR = os.path.join(DATA_DIR, "crawlers")

# Ensure directories exist
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(CRAWLER_DIR, exist_ok=True)

class HTMLParser(html.parser.HTMLParser):
    """Custom HTML parser to extract text and links"""
    
    def __init__(self):
        super().__init__()
        self.links = []
        self.text_content = []
        self.in_script_style = False
    
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ['script', 'style']:
            self.in_script_style = True
        elif tag.lower() == 'a':
            for attr_name, attr_value in attrs:
                if attr_name.lower() == 'href' and attr_value:
                    self.links.append(attr_value)
    
    def handle_endtag(self, tag):
        if tag.lower() in ['script', 'style']:
            self.in_script_style = False
    
    def handle_data(self, data):
        if not self.in_script_style:
            self.text_content.append(data)
    
    def get_text(self):
        return ' '.join(self.text_content)
    
    def get_links(self):
        return self.links

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
        
        # File paths
        self.status_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.data")
        self.visited_file = os.path.join(DATA_DIR, "visited_urls.data")
        
        # Initialize status file
        self._update_status_file()
    
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
                        url = line.strip()
                        if url:
                            self.visited_urls.add(url)
                self._log(f"Loaded {len(self.visited_urls)} previously visited URLs")
            else:
                self._log("No previous visited URLs file found, starting fresh")
        except Exception as e:
            self._log(f"Error loading visited URLs: {e}")
    
    def _save_visited_url(self, url):
        """Save a visited URL to the global file"""
        try:
            with open(self.visited_file, 'a') as f:
                f.write(f"{url}\n")
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
            parser = HTMLParser()
            parser.feed(html_content)
            
            # Get text and clean it
            text = parser.get_text()
            
            # Clean and count words (2+ characters, alphabetic only)
            words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
            word_freq = Counter(words)
            
            # Process links
            urls = []
            for link in parser.get_links():
                # Convert relative URLs to absolute
                full_url = urllib.parse.urljoin(base_url, link)
                
                # Only include HTTP/HTTPS URLs
                if full_url.startswith(('http://', 'https://')):
                    urls.append(full_url)
            
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
            
            # Make HTTP request
            with urllib.request.urlopen(req, timeout=10) as response:
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

def get_crawler_status(crawler_id):
    """Get crawler status from file"""
    try:
        status_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.data")
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                return json.load(f)
        else:
            return {"error": "Crawler not found"}
    except Exception as e:
        return {"error": f"Error reading crawler status: {e}"}

def search_words(query, page_limit=10, page_offset=0):
    """Search for words in the storage files"""
    try:
        results = []
        query_words = query.lower().split()
        
        for word in query_words:
            if len(word) >= 2:
                first_letter = word[0].lower()
                if not first_letter.isalpha():
                    first_letter = 'other'
                
                filename = os.path.join(STORAGE_DIR, f"{first_letter}.data")
                
                if os.path.exists(filename):
                    try:
                        with open(filename, 'r') as f:
                            data = json.load(f)
                        
                        # Look for exact matches and partial matches
                        for stored_word, entries in data.items():
                            if word in stored_word:
                                for entry in entries:
                                    results.append({
                                        "word": stored_word,
                                        "relevant_url": entry["relevant_url"],
                                        "origin_url": entry["origin_url"],
                                        "depth": entry["depth"],
                                        "frequency": entry["frequency"]
                                    })
                    except json.JSONDecodeError:
                        continue
        
        # Sort by frequency (descending)
        results.sort(key=lambda x: x["frequency"], reverse=True)
        
        # Apply pagination
        total_results = len(results)
        paginated_results = results[page_offset:page_offset + page_limit]
        
        return {
            "results": paginated_results,
            "total_results": total_results
        }
        
    except Exception as e:
        return {"error": f"Search error: {e}"}
