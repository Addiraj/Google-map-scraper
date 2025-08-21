import os
import re
import time
import random
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from lxml import html

# --- FastAPI App Initialization ---
app = FastAPI(title="Google Maps Scraper API",
              description="A standalone API to scrape business data from Google Maps.",
              version="1.0.0"
)


# --- Pydantic Models for a Clean API Schema (like your IndiaMart API) ---
class SearchRequest(BaseModel):
    search_query: str
    max_results: int = 20
    visit_websites: bool = True


class BusinessResult(BaseModel):
    business_name: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    phone_number: Optional[str] = None
    primary_email: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    google_maps_url: Optional[str] = None


class SearchResponse(BaseModel):
    success: bool
    data: List[BusinessResult]
    total_results: int
    message: str


# --- The Scraper Class (Modified to Return Data) ---
class AdvancedContactExtractor:
    def __init__(self, search_query, max_results=20, visit_websites=True):
        self.search_query = search_query
        self.max_results = max_results
        self.visit_websites = visit_websites
        self.driver = None

        # Add your regex patterns here
        self.email_patterns = [re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')]
        self.phone_patterns = [re.compile(r'\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})')]

    def setup_browser(self):
        """Sets up a headless Chrome browser with anti-detection features."""
        try:
            self.chrome_options = Options()
            
            # Standard headless arguments
            self.chrome_options.add_argument("--headless")
            self.chrome_options.add_argument("--no-sandbox")
            self.chrome_options.add_argument("--disable-dev-shm-usage")
            self.chrome_options.add_argument("--window-size=1920,1080") # Set a common window size

            # --- Anti-detection Arguments ---
            # This is the most important part. We are making the browser look like a real one.
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            self.chrome_options.add_argument(f'user-agent={user_agent}')
            
            self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.chrome_options.add_experimental_option('useAutomationExtension', False)
            
            from selenium.webdriver.chrome.service import Service
            from webdriver_manager.chrome import ChromeDriverManager
            
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.chrome_options)
            
            # This script hides the "navigator.webdriver" property that websites use to detect Selenium
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.wait = WebDriverWait(self.driver, 15) # Increase wait time for more stability
            print("Headless browser with anti-detection setup completed.")
        except Exception as e:
            print(f"Browser setup error: {e}")
            raise

    # --- PASTE YOUR OTHER SCRAPER METHODS HERE ---
    # (extract_contacts_from_text, search_google_maps, get_business_links_advanced,
    #  extract_business_contacts, extract_from_website)
    # The content of these methods does not need to change. They are omitted here for brevity.
    # --- ENSURE YOU COPY THEM INTO THIS CLASS ---

    def extract_digit_only_numbers(data_list):
        results = []
        for record in data_list:
            for item in record:
                text = item.strip()
                # Remove spaces, dashes, and plus for checking
                cleaned = text.replace(" ", "").replace("-", "").replace("+", "")
                if cleaned.isdigit() and len(cleaned) >= 6:  # Min length to avoid false positives
                    results.append(text)
        return results

    def extract_contacts_from_text(self, text):
        """Enhanced contact extraction from text using multiple patterns"""
        emails = set()
        phones = set()

        # Extract emails using multiple patterns
        for pattern in self.email_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    emails.update(match)
                else:
                    emails.add(match)

        # Extract phones using multiple patterns
        for pattern in self.phone_patterns:
            matches = pattern.findall(text)
            for match in matches:
                if isinstance(match, tuple):
                    # Join tuple elements for phone numbers
                    phone = ''.join(match)
                    if len(phone) >= 10:
                        phones.add(phone)
                else:
                    clean_phone = re.sub(r'[^\d]', '', match)
                    if len(clean_phone) >= 10:
                        phones.add(match)

        # Clean and validate emails
        valid_emails = []
        for email in emails:
            email = email.strip().lower()
            if '@' in email and '.' in email and len(email) > 5:
                # Exclude common non-business emails
                if not any(domain in email for domain in ['noreply', 'donotreply', 'no-reply']):
                    valid_emails.append(email)

        # Clean and validate phones
        valid_phones = []
        for phone in phones:
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if len(clean_phone) >= 10 and len(clean_phone) <= 15:
                # Format US phone numbers
                if len(clean_phone) == 10:
                    formatted = f"({clean_phone[:3]}) {clean_phone[3:6]}-{clean_phone[6:]}"
                    valid_phones.append(formatted)
                elif len(clean_phone) == 11 and clean_phone.startswith('1'):
                    formatted = f"({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:]}"
                    valid_phones.append(formatted)

        return {
            'emails': list(set(valid_emails))[:3],  # Limit to 3 best emails
            'phones': list(set(valid_phones))[:3]  # Limit to 3 best phones
        }

    def search_google_maps(self):
        """Navigate to Google Maps and perform search"""
        try:
            # Enable JavaScript for Google Maps
            self.chrome_options.add_argument("--enable-javascript")

            search_url = f"https://www.google.com/maps/search/{self.search_query.replace(' ', '+')}"
            print(f"Searching: {search_url}")

            self.driver.get(search_url)
            time.sleep(5)

            # Handle cookie consent
            try:
                accept_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button/span[contains(text(),'Accept all')]"))
                )
                accept_button.click()
                time.sleep(5)
            except TimeoutException:
                print("No cookie consent found")

            return True

        except Exception as e:
            print(f"Search error: {e}")
            return False

    def get_business_links_advanced(self):
        """Advanced business link extraction with better pagination"""
        try:
            # Find scrollable panel with multiple selectors
            scrollable_selectors = [
                '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[1]/div[1]',
                '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[1]',
                '//div[@role="main"]//div[contains(@class, "m6QErb")]',
                '//div[contains(@class, "Nv2PK")]'
            ]

            scrollable_div = None
            for selector in scrollable_selectors:
                try:
                    scrollable_div = self.driver.find_element(By.XPATH, selector)
                    break
                except NoSuchElementException:
                    continue

            if not scrollable_div:
                print("Could not find scrollable panel")
                return []

            all_links = set()
            scroll_attempts = 0
            max_scrolls = min(50, self.max_results // 10)  # Adaptive scrolling
            no_new_content_count = 0

            print(f"Starting pagination (max {max_scrolls} scrolls)...")

            while scroll_attempts < max_scrolls and len(all_links) < self.max_results:
                # Get current links
                page_source = self.driver.page_source
                tree = html.fromstring(page_source)
                current_links = tree.xpath('//a[contains(@href, "/maps/place/")]/@href')

                # Clean and add new links
                new_links_count = 0
                for link in current_links:
                    if link.startswith('/'):
                        link = 'https://www.google.com' + link
                    if link not in all_links:
                        all_links.add(link)
                        new_links_count += 1

                print(f"Scroll {scroll_attempts + 1}: Found {len(all_links)} total links (+{new_links_count} new)")

                # Check if we found new content
                if new_links_count == 0:
                    no_new_content_count += 1
                    if no_new_content_count >= 3:
                        print("No new content found after 3 attempts")
                        break
                else:
                    no_new_content_count = 0

                # Scroll down
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(random.uniform(2, 4))

                # Check for end indicators
                if any(indicator in page_source for indicator in [
                    "You've reached the end of the list",
                    "No more results",
                    "That's all the results"
                ]):
                    print("Reached end of results")
                    break

                scroll_attempts += 1

            final_links = list(all_links)[:self.max_results]
            print(f"Pagination completed: {len(final_links)} business links collected")
            return final_links

        except Exception as e:
            print(f"Pagination error: {e}")
            return []

    def extract_business_contacts(self, business_url):
        """Extract detailed contact information from business page"""
        try:
            print(f"Extracting: {business_url}")
            self.driver.get(business_url)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # time.sleep(random.uniform(2, 4))
            time.sleep(random.uniform(3, 6))

            data = {
                'google_maps_url': business_url,
                'search_query': self.search_query,
                'website_visited': False,
                'additional_contacts': ''
            }

            # Extract basic business info
            try:
                name_element = self.driver.find_element(By.CSS_SELECTOR, "h1")
                data['business_name'] = name_element.text.strip()
            except:
                data['business_name'] = "Unknown Business"

            try:
                scrollable_div = self.driver.find_element(By.XPATH,
                                                          '//div[@role="main"]//div[contains(@class, "m6QErb")]')
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(2)
                address_element = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//button[@data-item-id='address']"))
                )

                data['address'] = address_element.text.strip()
            except:
                data['address'] = "Address not found"

            try:
                rating_element = self.driver.find_element(By.CSS_SELECTOR, "span.MW4etd")
                data['rating'] = float(rating_element.text.strip())
            except:
                data['rating'] = None

            try:
                review_element = self.driver.find_element(By.CSS_SELECTOR, "span.UY7F9")
                review_text = review_element.text.strip()
                data['review_count'] = int(re.sub(r'[^\d]', '', review_text))
            except:
                data['review_count'] = None

            try:
                category_element = self.driver.find_element(By.CSS_SELECTOR, "button[jsaction*='category']")
                data['category'] = category_element.text.strip()
            except:
                data['category'] = "Unknown Category"

            # Extract website
            try:
                website_element = self.driver.find_element(By.CSS_SELECTOR, "[data-item-id='authority']")
                data['website'] = website_element.get_attribute('href')
            except:
                data['website'] = None

            try:
                data['base_url'] = business_url
            except:
                data['base_url'] = None

            try:
                elements = self.driver.find_elements(By.XPATH,
                                                     "//div[@class='rogA2c ']/div[@class='Io6YTe fontBodyMedium kR99db fdkmkc ']")
                data['mixed_data'] = json.dumps([el.text.strip() for el in elements])

            except:
                data['base_url'] = None

            def is_phone_number(text):
                cleaned = text.replace(" ", "").replace("-", "").replace("+", "")
                return cleaned.isdigit() and len(cleaned) >= 6

            data['phone_no'] = str(json.dumps([
                el.text.strip()
                for el in elements
                if is_phone_number(el.text.strip())
            ]))

            # Extract contacts from Google Maps page
            page_contacts = self.extract_contacts_from_text(self.driver.page_source)

            # Assign primary contacts
            data['primary_email'] = page_contacts['emails'][0] if page_contacts['emails'] else None
            data['secondary_email'] = page_contacts['emails'][1] if len(page_contacts['emails']) > 1 else None

            # Visit website for additional contacts if enabled
            if self.visit_websites and data['website']:
                website_contacts = self.extract_from_website(data['website'])
                if website_contacts:
                    data['website_visited'] = True

                    # Merge website contacts with existing ones
                    all_emails = page_contacts['emails'] + website_contacts['emails']
                    all_phones = page_contacts['phones'] + website_contacts['phones']

                    # Remove duplicates and update
                    unique_emails = list(dict.fromkeys(all_emails))[:3]
                    unique_phones = list(dict.fromkeys(all_phones))[:3]

                    data['primary_email'] = unique_emails[0] if unique_emails else None
                    data['secondary_email'] = unique_emails[1] if len(unique_emails) > 1 else None

                    # Store additional contacts as JSON
                    additional = {
                        'extra_emails': unique_emails[2:],
                        'extra_phones': unique_phones[2:],
                        'website_source': True
                    }
                    data['additional_contacts'] = json.dumps(additional)

            # Count contacts found
            contact_count = sum([
                1 if data['primary_email'] else 0,
                1 if data['secondary_email'] else 0
            ])

            if contact_count > 0:
                self.contacts_found += contact_count
                print(f"Found {contact_count} contacts for {data['business_name']}")
            else:
                print(f"No contacts found for {data['business_name']}")

            return data

        except Exception as e:
            print(f"Error extracting business: {e}")
            return None

    def extract_from_website(self, website_url):
        """Extract additional contacts from business website"""
        try:
            print(f"Visiting website: {website_url}")

            # Open website in new tab
            self.driver.execute_script(f"window.open('{website_url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])

            time.sleep(10)

            # Extract contacts from website
            website_contacts = self.extract_contacts_from_text(self.driver.page_source)

            # Try to find contact page
            contact_links = self.driver.find_elements(By.XPATH,
                                                      "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact')]")

            if contact_links and len(contact_links) > 0:
                try:
                    contact_links[0].click()
                    time.sleep(5)
                    contact_page_contacts = self.extract_contacts_from_text(self.driver.page_source)

                    # Merge contacts
                    website_contacts['emails'].extend(contact_page_contacts['emails'])
                    website_contacts['phones'].extend(contact_page_contacts['phones'])

                except:
                    pass

            # Close website tab and return to main tab
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])

            return website_contacts

        except Exception as e:
            print(f"Website extraction error: {e}")
            # Ensure we're back on main tab
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return {'emails': [], 'phones': []}

    def run_extraction(self) -> List[dict]:
        """The main execution flow. Returns a list of scraped business data."""
        all_scraped_data = []
        try:
            print("=" * 60)
            print(f"STARTING SCRAPING TASK for query: '{self.search_query}'")
            self.setup_browser()

            if not self.search_google_maps():
                raise Exception("Failed to perform initial search on Google Maps.")

            business_links = self.get_business_links_advanced()
            if not business_links:
                print("No business links found. Task finished.")
                return []

            print(f"Found {len(business_links)} businesses. Starting data extraction...")
            for i, link in enumerate(business_links, 1):
                print(f"\nProcessing {i}/{len(business_links)}: {link}")
                business_data = self.extract_business_contacts(link)
                if business_data:
                    all_scraped_data.append(business_data)
                time.sleep(random.uniform(2, 4))

            return all_scraped_data
        except Exception as e:
            print(f"A critical error occurred during extraction: {e}")
            # In case of error, return what was found so far
            return all_scraped_data
        finally:
            self.cleanup()

    def cleanup(self):
        """Closes browser connection safely."""
        try:
            if self.driver:
                self.driver.quit()
            print("✓ Resources cleaned up successfully.")
        except Exception as e:
            print(f"Cleanup error: {e}")


# --- API Endpoints ---
@app.post("/search", response_model=SearchResponse)
async def search_businesses(request: SearchRequest):
    """
    Scrapes Google Maps for business data. This is a synchronous process
    and may take a while to complete depending on max_results.
    """
    try:
        print(f"Initiating Google Maps scrape for: '{request.search_query}'")
        extractor = AdvancedContactExtractor(
            search_query=request.search_query,
            max_results=request.max_results,
            visit_websites=request.visit_websites
        )

        results = extractor.run_extraction()

        if not results:
            return SearchResponse(
                success=False, data=[], total_results=0, message="No results found or an error occurred."
            )

        return SearchResponse(
            success=True,
            data=results,
            total_results=len(results),
            message=f"Successfully scraped {len(results)} businesses."
        )

    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/")
def read_root():

    return {"status": "Google Maps Scraper API is running", "docs_url": "/docs"}
