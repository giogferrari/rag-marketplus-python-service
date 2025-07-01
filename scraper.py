# market_service.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
from playwright.async_api import async_playwright
import base64
import re
from collections import defaultdict
from typing import List, Dict, Any
import uvicorn
import random
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def strip_html(html):
    return re.sub('<[^<]+?>', '', html) if html else html

class ItemResponse(BaseModel):
    items: List[Dict[str, Any]]
    total_items: int
    pages_processed: int

async def process_page(browser, item_name_b64, page_number, results):
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="America/New_York",
        java_script_enabled=True,
        has_touch=False,
        is_mobile=False,
        bypass_csp=False,
        ignore_https_errors=False,
    )
    
    await context.add_init_script("""
    delete Object.getPrototypeOf(navigator).webdriver;
    window.navigator.chrome = {
        runtime: {},
    };
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
    });
    """)
    
    page = await context.new_page()
    
    itens = []
    processed = False
    
    async def handle_response(response):
        nonlocal processed
        if "api.ragnatales.com.br/market" in response.url and response.status == 200:
            try:
                json_data = await response.json()
                rows = json_data.get("rows", [])

                for row in rows:
                    if 'data' in row and 'description' in row['data']:
                        row['data']['description'] = strip_html(row['data']['description'])
                    itens.append(row)

                print(f"Page {page_number} loaded with {len(rows)} items")
                processed = True
            except Exception as e:
                print(f"Error processing page {page_number}: {e}")

    page.on("response", handle_response)
    
    base_url = "https://ragnatales.com.br/market"
    url = f"{base_url}?page={page_number}&query={item_name_b64}"
    print(f"Accessing: {url}")
    
    try:
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
        
        # Random delays between actions
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        await page.evaluate("""async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 100;
                const timer = setInterval(() => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    
                    if(totalHeight >= scrollHeight || totalHeight > 2000){
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }""")
        
        start_time = time.time()
        while not processed and time.time() - start_time < 30:
            await asyncio.sleep(1)
            
        if not processed:
            print(f"Timeout waiting for API response on page {page_number}")
    except Exception as e:
        print(f"Error accessing page {page_number}: {e}")
    finally:
        await context.close()
    
    results[page_number] = itens

@app.get("/api/items", response_model=ItemResponse)
async def get_items(item_name: str, max_pages: int = 5, concurrency: int = 2):
    item_name_b64 = base64.b64encode(item_name.encode()).decode()
    
    launch_options = {
        "headless": False,
        "slow_mo": 100,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--start-maximized",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--disable-extensions",
        ],
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_options)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()
        
        total_pages = 1
        url = f"https://ragnatales.com.br/market?page=1&query={item_name_b64}"
        
        try:
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            if await page.query_selector("text=Checking your browser before accessing"):
                print("Cloudflare challenge detected, waiting...")
                await page.wait_for_selector("text=Checking your browser before accessing", state="hidden", timeout=60000)
            
            async def get_total_pages(response):
                nonlocal total_pages
                if "api.ragnatales.com.br/market" in response.url and response.status == 200:
                    try:
                        json_data = await response.json()
                        total_pages = min(json_data.get("total_pages", 1), max_pages)
                        print(f"ℹ️ Total pages found: {total_pages}")
                    except:
                        pass
            
            page.on("response", get_total_pages)
            
            await asyncio.sleep(random.uniform(2.0, 5.0))
            
        except Exception as e:
            print(f"Initial page load failed: {e}")
            raise HTTPException(status_code=503, detail="Service temporarily unavailable")
        finally:
            await context.close()
            await browser.close()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(**launch_options)
        results = defaultdict(list)
        
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_task(page_num):
            async with semaphore:
                await asyncio.sleep(random.uniform(0.5, 2.0))
                return await process_page(browser, item_name_b64, page_num, results)
        
        try:
            await asyncio.gather(*[
                limited_task(page_num) 
                for page_num in range(1, total_pages + 1)
            ])
        except Exception as e:
            print(f"Error during parallel processing: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
        finally:
            await browser.close()
    
    # Combine and return results
    all_items = []
    for page_num in sorted(results.keys()):
        all_items.extend(results[page_num])
    
    return {
        "items": all_items,
        "total_items": len(all_items),
        "pages_processed": total_pages
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)