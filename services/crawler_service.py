import os
import json
import time
import threading
import shutil
import glob
from utils.crawler_job import CrawlerJob

# Storage directories
DATA_DIR = "data"
CRAWLER_DIR = os.path.join(DATA_DIR, "crawlers")
STORAGE_DIR = os.path.join(DATA_DIR, "storage")

class CrawlerService:
    """Service for managing crawler operations"""
    
    def __init__(self):
        self.active_crawlers = {}  # Track active crawler threads
    
    def create_crawler(self, origin, max_depth, hit_rate=100.0, max_queue_capacity=10000, max_urls_to_visit=1000):
        """
        Create and start a new crawler job
        
        Args:
            origin (str): Starting URL
            max_depth (int): Maximum crawling depth
            hit_rate (float): Hits per second rate limiting
            max_queue_capacity (int): Maximum queue capacity
            max_urls_to_visit (int): Maximum number of URLs to visit
            
        Returns:
            dict: Crawler creation result with crawler_id
        """
        try:
            # Generate crawler_id format: [EpochTimeCreated_ThreadID]
            epoch_time = int(time.time())
            thread_id = threading.get_ident()
            crawler_id = f"{epoch_time}_{thread_id}"
            
            # Create and start crawler job
            crawler = CrawlerJob(
                crawler_id=crawler_id,
                origin=origin,
                max_depth=max_depth,
                hit_rate=hit_rate,
                max_queue_capacity=max_queue_capacity,
                max_urls_to_visit=max_urls_to_visit
            )
            
            # Start the crawler thread
            crawler.start()
            
            # Track the active crawler
            self.active_crawlers[crawler_id] = crawler
            
            return {
                "crawler_id": crawler_id,
                "status": "Active",
                "message": "Crawler started successfully"
            }
            
        except Exception as e:
            return {
                "error": f"Failed to create crawler: {e}"
            }
    
    def get_crawler_status(self, crawler_id):
        """
        Get crawler status from file or active thread
        
        Args:
            crawler_id (str): Crawler ID
            
        Returns:
            dict: Crawler status data
        """
        try:
            status_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.data")
            logs_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.logs")
            queue_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.queue")
            
            if os.path.exists(status_file):
                # Read main status data
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # Read logs if file exists
                logs = []
                if os.path.exists(logs_file):
                    with open(logs_file, 'r') as f:
                        logs = [line.strip() for line in f.readlines() if line.strip()]
                
                # Read queue if file exists
                queue = []
                if os.path.exists(queue_file):
                    with open(queue_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                # Parse space-separated format: URL DEPTH
                                # Split from right to get depth (last part) and URL (everything else)
                                parts = line.rsplit(' ', 1)  # Split only on last space
                                if len(parts) == 2:
                                    url, depth = parts
                                    queue.append(f"{url} (depth: {depth})")  # Format for API response
                                else:
                                    queue.append(line)  # Fallback for any malformed lines
                
                # Combine all data
                status_data["logs"] = logs[-50:]  # Keep last 50 logs for API response
                status_data["queue"] = queue
                
                # Determine status based on active crawler state
                if crawler_id in self.active_crawlers:
                    crawler_thread = self.active_crawlers[crawler_id]
                    
                    if crawler_thread.is_alive():
                        # Crawler is active - check if it's paused
                        if hasattr(crawler_thread, 'is_paused') and crawler_thread.is_paused():
                            status_data["status"] = "Paused"
                        else:
                            status_data["status"] = "Active"
                        status_data["thread_alive"] = True
                    else:
                        # Thread died but still in active list - clean up and mark as stopped
                        del self.active_crawlers[crawler_id]
                        status_data["status"] = "Stopped"
                        status_data["thread_alive"] = False
                else:
                    # Not in active crawlers - it's stopped
                    status_data["status"] = "Stopped"
                    status_data["thread_alive"] = False
                
                return status_data
            else:
                return {"error": "Crawler not found"}
                
        except Exception as e:
            return {"error": f"Error reading crawler status: {e}"}
    
    def list_crawlers(self):
        """
        List all crawler jobs
        
        Returns:
            dict: List of all crawler jobs with their status
        """
        try:
            crawlers = []
            
            # Get all crawler status files
            if os.path.exists(CRAWLER_DIR):
                for filename in os.listdir(CRAWLER_DIR):
                    if filename.endswith('.data'):
                        crawler_id = filename[:-5]  # Remove .data extension
                        
                        try:
                            with open(os.path.join(CRAWLER_DIR, filename), 'r') as f:
                                status_data = json.load(f)
                            
                            # Add basic info for listing
                            crawlers.append({
                                "crawler_id": crawler_id,
                                "status": status_data.get("status", "Unknown"),
                                "origin": status_data.get("origin", "Unknown"),
                                "visited_count": status_data.get("visited_count", 0),
                                "created_at": status_data.get("created_at"),
                                "updated_at": status_data.get("updated_at"),
                                "completed_at": status_data.get("completed_at")
                            })
                            
                        except json.JSONDecodeError:
                            continue
            
            # Sort by created_at timestamp (newest first)
            crawlers.sort(key=lambda x: x["created_at"] or 0, reverse=True)
            
            return {
                "crawlers": crawlers,
                "total_count": len(crawlers),
                "active_count": len(self.active_crawlers)
            }
            
        except Exception as e:
            return {"error": f"Error listing crawlers: {e}"}
    
    def stop_crawler(self, crawler_id):
        """
        Stop an active crawler (if possible)
        
        Args:
            crawler_id (str): Crawler ID to stop
            
        Returns:
            dict: Stop operation result
        """
        try:
            if crawler_id in self.active_crawlers:
                crawler_thread = self.active_crawlers[crawler_id]
                
                if crawler_thread.is_alive():
                    # Signal the crawler thread to stop gracefully
                    crawler_thread.stop()
                    return {
                        "message": "Crawler stop signal sent. The crawler will finish its current operation and stop gracefully.",
                        "status": "stop_requested"
                    }
                else:
                    del self.active_crawlers[crawler_id]
                    return {
                        "message": "Crawler was already finished",
                        "status": "already_finished"
                    }
            else:
                return {
                    "message": "Crawler not found in active crawlers or already finished",
                    "status": "not_active"
                }
                
        except Exception as e:
            return {"error": f"Error stopping crawler: {e}"}
    
    def pause_crawler(self, crawler_id):
        """
        Pause an active crawler
        
        Args:
            crawler_id (str): Crawler ID to pause
            
        Returns:
            dict: Pause operation result
        """
        try:
            if crawler_id in self.active_crawlers:
                crawler_thread = self.active_crawlers[crawler_id]
                
                if crawler_thread.is_alive():
                    crawler_thread.pause()
                    return {
                        "message": "Crawler paused successfully",
                        "status": "paused"
                    }
                else:
                    # Clean up finished thread
                    del self.active_crawlers[crawler_id]
                    return {
                        "message": "Crawler was already finished",
                        "status": "already_finished"
                    }
            else:
                return {
                    "error": "Crawler not found in active crawlers"
                }
                
        except Exception as e:
            return {"error": f"Error pausing crawler: {e}"}
    
    def resume_crawler(self, crawler_id):
        """
        Resume a paused crawler
        
        Args:
            crawler_id (str): Crawler ID to resume
            
        Returns:
            dict: Resume operation result
        """
        try:
            if crawler_id in self.active_crawlers:
                crawler_thread = self.active_crawlers[crawler_id]
                
                if crawler_thread.is_alive():
                    crawler_thread.resume()
                    return {
                        "message": "Crawler resumed successfully",
                        "status": "resumed"
                    }
                else:
                    # Clean up finished thread
                    del self.active_crawlers[crawler_id]
                    return {
                        "message": "Crawler was already finished",
                        "status": "already_finished"
                    }
            else:
                # Crawler not in active list, try to resume from saved files
                resume_result = self.resume_crawler_from_files(crawler_id)
                
                if "error" in resume_result:
                    return {
                        "error": "Crawler not found in active crawlers and could not resume from files",
                        "details": resume_result["error"]
                    }
                else:
                    return {
                        "message": "Crawler was not active, so started a new instance using existing data and resumed operation",
                        "status": "resumed_from_files"
                    }
                
        except Exception as e:
            return {"error": f"Error resuming crawler: {e}"}
    
    def resume_crawler_from_files(self, crawler_id):
        """
        Resume a stopped crawler from its saved files
        
        Args:
            crawler_id (str): Crawler ID to resume from files
            
        Returns:
            dict: Resume operation result
        """
        try:
            # Check if crawler files exist
            status_file = os.path.join(CRAWLER_DIR, f"{crawler_id}.data")
            if not os.path.exists(status_file):
                return {
                    "error": "Crawler files not found"
                }
            
            # Make sure crawler is not already active
            if crawler_id in self.active_crawlers:
                crawler_thread = self.active_crawlers[crawler_id]
                if crawler_thread.is_alive():
                    return {
                        "error": "Crawler is already active"
                    }
                else:
                    # Clean up dead thread
                    del self.active_crawlers[crawler_id]
            
            # Read crawler configuration from status file
            with open(status_file, 'r') as f:
                status_data = json.load(f)
            
            origin = status_data.get('origin')
            max_depth = status_data.get('max_depth')
            hit_rate = status_data.get('hit_rate', 100)
            max_queue_capacity = status_data.get('max_queue_capacity', 10000)
            max_urls_to_visit = status_data.get('max_urls_to_visit', 1000)
            
            if not origin or max_depth is None:
                return {
                    "error": "Invalid crawler configuration in files"
                }
            
            # Create new crawler instance with resume_from_files=True
            crawler = CrawlerJob(
                crawler_id=crawler_id,
                origin=origin,
                max_depth=max_depth,
                hit_rate=hit_rate,
                max_queue_capacity=max_queue_capacity,
                max_urls_to_visit=max_urls_to_visit,
                resume_from_files=True
            )
            
            # Start the crawler thread
            crawler.start()
            
            # Track the active crawler
            self.active_crawlers[crawler_id] = crawler
            
            return {
                "message": "Crawler resumed from files successfully",
                "status": "active"
            }
                
        except Exception as e:
            return {"error": f"Error resuming crawler from files: {e}"}
    
    def clear_all_data(self):
        """
        Clear all crawler data including visited URLs, crawler files, and storage files
        
        Returns:
            dict: Clear operation result
        """
        try:
            files_deleted = 0
            directories_cleared = []
            
            # 1. Delete visited_urls.data file
            visited_file = os.path.join(DATA_DIR, "visited_urls.data")
            if os.path.exists(visited_file):
                os.remove(visited_file)
                files_deleted += 1
            
            # 2. Delete all crawler files (.data, .logs, .queue)
            if os.path.exists(CRAWLER_DIR):
                crawler_files = glob.glob(os.path.join(CRAWLER_DIR, "*"))
                for file_path in crawler_files:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        files_deleted += 1
                directories_cleared.append("crawlers")
            
            # 3. Delete all storage files
            if os.path.exists(STORAGE_DIR):
                storage_files = glob.glob(os.path.join(STORAGE_DIR, "*"))
                for file_path in storage_files:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        files_deleted += 1
                directories_cleared.append("storage")
            
            # 4. Clear active crawlers tracking (they may no longer be valid)
            active_count = len(self.active_crawlers)
            self.active_crawlers.clear()
            
            return {
                "message": "All crawler data cleared successfully",
                "files_deleted": files_deleted,
                "directories_cleared": directories_cleared,
                "active_crawlers_cleared": active_count,
                "status": "success"
            }
            
        except Exception as e:
            return {
                "error": f"Error clearing data: {e}",
                "status": "error"
            }
    
    def get_statistics(self):
        """
        Get comprehensive crawler statistics
        
        Returns:
            dict: Statistics including visited URLs, words in DB, and active crawlers
        """
        try:
            stats = {
                "total_visited_urls": 0,
                "total_words_in_database": 0,
                "total_active_crawlers": 0,
                "total_crawlers_created": 0,
                "active_crawler_ids": [],
                "storage_files": [],
                "timestamp": time.time()
            }
            
            # 1. Count visited URLs
            visited_file = os.path.join(DATA_DIR, "visited_urls.data")
            if os.path.exists(visited_file):
                try:
                    with open(visited_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                stats["total_visited_urls"] += 1
                except Exception:
                    pass
            
            # 2. Count words in database (from storage files)
            if os.path.exists(STORAGE_DIR):
                try:
                    storage_files = glob.glob(os.path.join(STORAGE_DIR, "*.data"))
                    for file_path in storage_files:
                        filename = os.path.basename(file_path)
                        stats["storage_files"].append(filename)
                        
                        try:
                            with open(file_path, 'r') as f:
                                for line in f:
                                    if line.strip():
                                        stats["total_words_in_database"] += 1
                        except Exception:
                            continue
                except Exception:
                    pass
            
            # 3. Count total crawlers created (by checking .data files in crawlers directory)
            if os.path.exists(CRAWLER_DIR):
                try:
                    crawler_data_files = glob.glob(os.path.join(CRAWLER_DIR, "*.data"))
                    stats["total_crawlers_created"] = len(crawler_data_files)
                except Exception:
                    pass
            
            # 4. Count active crawlers
            active_crawlers = []
            for crawler_id, crawler_thread in list(self.active_crawlers.items()):
                if crawler_thread.is_alive():
                    active_crawlers.append(crawler_id)
                    stats["total_active_crawlers"] += 1
                else:
                    # Clean up finished threads
                    del self.active_crawlers[crawler_id]
            
            stats["active_crawler_ids"] = active_crawlers
            
            return stats
            
        except Exception as e:
            return {
                "error": f"Error getting statistics: {e}",
                "total_visited_urls": 0,
                "total_words_in_database": 0,
                "total_active_crawlers": 0,
                "total_crawlers_created": 0,
                "active_crawler_ids": [],
                "storage_files": []
            }

# Global crawler service instance
crawler_service = CrawlerService()

def create_crawler(origin, max_depth, hit_rate=100.0, max_queue_capacity=10000, max_urls_to_visit=1000):
    """Main function to create a crawler job"""
    return crawler_service.create_crawler(origin, max_depth, hit_rate, max_queue_capacity, max_urls_to_visit)

def get_crawler_status(crawler_id):
    """Main function to get crawler status"""
    return crawler_service.get_crawler_status(crawler_id)

def list_all_crawlers():
    """Main function to list all crawlers"""
    return crawler_service.list_crawlers()

def stop_crawler(crawler_id):
    """Main function to stop a crawler"""
    return crawler_service.stop_crawler(crawler_id)

def pause_crawler(crawler_id):
    """Main function to pause a crawler"""
    return crawler_service.pause_crawler(crawler_id)

def resume_crawler(crawler_id):
    """Main function to resume a crawler"""
    return crawler_service.resume_crawler(crawler_id)

def resume_crawler_from_files(crawler_id):
    """Main function to resume a crawler from files"""
    return crawler_service.resume_crawler_from_files(crawler_id)

def clear_all_data():
    """Main function to clear all crawler data"""
    return crawler_service.clear_all_data()

def get_crawler_statistics():
    """Main function to get comprehensive crawler statistics"""
    return crawler_service.get_statistics()

def get_visited_urls_stats():
    """Get statistics about visited URLs"""
    try:
        visited_file = os.path.join(DATA_DIR, "visited_urls.data")
        
        if not os.path.exists(visited_file):
            return {
                "total_urls": 0,
                "crawlers": {},
                "recent_visits": []
            }
        
        stats = {
            "total_urls": 0,
            "crawlers": {},
            "recent_visits": [],
            "domains": {},
            "first_visit": None,
            "last_visit": None
        }
        
        with open(visited_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    from urllib.parse import urlparse
                    from datetime import datetime
                    
                    # Space-separated format: URL CRAWLER_ID DATETIME
                    parts = line.split()
                    
                    if len(parts) >= 3:
                        url = parts[0]
                        crawler_id = parts[1]
                        visited_at = parts[2]
                        
                        # Convert datetime to timestamp for sorting
                        try:
                            dt = datetime.fromisoformat(visited_at.replace('Z', '+00:00'))
                            timestamp = dt.timestamp()
                        except:
                            timestamp = 0
                        
                        if url.startswith(('http://', 'https://')):
                            stats["total_urls"] += 1
                            
                            # Track by crawler
                            if crawler_id not in stats["crawlers"]:
                                stats["crawlers"][crawler_id] = {
                                    "count": 0,
                                    "first_visit": visited_at,
                                    "last_visit": visited_at
                                }
                            stats["crawlers"][crawler_id]["count"] += 1
                            stats["crawlers"][crawler_id]["last_visit"] = visited_at
                            
                            # Track by domain
                            try:
                                domain = urlparse(url).netloc
                                if domain:
                                    stats["domains"][domain] = stats["domains"].get(domain, 0) + 1
                            except:
                                pass
                            
                            # Track recent visits (last 10)
                            if len(stats["recent_visits"]) < 10:
                                stats["recent_visits"].append({
                                    "url": url,
                                    "crawler_id": crawler_id,
                                    "visited_at": visited_at
                                })
                            
                            # Track first/last visit times
                            if not stats["first_visit"] or timestamp < stats.get("first_timestamp", float('inf')):
                                stats["first_visit"] = visited_at
                                stats["first_timestamp"] = timestamp
                            if not stats["last_visit"] or timestamp > stats.get("last_timestamp", 0):
                                stats["last_visit"] = visited_at
                                stats["last_timestamp"] = timestamp
        
        # Clean up temporary fields
        stats.pop("first_timestamp", None)
        stats.pop("last_timestamp", None)
        
        return stats
        
    except Exception as e:
        return {"error": f"Error analyzing visited URLs: {e}"}
