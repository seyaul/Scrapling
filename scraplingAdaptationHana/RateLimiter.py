import asyncio
import random
from typing import Optional

class RateLimiter:
    def __init__(self):
        self.consecutive_failures = 0
        self.last_request_time = 0
    async def wait_before_request(self):
        """Implement exponential backoff with jitter"""
        base_delay = 10.0  # Base delay in seconds
        
        if self.consecutive_failures > 0:
            # Exponential backoff: 2^failures * base_delay
            backoff_delay = (2 ** min(self.consecutive_failures, 6)) * base_delay
            jitter = random.uniform(0.5, 1.5)  # Add jitter
            delay = backoff_delay * jitter
            print(f"RateLimiter: Waiting {delay:.2f} seconds due to {self.consecutive_failures} consecutive failures.")
        else:
            delay = random.uniform(base_delay, base_delay * 2)
        
        # Ensure minimum time between requests
        time_since_last = asyncio.get_event_loop().time() - self.last_request_time
        if time_since_last < delay:
            await asyncio.sleep(delay - time_since_last)
        
        self.last_request_time = asyncio.get_event_loop().time()
    
    def record_success(self):
        self.consecutive_failures = 0
    
    def record_failure(self):
        self.consecutive_failures += 1