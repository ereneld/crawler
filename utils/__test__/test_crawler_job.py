import unittest
import tempfile
import shutil
import os
import sys
import time
import json
import threading
from unittest.mock import patch, mock_open, MagicMock

# Add the parent directory to sys.path to import utils modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.crawler_job import CrawlerJob


class TestCrawlerJob(unittest.TestCase):
    """Test cases for CrawlerJob class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        # Create temporary directories for testing
        self.test_data_dir = tempfile.mkdtemp()
        self.test_storage_dir = os.path.join(self.test_data_dir, "storage")
        self.test_crawler_dir = os.path.join(self.test_data_dir, "crawlers")
        
        os.makedirs(self.test_storage_dir, exist_ok=True)
        os.makedirs(self.test_crawler_dir, exist_ok=True)
        
        # Patch the directory constants
        self.data_dir_patcher = patch('utils.crawler_job.DATA_DIR', self.test_data_dir)
        self.storage_dir_patcher = patch('utils.crawler_job.STORAGE_DIR', self.test_storage_dir)
        self.crawler_dir_patcher = patch('utils.crawler_job.CRAWLER_DIR', self.test_crawler_dir)
        
        self.data_dir_patcher.start()
        self.storage_dir_patcher.start()
        self.crawler_dir_patcher.start()
        
        # Default test parameters
        self.crawler_id = "test_123_456"
        self.origin = "https://example.com"
        self.max_depth = 2
        self.hit_rate = 1.0
        self.max_queue_capacity = 100
        self.max_urls_to_visit = 10
    
    def tearDown(self):
        """Clean up after each test method"""
        # Stop patchers
        self.data_dir_patcher.stop()
        self.storage_dir_patcher.stop()
        self.crawler_dir_patcher.stop()
        
        # Remove temporary directory
        shutil.rmtree(self.test_data_dir, ignore_errors=True)
    
    def create_crawler(self, resume_from_files=False):
        """Helper method to create a CrawlerJob instance"""
        return CrawlerJob(
            crawler_id=self.crawler_id,
            origin=self.origin,
            max_depth=self.max_depth,
            hit_rate=self.hit_rate,
            max_queue_capacity=self.max_queue_capacity,
            max_urls_to_visit=self.max_urls_to_visit,
            resume_from_files=resume_from_files
        )
    
    def test_init_basic_properties(self):
        """Test basic initialization of CrawlerJob"""
        crawler = self.create_crawler()
        
        self.assertEqual(crawler.crawler_id, self.crawler_id)
        self.assertEqual(crawler.origin, self.origin)
        self.assertEqual(crawler.max_depth, self.max_depth)
        self.assertEqual(crawler.hit_rate, self.hit_rate)
        self.assertEqual(crawler.max_queue_capacity, self.max_queue_capacity)
        self.assertEqual(crawler.max_urls_to_visit, self.max_urls_to_visit)
        self.assertFalse(crawler.resume_from_files)
        
        # Check default state
        self.assertEqual(crawler.status, "Active")
        self.assertGreaterEqual(len(crawler.logs), 1)  # At least SSL setup log
        self.assertEqual(crawler.visited_urls, set())
        self.assertEqual(crawler.urls_visited_this_session, 0)
        
        # Check threading events
        self.assertTrue(crawler._pause_event.is_set())  # Should start unpaused
        self.assertFalse(crawler._stop_event.is_set())  # Should start not stopped
        
        # Check timestamps
        self.assertIsNotNone(crawler.created_at)
        self.assertIsNone(crawler.completed_at)
        
        # Check file paths
        expected_status_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.data")
        expected_logs_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.logs")
        expected_queue_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.queue")
        
        self.assertEqual(crawler.status_file, expected_status_file)
        self.assertEqual(crawler.logs_file, expected_logs_file)
        self.assertEqual(crawler.queue_file, expected_queue_file)
    
    def test_pause_resume_functionality(self):
        """Test pause and resume functionality"""
        crawler = self.create_crawler()
        
        # Initially should not be paused
        self.assertFalse(crawler.is_paused())
        
        # Test pause
        crawler.pause()
        self.assertTrue(crawler.is_paused())
        
        # Test resume
        crawler.resume()
        self.assertFalse(crawler.is_paused())
    
    def test_stop_functionality(self):
        """Test stop functionality"""
        crawler = self.create_crawler()
        
        # Initially should not be stopped
        self.assertFalse(crawler.is_stopped())
        
        # Test stop
        crawler.stop()
        self.assertTrue(crawler.is_stopped())
    
    def test_logging_functionality(self):
        """Test logging functionality"""
        crawler = self.create_crawler()
        
        # Test logging a message
        test_message = "Test log message"
        initial_log_count = len(crawler.logs)
        crawler._log(test_message)
        
        # Check that message was added to logs
        self.assertEqual(len(crawler.logs), initial_log_count + 1)
        self.assertIn(test_message, crawler.logs[-1])
        
        # Test multiple log messages
        crawler._log("Second message")
        self.assertEqual(len(crawler.logs), initial_log_count + 2)
    
    @patch('urllib.request.urlopen')
    def test_crawl_url_success(self, mock_urlopen):
        """Test successful URL crawling"""
        crawler = self.create_crawler()
        
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.read.return_value = b'<html><body><h1>Test Page</h1><a href="/test">Test Link</a></body></html>'
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Test crawling
        new_urls = crawler._crawl_url("https://example.com", 0)
        
        # Should return one URL
        self.assertEqual(len(new_urls), 1)
        self.assertIn("https://example.com/test", new_urls)
    
    @patch('urllib.request.urlopen')
    def test_crawl_url_http_error(self, mock_urlopen):
        """Test URL crawling with HTTP error"""
        crawler = self.create_crawler()
        
        # Mock HTTP error
        from urllib.error import HTTPError
        mock_urlopen.side_effect = HTTPError(
            url="https://example.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=None
        )
        
        # Test crawling - should handle error gracefully
        new_urls = crawler._crawl_url("https://example.com", 0)
        
        # Should return empty list on error
        self.assertEqual(new_urls, [])
        
        # Should log the error
        self.assertTrue(any("404" in log for log in crawler.logs))
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        crawler = self.create_crawler()
        crawler.hit_rate = 10.0  # 10 requests per second
        crawler.request_interval = 1.0 / crawler.hit_rate  # 0.1 seconds
        
        # First call should not wait
        start_time = time.time()
        crawler._rate_limit()
        first_call_time = time.time() - start_time
        
        # Should be very fast (no waiting)
        self.assertLess(first_call_time, 0.01)
        
        # Set last request time to now
        crawler.last_request_time = time.time()
        
        # Second immediate call should wait
        start_time = time.time()
        crawler._rate_limit()
        second_call_time = time.time() - start_time
        
        # Should wait approximately the request interval
        self.assertGreater(second_call_time, 0.05)  # At least half the interval
    
    def test_save_visited_url(self):
        """Test saving visited URL to file"""
        crawler = self.create_crawler()
        
        test_url = "https://example.com/page1"
        crawler._save_visited_url(test_url)
        
        # Check that URL was added to visited set
        self.assertIn(test_url, crawler.visited_urls)
        
        # Check that session counter was incremented
        self.assertEqual(crawler.urls_visited_this_session, 1)
        
        # Check that file was created
        visited_file = os.path.join(self.test_data_dir, "visited_urls.data")
        self.assertTrue(os.path.exists(visited_file))
        
        # Check file content
        with open(visited_file, 'r') as f:
            content = f.read()
            self.assertIn(test_url, content)
            self.assertIn(self.crawler_id, content)
    
    def test_load_visited_urls_empty_file(self):
        """Test loading visited URLs when file doesn't exist"""
        crawler = self.create_crawler()
        
        # Should handle missing file gracefully
        crawler._load_visited_urls()
        
        # Should start with empty set
        self.assertEqual(len(crawler.visited_urls), 0)
    
    def test_load_visited_urls_existing_file(self):
        """Test loading visited URLs from existing file"""
        # Create a visited URLs file with test data
        visited_file = os.path.join(self.test_data_dir, "visited_urls.data")
        test_content = "https://example.com/page1 test_crawler_1 1234567890\nhttps://example.com/page2 test_crawler_2 1234567891\n"
        
        with open(visited_file, 'w') as f:
            f.write(test_content)
        
        crawler = self.create_crawler()
        crawler._load_visited_urls()
        
        # Should load URLs into visited set
        self.assertEqual(len(crawler.visited_urls), 2)
        self.assertIn("https://example.com/page1", crawler.visited_urls)
        self.assertIn("https://example.com/page2", crawler.visited_urls)
    
    def test_store_words(self):
        """Test storing word frequencies"""
        crawler = self.create_crawler()
        
        # Test word frequencies
        word_freq = {"test": 3, "example": 2, "word": 1}
        test_url = "https://example.com/page"
        test_depth = 1
        
        crawler._store_words(word_freq, test_url, test_depth)
        
        # Check that files were created for each letter
        test_file = os.path.join(self.test_storage_dir, "t.data")
        example_file = os.path.join(self.test_storage_dir, "e.data")
        word_file = os.path.join(self.test_storage_dir, "w.data")
        
        self.assertTrue(os.path.exists(test_file))
        self.assertTrue(os.path.exists(example_file))
        self.assertTrue(os.path.exists(word_file))
        
        # Check content of one file
        with open(test_file, 'r') as f:
            content = f.read()
            self.assertIn("test", content)
            self.assertIn(test_url, content)
            self.assertIn(self.origin, content)
            self.assertIn(str(test_depth), content)
            self.assertIn("3", content)  # frequency
    
    def test_update_status_file(self):
        """Test updating status file"""
        crawler = self.create_crawler()
        
        # Update status
        crawler._update_status_file()
        
        # Check that status file was created
        status_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.data")
        self.assertTrue(os.path.exists(status_file))
        
        # Check file content
        with open(status_file, 'r') as f:
            data = json.load(f)
            self.assertEqual(data["crawler_id"], self.crawler_id)
            self.assertEqual(data["status"], "Active")
            self.assertEqual(data["origin"], self.origin)
            self.assertEqual(data["max_depth"], self.max_depth)
            self.assertEqual(data["hit_rate"], self.hit_rate)
            self.assertEqual(data["max_queue_capacity"], self.max_queue_capacity)
            self.assertEqual(data["max_urls_to_visit"], self.max_urls_to_visit)
            self.assertIn("created_at", data)
            self.assertIn("updated_at", data)
    
    def test_update_logs_file(self):
        """Test updating logs file"""
        crawler = self.create_crawler()
        
        # Add some logs
        crawler.logs = ["Log message 1", "Log message 2"]
        crawler._update_logs_file()
        
        # Check that logs file was created
        logs_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.logs")
        self.assertTrue(os.path.exists(logs_file))
        
        # Check file content
        with open(logs_file, 'r') as f:
            content = f.read()
            self.assertIn("Log message 1", content)
            self.assertIn("Log message 2", content)
    
    def test_update_queue_file(self):
        """Test updating queue file"""
        crawler = self.create_crawler()
        
        # Add items to queue
        crawler.url_queue.put(("https://example.com/page1", 1))
        crawler.url_queue.put(("https://example.com/page2", 2))
        
        crawler._update_queue_file()
        
        # Check that queue file was created
        queue_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.queue")
        self.assertTrue(os.path.exists(queue_file))
        
        # Check file content
        with open(queue_file, 'r') as f:
            content = f.read()
            self.assertIn("https://example.com/page1 1", content)
            self.assertIn("https://example.com/page2 2", content)
    
    def test_extract_text_and_urls(self):
        """Test text and URL extraction from HTML"""
        crawler = self.create_crawler()
        
        html_content = '''
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is test content with some words.</p>
            <a href="/page1">Link 1</a>
            <a href="https://external.com">External</a>
            <script>console.log("ignore this");</script>
        </body>
        </html>
        '''
        base_url = "https://example.com"
        
        word_freq, urls = crawler._extract_text_and_urls(html_content, base_url)
        
        # Check word frequencies
        self.assertIsInstance(word_freq, dict)
        self.assertIn("test", word_freq)
        self.assertIn("content", word_freq)
        self.assertIn("title", word_freq)
        
        # Check URLs
        self.assertIn("https://example.com/page1", urls)
        self.assertIn("https://external.com", urls)
        
        # Verify script content was ignored
        self.assertNotIn("console", word_freq)
        self.assertNotIn("log", word_freq)
    
    def test_resume_from_files_missing_files(self):
        """Test resuming from files when files don't exist"""
        crawler = self.create_crawler(resume_from_files=True)
        
        # Should handle missing files gracefully and start fresh
        self.assertGreaterEqual(len(crawler.logs), 1)  # At least SSL setup log
        self.assertTrue(crawler.url_queue.empty())
    
    def test_resume_from_files_existing_files(self):
        """Test resuming from files when files exist"""
        # Create existing files
        status_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.data")
        logs_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.logs")
        queue_file = os.path.join(self.test_crawler_dir, f"{self.crawler_id}.queue")
        
        # Create status file
        status_data = {
            "crawler_id": self.crawler_id,
            "status": "Paused",
            "created_at": time.time() - 100,
            "updated_at": time.time() - 50
        }
        with open(status_file, 'w') as f:
            json.dump(status_data, f)
        
        # Create logs file - write entries as separate lines like the real system would
        with open(logs_file, 'w') as f:
            f.write("2025-01-01 10:00:00 - Previous log entry 1\n")
            f.write("2025-01-01 10:00:01 - Previous log entry 2\n")
            f.flush()  # Force write to disk
        
        # Create queue file
        with open(queue_file, 'w') as f:
            f.write("https://example.com/page1 1\nhttps://example.com/page2 2\n")
        
        # Create crawler with resume_from_files=True
        crawler = self.create_crawler(resume_from_files=True)
        
        # Check that data was loaded (plus SSL setup log and resume log)
        self.assertGreaterEqual(len(crawler.logs), 4)  # 2 previous + SSL + resume log
        log_messages = " ".join(crawler.logs)
        self.assertIn("Previous log entry 1", log_messages)
        self.assertIn("Previous log entry 2", log_messages)
        self.assertIn("SSL contexts configured", log_messages)
        self.assertIn("Loaded 2 existing log entries", log_messages)
        
        # Check that queue was loaded
        self.assertFalse(crawler.url_queue.empty())
        self.assertEqual(crawler.url_queue.qsize(), 2)
    
    def test_max_urls_limit(self):
        """Test that crawler respects max URLs limit"""
        crawler = self.create_crawler()
        crawler.max_urls_to_visit = 2  # Set low limit for testing
        
        # Simulate visiting URLs
        crawler._save_visited_url("https://example.com/page1")
        self.assertEqual(crawler.urls_visited_this_session, 1)
        self.assertFalse(crawler.urls_visited_this_session >= crawler.max_urls_to_visit)
        
        crawler._save_visited_url("https://example.com/page2")
        self.assertEqual(crawler.urls_visited_this_session, 2)
        self.assertTrue(crawler.urls_visited_this_session >= crawler.max_urls_to_visit)
    
    def test_ssl_context_setup(self):
        """Test SSL context setup"""
        crawler = self.create_crawler()
        
        # Check that SSL contexts were created (they may have different names)
        # We'll just check that the SSL setup log was created
        self.assertTrue(any("SSL contexts configured" in log for log in crawler.logs))


class TestCrawlerJobFileOperations(unittest.TestCase):
    """Test cases for CrawlerJob file operations with mocked file system"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.crawler_id = "test_789_012"
        self.origin = "https://test.com"
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    @patch('os.makedirs')
    def test_file_operations_with_errors(self, mock_makedirs, mock_exists, mock_file):
        """Test file operations when errors occur"""
        mock_exists.return_value = True
        
        crawler = CrawlerJob(
            crawler_id=self.crawler_id,
            origin=self.origin,
            max_depth=1,
            hit_rate=1.0,
            max_queue_capacity=10,
            max_urls_to_visit=5
        )
        
        # Suppress error printing for this test
        crawler._suppress_file_errors = True
        
        # Mock file write error
        mock_file.side_effect = IOError("Permission denied")
        
        # Should handle file errors gracefully
        try:
            crawler._update_status_file()
            crawler._update_logs_file()
            crawler._update_queue_file()
        except IOError:
            self.fail("File operations should handle errors gracefully")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
