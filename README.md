# 🕷️ Web Crawler

A comprehensive web crawling platform built with Python Flask, featuring real-time monitoring, intelligent search, and a responsive web interface.

## 🌟 Features

- **Multi-threaded Web Crawler** with configurable depth and rate limiting
- **Real-time Status Monitoring** with live updates and progress tracking
- **Advanced Search Engine** with relevance ranking and pagination
- **Responsive Web Interface** for crawler management and data exploration
- **File-based Storage** with organized data structure
- **Pause/Resume/Stop** functionality for active crawlers
- **Resume from Files** capability for interrupted crawlers
- **Comprehensive Unit Tests** (41 tests with verbose logging)
- **SSL Certificate Handling** for secure HTTPS crawling
- **Rate Limiting & Back-pressure** management
- **Download Capabilities** for logs and queue data

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- Web browser (Chrome, Firefox, Safari, Edge)

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/ereneld/crawler.git
   cd crawler
   ```

2. **Install dependencies:**
   ```bash
   pip3 install flask flask-cors
   ```

3. **Start the API server:**
   ```bash
   python3 app.py
   ```
   
   The server will start on `http://localhost:3600`

4. **Open the web interface:**
   
   Open any of these files in your web browser:
   - **Crawler Dashboard**: `demo/crawler.html`
   - **Status Monitoring**: `demo/status.html`  
   - **Search Interface**: `demo/search.html`

## 📖 Usage Guide

### Creating a Crawler

1. Open `demo/crawler.html` in your browser
2. Fill in the crawler parameters:
   - **Origin URL**: Starting point for crawling (e.g., `https://www.wikipedia.org/`)
   - **Max Depth**: How deep to crawl (1-1000)
   - **Hit Rate**: Requests per second (0.1-1000.0)
   - **Queue Capacity**: Maximum URLs in queue (100-100000)
   - **Max URLs to Visit**: Total URLs to crawl (0-10000)
3. Click "🕷️ Start Crawler"
4. Monitor progress in real-time

### Monitoring Crawlers

- **Real-time Updates**: Status page auto-refreshes every 2 seconds
- **Download Data**: Get logs and queue files as text downloads
- **Control Options**: Pause, resume, or stop active crawlers
- **Statistics**: View total URLs visited, words indexed, and active crawlers

### Searching Content

1. Wait for crawler to index some content
2. Open `demo/search.html`
3. Enter search terms and browse paginated results
4. Use "🍀 I'm Feeling Lucky" for random word discovery

## 🔧 API Endpoints

### Crawler Management

```bash
# Create a new crawler
POST /crawler/create
{
  "origin": "https://example.com",
  "max_depth": 3,
  "hit_rate": 1.0,
  "max_queue_capacity": 10000,
  "max_urls_to_visit": 100
}

# Get crawler status
GET /crawler/status/{crawler_id}

# Pause crawler
POST /crawler/pause/{crawler_id}

# Resume crawler
POST /crawler/resume/{crawler_id}

# Stop crawler
POST /crawler/stop/{crawler_id}

# Resume from saved files
POST /crawler/resume-from-files/{crawler_id}

# Get all crawlers
GET /crawler/list

# Get crawler statistics
GET /crawler/stats

# Clear all data
POST /crawler/clear
```

### Search

```bash
# Search indexed content
GET /search?query=python&pageLimit=10&pageOffset=0

# Get random word
GET /search/random
```

## 🧪 Testing

### Run Unit Tests

```bash
# Test HTML parser (21 tests)
python3 utils/__test__/test_html_parser.py

# Test crawler job (20 tests)
python3 utils/__test__/test_crawler_job.py

# Run all tests
python3 utils/__test__/test_html_parser.py && python3 utils/__test__/test_crawler_job.py
```

### API Testing with curl

```bash
# Create a test crawler
curl -X POST http://localhost:3600/crawler/create \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "https://www.wikipedia.org/",
    "max_depth": 2,
    "max_urls_to_visit": 50
  }'

# Check status (replace {id} with actual crawler ID)
curl http://localhost:3600/crawler/status/{id}

# Search for content
curl "http://localhost:3600/search?query=wikipedia&pageLimit=5"
```

## 📁 Project Structure

```
crawler/
├── app.py                      # 🚀 Main Flask API server
├── services/                   # 🏗️ Business logic layer
│   ├── crawler_service.py      #    Crawler management
│   └── search_service.py       #    Search functionality
├── utils/                      # 🛠️ Core utilities
│   ├── crawler_job.py          #    Multi-threaded crawler
│   ├── html_parser.py          #    HTML parsing
│   └── __test__/               #    Unit tests (41 tests)
├── demo/                       # 🎨 Web interface
│   ├── crawler.html            #    Main dashboard
│   ├── status.html             #    Status monitoring
│   ├── search.html             #    Search interface
│   ├── css/style.css           #    Styling
│   └── js/                     #    Frontend JavaScript
├── data/                       # 💾 Storage (auto-created)
│   ├── visited_urls.data       #    Global visited URLs
│   ├── crawlers/               #    Crawler status files
│   └── storage/                #    Word index files
└── README.md                   # 📖 This file
```

## ⚙️ Configuration

### Default Parameters

- **Port**: 3600
- **Hit Rate**: 1.0 requests/second
- **Max Depth**: 1-1000
- **Queue Capacity**: 100-100000
- **Max URLs to Visit**: 0-10000

### Environment Variables

```bash
# Optional: Set custom port
export FLASK_PORT=3600

# Optional: Enable debug mode
export FLASK_ENV=development
```

## 🔍 How It Works

### Crawler Architecture

1. **Multi-threaded Design**: Each crawler runs in its own thread
2. **Queue Management**: URLs are queued with depth tracking
3. **Rate Limiting**: Configurable requests per second
4. **Back-pressure**: Queue capacity limits prevent memory issues
5. **File Storage**: Status, logs, and queue stored separately

### Search System

1. **Word Indexing**: Content is tokenized and stored by first letter
2. **Relevance Scoring**: Combines frequency, depth, and match quality
3. **Optimized Lookup**: Key-based search with progressive suffix matching
4. **Pagination**: Results are paginated for better performance

### Storage Format

- **Visited URLs**: `{url} {crawler_id} {timestamp}`
- **Word Index**: `{word} {relevant_url} {origin_url} {depth} {frequency}`
- **Crawler Status**: JSON with metadata and timestamps
- **Logs**: Timestamped log entries
- **Queue**: `{url} {depth}` space-separated

## 🛠️ Development

### Adding New Features

1. **Backend**: Extend services in `services/` directory
2. **API**: Add endpoints in `app.py`
3. **Frontend**: Modify HTML/CSS/JS in `demo/` directory
4. **Tests**: Add tests in `utils/__test__/`

### Code Style

- **Python**: Follow PEP 8 guidelines
- **JavaScript**: Use modern ES6+ features
- **HTML/CSS**: Responsive, accessible design
- **Documentation**: Comprehensive docstrings and comments

## 🚨 Troubleshooting

### Common Issues

**Port already in use:**
```bash
lsof -i :3600
kill -9 {PID}
```

**Permission errors:**
```bash
chmod -R 755 data/
```

**SSL certificate issues:**
- The crawler handles SSL issues automatically with fallback

**Memory usage:**
- Adjust `max_queue_capacity` and `max_urls_to_visit` for large crawls

### Debug Mode

```bash
# Enable verbose logging
FLASK_ENV=development python3 app.py

# Monitor data files
watch -n 2 'ls -la data/crawlers/ && echo "=== Storage ===" && ls -la data/storage/'
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit: `git commit -m 'Add amazing feature'`
5. Push: `git push origin feature/amazing-feature`
6. Open a Pull Request

### Testing Guidelines

- Write unit tests for new functionality
- Ensure all existing tests pass
- Test both success and error cases
- Use mocking for external dependencies

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for technical assessment
- Uses native Python libraries for core functionality
- Responsive design inspired by modern web standards
- Test coverage ensures reliability and maintainability

## 📞 Support

For questions or issues:
1. Check the [Issues](https://github.com/ereneld/crawler/issues) page
2. Create a new issue with detailed description
3. Include system info, error messages, and steps to reproduce

---

**Happy Crawling! 🕷️**
