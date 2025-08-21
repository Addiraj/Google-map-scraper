import re
import time
import random
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from lxml import html
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class AdvancedContactExtractor:
    def __init__(self, search_query, max_results=20, visit_websites=True):
        self.search_query = search_query
        self.max_results = max_results
        self.visit_websites = visit_websites
        self.extracted_count = 0
        self.contacts_found = 0
        self.duration = None

        # Enhanced regex patterns for better contact extraction
        self.email_patterns = [
            re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            re.compile(r'mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'),
            re.compile(r'email[:\s]*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})', re.IGNORECASE),
        ]

        self.phone_patterns = [
            re.compile(r'\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'),
            re.compile(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'),
            re.compile(r'\(\d{3}\)\s?\d{3}[-.]?\d{4}'),
            re.compile(r'tel[:\s]*(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})', re.IGNORECASE),
        ]

        # Setup browser only - removed database setup
        self.setup_browser()

    def setup_browser(self):
        """Setup Chrome browser with optimized settings for Railway deployment"""
        try:
            self.chrome_options = Options()
            self.chrome_options.add_argument("--headless")
            self.chrome_options.add_argument("--start-maximized")
            self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            self.chrome_options.add_argument("--no-sandbox")
            self.chrome_options.add_argument("--disable-dev-shm-usage")
            self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.chrome_options.add_experimental_option('useAutomationExtension', False)

            # Initialize driver for Railway environment
            service = Service(executable_path="/usr/bin/chromedriver")
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)

            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)

        except Exception as e:
            raise Exception(f"Browser setup error: {e}")

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
                if not any(domain in email for domain in ['noreply', 'donotreply', 'no-reply']):
                    valid_emails.append(email)

        # Clean and validate phones
        valid_phones = []
        for phone in phones:
            clean_phone = re.sub(r'[^\d+]', '', phone)
            if len(clean_phone) >= 10 and len(clean_phone) <= 15:
                if len(clean_phone) == 10:
                    formatted = f"({clean_phone[:3]}) {clean_phone[3:6]}-{clean_phone[6:]}"
                    valid_phones.append(formatted)
                elif len(clean_phone) == 11 and clean_phone.startswith('1'):
                    formatted = f"({clean_phone[1:4]}) {clean_phone[4:7]}-{clean_phone[7:]}"
                    valid_phones.append(formatted)

        return {
            'emails': list(set(valid_emails))[:3],
            'phones': list(set(valid_phones))[:3]
        }

    def search_google_maps(self):
        """Navigate to Google Maps and perform search"""
        try:
            self.chrome_options.add_argument("--enable-javascript")
            search_url = f"https://www.google.com/maps/search/{self.search_query.replace(' ', '+')}"
            self.driver.get(search_url)
            time.sleep(5)

            try:
                accept_button = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button/span[contains(text(),'Accept all')]"))
                )
                accept_button.click()
                time.sleep(5)
            except TimeoutException:
                pass

            return True

        except Exception as e:
            raise Exception(f"Search error: {e}")

    def get_business_links_advanced(self):
        """Advanced business link extraction with better pagination"""
        try:
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
                return []

            all_links = set()
            scroll_attempts = 0
            max_scrolls = min(50, self.max_results // 10)
            no_new_content_count = 0

            while scroll_attempts < max_scrolls and len(all_links) < self.max_results:
                page_source = self.driver.page_source
                tree = html.fromstring(page_source)
                current_links = tree.xpath('//a[contains(@href, "/maps/place/")]/@href')

                new_links_count = 0
                for link in current_links:
                    if link.startswith('/'):
                        link = 'https://www.google.com' + link
                    if link not in all_links:
                        all_links.add(link)
                        new_links_count += 1

                if new_links_count == 0:
                    no_new_content_count += 1
                    if no_new_content_count >= 3:
                        break
                else:
                    no_new_content_count = 0

                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
                time.sleep(random.uniform(2, 4))

                if any(indicator in page_source for indicator in [
                    "You've reached the end of the list",
                    "No more results",
                    "That's all the results"
                ]):
                    break

                scroll_attempts += 1

            return list(all_links)[:self.max_results]

        except Exception as e:
            raise Exception(f"Pagination error: {e}")

    def extract_business_contacts(self, business_url):
        """Extract detailed contact information from business page"""
        try:
            self.driver.get(business_url)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
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
                address_element = self.wait.until(
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
                elements = self.driver.find_elements(By.XPATH,
                                                   "//div[@class='rogA2c ']/div[@class='Io6YTe fontBodyMedium kR99db fdkmkc ']")
                data['mixed_data'] = json.dumps([el.text.strip() for el in elements])
            except:
                data['mixed_data'] = None

            # Extract phone numbers
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
            data['primary_email'] = page_contacts['emails'][0] if page_contacts['emails'] else None
            data['secondary_email'] = page_contacts['emails'][1] if len(page_contacts['emails']) > 1 else None

            # Visit website for additional contacts if enabled
            if self.visit_websites and data['website']:
                website_contacts = self.extract_from_website(data['website'])
                if website_contacts:
                    data['website_visited'] = True
                    all_emails = page_contacts['emails'] + website_contacts['emails']
                    all_phones = page_contacts['phones'] + website_contacts['phones']
                    unique_emails = list(dict.fromkeys(all_emails))[:3]
                    unique_phones = list(dict.fromkeys(all_phones))[:3]
                    data['primary_email'] = unique_emails[0] if unique_emails else None
                    data['secondary_email'] = unique_emails[1] if len(unique_emails) > 1 else None
                    additional = {
                        'extra_emails': unique_emails[2:],
                        'extra_phones': unique_phones[2:],
                        'website_source': True
                    }
                    data['additional_contacts'] = json.dumps(additional)

            if data.get('primary_email') or data.get('secondary_email'):
                self.contacts_found += sum([1 for x in [data['primary_email'], data['secondary_email']] if x])

            return data

        except Exception as e:
            print(f"Error extracting business: {e}")
            return None

    def extract_from_website(self, website_url):
        """Extract additional contacts from business website"""
        try:
            self.driver.execute_script(f"window.open('{website_url}', '_blank');")
            self.driver.switch_to.window(self.driver.window_handles[-1])
            time.sleep(10)

            website_contacts = self.extract_contacts_from_text(self.driver.page_source)

            contact_links = self.driver.find_elements(By.XPATH,
                                                    "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'contact')]")

            if contact_links and len(contact_links) > 0:
                try:
                    contact_links[0].click()
                    time.sleep(5)
                    contact_page_contacts = self.extract_contacts_from_text(self.driver.page_source)
                    website_contacts['emails'].extend(contact_page_contacts['emails'])
                    website_contacts['phones'].extend(contact_page_contacts['phones'])
                except:
                    pass

            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return website_contacts

        except Exception as e:
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
            return {'emails': [], 'phones': []}

    def run_extraction(self):
        """Main extraction process optimized for API usage"""
        start_time = datetime.now()

        try:
            if not self.search_google_maps():
                return False

            business_links = self.get_business_links_advanced()
            if not business_links:
                return False

            for i, link in enumerate(business_links, 1):
                business_data = self.extract_business_contacts(link)
                if business_data:
                    # Instead of saving to database, we'll use the callback
                    self.save_business_data(business_data)
                    self.extracted_count += 1

                time.sleep(random.uniform(2, 5))

            end_time = datetime.now()
            self.duration = end_time - start_time
            return True

        except Exception as e:
            raise Exception(f"Extraction error: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except Exception:
            pass
