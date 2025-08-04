from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator  # Изменено с validator на field_validator
from datetime import datetime
import logging
from typing import List, Dict
import httpx
import asyncio
from bs4 import BeautifulSoup

app = FastAPI()

# Пример модели с валидатором для Pydantic v2
class Item(BaseModel):
    name: str
    
    @field_validator('name')
    def validate_name(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Name must be at least 3 characters long")
        return v

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DiscountRequest(BaseModel):
    country: str
    zip: str
    stores: List[str] = ["amazon", "walmart", "target", "slickdeals"]
    categories: List[str] = []  # new field

    @field_validator('zip')
    def validate_zip(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError("ZIP code must be 5 digits")
        return v

class DiscountAggregator:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = httpx.AsyncClient(timeout=30.0)

    async def fetch_slickdeals_by_zip(self, zipcode: str) -> List[Dict]:
        try:
            rss_url = f"https://slickdeals.net/newsearch.php?searcharea=deals&searchin=first&rss=1&zipcode={zipcode}"
            response = await self.session.get(rss_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'xml')

            deals = []
            for item in soup.find_all('item')[:10]:
                deal = {
                    'title': item.title.text.strip(),
                    'link': item.link.text.strip(),
                    'price': 'N/A',
                    'store': 'N/A',
                    'votes': '0',
                    'source': 'Slickdeals'
                }
                deals.append(deal)

            logger.info(f"Found {len(deals)} ZIP-specific Slickdeals")
            return deals
        except Exception as e:
            logger.error(f"Slickdeals RSS error: {e}")
            return []

    async def fetch_category_deals(self, zip_code: str, category: str) -> List[Dict]:
        try:
            category_map = {
                'restaurants': 'food-and-drink',
                'entertainment': 'things-to-do',
                'clothing': 'apparel'
            }
            cat_id = category_map.get(category)
            if not cat_id:
                return []
            rss_url = f"https://www.groupon.com/feeds/deals.xml?category={cat_id}"
            response = await self.session.get(rss_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'xml')

            deals = []
            for item in soup.find_all('item')[:10]:
                deal = {
                    'title': item.title.text.strip(),
                    'link': item.link.text.strip(),
                    'price': 'N/A',
                    'source': 'Groupon',
                    'category': category
                }
                deals.append(deal)
            logger.info(f"Found {len(deals)} {category} deals from Groupon")
            return deals
        except Exception as e:
            logger.error(f"Groupon RSS error for {category}: {e}")
            return []

    async def fetch_store_deals(self, store: str) -> List[Dict]:
        try:
            if store == "amazon":
                return await self.fetch_amazon_deals()
            elif store == "walmart":
                return await self.fetch_walmart_deals()
            elif store == "target":
                return await self.fetch_target_deals()
            return []
        except Exception as e:
            logger.error(f"Store {store} error: {e}")
            return []

    async def fetch_amazon_deals(self) -> List[Dict]:
        url = "https://www.amazon.com/international-sales-offers/b/?ie=UTF8&node=15529609011"
        response = await self.session.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        deals = []
        for item in soup.select('div.s-main-slot div[data-component-type="s-search-result"]'):
            title_el = item.select_one('h2 a span')
            link_el = item.select_one('h2 a')
            if not title_el or not link_el:
                continue
            deal = {
                'title': title_el.text.strip(),
                'link': f"https://www.amazon.com{link_el['href']}",
                'price': item.select_one('span.a-price > span').text.strip() if item.select_one('span.a-price > span') else 'N/A',
                'original_price': item.select_one('span.a-text-price').text.strip() if item.select_one('span.a-text-price') else 'N/A',
                'source': 'Amazon'
            }
            deals.append(deal)
        logger.info(f"Found {len(deals)} deals from Amazon")
        return deals[:10]

    async def fetch_walmart_deals(self) -> List[Dict]:
        url = "https://www.walmart.com/cp/rollback"
        response = await self.session.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        deals = []
        for item in soup.select('div.search-result-gridview-item-wrapper'):
            title_el = item.select_one('a.product-title-link span')
            link_el = item.select_one('a.product-title-link')
            if not title_el or not link_el:
                continue
            deal = {
                'title': title_el.text.strip(),
                'link': f"https://www.walmart.com{link_el['href']}",
                'price': item.select_one('span.price-main span.visuallyhidden').text.strip() if item.select_one('span.price-main span.visuallyhidden') else 'N/A',
                'original_price': item.select_one('span.price-strike').text.strip() if item.select_one('span.price-strike') else 'N/A',
                'source': 'Walmart'
            }
            deals.append(deal)
        logger.info(f"Found {len(deals)} deals from Walmart")
        return deals[:10]

    async def fetch_target_deals(self) -> List[Dict]:
        url = "https://www.target.com/c/clearance/-/N-5q0ga"
        response = await self.session.get(url, headers=self.headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        deals = []
        for item in soup.select('li.h-padding-a-none'):
            title_el = item.select_one('a[data-test="product-title"]')
            link_el = item.select_one('a[data-test="product-title"]')
            if not title_el or not link_el:
                continue
            deal = {
                'title': title_el.text.strip(),
                'link': f"https://www.target.com{link_el['href']}",
                'price': item.select_one('span[data-test="current-price"]').text.strip() if item.select_one('span[data-test="current-price"]') else 'N/A',
                'original_price': item.select_one('span[data-test="comparison-price"]').text.strip() if item.select_one('span[data-test="comparison-price"]') else 'N/A',
                'source': 'Target'
            }
            deals.append(deal)
        logger.info(f"Found {len(deals)} deals from Target")
        return deals[:10]

@app.get("/")
def read_root():
    return {"status": "Discount Aggregator API is running"}

@app.post("/api/get-discounts")
async def get_discounts(req: DiscountRequest):
    if req.country != "US":
        raise HTTPException(status_code=400, detail="Only USA is currently supported")

    try:
        aggregator = DiscountAggregator()

        slickdeals_task = aggregator.fetch_slickdeals_by_zip(req.zip)
        store_tasks = [aggregator.fetch_store_deals(store) for store in req.stores if store != "slickdeals"]
        category_tasks = [aggregator.fetch_category_deals(req.zip, cat) for cat in req.categories]

        results = await asyncio.gather(slickdeals_task, *store_tasks, *category_tasks)

        all_deals = {
            'slickdeals': results[0],
            'store_deals': {},
            'category_deals': {},
            'timestamp': datetime.now().isoformat()
        }

        non_slick_stores = [s for s in req.stores if s != "slickdeals"]
        for i, store in enumerate(non_slick_stores):
            all_deals['store_deals'][store] = results[i + 1]

        for j, cat in enumerate(req.categories):
            all_deals['category_deals'][cat] = results[len(non_slick_stores) + 1 + j]

        return all_deals

    except Exception as e:
        logger.error(f"API error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
