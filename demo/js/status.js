// Status page functionality
const API_BASE = 'http://localhost:3600';

class StatusApp {
    constructor() {
        this.currentCrawlerId = null;
        this.refreshInterval = null;
        this.isLiveMode = false;
        this.currentQueue = [];
        this.currentLogs = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkUrlParams();
        this.loadAllCrawlers();
    }

    bindEvents() {
        // Status form submission
        document.getElementById('statusForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.loadCrawlerStatus();
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadCrawlerStatus();
        });

        // Pause button
        document.getElementById('pauseBtn').addEventListener('click', () => {
            this.pauseCrawler();
        });

        // Resume button
        document.getElementById('resumeBtn').addEventListener('click', () => {
            this.resumeCrawler();
        });

        // Stop button
        document.getElementById('stopBtn').addEventListener('click', () => {
            this.stopCrawler();
        });

        // Download queue button
        document.getElementById('downloadQueueBtn').addEventListener('click', () => {
            this.downloadQueue();
        });

        // Download logs button
        document.getElementById('downloadLogsBtn').addEventListener('click', () => {
            this.downloadLogs();
        });
    }

    checkUrlParams() {
        // Check if there's a crawler ID in URL params
        const urlParams = new URLSearchParams(window.location.search);
        const crawlerId = urlParams.get('id');
        if (crawlerId) {
            document.getElementById('crawlerId').value = crawlerId;
            this.loadCrawlerStatus();
        }
    }

    async loadCrawlerStatus() {
        const crawlerId = document.getElementById('crawlerId').value.trim();
        
        if (!crawlerId) {
            this.showError('Please enter a crawler ID');
            return;
        }

        this.currentCrawlerId = crawlerId;

        // Update URL
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('id', crawlerId);
        window.history.pushState({}, '', newUrl);

        this.showLoading(true);
        this.hideError();
        this.hideStatus();

        try {
            const response = await fetch(`${API_BASE}/crawler/status/${crawlerId}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Crawler not found. Please check the crawler ID.');
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.displayStatus(data);
            this.setupLiveUpdates(data.status === 'Active');

        } catch (error) {
            console.error('Status loading error:', error);
            this.showError(`Failed to load crawler status: ${error.message}`);
            this.stopLiveUpdates();
        } finally {
            this.showLoading(false);
        }
    }

    displayStatus(data) {
        // Update status badge
        const statusBadge = document.getElementById('statusBadge');
        statusBadge.textContent = data.status;
        statusBadge.className = `status-badge ${this.getStatusClass(data.status)}`;

        // Update title
        document.getElementById('statusTitle').textContent = `Crawler ${data.crawler_id}`;

        // Update details
        document.getElementById('originUrl').href = data.origin;
        document.getElementById('originUrl').textContent = data.origin;
        document.getElementById('maxDepth').textContent = data.max_depth;
        document.getElementById('hitRate').textContent = data.hit_rate;
        document.getElementById('visitedCount').textContent = data.visited_count || 0;
        document.getElementById('queueSize').textContent = data.queue ? data.queue.length : 0;

        // Update timestamps
        if (data.created_at) {
            const startTime = new Date(data.created_at * 1000);
            document.getElementById('startTime').textContent = startTime.toLocaleString();
        } else {
            document.getElementById('startTime').textContent = 'Unknown';
        }
        
        if (data.updated_at) {
            const lastUpdate = new Date(data.updated_at * 1000);
            document.getElementById('lastUpdate').textContent = lastUpdate.toLocaleString();
        } else {
            document.getElementById('lastUpdate').textContent = 'Unknown';
        }

        // Update queue
        this.displayQueue(data.queue || []);

        // Update logs
        this.displayLogs(data.logs || []);

        // Show/hide action buttons based on status
        const pauseBtn = document.getElementById('pauseBtn');
        const resumeBtn = document.getElementById('resumeBtn');
        const stopBtn = document.getElementById('stopBtn');
        
        pauseBtn.style.display = data.status === 'Active' ? 'inline-flex' : 'none';
        resumeBtn.style.display = data.status === 'Paused' ? 'inline-flex' : 'none';
        stopBtn.style.display = (data.status === 'Active' || data.status === 'Paused') ? 'inline-flex' : 'none';

        // Show status container
        document.getElementById('statusContainer').style.display = 'block';
    }

    displayQueue(queue) {
        const container = document.getElementById('queueContainer');
        this.currentQueue = queue || [];
        
        // Update download button state
        const downloadBtn = document.getElementById('downloadQueueBtn');
        downloadBtn.disabled = this.currentQueue.length === 0;
        
        if (queue.length === 0) {
            container.innerHTML = '<div style="color: #5f6368; font-style: italic;">Queue is empty</div>';
            return;
        }

        const queueHTML = queue.slice(0, 10).map(item => `
            <div style="margin-bottom: 0.5rem; padding: 0.5rem; background: white; border-radius: 4px; border-left: 3px solid #4285f4;">
                ${item}
            </div>
        `).join('');

        const moreCount = queue.length - 10;
        const moreHTML = moreCount > 0 ? `
            <div style="color: #5f6368; font-style: italic; margin-top: 1rem;">
                ... and ${moreCount} more URLs in queue
            </div>
        ` : '';

        container.innerHTML = queueHTML + moreHTML;
    }

    displayLogs(logs) {
        const container = document.getElementById('logsContainer');
        this.currentLogs = logs || [];
        
        // Update download button state
        const downloadBtn = document.getElementById('downloadLogsBtn');
        downloadBtn.disabled = this.currentLogs.length === 0;
        
        if (logs.length === 0) {
            container.textContent = 'No logs available';
            return;
        }

        // Show latest logs first, but maintain chronological order within the display
        const recentLogs = logs.slice(-50).reverse();
        container.textContent = recentLogs.join('\n');
        
        // Auto-scroll to bottom
        container.scrollTop = container.scrollHeight;
    }

    setupLiveUpdates(isActive) {
        this.stopLiveUpdates();
        
        if (isActive) {
            this.isLiveMode = true;
            document.getElementById('liveIndicator').style.display = 'block';
            
            // Refresh every 3 seconds
            this.refreshInterval = setInterval(() => {
                this.refreshStatus();
            }, 3000);
        } else {
            this.isLiveMode = false;
            document.getElementById('liveIndicator').style.display = 'none';
        }
    }

    stopLiveUpdates() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
        this.isLiveMode = false;
        document.getElementById('liveIndicator').style.display = 'none';
    }

    async refreshStatus() {
        if (!this.currentCrawlerId) return;

        try {
            const response = await fetch(`${API_BASE}/crawler/status/${this.currentCrawlerId}`);
            
            if (response.ok) {
                const data = await response.json();
                if (!data.error) {
                    this.displayStatus(data);
                    
                    // Stop live updates if crawler is no longer active
                    if (data.status !== 'Active') {
                        this.stopLiveUpdates();
                    }
                }
            }
        } catch (error) {
            console.error('Refresh error:', error);
            // Don't show error for background refreshes
        }
    }

    async stopCrawler() {
        if (!this.currentCrawlerId) return;

        if (!confirm('Are you sure you want to stop this crawler?')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/stop/${this.currentCrawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler stop request: ${data.message}`);
            
            // Refresh status after a short delay
            setTimeout(() => {
                this.loadCrawlerStatus();
            }, 1000);

        } catch (error) {
            console.error('Error stopping crawler:', error);
            alert(`Failed to stop crawler: ${error.message}`);
        }
    }

    async pauseCrawler() {
        if (!this.currentCrawlerId) return;

        if (!confirm('Are you sure you want to pause this crawler?')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/pause/${this.currentCrawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler pause request: ${data.message}`);
            
            // Refresh status after a short delay
            setTimeout(() => {
                this.loadCrawlerStatus();
            }, 1000);

        } catch (error) {
            console.error('Error pausing crawler:', error);
            alert(`Failed to pause crawler: ${error.message}`);
        }
    }

    async resumeCrawler() {
        if (!this.currentCrawlerId) return;

        if (!confirm('Are you sure you want to resume this crawler?')) {
            return;
        }

        try {
            const response = await fetch(`${API_BASE}/crawler/resume/${this.currentCrawlerId}`, {
                method: 'POST'
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            alert(`Crawler resume request: ${data.message}`);
            
            // Refresh status after a short delay
            setTimeout(() => {
                this.loadCrawlerStatus();
            }, 1000);

        } catch (error) {
            console.error('Error resuming crawler:', error);
            alert(`Failed to resume crawler: ${error.message}`);
        }
    }

    async loadAllCrawlers() {
        const container = document.getElementById('allCrawlers');

        try {
            const response = await fetch(`${API_BASE}/crawler/list`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.displayAllCrawlers(container, data);

        } catch (error) {
            console.error('Error loading crawlers:', error);
            container.innerHTML = `
                <div class="error">
                    Failed to load crawlers: ${error.message}
                </div>
            `;
        }
    }

    displayAllCrawlers(container, data) {
        if (!data.crawlers || data.crawlers.length === 0) {
            container.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: #5f6368;">
                    <p>No crawlers found.</p>
                    <a href="crawler.html" class="btn btn-primary">Create First Crawler</a>
                </div>
            `;
            return;
        }

        const crawlersHTML = data.crawlers.map(crawler => {
            const statusClass = this.getStatusClass(crawler.status);
            const createdAt = crawler.created_at ? new Date(crawler.created_at * 1000).toLocaleString() : 'Unknown';
            const updatedAt = crawler.updated_at ? new Date(crawler.updated_at * 1000).toLocaleString() : 'Unknown';
            
            return `
                <div class="result-item" style="cursor: pointer;" onclick="statusApp.selectCrawler('${crawler.crawler_id}')">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                        <div>
                            <strong style="color: #4285f4;">🕷️ ${crawler.crawler_id}</strong>
                            <span class="status-badge ${statusClass}" style="margin-left: 1rem;">
                                ${crawler.status}
                            </span>
                        </div>
                        <small style="color: #5f6368;">Created: ${createdAt}</small>
                    </div>
                    <div class="result-meta">
                        <strong>Origin:</strong> ${crawler.origin}<br>
                        <strong>URLs Visited:</strong> ${crawler.visited_count} | 
                        <strong>Last Updated:</strong> ${updatedAt}
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

    selectCrawler(crawlerId) {
        document.getElementById('crawlerId').value = crawlerId;
        this.loadCrawlerStatus();
        
        // Scroll to status form
        document.getElementById('statusForm').scrollIntoView({ behavior: 'smooth' });
    }

    downloadQueue() {
        if (!this.currentCrawlerId || this.currentQueue.length === 0) {
            alert('No queue data available to download');
            return;
        }

        try {
            // Create downloadable content
            const content = this.currentQueue.join('\n');
            const filename = `${this.currentCrawlerId}_queue.txt`;
            
            this.downloadTextFile(content, filename);
        } catch (error) {
            console.error('Error downloading queue:', error);
            alert('Failed to download queue file');
        }
    }

    downloadLogs() {
        if (!this.currentCrawlerId || this.currentLogs.length === 0) {
            alert('No log data available to download');
            return;
        }

        try {
            // Create downloadable content (maintain chronological order)
            const content = this.currentLogs.join('\n');
            const filename = `${this.currentCrawlerId}_logs.txt`;
            
            this.downloadTextFile(content, filename);
        } catch (error) {
            console.error('Error downloading logs:', error);
            alert('Failed to download logs file');
        }
    }

    downloadTextFile(content, filename) {
        // Create blob with content
        const blob = new Blob([content], { type: 'text/plain' });
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        
        // Cleanup
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
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

    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }

    hideError() {
        document.getElementById('errorMessage').style.display = 'none';
    }

    hideStatus() {
        document.getElementById('statusContainer').style.display = 'none';
    }
}

// Initialize the status app
const statusApp = new StatusApp();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    statusApp.stopLiveUpdates();
});
