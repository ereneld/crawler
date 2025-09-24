import os
import json
import time
import threading
from utils.crawler_job import CrawlerJob

# Storage directories
DATA_DIR = "data"
CRAWLER_DIR = os.path.join(DATA_DIR, "crawlers")

class CrawlerService:
    """Service for managing crawler operations"""
    
    def __init__(self):
        self.active_crawlers = {}  # Track active crawler threads
    
    def create_crawler(self, origin, max_depth, hit_rate=100.0, max_queue_capacity=10000):
        """
        Create and start a new crawler job
        
        Args:
            origin (str): Starting URL
            max_depth (int): Maximum crawling depth
            hit_rate (float): Hits per second rate limiting
            max_queue_capacity (int): Maximum queue capacity
            
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
                max_queue_capacity=max_queue_capacity
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
            
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # Add live thread status if crawler is still active
                if crawler_id in self.active_crawlers:
                    crawler_thread = self.active_crawlers[crawler_id]
                    status_data["thread_alive"] = crawler_thread.is_alive()
                    
                    # Clean up finished threads
                    if not crawler_thread.is_alive():
                        del self.active_crawlers[crawler_id]
                
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
                                "timestamp": status_data.get("timestamp", 0)
                            })
                            
                        except json.JSONDecodeError:
                            continue
            
            # Sort by timestamp (newest first)
            crawlers.sort(key=lambda x: x["timestamp"], reverse=True)
            
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
                    # Note: Python threads cannot be forcefully stopped
                    # This is a limitation we acknowledge
                    return {
                        "message": "Crawler stop requested, but Python threads cannot be forcefully terminated. The crawler will finish its current operation and stop naturally.",
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

# Global crawler service instance
crawler_service = CrawlerService()

def create_crawler(origin, max_depth, hit_rate=100.0, max_queue_capacity=10000):
    """Main function to create a crawler job"""
    return crawler_service.create_crawler(origin, max_depth, hit_rate, max_queue_capacity)

def get_crawler_status(crawler_id):
    """Main function to get crawler status"""
    return crawler_service.get_crawler_status(crawler_id)

def list_all_crawlers():
    """Main function to list all crawlers"""
    return crawler_service.list_crawlers()

def stop_crawler(crawler_id):
    """Main function to stop a crawler"""
    return crawler_service.stop_crawler(crawler_id)
