from scrapling.fetchers import StealthyFetcher
from urllib.parse import urlparse
import asyncio
import json
import pandas as pd
import logging, sys, pathlib
import urllib.parse
import os
import random
import time
from datetime import datetime, timedelta




# File configurations
LOG_FILE = pathlib.Path("harris_teeter_scrape.log")

BASE_FILE = pathlib.Path(__file__).resolve().parent

PARENT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(PARENT_DIR))
from RateLimiter import RateLimiter

CHECKPOINT_FILE = BASE_FILE / "ht_scraping/ht_scraping_checkpoint.json"
# TODO: Remember this selection for next time?
SOURCE_EXCEL = input("📁 Enter path to your input XLSX file: ").strip().strip('"\'')
OUTPUT_EXCEL = BASE_FILE / "harris_teeter_price_compare/harris_teeter_pc.xlsx"  # Final results
TEMP_RESULTS_FILE = BASE_FILE / "ht_scraping/temp_session_results.json"

# Scraping configurations
BATCH_SIZE = 26  # Conservative batch size
MAX_REQUESTS_PER_SESSION = 99999  # Stop after this many requests
SESSION_TIMEOUT_MINUTES = 10  # Auto-pause after this time
QUERIES = ["cheerios", "cinnamon", "apples", "hazelnut", "peanet", "milk", "eggs"]
USER_AGENTs = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
]

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
        return self.current_batch_failures >= 1

    def wait_for_user_continue(self):
        """Wait for user to change VPN and continue"""
        print(f"\n🛑 1 consecutive batch failures detected!")
        print("📍 Please change your VPN location/IP address")
        print("🔄 Press Enter when ready to continue with the same batch...")
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
    def __init__(self, source_file=SOURCE_EXCEL, output_file=OUTPUT_EXCEL):
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
            required_columns = ['UPC']  # Add other required columns
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
            original_upc = str(row.get('UPC', ''))
            original_upc = upc_to_gtin13(original_upc)  # Ensure UPC is in GTIN-13 format
            # Add scraped data
            scraped_data = result['data']
            if scraped_data:
                scraped_upc = str(scraped_data.get('upc', ''))
                # Verify UPC matches (add warning if mismatch)
                upc_match = original_upc == scraped_upc
                if not upc_match and scraped_upc:
                    print(f"⚠️ UPC mismatch at row {result['index']}: Expected {original_upc}, Got {scraped_upc}")
                
                row.update({
                    'scraped_upc': scraped_upc,
                    'scraped_price': scraped_data.get('price'),
                    'scraped_size': scraped_data.get('size'),
                    'scraped_description': scraped_data.get('description'),
                    'scraped_timestamp': result['timestamp'],
                    'scraping_status': 'success',
                    'upc_match': upc_match
                })
            else:
                row.update({
                    'scraped_upc': None,
                    'scraped_price': None,
                    'scraped_size': None,
                    'scraped_description': None,
                    'scraped_timestamp': result['timestamp'],
                    'scraping_status': 'failed',
                    'upc_match': None
                })
            
            results_data.append(row)
    
        
        # Save to Excel
        results_df = pd.DataFrame(results_data)
        results_df.to_excel(self.output_file, index=False)
        print(f"💾 Saved {len(results_data)} results to {self.output_file}")
        if 'upc_match' in results_df.columns:
            mismatches = results_df['upc_match'] == False
            if mismatches.any():
                mismatch_count = mismatches.sum()
                print(f"⚠️ WARNING: {mismatch_count} UPC mismatches detected in results!")
                print("📋 Check the 'upc_match' column in the output file")

    
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
        
        # Only check time limit now (removed request limit check)
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

# Global variables
laf_object = None
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

async def set_zip_harTeet(page, zipcode):
    """Setup Harris Teeter store selection"""
    print("🛠️ Setting up Harris Teeter store...")
    global laf_object
    
    await page.wait_for_selector("button[data-testid = 'CurrentModality-button']", timeout=5000)
    await page.click("button[data-testid = 'CurrentModality-button']", timeout=5000)
    await page.wait_for_selector("button[data-testid = 'ModalityOption-Button-PICKUP']", timeout=5000)
    await page.click("button[data-testid = 'ModalityOption-Button-PICKUP']", timeout=5000)
    await page.fill("input[data-testid='PostalCodeSearchBox-input']", zipcode, timeout=5000)
    await page.click("button[aria-label = 'Search']", timeout=5000)
    print("✅ search clicked")
    await page.wait_for_selector("button[data-testid = 'SelectStore-09700352']", timeout=5000)
    await page.click("button[data-testid = 'SelectStore-09700352']", timeout=5000)
    # Find a more robust way to do this
    await page.wait_for_timeout(5000)
    page.on("request", on_request)  
    await page.goto("https://www.harristeeter.com/search?query=nutella&searchType=default_search", timeout=10000)
    await page.wait_for_timeout(4000)
    
    if not laf_object:
        raise RuntimeError("❌ No laf_object captured from requests. Ensure you clicked the store selector.")

async def create_stealth_context(browser):
    """Create stealth browser context"""
    context = await browser.new_context(
        user_agent=random.choice(USER_AGENTs),
        viewport={'width': random.randint(1200, 1920), 'height': random.randint(800, 1080)},
        extra_http_headers={
            'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.9', 'en-CA,en;q=0.9']),
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
        }
    )
    return context

async def fetch_ht_batch(gtin_list, page, laf_object, query_url):
    """Fetch Harris Teeter batch data"""
    url = build_ht_url(gtin_list)
    results = []
    
    common_headers = {
        "Accept": "application/json, text/plain, */*",
        'accept-language': 'en,en-US;q=0.9',
        'cache-control': 'no-cache',
        "x-laf-object": laf_object,
        'device-memory': '8',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': query_url,
        'sec-ch-ua': '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'user-time-zone': 'America/New_York',
        "x-ab-test": '[{"testVersion":"B","testID":"5388ca","testOrigin":"cb"}]',
        "x-call-origin": '{"component":"internal search","page":"internal search"}',
        "x-facility-id": "09700352",
        'x-geo-location-v1': '{"id":"b9c9c75e-930e-4073-9f2b-cee2aa4fa318","proxyStore":"09700819"}',
        "x-kroger-channel": "WEB",
        'x-modality': '{"type":"PICKUP","locationId":"09700352"}',
        'x-modality-type': 'PICKUP'
    }
    
    try:
        response = await page.context.request.get(url, headers=common_headers)
        if response.status in [429, 403, 503, 520, 521, 522, 523, 524]:
            raise Exception(f"Throttled with status {response.status}")
        
        if response.status == 200:
            data = await response.json()
            for prod in data["data"]["products"]:
                pickup_summary = next((summary for summary in prod["fulfillmentSummaries"] 
                                     if summary["type"] == "PICKUP"), None)
                if pickup_summary:
                    results.append({
                        "upc": prod["item"]["upc"],
                        "price": pickup_summary["regular"]["price"],
                        "size": pickup_summary["regular"]["pricePerUnitString"],
                        "description": prod["item"]["description"]
                    })
                else:
                    results.append({
                        "upc": prod["item"]["upc"],
                        "price": None,
                        "size": None,
                        "description": prod["item"]["description"]
                    })
        
        return results
        
    except Exception as e:
        print(f"❌ Request failed: {e}")
        raise

async def scrape_checkpoint_session():
    """Main checkpoint-based scraping session"""
    checkpoint_manager = CheckpointManager()
    excel_manager = ExcelManager()
    session_manager = SessionManager()
    rate_limiter = RateLimiter()
    
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
    print(f"📊 Progress: {stats['completed']}/{stats['total']} ({stats['completion_percentage']:.1f}%) complete")
    print(f"🎯 Remaining: {stats['remaining']} items")
    
    # Start session
    checkpoint_manager.start_new_session()
    session_manager.start_session()
    
    url = "https://www.harristeeter.com"
    domain = urlparse(url).netloc.replace("www.", "")
    ht_locstr = "20002"
    
    async def page_action(page):
        await set_zip_harTeet(page, ht_locstr)
        
        # Main scraping loop
        while not session_manager.should_pause():
            # Get next batch
            batch_data = checkpoint_manager.get_next_batch(excel_manager.source_data, BATCH_SIZE)
            if not batch_data:
                print("✅ All items completed!")
                break
            
            if checkpoint_manager.should_pause_for_failures():
                checkpoint_manager.wait_for_user_continue()

            print(f"🔄 Processing batch of {len(batch_data)} items...")
            
            # Process batch
            upc_list = [str(row_data['UPC']) for _, row_data in batch_data]
            
            try:
                #await rate_limiter.wait_before_request()
                
                # Navigate to random search
                rand_query = random.choice(QUERIES)
                query_url = build_query_url(rand_query)
                await page.goto(query_url, timeout=15000)
                await asyncio.sleep(random.uniform(2.0, 5.0))
                
                # Fetch data
                batch_results = await fetch_ht_batch(upc_list, page, laf_object, query_url)
                
                upc_to_result = {}
                for result in batch_results:
                    if result and result.get('upc'):
                        upc_to_result[str(result['upc'])] = result
                
                # Process results in the correct order matching our batch_data
                for index, row_data in batch_data:
                    original_upc = str(row_data['UPC'])
                    original_upc = upc_to_gtin13(original_upc)  # Ensure UPC is in GTIN-13 format
                    # Find the matching result for this specific UPC
                    matched_result = upc_to_result.get(original_upc)
                    
                    if matched_result:
                        print(f"✅ Found result for UPC {original_upc}")
                    else:
                        print(f"⚠️ No result found for UPC {original_upc}")
                        matched_result = None
                    
                    checkpoint_manager.mark_completed(index, matched_result)
                    session_manager.record_request()
                
                rate_limiter.record_success()
                checkpoint_manager.reset_batch_failures()
                successful_count = len([r for r in batch_results if r])
                print(f"✅ Batch completed: {successful_count}/{len(batch_data)} successful results")
                print(f"✅ Batch completed: {len(batch_results)} results")
                
                # Save checkpoint periodically
                checkpoint_manager.save_checkpoint()
                
                # Brief delay between batches
                await asyncio.sleep(random.uniform(5.0, 10.0))
                
            except Exception as e:
                print(f"❌ Batch failed: {e}")
                rate_limiter.record_failure()
                checkpoint_manager.record_batch_failure()

                # # Mark items as failed (you might want to retry these)
                # for index, row_data in batch_data:
                #     checkpoint_manager.mark_completed(index, None)  # None indicates failure
                
                # Longer delay on failure
                await asyncio.sleep(3.0)
        
        # Session ended
        session_stats = session_manager.get_session_stats()
        print(f"⏹️ Session ended after {session_stats['requests_made']} requests in {session_stats['elapsed_minutes']:.1f} minutes")
        
        # Save final results
        checkpoint_manager.save_checkpoint()
        excel_manager.save_results(checkpoint_manager)
        
        # Show completion status
        final_stats = excel_manager.get_completion_stats(checkpoint_manager)
        print(f"📊 Session complete: {final_stats['completed']}/{final_stats['total']} ({final_stats['completion_percentage']:.1f}%)")
        
        if final_stats['remaining'] > 0:
            print(f"🔄 {final_stats['remaining']} items remaining. Change your VPN/IP and run again to continue.")
        else:
            print("🎉 All scraping complete!")
        
        return page
    
    await StealthyFetcher.async_fetch(
        url=url,
        headless=False,
        network_idle=True,
        block_images=False,
        disable_resources=False,
        page_action=page_action
    )

def build_query_url(query):
    base_url = "https://www.harristeeter.com/search"
    suffix = "&searchType=default_search"
    return f"{base_url}?query={urllib.parse.quote(query)}{suffix}"

def build_ht_url(gtin_batch):
    base_url = "https://www.harristeeter.com/atlas/v1/product/v2/products"
    gtin_params = "&".join([f"filter.gtin13s={upc_to_gtin13(gtin)}" for gtin in gtin_batch])
    suffix = (
        "&filter.verified=true"
        "&projections=items.full,offers.compact,nutrition.label,variantGroupings.compact"
    )
    full_url = f"{base_url}?{gtin_params}{suffix}"
    return full_url

def on_request(request):
    global laf_object
    if "atlas/v1/product/v2/products" in request.url and request.headers.get("x-laf-object"):
        laf_object = request.headers["x-laf-object"]
        print("📦 Captured laf_object")
    return laf_object

def upc_to_gtin13(upc12):
    core = upc12[:-1]
    return core.zfill(13)

# Utility functions for manual control
def show_progress():
    """Show current progress"""
    checkpoint_manager = CheckpointManager()
    excel_manager = ExcelManager()
    stats = excel_manager.get_completion_stats(checkpoint_manager)
    
    print(f"📊 Current Progress:")
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

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            show_progress()
        elif sys.argv[1] == "reset":
            reset_checkpoint()
        else:
            print("Usage: python script.py [status|reset]")
    else:
        # Run main scraping session
        asyncio.run(scrape_checkpoint_session())