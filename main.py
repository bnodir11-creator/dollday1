from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from datetime import datetime
import logging
from typing import List, Dict, Optional
import httpx
import asyncio
from bs4 import BeautifulSoup
import os
import time

# Инициализация приложения
app = FastAPI(
    title="Discount Aggregator API",
    description="API для агрегации скидок и промо-акций",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Модели Pydantic
class Item(BaseModel):
    name: str
    
    @field_validator('name')
    def validate_name(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("Name must be at least 3 characters long")
        return v

class DiscountRequest(BaseModel):
    country: str
    zip: str
    stores: List[str] = ["amazon", "walmart", "target", "slickdeals"]
    categories: List[str] = []

    @field_validator('zip')
    def validate_zip(cls, v):
        if not v.isdigit() or len(v) != 5:
            raise ValueError("ZIP code must be 5 digits")
        return v

class HealthCheck(BaseModel):
    status: str
    timestamp: str
    version: str
    uptime: float

# Конфигурация статических файлов
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Класс DiscountAggregator
class DiscountAggregator:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = httpx.AsyncClient(timeout=30.0)
        self.start_time = time.time()

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

    # ... (остальные методы класса остаются без изменений)

# Эндпоинты
@app.get("/", tags=["Root"])
async def root():
    return {
        "status": "Discount Aggregator API is running",
        "docs": "/docs",
        "redoc": "/redoc",
        "endpoints": {
            "get_discounts": "/api/get-discounts (POST)",
            "health_check": "/health"
        }
    }

@app.get("/health", tags=["Status"], response_model=HealthCheck)
async def health_check():
    return {
        "status": "OK",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "uptime": round(time.time() - DiscountAggregator().start_time, 2)
    }

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(
        "static/favicon.ico",
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=86400"}
    )

@app.get("/discounts", tags=["Discounts"])
async def get_discounts():
    """Получить список текущих скидок"""
    return {"discounts": [...]}

@app.post("/api/get-discounts", tags=["Discounts"])
async def get_discounts(req: DiscountRequest):
    if req.country != "US":
        raise HTTPException(status_code=400, detail="Only USA is currently supported")

    try:
        aggregator = DiscountAggregator()
        results = await asyncio.gather(
            aggregator.fetch_slickdeals_by_zip(req.zip),
            *[aggregator.fetch_store_deals(store) for store in req.stores if store != "slickdeals"],
            *[aggregator.fetch_category_deals(req.zip, cat) for cat in req.categories]
        )

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
