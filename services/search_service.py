import os
import json
import re

# Storage directories
DATA_DIR = "data"
STORAGE_DIR = os.path.join(DATA_DIR, "storage")

class SearchService:
    """Service for searching indexed content with pagination and ranking"""
    
    def __init__(self):
        self.storage_dir = STORAGE_DIR
    
    def _normalize_query(self, query):
        """Normalize query string for better matching"""
        # Convert to lowercase and extract words
        words = re.findall(r'\b[a-zA-Z]{2,}\b', query.lower())
        return words
    
    def _get_alphabet_files(self, words):
        """Get list of alphabet files to search based on query words"""
        files_to_search = set()
        
        for word in words:
            if len(word) >= 2:
                first_letter = word[0].lower()
                if not first_letter.isalpha():
                    first_letter = 'other'
                
                filename = os.path.join(self.storage_dir, f"{first_letter}.data")
                if os.path.exists(filename):
                    files_to_search.add(filename)
        
        return list(files_to_search)
    
    def _load_word_data(self, filename):
        """Load word data from a single alphabet file (space-separated format)"""
        try:
            word_data = {}
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        # Parse space-separated format: word relevant_url origin_url depth frequency
                        parts = line.split(' ', 4)  # Split into 5 parts max
                        if len(parts) >= 5:
                            word, relevant_url, origin_url, depth_str, frequency_str = parts
                            try:
                                depth = int(depth_str)
                                frequency = int(frequency_str)
                                
                                if word not in word_data:
                                    word_data[word] = []
                                
                                word_data[word].append({
                                    "relevant_url": relevant_url,
                                    "origin_url": origin_url,
                                    "depth": depth,
                                    "frequency": frequency
                                })
                            except ValueError:
                                continue  # Skip malformed lines
            return word_data
        except FileNotFoundError:
            return {}
    
    def _find_word_matches(self, query_word, word_data):
        """
        Find matching words using optimized key-based lookup with suffix removal
        
        Args:
            query_word (str): The word to search for
            word_data (dict): Dictionary of words in the current file
            
        Returns:
            set: Set of matching words from word_data
        """
        matches = set()
        query_word_lower = query_word.lower()
        
        # For words less than 3 letters, only check exact match
        if len(query_word_lower) < 3:
            if query_word_lower in word_data:
                matches.add(query_word_lower)
            return matches
        
        # For words 3+ letters, check progressively shorter suffixes
        # Start with full word (highest score) and work backwards
        for i in range(len(query_word_lower), 2, -1):  # Down to 3 letters minimum
            substring = query_word_lower[:i]
            
            # Direct key lookup - much faster than iteration
            if substring in word_data:
                matches.add(substring)
        
        return matches
    
    def _calculate_word_match_score(self, query_word, matched_word, entry):
        """
        Calculate relevance score based on word match quality and entry data
        
        Args:
            query_word (str): Original query word
            matched_word (str): Word that was matched in the database
            entry (dict): Word entry with frequency, depth, etc.
            
        Returns:
            int: Relevance score
        """
        # Base score from frequency
        score = entry['frequency'] * 10
        
        # Full word match gets highest bonus
        if query_word.lower() == matched_word.lower():
            score += 1000  # Highest priority for exact matches
        else:
            # Partial match bonus based on match length
            match_ratio = len(matched_word) / len(query_word)
            score += int(500 * match_ratio)  # Scale bonus by match quality
        
        # Depth penalty (shallower pages are better)
        score -= entry['depth'] * 5
        
        return max(score, 0)
    
    def _search_in_file(self, filename, query_words):
        """Search for query words in a specific alphabet file"""
        results = []
        word_data = self._load_word_data(filename)
        
        # Extract the letter from filename (e.g., 'a.data' -> 'a')
        letter = os.path.basename(filename).split('.')[0].lower()
        
        # Process each query word against the word data for this letter
        for query_word in query_words:
            # Only process query words that start with the current letter
            if not query_word.startswith(letter):
                continue
                
            # Find matches using optimized key-based lookup
            matched_words = self._find_word_matches(query_word, word_data)
            
            for matched_word in matched_words:
                if matched_word in word_data:
                    for entry in word_data[matched_word]:
                        relevance_score = self._calculate_word_match_score(
                            query_word, matched_word, entry
                        )
                        
                        if relevance_score > 0:
                            results.append({
                                "word": matched_word,
                                "relevant_url": entry["relevant_url"],
                                "origin_url": entry["origin_url"],
                                "depth": entry["depth"],
                                "frequency": entry["frequency"],
                                "relevance_score": relevance_score
                            })
                else: 
                    print(f"Error. This should not happen. No matches found for {matched_word} in {filename}")
        
        return results
    
    def search(self, query, page_limit=10, page_offset=0, sort_by="relevance"):
        """
        Search for content based on query string with pagination
        
        Args:
            query (str): Search query
            page_limit (int): Number of results per page
            page_offset (int): Starting offset for pagination
            sort_by (str): Sort criteria - "relevance", "frequency", "depth"
        
        Returns:
            dict: Search results with pagination info
        """
        try:
            # Normalize query
            query_words = self._normalize_query(query)
            
            if not query_words:
                return {
                    "results": [],
                    "total_results": 0,
                    "message": "No valid search terms found"
                }
            
            # Get relevant files to search
            files_to_search = self._get_alphabet_files(query_words)
            
            if not files_to_search:
                return {
                    "results": [],
                    "total_results": 0,
                    "message": "No indexed content found for query"
                }
            
            # Search in all relevant files
            all_results = []
            for filename in files_to_search:
                file_results = self._search_in_file(filename, query_words)
                all_results.extend(file_results)
            
            # Remove duplicates (same URL with different words)
            unique_results = {}
            for result in all_results:
                url = result["relevant_url"]
                if url not in unique_results:
                    unique_results[url] = result
                else:
                    # Keep the result with higher relevance score
                    if result["relevance_score"] > unique_results[url]["relevance_score"]:
                        unique_results[url] = result
            
            results = list(unique_results.values())
            
            # Sort results
            if sort_by == "relevance":
                results.sort(key=lambda x: x["relevance_score"], reverse=True)
            elif sort_by == "frequency":
                results.sort(key=lambda x: x["frequency"], reverse=True)
            elif sort_by == "depth":
                results.sort(key=lambda x: x["depth"])
            else:
                # Default to relevance
                results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            # Apply pagination
            total_results = len(results)
            paginated_results = results[page_offset:page_offset + page_limit]
            
            # Keep relevance_score in final results for debugging and user insight
            
            return {
                "results": paginated_results,
                "total_results": total_results,
                "query_words": query_words,
                "files_searched": len(files_to_search)
            }
            
        except Exception as e:
            return {"error": f"Search error: {e}"}
    
    def get_random_word(self):
        """Get a random word from the database for 'I'm Feeling Lucky' functionality"""
        try:
            import random
            
            # Get all storage files
            storage_files = []
            if os.path.exists(self.storage_dir):
                for filename in os.listdir(self.storage_dir):
                    if filename.endswith('.data'):
                        storage_files.append(os.path.join(self.storage_dir, filename))
            
            if not storage_files:
                return {"error": "No words found in database"}
            
            # Pick a random storage file
            random_file = random.choice(storage_files)
            
            # Load words from the file and pick a random one
            word_data = self._load_word_data(random_file)
            
            if not word_data:
                return {"error": "No words found in selected file"}
            
            # Get all words and pick a random one
            words = list(word_data.keys())
            random_word = random.choice(words)
            
            return {"word": random_word}
            
        except Exception as e:
            return {"error": f"Random word error: {e}"}

# Global search service instance
search_service = SearchService()

def search_words(query, page_limit=10, page_offset=0, sort_by="relevance"):
    """Main search function to be used by the API"""
    return search_service.search(query, page_limit, page_offset, sort_by)


def get_random_word():
    """Get a random word for I'm Feeling Lucky functionality"""
    return search_service.get_random_word()
