#!/usr/bin/env python3
"""
Benchmark script to simulate load and measure CDN cache hit ratio.
"""
import asyncio
import aiohttp
import time
import random
import string
from datetime import datetime
import io

BASE_URL = "http://localhost:8000"
NUM_ASSETS = 10
NUM_REQUESTS = 100


async def upload_test_asset(session, asset_num):
    """Upload a test asset."""
    content = f"Test asset {asset_num} - " + "x" * 1000
    data = aiohttp.FormData()
    data.add_field('file', io.BytesIO(content.encode()), filename=f"test-asset-{asset_num}.txt")
    
    async with session.post(
        f"{BASE_URL}/assets/upload",
        data=data,
        params={"is_public": True}
    ) as resp:
        if resp.status == 200:
            return await resp.json()
    return None


async def download_asset(session, asset_id):
    """Download an asset and track response time."""
    start = time.time()
    async with session.get(f"{BASE_URL}/assets/assets/{asset_id}/download") as resp:
        content = await resp.read()
        elapsed = time.time() - start
        return {
            "status": resp.status,
            "time": elapsed,
            "from_cache": resp.headers.get("CF-Cache-Status") == "HIT" if "CF-Cache-Status" in resp.headers else None
        }


async def run_benchmark():
    """Run the benchmark."""
    print("=" * 80)
    print("HIGH-PERFORMANCE CONTENT DELIVERY API - BENCHMARK")
    print("=" * 80)
    
    async with aiohttp.ClientSession() as session:
        # Upload test assets
        print(f"\n[1] Uploading {NUM_ASSETS} test assets...")
        assets = []
        for i in range(NUM_ASSETS):
            asset = await upload_test_asset(session, i)
            if asset:
                assets.append(asset)
                print(f"  ✓ Uploaded {asset['filename']}")
        
        if not assets:
            print("ERROR: Failed to upload test assets")
            return
        
        print(f"\nSuccessfully uploaded {len(assets)} assets")
        
        # Warm up cache
        print(f"\n[2] Warming up cache with {len(assets)} requests...")
        for asset in assets:
            await download_asset(session, asset["id"])
        print("  ✓ Cache warming complete")
        
        # Run benchmark requests
        print(f"\n[3] Running {NUM_REQUESTS} benchmark requests...")
        results = []
        response_times = []
        
        for i in range(NUM_REQUESTS):
            asset = random.choice(assets)
            result = await download_asset(session, asset["id"])
            results.append(result)
            response_times.append(result["time"])
            
            if (i + 1) % 20 == 0:
                print(f"  Completed {i + 1}/{NUM_REQUESTS} requests")
        
        # Calculate statistics
        successful = sum(1 for r in results if r["status"] == 200)
        cache_hits = sum(1 for r in results if r["status"] == 304)
        cache_hit_ratio = (cache_hits / len(results) * 100) if results else 0
        
        avg_time = sum(response_times) / len(response_times)
        min_time = min(response_times)
        max_time = max(response_times)
        
        print("\n" + "=" * 80)
        print("BENCHMARK RESULTS")
        print("=" * 80)
        print(f"\nTotal Requests: {len(results)}")
        print(f"Successful Responses: {successful}")
        print(f"304 Not Modified Responses: {cache_hits}")
        print(f"\nCache Hit Ratio: {cache_hit_ratio:.2f}%")
        print(f"Average Response Time: {avg_time*1000:.2f}ms")
        print(f"Min Response Time: {min_time*1000:.2f}ms")
        print(f"Max Response Time: {max_time*1000:.2f}ms")
        
        print("\n" + "=" * 80)
        print("PERFORMANCE ANALYSIS")
        print("=" * 80)
        
        if cache_hit_ratio >= 95:
            print(f"✓ EXCELLENT: Cache hit ratio is {cache_hit_ratio:.2f}% (>95%)")
        elif cache_hit_ratio >= 80:
            print(f"✓ GOOD: Cache hit ratio is {cache_hit_ratio:.2f}% (>80%)")
        else:
            print(f"✗ NEEDS IMPROVEMENT: Cache hit ratio is {cache_hit_ratio:.2f}% (<80%)")
        
        if avg_time < 0.1:
            print(f"✓ EXCELLENT: Average response time is {avg_time*1000:.2f}ms (<100ms)")
        elif avg_time < 0.5:
            print(f"✓ GOOD: Average response time is {avg_time*1000:.2f}ms (<500ms)")
        else:
            print(f"✗ NEEDS IMPROVEMENT: Average response time is {avg_time*1000:.2f}ms (>500ms)")
        
        print("\n" + "=" * 80)
        print(f"Benchmark completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_benchmark())
