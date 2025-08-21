from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import json
from datetime import datetime
from your_scraper_file import AdvancedContactExtractor  # Import your scraper class

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

@app.post("/scrape", response_model=List[BusinessData])
async def scrape_businesses(request: SearchRequest, background_tasks: BackgroundTasks):
    try:
        # Initialize scraper
        scraper = AdvancedContactExtractor(
            search_query=request.search_query,
            max_results=request.max_results,
            visit_websites=request.visit_websites
        )

        # Start scraping
        results = []

        # Search Google Maps
        if not scraper.search_google_maps():
            return {"error": "Failed to search Google Maps"}

        # Get business links
        business_links = scraper.get_business_links_advanced()
        if not business_links:
            return {"error": "No businesses found"}

        # Extract data for each business
        for link in business_links:
            business_data = scraper.extract_business_contacts(link)
            if business_data:
                # Convert the data to match the BusinessData model
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
                results.append(formatted_data)

        return results

    except Exception as e:
        return {"error": str(e)}
    finally:
        if 'scraper' in locals():
            scraper.cleanup()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
