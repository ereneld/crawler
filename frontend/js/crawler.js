// Crawler functionality
const API_BASE = 'http://localhost:5000';

class CrawlerApp {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadRecentCrawlers();
    }

    bindEvents() {
        // Crawler form submission
        document.getElementById('crawlerForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createCrawler();
        });
    }

    async createCrawler() {
        const formData = {
            origin: document.getElementById('origin').value.trim(),
            max_depth: parseInt(document.getElementById('maxDepth').value),
            hit_rate: parseFloat(document.getElementById('hitRate').value) || 100,
            max_queue_capacity: parseInt(document.getElementById('queueCapacity').value) || 10000
        };

        // Validate required fields
        if (!formData.origin) {
            this.showError('Origin URL is required');
            return;
        }

        if (!formData.max_depth || formData.max_depth < 1 || formData.max_depth > 1000) {
            this.showError('Max depth must be between 1 and 1000');
            return;
        }

        this.showLoading(true);
        this.hideMessages();
        this.disableForm(true);

        try {
            const response = await fetch(`${API_BASE}/crawler/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.showSuccess(`
                🎉 Crawler created successfully!<br>
                <strong>Crawler ID:</strong> ${data.crawler_id}<br>
                <strong>Status:</strong> ${data.status}<br>
                <a href="status.html?id=${data.crawler_id}" class="btn btn-primary" style="margin-top: 1rem; display: inline-block;">
                    📊 View Status
                </a>
            `);

            // Reset form
            document.getElementById('crawlerForm').reset();
            document.getElementById('maxDepth').value = 3;
            document.getElementById('hitRate').value = 100;
            document.getElementById('queueCapacity').value = 10000;

            // Refresh recent crawlers list
            setTimeout(() => {
                this.loadRecentCrawlers();
            }, 1000);

        } catch (error) {
            console.error('Crawler creation error:', error);
            this.showError(`Failed to create crawler: ${error.message}`);
        } finally {
            this.showLoading(false);
            this.disableForm(false);
        }
    }

    async loadRecentCrawlers() {
        const container = document.getElementById('recentCrawlers');

        try {
            const response = await fetch(`${API_BASE}/crawler/list`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.displayRecentCrawlers(container, data);

        } catch (error) {
            console.error('Error loading crawlers:', error);
            container.innerHTML = `
                <div class="error">
                    Failed to load recent crawlers: ${error.message}
                </div>
            `;
        }
    }

    displayRecentCrawlers(container, data) {
        if (!data.crawlers || data.crawlers.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: #5f6368;">
                    <p>No crawlers found. Create your first crawler above!</p>
                </div>
            `;
            return;
        }

        const crawlersHTML = data.crawlers.map(crawler => {
            const statusClass = this.getStatusClass(crawler.status);
            const timestamp = new Date(crawler.timestamp * 1000).toLocaleString();
            
            return `
                <div class="result-item">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                        <div>
                            <a href="status.html?id=${crawler.crawler_id}" class="result-url">
                                🕷️ ${crawler.crawler_id}
                            </a>
                            <span class="status-badge ${statusClass}" style="margin-left: 1rem;">
                                ${crawler.status}
                            </span>
                        </div>
                        <small style="color: #5f6368;">${timestamp}</small>
                    </div>
                    <div class="result-meta">
                        <strong>Origin:</strong> <a href="${crawler.origin}" target="_blank">${crawler.origin}</a><br>
                        <strong>URLs Visited:</strong> ${crawler.visited_count} | 
                        <strong>Created:</strong> ${timestamp}
                    </div>
                    <div style="margin-top: 1rem;">
                        <a href="status.html?id=${crawler.crawler_id}" class="btn">📊 View Status</a>
                        ${crawler.status === 'Active' ? `
                            <button class="btn" onclick="crawlerApp.stopCrawler('${crawler.crawler_id}')" style="margin-left: 0.5rem;">
                                🛑 Stop
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        container.innerHTML = `
            <div style="margin-bottom: 1rem; color: #5f6368;">
                Total: ${data.total_count} crawlers | Active: ${data.active_count}
            </div>
            ${crawlersHTML}
        `;
    }

    async stopCrawler(crawlerId) {
        if (!confirm('Are you sure you want to stop this crawler?')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/stop/${crawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler stop request: ${data.message}`);
            
            // Refresh the list
            this.loadRecentCrawlers();

        } catch (error) {
            console.error('Error stopping crawler:', error);
            alert(`Failed to stop crawler: ${error.message}`);
        }
    }

    getStatusClass(status) {
        switch (status) {
            case 'Active':
                return 'status-active';
            case 'Finished':
                return 'status-finished';
            case 'Interrupted':
                return 'status-interrupted';
            default:
                return '';
        }
    }

    showLoading(show) {
        document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
    }

    showSuccess(message) {
        const successDiv = document.getElementById('successMessage');
        successDiv.innerHTML = message;
        successDiv.style.display = 'block';
    }

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    hideMessages() {
        document.getElementById('successMessage').style.display = 'none';
        document.getElementById('errorMessage').style.display = 'none';
    }

    disableForm(disabled) {
        const form = document.getElementById('crawlerForm');
        const inputs = form.querySelectorAll('input, button');
        inputs.forEach(input => {
            input.disabled = disabled;
        });
    }
}

// Initialize the crawler app
const crawlerApp = new CrawlerApp();
