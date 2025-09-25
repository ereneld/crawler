// Crawler functionality
const API_BASE = 'http://localhost:3600';

class CrawlerApp {
    constructor() {
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadCrawlerStats();
        this.loadRecentCrawlers();
        
        // Refresh stats every 5 seconds
        setInterval(() => {
            this.loadCrawlerStats();
        }, 5000);
    }

    bindEvents() {
        // Crawler form submission
        document.getElementById('crawlerForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createCrawler();
        });

        // Clear data button
        document.getElementById('clearDataBtn').addEventListener('click', () => {
            this.clearAllData();
        });

        // Refresh stats button
        document.getElementById('refreshStatsBtn').addEventListener('click', () => {
            this.loadCrawlerStats();
        });
    }

    async createCrawler() {
        const formData = {
            origin: document.getElementById('origin').value.trim(),
            max_depth: parseInt(document.getElementById('maxDepth').value),
            hit_rate: parseFloat(document.getElementById('hitRate').value) || 1.0,
            max_queue_capacity: parseInt(document.getElementById('queueCapacity').value) || 10000,
            max_urls_to_visit: parseInt(document.getElementById('maxUrlsToVisit').value) || 100
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

        if (formData.hit_rate < 0.1 || formData.hit_rate > 1000) {
            this.showError('Hit rate must be between 0.1 and 1000');
            return;
        }

        if (formData.max_queue_capacity < 100 || formData.max_queue_capacity > 100000) {
            this.showError('Queue capacity must be between 100 and 100,000');
            return;
        }

        if (formData.max_urls_to_visit < 0 || formData.max_urls_to_visit > 10000) {
            this.showError('Max URLs to visit must be between 0 and 10,000');
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
            document.getElementById('origin').value = 'https://www.wikipedia.org/';
            document.getElementById('maxDepth').value = 3;
            document.getElementById('hitRate').value = 100;
            document.getElementById('queueCapacity').value = 10000;

            // Refresh recent crawlers list and stats
            setTimeout(() => {
                this.loadRecentCrawlers();
                this.loadCrawlerStats();
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
            const createdAt = crawler.created_at ? new Date(crawler.created_at * 1000).toLocaleString() : 'Unknown';
            const updatedAt = crawler.updated_at ? new Date(crawler.updated_at * 1000).toLocaleString() : 'Unknown';
            
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
                        <small style="color: #5f6368;">Created: ${createdAt}</small>
                    </div>
                    <div class="result-meta">
                        <strong>Origin:</strong> <a href="${crawler.origin}" target="_blank">${crawler.origin}</a><br>
                        <strong>URLs Visited:</strong> ${crawler.visited_count} | 
                        <strong>Last Updated:</strong> ${updatedAt}
                    </div>
                    <div style="margin-top: 1rem;">
                        <a href="status.html?id=${crawler.crawler_id}" class="btn">📊 View Status</a>
                        ${crawler.status === 'Active' ? `
                            <button class="btn" onclick="crawlerApp.pauseCrawler('${crawler.crawler_id}')" style="margin-left: 0.5rem;">
                                ⏸️ Pause
                            </button>
                            <button class="btn" onclick="crawlerApp.stopCrawler('${crawler.crawler_id}')" style="margin-left: 0.5rem;">
                                🛑 Stop
                            </button>
                        ` : ''}
                        ${crawler.status === 'Paused' ? `
                            <button class="btn" onclick="crawlerApp.resumeCrawler('${crawler.crawler_id}')" style="margin-left: 0.5rem;">
                                ▶️ Resume
                            </button>
                            <button class="btn" onclick="crawlerApp.stopCrawler('${crawler.crawler_id}')" style="margin-left: 0.5rem;">
                                🛑 Stop
                            </button>
                        ` : ''}
                        ${crawler.status === 'Stopped' ? `
                            <button class="btn" onclick="crawlerApp.resumeFromFiles('${crawler.crawler_id}')" style="margin-left: 0.5rem;">
                                🔄 Resume from Files
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

    async pauseCrawler(crawlerId) {
        if (!confirm('Are you sure you want to pause this crawler?')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/pause/${crawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler pause request: ${data.message}`);
            
            // Refresh the list
            this.loadRecentCrawlers();

        } catch (error) {
            console.error('Error pausing crawler:', error);
            alert(`Failed to pause crawler: ${error.message}`);
        }
    }

    async resumeCrawler(crawlerId) {
        if (!confirm('Are you sure you want to resume this crawler?')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/resume/${crawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler resume request: ${data.message}`);
            
            // Refresh the list
            this.loadRecentCrawlers();

        } catch (error) {
            console.error('Error resuming crawler:', error);
            alert(`Failed to resume crawler: ${error.message}`);
        }
    }

    async resumeFromFiles(crawlerId) {
        if (!confirm('Are you sure you want to resume this crawler from its saved files? This will continue from where it left off.')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/resume-from-files/${crawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler resume from files request: ${data.message}`);
            
            // Refresh the list
            this.loadRecentCrawlers();

        } catch (error) {
            console.error('Error resuming crawler from files:', error);
            alert(`Failed to resume crawler from files: ${error.message}`);
        }
    }

    async loadCrawlerStats() {
        try {
            const response = await fetch(`${API_BASE}/crawler/stats`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            // Update the statistics display
            document.getElementById('statVisitedUrls').textContent = data.total_visited_urls || 0;
            document.getElementById('statWordsInDb').textContent = data.total_words_in_database || 0;
            document.getElementById('statActiveCrawlers').textContent = data.total_active_crawlers || 0;
            document.getElementById('statTotalCrawlers').textContent = data.total_crawlers_created || 0;

            // Add active crawler indicator
            const activeCrawlersElement = document.getElementById('statActiveCrawlers');
            if (data.total_active_crawlers > 0) {
                activeCrawlersElement.style.backgroundColor = '#28a745';
                activeCrawlersElement.style.animation = 'pulse 2s infinite';
            } else {
                activeCrawlersElement.style.backgroundColor = 'rgba(255,255,255,0.2)';
                activeCrawlersElement.style.animation = 'none';
            }

        } catch (error) {
            console.error('Error loading crawler stats:', error);
            // Show error values
            document.getElementById('statVisitedUrls').textContent = '!';
            document.getElementById('statWordsInDb').textContent = '!';
            document.getElementById('statActiveCrawlers').textContent = '!';
            document.getElementById('statTotalCrawlers').textContent = '!';
        }
    }

    async clearAllData() {
        if (!confirm('Are you sure you want to clear all crawler data? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/clear`, {
                method: 'POST'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Successfully cleared ${data.files_deleted} files from ${data.directories_cleared.join(', ')} directories.`);
            
            // Refresh stats and recent crawlers
            this.loadCrawlerStats();
            this.loadRecentCrawlers();

        } catch (error) {
            console.error('Error clearing data:', error);
            alert(`Failed to clear data: ${error.message}`);
        }
    }

    getStatusClass(status) {
        switch (status) {
            case 'Active':
                return 'status-active';
            case 'Paused':
                return 'status-paused';
            case 'Stopped':
                return 'status-stopped';
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
