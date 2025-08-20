# Google Maps Scraper API

A FastAPI-based service for extracting real-time business data from Google Maps using Selenium.

## Features

- **Real-time scraping** from Google Maps
- **Headless browser automation** with Selenium
- **RESTful API** with FastAPI
- **Pagination support** for deep searches
- Returns structured JSON data

## API Endpoints

### POST /search
Search for businesses on Google Maps.

**Request Body:**
```json
{
  "search_query": "restaurants in New York",
  "max_results": 10,
  "visit_websites": false
}
```

**Response:**
```JSON
{
  "success": true,
  "data": [
    {
      "business_name": "Katz's Delicatessen",
      "address": "205 E Houston St, New York, NY 10002, USA",
      "website": "http://katzsdelicatessen.com/",
      "phone_number": "(212) 254-2246",
      "primary_email": null,
      "rating": 4.6,
      "review_count": 28000,
      "google_maps_url": "https://www.google.com/maps/place/..."
    }
  ],
  "total_results": 10,
  "message": "Successfully scraped 10 businesses."
}
```
### GET / 
API information and documentation URL.
Railway Deployment
Connect your GitHub repository to Railway.
Crucially, add google-chrome-stable as a System Package in your service's settings under "Build".
Railway will automatically deploy the service.
### Usage Example

```Bash
curl -X POST "https://your-gmaps-api.up.railway.app/search" \
  -H "Content-Type: application/json" \
  -d '{
    "search_query": "cafes in London",
    "max_results": 5
  }'
```