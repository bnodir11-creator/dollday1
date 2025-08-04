from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime
import logging
from typing import List, Dict
import httpx
import asyncio
from bs4 import BeautifulSoup

# Инициализация приложения (ОДИН РАЗ)
app = FastAPI(
    title="Discount Aggregator API",
    description="API для агрегации скидок и промо-акций",
    version="1.0.0"
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
logging.basicConfig(level=logging.INFO)
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

# Класс DiscountAggregator (оставить без изменений)
# ...

# Endpoints должны быть ПОСЛЕ всех определений
@app.get("/")
async def root():
    return {"status": "Discount Aggregator API is running"}

@app.get("/discounts")
async def get_discounts():
    """Получить список текущих скидок"""
    return {"discounts": [...]}

@app.post("/api/get-discounts")
async def get_discounts(req: DiscountRequest):
    # Ваша реализация...
    pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
