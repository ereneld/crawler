import unittest
import sys
import os

# Add the parent directory to sys.path to import utils modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.html_parser import HTMLParser, parse_html_content


class TestHTMLParser(unittest.TestCase):
    """Test cases for HTMLParser class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.parser = HTMLParser()
    
    def tearDown(self):
        """Clean up after each test method"""
        self.parser = None
    
    def test_init(self):
        """Test HTMLParser initialization"""
        self.assertEqual(self.parser.links, [])
        self.assertEqual(self.parser.text_content, [])
        self.assertEqual(self.parser.in_script_style, False)
    
    def test_extract_simple_text(self):
        """Test extracting simple text content"""
        html = "<p>Hello world</p>"
        self.parser.feed(html)
        
        text = self.parser.get_text()
        self.assertEqual(text, "Hello world")
    
    def test_extract_multiple_text_elements(self):
        """Test extracting text from multiple elements"""
        html = "<h1>Title</h1><p>Paragraph 1</p><p>Paragraph 2</p>"
        self.parser.feed(html)
        
        text = self.parser.get_text()
        self.assertEqual(text, "Title Paragraph 1 Paragraph 2")
    
    def test_ignore_script_content(self):
        """Test that script content is ignored"""
        html = "<p>Before script</p><script>alert('hello');</script><p>After script</p>"
        self.parser.feed(html)
        
        text = self.parser.get_text()
        self.assertEqual(text, "Before script After script")
    
    def test_ignore_style_content(self):
        """Test that style content is ignored"""
        html = "<p>Before style</p><style>body { color: red; }</style><p>After style</p>"
        self.parser.feed(html)
        
        text = self.parser.get_text()
        self.assertEqual(text, "Before style After style")
    
    def test_extract_simple_link(self):
        """Test extracting a simple link"""
        html = '<a href="https://example.com">Link text</a>'
        self.parser.feed(html)
        
        links = self.parser.get_links()
        self.assertEqual(links, ["https://example.com"])
    
    def test_extract_multiple_links(self):
        """Test extracting multiple links"""
        html = '''
        <a href="https://example.com">Link 1</a>
        <a href="/relative/path">Link 2</a>
        <a href="https://another-site.com">Link 3</a>
        '''
        self.parser.feed(html)
        
        links = self.parser.get_links()
        expected = ["https://example.com", "/relative/path", "https://another-site.com"]
        self.assertEqual(links, expected)
    
    def test_ignore_empty_href(self):
        """Test that empty href attributes are ignored"""
        html = '<a href="">Empty link</a><a href="https://example.com">Valid link</a>'
        self.parser.feed(html)
        
        links = self.parser.get_links()
        self.assertEqual(links, ["https://example.com"])
    
    def test_ignore_missing_href(self):
        """Test that links without href are ignored"""
        html = '<a>No href link</a><a href="https://example.com">Valid link</a>'
        self.parser.feed(html)
        
        links = self.parser.get_links()
        self.assertEqual(links, ["https://example.com"])
    
    def test_case_insensitive_tags(self):
        """Test that tag parsing is case insensitive"""
        html = '<A HREF="https://example.com">UPPERCASE</A><SCRIPT>ignore this</SCRIPT>'
        self.parser.feed(html)
        
        links = self.parser.get_links()
        text = self.parser.get_text()
        
        self.assertEqual(links, ["https://example.com"])
        self.assertEqual(text, "UPPERCASE")
    
    def test_nested_script_style_handling(self):
        """Test handling of nested script/style tags"""
        html = '''
        <div>
            <p>Visible text</p>
            <script>
                var hidden = "this should not appear";
            </script>
            <style>
                .hidden { display: none; }
            </style>
            <p>More visible text</p>
        </div>
        '''
        self.parser.feed(html)
        
        text = self.parser.get_text()
        self.assertIn("Visible text", text)
        self.assertIn("More visible text", text)
        self.assertNotIn("hidden", text)
        self.assertNotIn("display: none", text)
    
    def test_reset_parser(self):
        """Test parser reset functionality"""
        html = '<a href="https://example.com">Link</a><p>Text</p>'
        self.parser.feed(html)
        
        # Verify data is collected
        self.assertEqual(len(self.parser.get_links()), 1)
        self.assertNotEqual(self.parser.get_text(), "")
        
        # Reset and verify clean state
        self.parser.reset()
        self.assertEqual(self.parser.links, [])
        self.assertEqual(self.parser.text_content, [])
        self.assertEqual(self.parser.in_script_style, False)
    
    def test_complex_html_document(self):
        """Test parsing a complex HTML document"""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Page</title>
            <style>body { margin: 0; }</style>
            <script>console.log("test");</script>
        </head>
        <body>
            <h1>Main Title</h1>
            <nav>
                <a href="/home">Home</a>
                <a href="/about">About</a>
            </nav>
            <main>
                <p>This is the main content.</p>
                <a href="https://external.com">External Link</a>
            </main>
        </body>
        </html>
        '''
        self.parser.feed(html)
        
        text = self.parser.get_text()
        links = self.parser.get_links()
        
        # Check text extraction
        self.assertIn("Test Page", text)
        self.assertIn("Main Title", text)
        self.assertIn("Home", text)
        self.assertIn("About", text)
        self.assertIn("This is the main content", text)
        self.assertIn("External Link", text)
        
        # Check that script/style content is excluded
        self.assertNotIn("margin: 0", text)
        self.assertNotIn("console.log", text)
        
        # Check link extraction
        expected_links = ["/home", "/about", "https://external.com"]
        self.assertEqual(links, expected_links)


class TestParseHTMLContent(unittest.TestCase):
    """Test cases for parse_html_content function"""
    
    def test_parse_simple_content(self):
        """Test parsing simple HTML content"""
        html = '<p>Hello world</p><a href="/test">Test link</a>'
        base_url = "https://example.com"
        
        text, urls = parse_html_content(html, base_url)
        
        self.assertEqual(text, "Hello world Test link")
        self.assertEqual(urls, ["https://example.com/test"])
    
    def test_relative_url_resolution(self):
        """Test that relative URLs are properly resolved"""
        html = '''
        <a href="/path1">Link 1</a>
        <a href="path2">Link 2</a>
        <a href="../path3">Link 3</a>
        <a href="./path4">Link 4</a>
        '''
        base_url = "https://example.com/folder/"
        
        text, urls = parse_html_content(html, base_url)
        
        expected_urls = [
            "https://example.com/path1",
            "https://example.com/folder/path2", 
            "https://example.com/path3",
            "https://example.com/folder/path4"
        ]
        self.assertEqual(urls, expected_urls)
    
    def test_absolute_url_preservation(self):
        """Test that absolute URLs are preserved"""
        html = '''
        <a href="https://external.com">External</a>
        <a href="http://another.com">Another</a>
        <a href="/relative">Relative</a>
        '''
        base_url = "https://example.com"
        
        text, urls = parse_html_content(html, base_url)
        
        expected_urls = [
            "https://external.com",
            "http://another.com", 
            "https://example.com/relative"
        ]
        self.assertEqual(urls, expected_urls)
    
    def test_filter_non_http_urls(self):
        """Test that non-HTTP(S) URLs are filtered out"""
        html = '''
        <a href="https://valid.com">HTTPS</a>
        <a href="http://valid.com">HTTP</a>
        <a href="ftp://invalid.com">FTP</a>
        <a href="mailto:test@example.com">Email</a>
        <a href="javascript:alert('test')">JavaScript</a>
        <a href="tel:+1234567890">Phone</a>
        '''
        base_url = "https://example.com"
        
        text, urls = parse_html_content(html, base_url)
        
        # Only HTTP and HTTPS URLs should be included
        expected_urls = [
            "https://valid.com",
            "http://valid.com"
        ]
        self.assertEqual(urls, expected_urls)
    
    def test_empty_html_content(self):
        """Test parsing empty HTML content"""
        html = ""
        base_url = "https://example.com"
        
        text, urls = parse_html_content(html, base_url)
        
        self.assertEqual(text, "")
        self.assertEqual(urls, [])
    
    def test_html_with_no_links(self):
        """Test HTML content with no links"""
        html = "<h1>Title</h1><p>Just some text content here.</p>"
        base_url = "https://example.com"
        
        text, urls = parse_html_content(html, base_url)
        
        self.assertEqual(text, "Title Just some text content here.")
        self.assertEqual(urls, [])
    
    def test_html_with_no_text(self):
        """Test HTML content with only links, no text"""
        html = '<a href="/link1"></a><a href="/link2"></a>'
        base_url = "https://example.com"
        
        text, urls = parse_html_content(html, base_url)
        
        self.assertEqual(text, "")  # Empty link text results in empty string
        expected_urls = [
            "https://example.com/link1",
            "https://example.com/link2"
        ]
        self.assertEqual(urls, expected_urls)
    
    def test_malformed_html(self):
        """Test parsing malformed HTML"""
        html = '<p>Unclosed paragraph<a href="/test">Link without closing tag<div>Mixed content'
        base_url = "https://example.com"
        
        # Should not raise an exception
        text, urls = parse_html_content(html, base_url)
        
        self.assertIn("Unclosed paragraph", text)
        self.assertIn("Link without closing tag", text)
        self.assertIn("Mixed content", text)
        self.assertEqual(urls, ["https://example.com/test"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
