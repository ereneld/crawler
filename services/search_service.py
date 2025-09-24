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
        """Load word data from a single alphabet file"""
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _calculate_relevance_score(self, word, query_words, entry):
        """Calculate relevance score for a search result"""
        score = 0
        
        # Exact match bonus
        if word in query_words:
            score += 100
        
        # Partial match bonus
        for query_word in query_words:
            if query_word in word:
                score += 50
            elif word in query_word:
                score += 30
        
        # Frequency weight
        score += min(entry['frequency'], 50)  # Cap frequency impact
        
        # Depth penalty (shallower is better)
        score -= entry['depth'] * 5
        
        return max(score, 0)
    
    def _search_in_file(self, filename, query_words):
        """Search for query words in a specific alphabet file"""
        results = []
        word_data = self._load_word_data(filename)
        
        for stored_word, entries in word_data.items():
            # Check if any query word matches this stored word
            matches = False
            for query_word in query_words:
                if (query_word == stored_word or 
                    query_word in stored_word or 
                    stored_word in query_word):
                    matches = True
                    break
            
            if matches:
                for entry in entries:
                    relevance_score = self._calculate_relevance_score(
                        stored_word, query_words, entry
                    )
                    
                    if relevance_score > 0:
                        results.append({
                            "word": stored_word,
                            "relevant_url": entry["relevant_url"],
                            "origin_url": entry["origin_url"],
                            "depth": entry["depth"],
                            "frequency": entry["frequency"],
                            "relevance_score": relevance_score
                        })
        
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
            
            # Remove relevance_score from final results (internal use only)
            for result in paginated_results:
                result.pop("relevance_score", None)
            
            return {
                "results": paginated_results,
                "total_results": total_results,
                "query_words": query_words,
                "files_searched": len(files_to_search)
            }
            
        except Exception as e:
            return {"error": f"Search error: {e}"}
    
    def get_search_stats(self):
        """Get statistics about the search index"""
        try:
            stats = {
                "total_files": 0,
                "total_words": 0,
                "total_entries": 0,
                "alphabet_distribution": {}
            }
            
            # Check each possible alphabet file
            for letter in 'abcdefghijklmnopqrstuvwxyz':
                filename = os.path.join(self.storage_dir, f"{letter}.data")
                if os.path.exists(filename):
                    stats["total_files"] += 1
                    word_data = self._load_word_data(filename)
                    
                    word_count = len(word_data)
                    entry_count = sum(len(entries) for entries in word_data.values())
                    
                    stats["total_words"] += word_count
                    stats["total_entries"] += entry_count
                    stats["alphabet_distribution"][letter] = {
                        "words": word_count,
                        "entries": entry_count
                    }
            
            # Check 'other' file for non-alphabetic words
            other_filename = os.path.join(self.storage_dir, "other.data")
            if os.path.exists(other_filename):
                stats["total_files"] += 1
                word_data = self._load_word_data(other_filename)
                
                word_count = len(word_data)
                entry_count = sum(len(entries) for entries in word_data.values())
                
                stats["total_words"] += word_count
                stats["total_entries"] += entry_count
                stats["alphabet_distribution"]["other"] = {
                    "words": word_count,
                    "entries": entry_count
                }
            
            return stats
            
        except Exception as e:
            return {"error": f"Stats error: {e}"}
    
    def suggest_completions(self, partial_word, limit=10):
        """Suggest word completions for autocomplete functionality"""
        try:
            if len(partial_word) < 2:
                return {"suggestions": []}
            
            partial_word = partial_word.lower()
            first_letter = partial_word[0]
            
            if not first_letter.isalpha():
                first_letter = 'other'
            
            filename = os.path.join(self.storage_dir, f"{first_letter}.data")
            
            if not os.path.exists(filename):
                return {"suggestions": []}
            
            word_data = self._load_word_data(filename)
            suggestions = []
            
            for word in word_data.keys():
                if word.startswith(partial_word):
                    # Calculate suggestion score based on total frequency
                    total_frequency = sum(entry["frequency"] for entry in word_data[word])
                    suggestions.append({
                        "word": word,
                        "frequency": total_frequency,
                        "occurrences": len(word_data[word])
                    })
            
            # Sort by frequency and limit results
            suggestions.sort(key=lambda x: x["frequency"], reverse=True)
            suggestions = suggestions[:limit]
            
            return {"suggestions": suggestions}
            
        except Exception as e:
            return {"error": f"Suggestion error: {e}"}

# Global search service instance
search_service = SearchService()

def search_words(query, page_limit=10, page_offset=0, sort_by="relevance"):
    """Main search function to be used by the API"""
    return search_service.search(query, page_limit, page_offset, sort_by)

def get_search_statistics():
    """Get search index statistics"""
    return search_service.get_search_stats()

def get_word_suggestions(partial_word, limit=10):
    """Get word completion suggestions"""
    return search_service.suggest_completions(partial_word, limit)
