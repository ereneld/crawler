import html.parser
import urllib.parse

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
        """Get cleaned text content"""
        return ' '.join(self.text_content)
    
    def get_links(self):
        """Get extracted links"""
        return self.links
    
    def reset(self):
        """Reset parser for reuse"""
        super().reset()
        self.links = []
        self.text_content = []
        self.in_script_style = False

def parse_html_content(html_content, base_url):
    """
    Parse HTML content and extract text and absolute URLs
    
    Args:
        html_content (str): HTML content to parse
        base_url (str): Base URL for resolving relative links
        
    Returns:
        tuple: (cleaned_text, absolute_urls)
    """
    parser = HTMLParser()
    parser.feed(html_content)
    
    # Get cleaned text
    text = parser.get_text()
    
    # Process links to make them absolute
    absolute_urls = []
    for link in parser.get_links():
        # Convert relative URLs to absolute
        full_url = urllib.parse.urljoin(base_url, link)
        
        # Only include HTTP/HTTPS URLs
        if full_url.startswith(('http://', 'https://')):
            absolute_urls.append(full_url)
    
    return text, absolute_urls
