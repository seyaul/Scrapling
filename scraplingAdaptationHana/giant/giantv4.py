import asyncio
import json
from scrapling.fetchers import StealthyFetcher
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
import random
import pandas as pd
import os
from datetime import datetime, timedelta
import logging
import sys
import pathlib

BASE_FILE = pathlib.Path(__file__).resolve().parent

# File configurations
SOURCE_DATA = input("📁 Enter path to your input XLSX file: ").strip().strip('"\'')
OUTPUT_DATA = BASE_FILE / "giant_price_compare/giant_foods_pc.xlsx"
CHECKPOINT_FILE = BASE_FILE / "giant_scraping/scraping_checkpoint_giant.json"
TEMP_RESULTS_FILE = BASE_FILE / "giant_scraping/temp_session_results_giant.json"
LOG_FILE = BASE_FILE / ".giant_log/giant_foods_scrape.log"

# Scraping configurations
BATCH_SIZE = 10  # Process 10 items at a time
MAX_REQUESTS_PER_SESSION = 465  # Stop after this many requests
SESSION_TIMEOUT_MINUTES = 60  # Auto-pause after this time
MIN_DELAY = 2.0  # Minimum delay between requests
MAX_DELAY = 5.0  # Maximum delay between requests
ZIP_CODE = "20010"  # Default ZIP code
STORE_ADDRESS = "1345 Park Road N.W." 

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

class CheckpointManager:
    def __init__(self, checkpoint_file=CHECKPOINT_FILE):
        self.checkpoint_file = checkpoint_file
        self.checkpoint_data = self.load_checkpoint()
        self.current_batch_failures = 0

    def load_checkpoint(self):
        """Load existing checkpoint or create new one"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                    print(f"📂 Loaded checkpoint: {data['completed_count']}/{data['total_count']} completed")
                    return data
            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠️ Corrupted checkpoint file, starting fresh: {e}")
        
        return {
            'completed_indices': [],
            'completed_count': 0,
            'total_count': 0,
            'last_session_start': None,
            'session_count': 0,
            'results': []
        }
    
    def save_checkpoint(self):
        """Save current progress"""
        self.checkpoint_data['last_updated'] = datetime.now().isoformat()
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.checkpoint_data, f, indent=2)
        print(f"💾 Checkpoint saved: {self.checkpoint_data['completed_count']}/{self.checkpoint_data['total_count']}")
    
    def mark_completed(self, index, result_data):
        """Mark an item as completed"""
        if index not in self.checkpoint_data['completed_indices']:
            self.checkpoint_data['completed_indices'].append(index)
            self.checkpoint_data['completed_count'] += 1
            self.checkpoint_data['results'].append({
                'index': index,
                'data': result_data,
                'timestamp': datetime.now().isoformat()
            })
    
    def record_batch_failure(self):
        """Record a batch failure"""
        self.current_batch_failures += 1
        print(f"⚠️ Batch failure #{self.current_batch_failures}")

    def reset_batch_failures(self):
        """Reset batch failure counter"""
        self.current_batch_failures = 0

    def should_pause_for_failures(self):
        """Check if should pause due to repeated failures"""
        return self.current_batch_failures >= 3

    def wait_for_user_continue(self):
        """Wait for user to change VPN and continue"""
        print(f"\n🛑 {self.current_batch_failures} consecutive batch failures detected!")
        print("📍 Please change your VPN location/IP address")
        print("🔄 Press Enter when ready to continue...")
        input()
        self.reset_batch_failures()
        print("▶️ Resuming scraping...")
    
    def get_next_batch(self, source_data, batch_size=BATCH_SIZE):
        """Get next batch of items to process"""
        completed_set = set(self.checkpoint_data['completed_indices'])
        remaining_indices = [i for i in range(len(source_data)) if i not in completed_set]
        
        if not remaining_indices:
            return []
        
        # Get next batch
        batch_indices = remaining_indices[:batch_size]
        batch_data = [(i, source_data.iloc[i]) for i in batch_indices]
        
        return batch_data
    
    def is_complete(self, total_count):
        """Check if scraping is complete"""
        return self.checkpoint_data['completed_count'] >= total_count
    
    def start_new_session(self):
        """Mark start of new session"""
        self.checkpoint_data['session_count'] += 1
        self.checkpoint_data['last_session_start'] = datetime.now().isoformat()
        print(f"🚀 Starting session #{self.checkpoint_data['session_count']}")

class ExcelManager:
    def __init__(self, source_file=SOURCE_DATA, output_file=OUTPUT_DATA):
        self.source_file = source_file
        self.output_file = output_file
        self.source_data = None
        self.load_source_data()
    
    def load_source_data(self):
        """Load source Excel file"""
        try:
            self.source_data = pd.read_excel(self.source_file)
            print(f"📊 Loaded {len(self.source_data)} items from {self.source_file}")
            
            # Validate required columns
            required_columns = ['UPC']  # Add other required columns as needed
            missing_columns = [col for col in required_columns if col not in self.source_data.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
        except Exception as e:
            print(f"❌ Error loading source file: {e}")
            raise
    
    def save_results(self, checkpoint_manager):
        """Save results to Excel file"""
        if not checkpoint_manager.checkpoint_data['results']:
            print("⚠️ No results to save")
            return
        
        # Create results dataframe
        results_data = []
        sorted_results = sorted(checkpoint_manager.checkpoint_data['results'], 
                              key=lambda x: x['index'])
        
        for result in sorted_results:
            row = self.source_data.iloc[result['index']].to_dict()
            
            # Add scraped data
            scraped_data = result['data']
            if scraped_data:
                row.update({
                    'scraped_upc': scraped_data.get('upc'),
                    'scraped_price': scraped_data.get('price'),
                    'scraped_size': scraped_data.get('size'),
                    'scraped_name': scraped_data.get('name'),
                    'scraped_timestamp': result['timestamp'],
                    'scraping_status': 'success'
                })
            else:
                row.update({
                    'scraped_upc': None,
                    'scraped_price': None,
                    'scraped_size': None,
                    'scraped_name': None,
                    'scraped_timestamp': result['timestamp'],
                    'scraping_status': 'failed'
                })
            
            results_data.append(row)
        
        # Save to Excel
        results_df = pd.DataFrame(results_data)
        results_df.to_excel(self.output_file, index=False)
        print(f"💾 Saved {len(results_data)} results to {self.output_file}")
    
    def get_completion_stats(self, checkpoint_manager):
        """Get completion statistics"""
        total = len(self.source_data)
        completed = checkpoint_manager.checkpoint_data['completed_count']
        remaining = total - completed
        
        return {
            'total': total,
            'completed': completed,
            'remaining': remaining,
            'completion_percentage': (completed / total * 100) if total > 0 else 0
        }

class SessionManager:
    def __init__(self, max_requests=MAX_REQUESTS_PER_SESSION, timeout_minutes=SESSION_TIMEOUT_MINUTES):
        self.max_requests = max_requests
        self.timeout_minutes = timeout_minutes
        self.requests_made = 0
        self.session_start_time = None
        self.paused = False
    
    def start_session(self):
        """Start a new session"""
        self.requests_made = 0
        self.session_start_time = datetime.now()
        self.paused = False
        print(f"▶️ Session started at {self.session_start_time.strftime('%H:%M:%S')}")
    
    def should_pause(self):
        """Check if session should be paused"""
        if self.paused:
            return True
        
        # Check request limit
        if self.requests_made >= self.max_requests:
            print(f"🛑 Request limit reached ({self.max_requests} requests)")
            return True
        
        # Check time limit
        if self.session_start_time:
            elapsed = datetime.now() - self.session_start_time
            if elapsed.total_seconds() > (self.timeout_minutes * 60):
                print(f"🛑 Time limit reached ({self.timeout_minutes} minutes)")
                return True
        
        return False
    
    def record_request(self):
        """Record a request made"""
        self.requests_made += 1
    
    def pause_session(self):
        """Manually pause the session"""
        self.paused = True
        print("⏸️ Session manually paused")
    
    def get_session_stats(self):
        """Get current session statistics"""
        elapsed = datetime.now() - self.session_start_time if self.session_start_time else timedelta(0)
        return {
            'requests_made': self.requests_made,
            'max_requests': self.max_requests,
            'elapsed_minutes': elapsed.total_seconds() / 60,
            'timeout_minutes': self.timeout_minutes
        }

async def fetch_upc_via_playwright(checkpoint_manager, excel_manager):
    async def page_action(page):
        # Store all API responses
        api_responses = []
        
        # Set up response listener for ALL requests
        async def handle_response(response):
            if "/api/v6.0/products" in response.url:
                try:
                    data = await response.json()
                    api_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'data': data
                    })
                    log.info(f"📡 Captured API response: {response.url}")
                except Exception as e:
                    log.error(f"❌ Error parsing response: {e}")
        
        # Attach the listener
        page.on("response", handle_response)
        
        # Navigate to Giant homepage
        await page.goto("https://giantfood.com", timeout=30000)

        # Fill in ZIP code and select store
        await page.wait_for_selector('button.robot-shopping-mode-location', timeout=30000)
        await page.click('button.robot-shopping-mode-location', timeout=5000)
        await page.fill("input[name='zipCode']", ZIP_CODE)  
        await page.click('#search-location', timeout=5000)
        await page.wait_for_timeout(1000)
        address = page.locator("li", has_text=STORE_ADDRESS)
        await address.locator("button").click(timeout=7000)
        await page.wait_for_timeout(10000)
        print("🌐 Giant Foods location selected, starting product search...")

        # Create session manager
        session_manager = SessionManager()
        session_manager.start_session()

        # Main scraping loop
        # Main scraping loop
        while not session_manager.should_pause():
            # Get all remaining items (not completed)
            completed_set = set(checkpoint_manager.checkpoint_data['completed_indices'])
            remaining_indices = [i for i in range(len(excel_manager.source_data)) if i not in completed_set]
            
            if not remaining_indices:
                print("✅ All items completed!")
                break
            
            print(f"\n📊 Progress: {len(completed_set)}/{len(excel_manager.source_data)} completed ({len(completed_set)/len(excel_manager.source_data)})%")
            print(f"🎯 {len(remaining_indices)} items remaining")
            
            # Process next item
            item_index = remaining_indices[0]
            row_data = excel_manager.source_data.iloc[item_index]
            upc = str(row_data['UPC'])
            
            print(f"\n🔍 Fetching product for UPC: {upc} (index: {item_index})")
            search_url = f"https://giantfood.com/product-search/{upc}?semanticSearch=false"
            
            # Clear previous responses
            api_responses.clear()
            
            # Keep trying until successful
            while True:
                try:
                    # Navigate and wait for the page to load
                    await page.goto(search_url, timeout=30000)
                    
                    # Wait for network idle
                    await page.wait_for_load_state("networkidle", timeout=17000)
                    
                    # If no response yet, wait a bit more
                    if not api_responses:
                        log.info("⏳ Waiting for API response...")
                        await page.wait_for_timeout(3000)
                    
                    # Process the captured responses
                    result_data = None
                    if api_responses:
                        valid_responses = [r for r in api_responses if r['status'] == 200]
                        if valid_responses:
                            response_data = valid_responses[-1]['data']
                            response = response_data.get('response', {})
                            products = response.get("products", [])
                            
                            if products:
                                product = products[0]
                                result_data = {
                                    'price': product.get('price'),
                                    'upc': product.get('upc'),
                                    'size': product.get('size'),
                                    'name': product.get('name')
                                }
                                print(f"✅ Found: {product.get('name', 'Unknown')} - ${product.get('price', 'N/A')}")
                                checkpoint_manager.mark_completed(item_index, result_data)
                                checkpoint_manager.save_checkpoint()
                                session_manager.record_request()
                            else:
                                print(f"⚠️ No products found for UPC: {upc}")
                                checkpoint_manager.mark_completed(item_index, result_data)
                                checkpoint_manager.save_checkpoint()
                                session_manager.record_request()
                        else:
                            print(f"❌ No successful API responses for UPC: {upc}")
                            print(f"\n🛑 Request failed!")
                            print("💡 This likely means you've been throttled.")
                            print("🔄 Please change your VPN location/IP address")
                            print("📌 Press Enter when ready to retry this UPC...")
                            input()
                            print("🔄 Retrying...")
                    else:
                        print(f"❌ No API responses captured for UPC: {upc}")
                        print(f"\n🛑 Request failed!")
                        print("💡 This likely means you've been throttled.")
                        print("🔄 Please change your VPN location/IP address")
                        print("📌 Press Enter when ready to retry this UPC...")
                        input()
                        print("🔄 Retrying...")
                    
                    # Mark as completed and save immediately
                    
                    
                    # Success - break out of retry loop
                    break
                    
                except (PlaywrightTimeoutError) as e:
                    error_type = "Timeout" if isinstance(e, PlaywrightTimeoutError) else "Error"
                    log.error(f"❌ {error_type} for UPC {upc}: {e}")
                    print(f"\n🛑 Request failed!")
                    print(f"📍 Error: {str(e)}")
                    print("💡 This likely means you've been throttled.")
                    print("🔄 Please change your VPN location/IP address")
                    print("📌 Press Enter when ready to retry this UPC...")
                    input()
                    print("🔄 Retrying...")
                except Exception as e:
                    raise e
                    # Loop will continue and retry the same UPC
            
            # Delay before next item
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            log.info(f"💤 Waiting {delay:.1f} seconds before next item...")
            await asyncio.sleep(delay)
        
        # Session ended
        session_stats = session_manager.get_session_stats()
        print(f"\n⏹️ Session ended after {session_stats['requests_made']} requests in {session_stats['elapsed_minutes']:.1f} minutes")
        
        return page

    # Launch browser and run the page_action
    await StealthyFetcher.async_fetch(
        url="https://giantfood.com",
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

async def scrape_with_checkpoint():
    """Main function to run checkpoint-based scraping"""
    checkpoint_manager = CheckpointManager()
    excel_manager = ExcelManager()
    
    # Initialize checkpoint if first run
    if checkpoint_manager.checkpoint_data['total_count'] == 0:
        checkpoint_manager.checkpoint_data['total_count'] = len(excel_manager.source_data)
    
    # Check if already complete
    if checkpoint_manager.is_complete(len(excel_manager.source_data)):
        print("🎉 Scraping already complete!")
        excel_manager.save_results(checkpoint_manager)
        return
    
    # Show progress
    stats = excel_manager.get_completion_stats(checkpoint_manager)
    print(f"\n📊 Current Progress:")
    print(f"   Total items: {stats['total']}")
    print(f"   Completed: {stats['completed']}")
    print(f"   Remaining: {stats['remaining']}")
    print(f"   Progress: {stats['completion_percentage']:.1f}%")
    
    # Start session
    checkpoint_manager.start_new_session()
    
    try:
        # Run scraping
        await fetch_upc_via_playwright(checkpoint_manager, excel_manager)
    finally:
        # Always save results at the end
        checkpoint_manager.save_checkpoint()
        excel_manager.save_results(checkpoint_manager)
        
        # Show final status
        final_stats = excel_manager.get_completion_stats(checkpoint_manager)
        print(f"\n📊 Session Summary:")
        print(f"   Completed: {final_stats['completed']}/{final_stats['total']} ({final_stats['completion_percentage']:.1f}%)")
        
        if final_stats['remaining'] > 0:
            print(f"\n🔄 {final_stats['remaining']} items remaining.")
            print("💡 Change your VPN/IP and run again to continue.")
        else:
            print("\n🎉 All scraping complete!")

# Utility functions
def show_progress():
    """Show current progress"""
    checkpoint_manager = CheckpointManager()
    excel_manager = ExcelManager()
    stats = excel_manager.get_completion_stats(checkpoint_manager)
    
    print(f"\n📊 Current Progress:")
    print(f"   Total items: {stats['total']}")
    print(f"   Completed: {stats['completed']}")
    print(f"   Remaining: {stats['remaining']}")
    print(f"   Progress: {stats['completion_percentage']:.1f}%")
    
    if stats['remaining'] > 0:
        print(f"\n🔄 Ready to continue scraping {stats['remaining']} items")
        print("💡 Make sure to change your VPN location before continuing")

def reset_checkpoint():
    """Reset checkpoint to start over"""
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("🔄 Checkpoint reset. Will start from beginning.")
    else:
        print("ℹ️ No checkpoint file found.")

def export_results():
    """Export current results to Excel"""
    checkpoint_manager = CheckpointManager()
    excel_manager = ExcelManager()
    excel_manager.save_results(checkpoint_manager)
    print(f"📊 Results exported to {OUTPUT_DATA}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            show_progress()
        elif sys.argv[1] == "reset":
            reset_checkpoint()
        elif sys.argv[1] == "export":
            export_results()
        else:
            print("Usage: python giantv3_checkpoint.py [status|reset|export]")
            print("  status - Show current scraping progress")
            print("  reset  - Reset checkpoint and start over")
            print("  export - Export current results to Excel")
            print("  (no args) - Run scraping session")
    else:
        # Run main scraping session
        asyncio.run(scrape_with_checkpoint())