from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import uvicorn
from scraper import AdvancedContactExtractor

app = FastAPI(
    title="Google Maps Business Scraper",
    description="Advanced Google Maps business data extraction API"
)

class ScrapingRequest(BaseModel):
    search_query: str
    max_results: Optional[int] = 20
    visit_websites: Optional[bool] = True

class ScrapingResponse(BaseModel):
    status: str
    message: str
    duration: Optional[str]
    extracted_count: int
    contacts_found: int
    results: List[Dict]

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "Google Maps Business Scraper",
        "endpoints": {
            "POST /scrape": "Extract business data from Google Maps"
        }
    }

@app.post("/scrape", response_model=ScrapingResponse)
def scrape_businesses(request: ScrapingRequest):
    try:
        # Initialize the scraper with user parameters
        scraper = AdvancedContactExtractor(
            search_query=request.search_query,
            max_results=request.max_results,
            visit_websites=request.visit_websites
        )

        # Run the extraction
        results = []

        # Override the save_business_data method to collect results
        def collect_data(data):
            if data:
                results.append(data)
                return True
            return False

        # Store original method
        original_save = scraper.save_business_data
        scraper.save_business_data = collect_data

        # Run extraction
        success = scraper.run_extraction()

        # Restore original method
        scraper.save_business_data = original_save

        if not success:
            raise HTTPException(status_code=500, detail="Extraction failed")

        return {
            "status": "success",
            "message": f"Successfully extracted {len(results)} businesses",
            "duration": str(scraper.duration) if hasattr(scraper, 'duration') else None,
            "extracted_count": scraper.extracted_count,
            "contacts_found": scraper.contacts_found,
            "results": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
