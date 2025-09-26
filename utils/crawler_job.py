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
    
    def __init__(self, crawler_id, origin, max_depth, hit_rate, max_queue_capacity, max_urls_to_visit, resume_from_files=False):
        super().__init__()
        self.crawler_id = crawler_id
        self.origin = origin
        self.max_depth = max_depth
        self.hit_rate = hit_rate
        self.max_queue_capacity = max_queue_capacity
        self.max_urls_to_visit = max_urls_to_visit
        self.resume_from_files = resume_from_files
        
        # Thread-safe queue for URLs to visit
        self.url_queue = queue.Queue(maxsize=max_queue_capacity)
        self.visited_urls = set()
        self.urls_visited_this_session = 0  # Counter for this crawler session only
        self.status = "Active"
        self.logs = []
        
        # Pause/Resume control
        self._pause_event = threading.Event()
        self._pause_event.set()  # Start unpaused
        self._stop_event = threading.Event()
        
        # Timestamp tracking
        self.created_at = time.time()
        self.completed_at = None
        
        # Rate limiting
        self.last_request_time = 0
        self.request_interval = 1.0 / hit_rate  # seconds between requests
        
        # File paths
        self.status_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.data")
        self.logs_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.logs")
        self.queue_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.queue")
        self.visited_file = os.path.join(DATA_DIR, "visited_urls.data")
        
        # Resume from existing files if requested (before SSL setup to avoid overwriting logs)
        if self.resume_from_files:
            self._resume_from_files()
        
        # SSL context configurations (after resume to avoid overwriting logs)
        self._setup_ssl_contexts()
        
        # Initialize status file for new crawler (if not resuming)
        if not self.resume_from_files:
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
    
    def _resume_from_files(self):
        """Resume crawler from existing files (queue, logs, status)"""
        try:
            # Load existing logs
            if os.path.exists(self.logs_file):
                with open(self.logs_file, 'r') as f:
                    existing_logs = [line.strip() for line in f.readlines() if line.strip()]
                    # Add existing logs to current logs list
                    self.logs.extend(existing_logs)
                self._log(f"Loaded {len(existing_logs)} existing log entries")
            
            # Load existing queue
            if os.path.exists(self.queue_file):
                with open(self.queue_file, 'r') as f:
                    queue_count = 0
                    for line in f:
                        line = line.strip()
                        if line:
                            # Parse space-separated format: URL DEPTH
                            parts = line.rsplit(' ', 1)  # Split only on last space
                            if len(parts) == 2:
                                url, depth_str = parts
                                try:
                                    depth = int(depth_str)
                                    self.url_queue.put((url, depth))
                                    queue_count += 1
                                except (ValueError, queue.Full):
                                    continue
                self._log(f"Loaded {queue_count} URLs from existing queue")
            
            # Load visited URLs to avoid re-crawling
            self._load_visited_urls()
            
            # Load existing timestamps from status file if available
            if os.path.exists(self.status_file):
                try:
                    with open(self.status_file, 'r') as f:
                        status_data = json.load(f)
                        # Preserve original creation time
                        if 'created_at' in status_data:
                            self.created_at = status_data['created_at']
                        elif 'timestamp' in status_data:
                            # Backward compatibility for old timestamp format
                            self.created_at = status_data['timestamp']
                        # Reset completed_at since we're resuming
                        self.completed_at = None
                except Exception as e:
                    self._log(f"Could not load existing timestamps: {e}")
            
            # Reset status to Active
            self.status = "Active"
            self._log("Resumed crawler from existing files")
            self._update_status_file()
            
        except Exception as e:
            self._log(f"Error resuming from files: {e}")
            # Fall back to normal initialization
            self._update_status_file()
    
    def _log(self, message):
        """Add log entry with timestamp"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - {message}"
        self.logs.append(log_entry)
        print(f"[{self.crawler_id}] {log_entry}")  # Also print to console
        self._update_logs_file()
        self._update_status_file()
    
    def pause(self):
        """Pause the crawler"""
        self._pause_event.clear()
        self.status = "Paused"
        self._log("Crawler paused")
        self._update_status_file()
    
    def resume(self):
        """Resume the crawler"""
        self._pause_event.set()
        self.status = "Active"
        self._log("Crawler resumed")
        self._update_status_file()
    
    def stop(self):
        """Stop the crawler"""
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        self.status = "Interrupted"
        self._log("Crawler stop requested")
        self._update_status_file()
    
    def is_paused(self):
        """Check if the crawler is paused"""
        return not self._pause_event.is_set()
    
    def is_stopped(self):
        """Check if the crawler should stop"""
        return self._stop_event.is_set()
    
    def _update_logs_file(self):
        """Update the crawler logs file"""
        try:
            with open(self.logs_file, 'w') as f:
                for log_entry in self.logs:
                    f.write(f"{log_entry}\n")
        except Exception as e:
            # Only print error if not in testing environment
            if not hasattr(self, '_suppress_file_errors'):
                print(f"Error updating logs file: {e}")
    
    def _update_queue_file(self):
        """Update the crawler queue file"""
        try:
            # Get current queue contents (safely)
            queue_list = []
            temp_queue = queue.Queue()
            
            # Drain queue to get contents
            while not self.url_queue.empty():
                try:
                    item = self.url_queue.get_nowait()
                    queue_list.append(f"{item[0]} {item[1]}")  # Space-separated URL and depth
                    temp_queue.put(item)
                except queue.Empty:
                    break
            
            # Restore queue
            while not temp_queue.empty():
                self.url_queue.put(temp_queue.get_nowait())
            
            with open(self.queue_file, 'w') as f:
                for queue_item in queue_list:
                    f.write(f"{queue_item}\n")
        except Exception as e:
            # Only print error if not in testing environment
            if not hasattr(self, '_suppress_file_errors'):
                print(f"Error updating queue file: {e}")
    
    def _update_status_file(self):
        """Update the crawler status file (main data only)"""
        try:
            status_data = {
                "crawler_id": self.crawler_id,
                "status": self.status,
                "origin": self.origin,
                "max_depth": self.max_depth,
                "hit_rate": self.hit_rate,
                "max_queue_capacity": self.max_queue_capacity,
                "max_urls_to_visit": self.max_urls_to_visit,
                "visited_count": self.urls_visited_this_session,
                "created_at": self.created_at,
                "updated_at": time.time()
            }
            
            # Add completed_at if crawler is finished
            if self.completed_at is not None:
                status_data["completed_at"] = self.completed_at
            
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            # Only print error if not in testing environment
            if not hasattr(self, '_suppress_file_errors'):
                print(f"Error updating status file: {e}")
    
    def _load_visited_urls(self):
        """Load global visited URLs from file"""
        try:
            if os.path.exists(self.visited_file):
                with open(self.visited_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Space-separated format: URL CRAWLER_ID DATETIME
                            parts = line.split()
                            if len(parts) >= 3:
                                url = parts[0]
                                if url.startswith(('http://', 'https://')):
                                    self.visited_urls.add(url)
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
            self.urls_visited_this_session += 1
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
        """Store words by their initial letter in alphabet files using space-separated format"""
        try:
            for word, frequency in word_freq.items():
                if len(word) >= 2:  # Only store words with 2+ characters
                    first_letter = word[0].lower()
                    
                    # Handle non-alphabetic first characters
                    if not first_letter.isalpha():
                        first_letter = 'other'
                    
                    filename = os.path.join(STORAGE_DIR, f"{first_letter}.data")
                    
                    # Read existing entries
                    entries = []
                    if os.path.exists(filename):
                        try:
                            with open(filename, 'r') as f:
                                for line in f:
                                    line = line.strip()
                                    if line:
                                        entries.append(line)
                        except Exception:
                            entries = []
                    
                    # Add new entry in space-separated format: word relevant_url origin_url depth frequency
                    new_entry = f"{word} {url} {self.origin} {depth} {frequency}"
                    entries.append(new_entry)
                    
                    # Sort entries: first by word, then by frequency (descending) within the word
                    def sort_key(entry_line):
                        parts = entry_line.split(' ', 4)  # Split into 5 parts max
                        if len(parts) >= 5:
                            entry_word = parts[0]
                            entry_frequency = int(parts[4])
                            return (entry_word, -entry_frequency)  # Negative for descending frequency
                        return (entry_line, 0)
                    
                    entries.sort(key=sort_key)
                    
                    # Write sorted entries back to file
                    with open(filename, 'w') as f:
                        for entry in entries:
                            f.write(f"{entry}\n")
            
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
                    'User-Agent': 'Mozilla/5.0 (compatible; GenericCrawler/1.0)'
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
            self._update_queue_file()
            
            while not self.url_queue.empty() and not self.is_stopped():
                # Check for pause
                self._pause_event.wait()  # Block if paused
                
                # Check if stopped while paused
                if self.is_stopped():
                    break
                
                try:
                    url, depth = self.url_queue.get(timeout=1)
                    
                    # Update queue file immediately after removing URL from queue
                    self._update_queue_file()
                    
                    # Check if we've exceeded max depth
                    if depth > self.max_depth:
                        continue
                    
                    # Crawl the URL
                    new_urls = self._crawl_url(url, depth)
                    
                    # Check if we've reached the maximum number of URLs to visit
                    if self.max_urls_to_visit > 0 and self.urls_visited_this_session >= self.max_urls_to_visit:
                        self._log(f"Reached maximum URL limit ({self.max_urls_to_visit}). Stopping crawler.")
                        break
                    
                    # Add new URLs to queue for next depth level
                    if depth < self.max_depth and not self.is_stopped():
                        urls_added = False
                        for new_url in new_urls:
                            try:
                                self.url_queue.put((new_url, depth + 1), timeout=1)
                                urls_added = True
                            except queue.Full:
                                self._log("Queue full, pausing URL discovery")
                                break
                        
                        # Update queue file again if new URLs were added
                        if urls_added:
                            self._update_queue_file()
                    
                except queue.Empty:
                    # No more URLs to process
                    break
                except Exception as e:
                    self._log(f"Error in crawler loop: {e}")
                    self.status = "Interrupted"
                    self._update_status_file()
                    return
            
            # Check if stopped or naturally completed
            if self.is_stopped():
                self.status = "Interrupted"
                self.completed_at = time.time()
                self._log("Crawler stopped by user request")
            else:
                self.status = "Finished"
                self.completed_at = time.time()
                self._log("Crawler completed successfully")
            # Final queue file update
            self._update_queue_file()
            
        except Exception as e:
            self.status = "Interrupted"
            self.completed_at = time.time()
            self._log(f"Crawler interrupted: {e}")
        finally:
            # Ensure that if the thread is closing and status wasn't set to Finished,
            # mark it as Interrupted (handles forced termination cases)
            if self.status != "Finished":
                self.status = "Interrupted"
                if self.completed_at is None:
                    self.completed_at = time.time()
                self._log("Crawler thread closing - marked as Interrupted")
            self._update_status_file()
