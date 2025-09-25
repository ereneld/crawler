// Search functionality
const API_BASE = 'http://localhost:3600';

class SearchApp {
    constructor() {
        this.currentPage = 0;
        this.pageLimit = 10;
        this.currentQuery = '';
        this.sortBy = 'relevance';
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkUrlParams();
    }

    bindEvents() {
        // Search form submission
        document.getElementById('searchForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.performSearch();
        });

        // I'm Feeling Lucky button
        document.getElementById('luckyBtn').addEventListener('click', () => {
            this.performLuckySearch();
        });

        // Enter key support
        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.performSearch();
            }
        });
    }

    checkUrlParams() {
        // Check if there's a query in URL params
        const urlParams = new URLSearchParams(window.location.search);
        const query = urlParams.get('q');
        if (query) {
            document.getElementById('searchInput').value = query;
            this.performSearch();
        }
    }

    async performSearch(page = 0) {
        const query = document.getElementById('searchInput').value.trim();
        
        if (!query) {
            this.showError('Please enter a search query');
            return;
        }

        this.currentQuery = query;
        this.currentPage = page;

        // Update URL
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('q', query);
        if (page > 0) {
            newUrl.searchParams.set('page', page);
        } else {
            newUrl.searchParams.delete('page');
        }
        window.history.pushState({}, '', newUrl);

        this.showLoading(true);
        this.hideError();
        this.hideResults();

        try {
            const offset = page * this.pageLimit;
            const response = await fetch(
                `${API_BASE}/search?query=${encodeURIComponent(query)}&pageLimit=${this.pageLimit}&pageOffset=${offset}&sortBy=${this.sortBy}`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.displayResults(data);
        } catch (error) {
            console.error('Search error:', error);
            this.showError(`Search failed: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    async performLuckySearch() {
        this.showLoading(true);
        this.hideError();

        try {
            // First, get a random word from the database
            const randomResponse = await fetch(`${API_BASE}/search/random`);
            
            if (!randomResponse.ok) {
                throw new Error(`HTTP ${randomResponse.status}: ${randomResponse.statusText}`);
            }

            const randomData = await randomResponse.json();
            
            if (randomData.error) {
                throw new Error(randomData.error);
            }

            const randomWord = randomData.word;
            
            // Update the search input to show the random word
            document.getElementById('searchInput').value = randomWord;
            
            // Now search for that random word
            const searchResponse = await fetch(
                `${API_BASE}/search?query=${encodeURIComponent(randomWord)}&pageLimit=${this.pageLimit}&pageOffset=0&sortBy=relevance`
            );

            if (!searchResponse.ok) {
                throw new Error(`HTTP ${searchResponse.status}: ${searchResponse.statusText}`);
            }

            const searchData = await searchResponse.json();
            
            if (searchData.error) {
                throw new Error(searchData.error);
            }

            // Display the search results for the random word
            this.currentQuery = randomWord;
            this.currentPage = 0;
            this.displayResults(searchData);
            
        } catch (error) {
            console.error('Lucky search error:', error);
            this.showError(`I'm Feeling Lucky failed: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    displayResults(data) {
        const resultsContainer = document.getElementById('resultsContainer');
        const resultsInfo = document.getElementById('resultsInfo');
        const resultsList = document.getElementById('resultsList');
        const pagination = document.getElementById('pagination');

        // Show results info
        const totalResults = data.total_results || 0;
        const startResult = this.currentPage * this.pageLimit + 1;
        const endResult = Math.min(startResult + this.pageLimit - 1, totalResults);
        
        resultsInfo.innerHTML = `
            <div style="margin-bottom: 1rem; color: #5f6368;">
                About ${totalResults.toLocaleString()} results (${data.query_words ? data.query_words.join(', ') : this.currentQuery})
            </div>
        `;

        // Display results
        if (data.results && data.results.length > 0) {
            resultsList.innerHTML = data.results.map(result => `
                <div class="result-item">
                    <a href="${result.relevant_url}" target="_blank" class="result-url">
                        ${result.relevant_url}
                    </a>
                    <div class="result-meta">
                        Word: <strong>${result.word}</strong> | 
                        Frequency: ${result.frequency} | 
                        Depth: ${result.depth} | 
                        Origin: ${result.origin_url}
                    </div>
                </div>
            `).join('');

            // Add pagination
            this.addPagination(pagination, totalResults);
        } else {
            resultsList.innerHTML = `
                <div style="text-align: center; padding: 2rem; color: #5f6368;">
                    <h3>No results found</h3>
                    <p>Try different keywords or check if the content has been crawled.</p>
                </div>
            `;
            pagination.innerHTML = '';
        }

        resultsContainer.style.display = 'block';
    }

    addPagination(container, totalResults) {
        const totalPages = Math.ceil(totalResults / this.pageLimit);
        const currentPage = this.currentPage;

        if (totalPages <= 1) {
            container.innerHTML = '';
            return;
        }

        let paginationHTML = '<div style="text-align: center; margin-top: 2rem;">';

        // Previous button
        if (currentPage > 0) {
            paginationHTML += `<button class="btn" onclick="searchApp.performSearch(${currentPage - 1})">← Previous</button>`;
        }

        // Page numbers (show max 10 pages)
        const startPage = Math.max(0, currentPage - 5);
        const endPage = Math.min(totalPages - 1, startPage + 9);

        for (let i = startPage; i <= endPage; i++) {
            const isActive = i === currentPage;
            paginationHTML += `
                <button class="btn ${isActive ? 'btn-primary' : ''}" 
                        onclick="searchApp.performSearch(${i})"
                        ${isActive ? 'disabled' : ''}>
                    ${i + 1}
                </button>
            `;
        }

        // Next button
        if (currentPage < totalPages - 1) {
            paginationHTML += `<button class="btn" onclick="searchApp.performSearch(${currentPage + 1})">Next →</button>`;
        }

        paginationHTML += '</div>';
        container.innerHTML = paginationHTML;
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

    hideResults() {
        document.getElementById('resultsContainer').style.display = 'none';
    }
}

// Initialize the search app
const searchApp = new SearchApp();
