from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime
from scraper import AdvancedContactExtractor

app = FastAPI(title="Google Maps Business Scraper API")

class SearchRequest(BaseModel):
    search_query: str
    max_results: Optional[int] = 20
    visit_websites: Optional[bool] = True

class BusinessData(BaseModel):
    business_name: str
    address: Optional[str]
    phone_no: Optional[str]
    website: Optional[str]
    rating: Optional[float]
    review_count: Optional[int]
    category: Optional[str]
    primary_email: Optional[str]
    secondary_email: Optional[str]
    additional_contacts: Optional[dict]

@app.get("/")
async def root():
    return {"status": "active", "message": "Google Maps Business Scraper API is running"}

@app.post("/scrape")
async def scrape_businesses(request: SearchRequest):
    try:
        # Initialize scraper
        scraper = AdvancedContactExtractor(
            search_query=request.search_query,
            max_results=request.max_results,
            visit_websites=request.visit_websites
        )

        # Run extraction
        results = scraper.run_extraction()

        # Format results
        formatted_results = []
        for business_data in results:
            if business_data:
                formatted_data = {
                    "business_name": business_data.get("business_name", ""),
                    "address": business_data.get("address"),
                    "phone_no": business_data.get("phone_no"),
                    "website": business_data.get("website"),
                    "rating": business_data.get("rating"),
                    "review_count": business_data.get("review_count"),
                    "category": business_data.get("category"),
                    "primary_email": business_data.get("primary_email"),
                    "secondary_email": business_data.get("secondary_email"),
                    "additional_contacts": json.loads(business_data.get("additional_contacts", "{}"))
                }
                formatted_results.append(formatted_data)

        return formatted_results

    except Exception as e:
        return {"error": str(e)}
