import json
import re
import time
import logging
import random
import os
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GoogleShoppingPriceScraper:
    def __init__(self, debug_mode=True):
        self.debug_mode = debug_mode
        self.request_lock = threading.Lock()
        self.last_request_time = 0
        
        # NEW: Batch processing variables for anti-detection
        self.searches_count = 0
        self.batch_size = 20  # Searches before long break
        self.batch_cooldown_min = 120  # 2 minutes minimum
        self.batch_cooldown_max = 180  # 3 minutes maximum
        self.captcha_detected_count = 0
        
        # Enhanced user agents to avoid detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        ]
        
        # Target competitor domains
        self.target_domains = {
            'coastalbeauty.ca': 'coastalbeauty',
            'beautywellness.ca': 'beautywellness', 
            'shopempire.ca': 'shopempire',
            'matandmax.com': 'matandmax',
            'shoptbbs.ca': 'shoptbbs',
            'liviabeauty.ca': 'liviabeauty',
            'aonebeauty.com': 'aonebeauty',
            'cosmeticworld.ca': 'cosmeticworld'
        }

    def check_batch_cooldown(self):
        """NEW: Check if we need a batch cooldown and execute it"""
        if self.searches_count > 0 and self.searches_count % self.batch_size == 0:
            cooldown_time = random.uniform(self.batch_cooldown_min, self.batch_cooldown_max)
            logger.info(f"🛑 BATCH COOLDOWN: Completed {self.searches_count} searches")
            logger.info(f"⏳ Taking a {cooldown_time:.1f} second break to avoid detection...")
            logger.info(f"☕ Time to grab a coffee! This helps prevent Google's bot detection.")
            
            # Show countdown every 30 seconds
            remaining = cooldown_time
            while remaining > 0:
                if remaining > 30:
                    time.sleep(30)
                    remaining -= 30
                    logger.info(f"⏱️  Still cooling down... {remaining:.0f} seconds remaining")
                else:
                    time.sleep(remaining)
                    remaining = 0
            
            logger.info(f"✅ Cooldown complete! Resuming searches...")

    def detect_and_handle_captcha(self, html: str) -> bool:
        """NEW: Enhanced CAPTCHA detection and handling"""
        captcha_indicators = [
            'unusual traffic',
            'captcha',
            'verify you are human',
            'prove you\'re not a robot',
            'suspicious activity',
            'automated queries',
            'please verify',
            'security check'
        ]
        
        html_lower = html.lower()
        captcha_detected = any(indicator in html_lower for indicator in captcha_indicators)
        
        if captcha_detected:
            self.captcha_detected_count += 1
            logger.error(f"🚨 CAPTCHA DETECTED (#{self.captcha_detected_count})")
            logger.error("🤖 Google is blocking our requests - implementing emergency cooldown")
            
            # Emergency longer cooldown when CAPTCHA is detected
            emergency_cooldown = random.uniform(300, 600)  # 5-10 minutes
            logger.error(f"🆘 Emergency cooldown: {emergency_cooldown/60:.1f} minutes")
            
            # Show progress every minute
            remaining = emergency_cooldown
            while remaining > 0:
                if remaining > 60:
                    time.sleep(60)
                    remaining -= 60
                    logger.error(f"⏱️  Emergency cooldown... {remaining/60:.0f} minutes remaining")
                else:
                    time.sleep(remaining)
                    remaining = 0
            
            logger.info("🔄 Emergency cooldown complete - trying with fresh session")
            return True
        
        return False

    def create_driver(self) -> webdriver.Chrome:
        """Enhanced driver creation with more randomization"""
        options = Options()
        
        if not self.debug_mode:
            options.add_argument('--headless')
        
        # Enhanced stealth options
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        # Randomize window size
        window_sizes = ['1920,1080', '1366,768', '1440,900', '1536,864']
        window_size = random.choice(window_sizes)
        options.add_argument(f'--window-size={window_size}')
        options.add_argument('--start-maximized')
        
        # Advanced anti-detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')  # Speed up loading
        options.add_argument('--disable-javascript-harmony-shipping')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        
        # NEW: Additional stealth options
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-background-timer-throttling')
        
        # User agent rotation
        user_agent = random.choice(self.user_agents)
        options.add_argument(f'--user-agent={user_agent}')
        
        # Advanced experimental options
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option("detach", True)
        
        # Enhanced prefs
        prefs = {
            "profile.default_content_setting_values": {
                "notifications": 2,
                "geolocation": 2,
                "media_stream": 2,
            },
            "profile.managed_default_content_settings": {
                "images": 2
            }
        }
        options.add_experimental_option("prefs", prefs)
        
        try:
            # Try to use Service if available (newer versions)
            try:
                service = Service()
                driver = webdriver.Chrome(service=service, options=options)
            except:
                # Fallback for older selenium versions
                driver = webdriver.Chrome(options=options)
            
            # Enhanced scripts to remove webdriver traces
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})")
            driver.execute_script("Object.defineProperty(navigator, 'permissions', {get: () => undefined})")
            
            return driver
        except Exception as e:
            logger.error(f"❌ Failed to create Chrome driver: {e}")
            logger.error("Make sure ChromeDriver is installed and in PATH")
            logger.error("Download from: https://chromedriver.chromium.org/")
            raise

    def save_debug_html(self, html: str, filename: str):
        """Save HTML to file for debugging"""
        if self.debug_mode:
            debug_dir = "debug_html"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            filepath = os.path.join(debug_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html)
            logger.info(f"🐛 Debug HTML saved to: {filepath}")

    def make_request(self, url: str, timeout: int = 30) -> Optional[str]:
        """Enhanced request method with batch cooldown"""
        # NEW: Check if we need batch cooldown BEFORE making request
        self.check_batch_cooldown()
        
        with self.request_lock:
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            
            # Dynamic delay based on search count
            if self.searches_count < 10:
                min_delay = random.uniform(8, 12)  # Faster start
            elif self.searches_count < 15:
                min_delay = random.uniform(12, 18)  # Medium delay
            else:
                min_delay = random.uniform(15, 25)  # Slower as we approach batch limit
            
            if time_since_last < min_delay:
                sleep_time = min_delay - time_since_last
                logger.info(f"⏳ Rate limiting: sleeping for {sleep_time:.1f} seconds... (search #{self.searches_count + 1})")
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
        
        driver = None
        try:
            driver = self.create_driver()
            logger.info(f"🌐 Loading page with Selenium: {url}")
            logger.info(f"📊 Search #{self.searches_count + 1} (next cooldown at {((self.searches_count // self.batch_size) + 1) * self.batch_size})")
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            
            # Load the page
            driver.get(url)
            
            # Wait a bit for page to settle
            time.sleep(random.uniform(3, 6))
            
            # Get HTML and check for CAPTCHA
            html = driver.page_source
            
            # NEW: Check for CAPTCHA and handle it
            if self.detect_and_handle_captcha(html):
                # If CAPTCHA detected, return None to trigger retry
                return None
            
            # Increment search count after successful request
            self.searches_count += 1
            
            # Check if we're on the right page
            current_url = driver.current_url
            page_title = driver.title
            logger.info(f"📄 Current URL: {current_url}")
            logger.info(f"📄 Page title: {page_title}")
            
            # Take screenshot if in debug mode
            if self.debug_mode:
                try:
                    screenshot_path = f"debug_html/screenshot_{int(time.time())}.png"
                    driver.save_screenshot(screenshot_path)
                    logger.info(f"📸 Screenshot saved: {screenshot_path}")
                except Exception as e:
                    logger.debug(f"Could not save screenshot: {e}")
            
            # Get initial HTML for debugging
            self.save_debug_html(html, f"initial_page_{int(time.time())}.html")
            
            # Check for common Google blocking indicators
            if "unusual traffic" in html.lower() or "captcha" in html.lower():
                logger.error("🚨 Google is blocking our requests - CAPTCHA or unusual traffic detected")
                return None
            
            if "enable javascript" in html.lower():
                logger.warning("⚠️ JavaScript not enabled properly")
            
            # Try multiple approaches to wait for content
            selectors_to_try = [
                'a.plantl',
                '[data-merchant-id]',
                '.pla-unit',
                'div[data-dtld]',
                'a[data-offer-id]',
                'div[jsname="mRhGLc"]',
                'div.ArOTm'  # From your HTML sample
            ]
            
            found_elements = False
            for selector in selectors_to_try:
                try:
                    elements = WebDriverWait(driver, 5).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                    )
                    if elements:
                        logger.info(f"✅ Found {len(elements)} elements with selector: {selector}")
                        found_elements = True
                        break
                except TimeoutException:
                    logger.debug(f"No elements found with selector: {selector}")
                    continue
            
            if not found_elements:
                logger.warning("⚠️ No shopping elements found with any selector")
                
                # Let's see what we actually have
                all_divs = driver.find_elements(By.TAG_NAME, 'div')
                all_as = driver.find_elements(By.TAG_NAME, 'a')
                logger.info(f"📊 Page contains {len(all_divs)} divs and {len(all_as)} links")
                
                # Check for specific Google Shopping indicators
                shopping_indicators = [
                    'shopping', 'merchant', 'product', 'price', 'pla-unit', 'data-merchant'
                ]
                
                page_text = html.lower()
                found_indicators = [indicator for indicator in shopping_indicators if indicator in page_text]
                logger.info(f"🔍 Found shopping indicators: {found_indicators}")
            
            # Wait a bit more for dynamic content
            time.sleep(random.uniform(3, 6))
            
            # Get final HTML
            final_html = driver.page_source
            self.save_debug_html(final_html, f"final_page_{int(time.time())}.html")
            
            # Quick validation
            if any(indicator in final_html.lower() for indicator in ['data-merchant-id', 'plantl', 'pla-unit']):
                logger.info("✅ Page appears to contain shopping data")
                return final_html
            else:
                logger.warning("❌ Page does not contain expected shopping indicators")
                logger.info("🔍 Checking for alternative shopping content...")
                
                # Look for any price-like content
                if '$' in final_html or 'price' in final_html.lower() or 'cad' in final_html.lower():
                    logger.info("💰 Found price-related content, returning HTML")
                    return final_html
                else:
                    logger.warning("❌ No price content detected")
                    return final_html  # Return anyway for further analysis
                
        except WebDriverException as e:
            logger.error(f"❌ Selenium WebDriver error: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error in make_request: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def analyze_page_content(self, html: str, search_query: str) -> Dict:
        """Analyze the page content to understand what we're getting"""
        soup = BeautifulSoup(html, 'html.parser')
        
        analysis = {
            'title': soup.title.string if soup.title else 'No title',
            'has_shopping_results': False,
            'total_links': len(soup.find_all('a')),
            'shopping_links': [],
            'price_mentions': [],
            'domain_mentions': []
        }
        
        # Check for shopping-specific elements
        shopping_selectors = [
            'a.plantl',
            '[data-merchant-id]',
            '.pla-unit',
            'div[data-dtld]'
        ]
        
        for selector in shopping_selectors:
            elements = soup.select(selector)
            if elements:
                analysis['has_shopping_results'] = True
                analysis['shopping_links'].extend(elements)
        
        # Look for price mentions
        price_pattern = r'\$\d+(?:\.\d{2})?'
        price_matches = re.findall(price_pattern, html)
        analysis['price_mentions'] = list(set(price_matches))
        
        # Look for our target domains
        for domain in self.target_domains.keys():
            if domain in html:
                analysis['domain_mentions'].append(domain)
        
        return analysis

    def search_google_shopping(self, product: Dict) -> Dict:
        """Search Google Shopping with enhanced retry logic for CAPTCHA"""
        product_name = product.get('product_name', '').strip()
        company_name = product.get('companyName', {}).get('name', '').strip()
        barcode = product.get('bar_code_value', '').strip()
        
        # Initialize result structure
        result = {
            'product_name': product_name,
            'bar_code_value': barcode,
            'sale_price': product.get('sale_price', {}).get('sale'),
            'regular_price': product.get('price', {}).get('regular'),
            'coastalbeauty_price': None,
            'coastalbeauty_url': None,
            'beautywellness_price': None,
            'beautywellness_url': None,
            'shopempire_price': None,
            'shopempire_url': None,
            'matandmax_price': None,
            'matandmax_url': None,
            'shoptbbs_price': None,
            'shoptbbs_url': None,
            'liviabeauty_price': None,
            'liviabeauty_url': None,
            'aonebeauty_price': None,
            'aonebeauty_url': None,
            'cosmeticworld_price': None,
            'cosmeticworld_url': None
        }
        
        if not product_name or not company_name:
            logger.warning("❌ Missing product name or company name")
            return result
        
        # Try different search query variations
        search_queries = [
            f"{company_name} {product_name}",
            f'"{company_name}" "{product_name}"',
            f"{product_name} {company_name}",
        ]
        
        # If we have a barcode, try that too
        if barcode:
            search_queries.append(f"{company_name} {barcode}")
        
        for i, search_query in enumerate(search_queries):
            logger.info(f"🔍 Attempt {i+1}: Searching for '{search_query}'")
            
            # Construct Google Shopping URL
            encoded_query = quote_plus(search_query)
            google_shopping_url = f"https://www.google.com/search?q={encoded_query}&gl=ca&hl=en"

            # NEW: Retry logic for CAPTCHA
            max_retries = 3
            response_html = None
            for retry in range(max_retries):
                try:
                    response_html = self.make_request(google_shopping_url)
                    if response_html is None:
                        if retry < max_retries - 1:
                            logger.warning(f"🔄 Request failed (attempt {retry + 1}/{max_retries}), retrying...")
                            time.sleep(random.uniform(30, 60))  # Wait before retry
                            continue
                        else:
                            logger.error(f"❌ All retries failed for search query {i+1}")
                            break
                    else:
                        # Success! Break out of retry loop
                        break
                except Exception as e:
                    logger.error(f"❌ Error in retry {retry + 1}: {e}")
                    if retry < max_retries - 1:
                        time.sleep(random.uniform(30, 60))
                        continue
                    else:
                        response_html = None
            
            if not response_html:
                logger.warning(f"❌ Failed to get response for attempt {i+1}")
                continue
            
            # Analyze what we got
            analysis = self.analyze_page_content(response_html, search_query)
            logger.info(f"📊 Page analysis for attempt {i+1}:")
            logger.info(f"   Title: {analysis['title'][:100]}...")
            logger.info(f"   Has shopping results: {analysis['has_shopping_results']}")
            logger.info(f"   Total links: {analysis['total_links']}")
            logger.info(f"   Price mentions: {len(analysis['price_mentions'])}")
            logger.info(f"   Target domains found: {analysis['domain_mentions']}")
            
            if analysis['price_mentions']:
                logger.info(f"   Sample prices: {analysis['price_mentions'][:5]}")
            
            soup = BeautifulSoup(response_html, 'html.parser')
            
            # Try to extract results with more flexible approach
            shopping_results = []
            
            # Primary selectors (most specific first)
            selectors = [
                'a.plantl.clickable-card.pla-unit-single-clickable-target',
                'a.plantl',
                'a[data-merchant-id]',
                'a[data-offer-id]',
                'a[href*="matandmax.com"]',
                'a[href*="beautywellness.ca"]',
                'a[href*="coastalbeauty.ca"]',
                'a[href*="shopempire.ca"]',
                'a[href*="shoptbbs.ca"]',
                'a[href*="liviabeauty.ca"]',
                'a[href*="aonebeauty.com"]',
                'a[href*="cosmeticworld.ca"]'
            ]
            
            for selector in selectors:
                elements = soup.select(selector)
                if elements:
                    shopping_results.extend(elements)
                    logger.info(f"   Found {len(elements)} results with: {selector}")
            
            # Remove duplicates while preserving order
            seen_hrefs = set()
            unique_results = []
            for elem in shopping_results:
                href = elem.get('href', '')
                if href and href not in seen_hrefs:
                    seen_hrefs.add(href)
                    unique_results.append(elem)
            
            shopping_results = unique_results
            
            if not shopping_results:
                logger.warning(f"❌ No shopping results found for attempt {i+1}")
                if i < len(search_queries) - 1:
                    logger.info("   Trying next search variation...")
                    time.sleep(5)  # Brief pause between attempts
                    continue
                else:
                    logger.warning("   No more search variations to try")
                    return result
            
            logger.info(f"📦 Found {len(shopping_results)} unique shopping results")
            
            # Process results
            for j, result_elem in enumerate(shopping_results[:20]):
                try:
                    href = result_elem.get('href', '')
                    aria_label = result_elem.get('aria-label', '')
                    text_content = result_elem.get_text()
                    
                    logger.debug(f"   Result {j+1}: {href[:50]}...")
                    if aria_label:
                        logger.debug(f"   Aria-label: {aria_label[:100]}...")
                    
                    self.extract_competitor_data_from_link(result_elem, result, product, j+1)
                except Exception as e:
                    logger.debug(f"Error processing result {j+1}: {e}")
                    continue
            
            # Check if we found anything
            found_any = any(result.get(f'{key}_price') is not None for key in self.target_domains.values())
            
            if found_any:
                logger.info("✅ Found competitor data, using this search")
                break
            else:
                logger.warning(f"❌ No competitor data extracted from attempt {i+1}")
                if i < len(search_queries) - 1:
                    logger.info("   Trying next search variation...")
                    time.sleep(5)
        
        # Log final results
        found_competitors = []
        for domain, key in self.target_domains.items():
            if result.get(f'{key}_price') is not None:
                price = result[f'{key}_price']
                found_competitors.append(f"{key}: ${price}")
                logger.info(f"✅ Final result - {key}: ${price}")
        
        if found_competitors:
            logger.info(f"🎯 Total competitors found: {len(found_competitors)}")
        else:
            logger.warning("❌ No competitor prices found after all attempts")
        
        return result

    def extract_competitor_data_from_link(self, link_elem, result_dict: Dict, product: Dict, position: int):
        """Enhanced competitor data extraction - Choose best match, not lowest price"""
        try:
            href = link_elem.get('href', '')
            if not href:
                return
            
            # Clean up URLs
            if '/url?q=' in href:
                match = re.search(r'/url\?q=([^&]+)', href)
                if match:
                    from urllib.parse import unquote
                    href = unquote(match.group(1))
            
            parsed_url = urlparse(href)
            domain = parsed_url.netloc.lower()
            if domain.startswith('www.'):
                domain = domain[4:]
            
            # Check if this is a target domain
            competitor_key = None
            for target_domain, key in self.target_domains.items():
                if target_domain in domain:
                    competitor_key = key
                    break
            
            if not competitor_key:
                return
            
            logger.debug(f"🎯 Processing {competitor_key} (pos {position}): {href[:80]}...")
            
            # Extract price from aria-label or text
            aria_label = link_elem.get('aria-label', '')
            price = None
            
            if aria_label:
                price = self.extract_price_from_aria_label(aria_label)
                if price:
                    logger.debug(f"   Price from aria-label: ${price}")
            
            if not price:
                text_content = link_elem.get_text()
                price = self.parse_price_text(text_content)
                if price:
                    logger.debug(f"   Price from text: ${price}")
            
            if price:
                # RELAXED VALIDATION: Trust Google's matching + basic price sanity check
                validation_passed = False
                
                # Method 1: Position-based trust (top results are more reliable)
                if position <= 10:
                    logger.debug(f"   ✅ Position-based validation: {position} <= 10")
                    validation_passed = True
                
                # Method 2: Price reasonableness check
                elif self.is_price_reasonable(price, product):
                    logger.debug(f"   ✅ Price reasonableness validation passed")
                    validation_passed = True
                
                # Method 3: Basic keyword matching (much more lenient)
                elif self.has_basic_product_match(aria_label, link_elem.get_text(), product):
                    logger.debug(f"   ✅ Basic keyword validation passed")
                    validation_passed = True
                
                # Method 4: For positions 11-20, just trust Google if it's from target domain
                elif position <= 20:
                    logger.debug(f"   ✅ Extended position trust: {position} <= 20")
                    validation_passed = True
                
                if validation_passed:
                    # Choose best match logic instead of lowest price
                    existing_price = result_dict.get(f'{competitor_key}_price')
                    existing_position = result_dict.get(f'{competitor_key}_position', float('inf'))
                    
                    should_update = False
                    update_reason = ""
                    
                    if existing_price is None:
                        # No existing price - accept this one
                        should_update = True
                        update_reason = "first match"
                    else:
                        # We have an existing price - use best match logic
                        match_score = self.calculate_match_score(aria_label, link_elem.get_text(), product, position)
                        existing_match_score = result_dict.get(f'{competitor_key}_match_score', 0)
                        
                        if match_score > existing_match_score:
                            should_update = True
                            update_reason = f"better match (score: {match_score:.2f} > {existing_match_score:.2f})"
                        elif match_score == existing_match_score and position < existing_position:
                            should_update = True
                            update_reason = f"same match quality but better position ({position} < {existing_position})"
                        elif match_score == existing_match_score and position == existing_position and price < existing_price:
                            should_update = True
                            update_reason = f"same match and position, lower price (${price} < ${existing_price})"
                    
                    if should_update:
                        result_dict[f'{competitor_key}_price'] = price
                        result_dict[f'{competitor_key}_url'] = href
                        result_dict[f'{competitor_key}_position'] = position
                        result_dict[f'{competitor_key}_match_score'] = match_score if 'match_score' in locals() else 1.0
                        logger.info(f"✅ ACCEPTED {competitor_key}: ${price} (pos {position}) - {update_reason}")
                    else:
                        logger.debug(f"   Skipping {competitor_key} - existing match is better")
                else:
                    logger.debug(f"   ❌ Validation failed for {competitor_key}")
            else:
                logger.debug(f"   No price found for {competitor_key}")
                
        except Exception as e:
            logger.debug(f"Error in extract_competitor_data_from_link: {e}")

    def calculate_match_score(self, aria_label: str, text_content: str, product: Dict, position: int) -> float:
        """Calculate how well this result matches our product (higher = better match)"""
        try:
            search_text = (aria_label + " " + text_content).lower()
            company_name = product.get('companyName', {}).get('name', '').lower()
            product_name = product.get('product_name', '').lower()
            
            score = 0.0
            
            # Position bonus (earlier positions are more likely to be correct)
            position_score = max(0, (21 - position) / 20)  # position 1 = 1.0, position 20 = 0.05
            score += position_score * 0.3
            
            # Brand name matching
            if company_name:
                brand_parts = re.split(r'[^a-zA-Z0-9]+', company_name)
                brand_keywords = [part for part in brand_parts if len(part) > 2]
                brand_matches = sum(1 for keyword in brand_keywords if keyword in search_text)
                if brand_keywords:
                    brand_match_ratio = brand_matches / len(brand_keywords)
                    score += brand_match_ratio * 0.4
            
            # Product name matching
            if product_name:
                product_parts = re.split(r'[^a-zA-Z0-9]+', product_name)
                product_keywords = [part for part in product_parts if len(part) > 2]
                product_matches = sum(1 for keyword in product_keywords if keyword in search_text)
                if product_keywords:
                    product_match_ratio = product_matches / len(product_keywords)
                    score += product_match_ratio * 0.3
            
            # Exact phrase bonuses
            if company_name and company_name in search_text:
                score += 0.2
            
            # Look for size/quantity matches (e.g., "33.8oz")
            size_patterns = re.findall(r'\d+(?:\.\d+)?\s*(?:oz|ml|g|kg|lb)', product_name.lower())
            for size_pattern in size_patterns:
                if size_pattern in search_text:
                    score += 0.1
            
            return min(score, 1.0)  # Cap at 1.0
            
        except Exception as e:
            logger.debug(f"Error calculating match score: {e}")
            return 0.5  # Default moderate score

    def clean_result(self, result: Dict) -> Dict:
        """Remove internal tracking fields from final result"""
        cleaned = {}
        for key, value in result.items():
            if not key.endswith('_position') and not key.endswith('_match_score'):
                cleaned[key] = value
        return cleaned

    def is_price_reasonable(self, competitor_price: float, product: Dict) -> bool:
        """Check if the competitor price is in a reasonable range compared to our price"""
        try:
            # Get our price (prefer sale price, fall back to regular)
            our_price = None
            if product.get('sale_price', {}).get('sale'):
                our_price = float(product['sale_price']['sale'])
            elif product.get('price', {}).get('regular'):
                our_price = float(product['price']['regular'])
            
            if our_price:
                # Allow prices within 0.3x to 3x of our price (pretty generous range)
                min_price = our_price * 0.3
                max_price = our_price * 3.0
                is_reasonable = min_price <= competitor_price <= max_price
                logger.debug(f"   Price check: ${competitor_price} vs our ${our_price} (range: ${min_price:.2f}-${max_price:.2f}) = {is_reasonable}")
                return is_reasonable
            else:
                # If we don't have our price, just check if it's a sensible cosmetic/beauty price
                is_reasonable = 5.0 <= competitor_price <= 500.0
                logger.debug(f"   Generic price check: ${competitor_price} in $5-500 range = {is_reasonable}")
                return is_reasonable
                
        except (ValueError, TypeError, KeyError):
            # If we can't parse prices, just check if it's reasonable for beauty products
            is_reasonable = 5.0 <= competitor_price <= 500.0
            logger.debug(f"   Fallback price check: ${competitor_price} in $5-500 range = {is_reasonable}")
            return is_reasonable

    def has_basic_product_match(self, aria_label: str, text_content: str, product: Dict) -> bool:
        """Very basic keyword matching - much more lenient than before"""
        try:
            search_text = (aria_label + " " + text_content).lower()
            
            # Get brand/company name and split into parts
            company_name = product.get('companyName', {}).get('name', '').lower()
            product_name = product.get('product_name', '').lower()
            
            # Split brand names and product names into keywords
            brand_keywords = set()
            product_keywords = set()
            
            if company_name:
                # Handle common brand variations
                brand_parts = re.split(r'[^a-zA-Z0-9]+', company_name)
                brand_keywords.update([part for part in brand_parts if len(part) > 2])
            
            if product_name:
                # Get meaningful words from product name
                product_parts = re.split(r'[^a-zA-Z0-9]+', product_name)
                product_keywords.update([part for part in product_parts if len(part) > 3])
            
            # Check if any brand keyword matches
            brand_match = any(keyword in search_text for keyword in brand_keywords if keyword)
            
            # Check if any significant product keyword matches
            product_match = any(keyword in search_text for keyword in product_keywords if keyword)
            
            # Accept if either brand OR product keywords match
            has_match = brand_match or product_match
            
            if has_match:
                logger.debug(f"   Keyword match: brand_keywords={brand_keywords}, product_keywords={product_keywords}")
            
            return has_match
            
        except Exception as e:
            logger.debug(f"   Keyword matching error: {e}")
            return False  # If anything goes wrong, don't match

    def extract_price_from_aria_label(self, aria_label: str) -> Optional[float]:
        """Extract price from aria-label"""
        if not aria_label:
            return None
        
        price_patterns = [
            r'for\s+\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*CAD',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, aria_label, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1).replace(',', '')
                    price = float(price_str)
                    if 1.0 <= price <= 2000.0:
                        return round(price, 2)
                except (ValueError, TypeError):
                    continue
        
        return None

    def parse_price_text(self, text: str) -> Optional[float]:
        """Parse price from text"""
        if not text:
            return None
        
        patterns = [
            r'C?\$\s*(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)',
            r'(\d{1,4}(?:,\d{3})*(?:\.\d{2})?)\s*CAD',
            r'(\d{1,4}(?:,\d{3})*(?:\.\d{2}))',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    price_str = match.replace(',', '')
                    price = float(price_str)
                    if 1.0 <= price <= 2000.0:
                        return round(price, 2)
                except (ValueError, TypeError):
                    continue
        
        return None

    def process_products(self, products: List[Dict], max_products: int = None) -> List[Dict]:
        """Enhanced product processing with batch tracking"""
        if max_products:
            products = products[:max_products]
        
        results = []
        total_products = len(products)
        
        logger.info(f"🚀 Starting Google Shopping search for {total_products} products")
        logger.info(f"🎯 Looking for prices from: {', '.join(self.target_domains.values())}")
        logger.info(f"🛡️ Anti-detection: {self.batch_size} searches per cooldown cycle")
        logger.info(f"⏰ Cooldown duration: {self.batch_cooldown_min/60:.1f}-{self.batch_cooldown_max/60:.1f} minutes")
        logger.info(f"✨ Using BEST MATCH logic instead of lowest price!")
        
        for i, product in enumerate(products):
            logger.info(f"\n{'='*80}")
            logger.info(f"📦 PROCESSING PRODUCT {i+1}/{total_products}")
            logger.info(f"Product: {product.get('companyName', {}).get('name', 'Unknown')} - {product.get('product_name', 'Unknown')}")
            logger.info(f"🔢 Total searches so far: {self.searches_count}")
            logger.info(f"{'='*80}")
            
            try:
                result = self.search_google_shopping(product)
                cleaned_result = self.clean_result(result)
                results.append(cleaned_result)
                
                found_count = sum(1 for key, value in cleaned_result.items() 
                                if key.endswith('_price') and value is not None)
                logger.info(f"📊 Product {i+1} complete: Found {found_count}/{len(self.target_domains)} competitor prices")
                
                # Show batch progress
                next_cooldown = ((self.searches_count // self.batch_size) + 1) * self.batch_size
                searches_until_cooldown = next_cooldown - self.searches_count
                if searches_until_cooldown <= 5:
                    logger.info(f"⚠️  Approaching batch cooldown: {searches_until_cooldown} searches remaining")
                
                if i < total_products - 1:
                    delay = random.uniform(2, 5)  # Shorter delay since we have batch cooldowns
                    logger.info(f"⏳ Brief pause: {delay:.1f}s before next product...")
                    time.sleep(delay)
                
            except Exception as e:
                logger.error(f"❌ Error processing product {i+1}: {e}")
                results.append(self.create_empty_result(product))
        
        logger.info(f"\n🏁 FINAL STATS:")
        logger.info(f"   Total searches performed: {self.searches_count}")
        logger.info(f"   CAPTCHA encounters: {self.captcha_detected_count}")
        logger.info(f"   Batch cooldowns taken: {self.searches_count // self.batch_size}")
        
        # Clean up final driver
        self.cleanup_driver()
        
        return results

    def create_empty_result(self, product: Dict) -> Dict:
        """Create empty result structure"""
        return {
            'product_name': product.get('product_name', ''),
            'bar_code_value': product.get('bar_code_value', ''),
            'sale_price': product.get('sale_price', {}).get('sale'),
            'regular_price': product.get('price', {}).get('regular'),
            'coastalbeauty_price': None, 'coastalbeauty_url': None,
            'beautywellness_price': None, 'beautywellness_url': None,
            'shopempire_price': None, 'shopempire_url': None,
            'matandmax_price': None, 'matandmax_url': None,
            'shoptbbs_price': None, 'shoptbbs_url': None,
            'liviabeauty_price': None, 'liviabeauty_url': None,
            'aonebeauty_price': None, 'aonebeauty_url': None,
            'cosmeticworld_price': None, 'cosmeticworld_url': None
        }

def main():
    # Enable debug mode for first run
    scraper = GoogleShoppingPriceScraper(debug_mode=True)
    
    input_file = 'data.json'
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            products = json.load(f)
        logger.info(f"📂 Loaded {len(products)} products from {input_file}")
    except FileNotFoundError:
        logger.error(f"❌ Input file {input_file} not found")
        return
    except json.JSONDecodeError as e:
        logger.error(f"❌ Error parsing JSON: {e}")
        return

    logger.info("🧪 Starting with enhanced anti-detection system...")
    results = scraper.process_products(products, max_products=1500)
    
    # Save results
    output_file = input_file.replace('.json', '_anti_detection_results.json')
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Results saved to {output_file}")
        
        # Show sample
        if results:
            logger.info("\n📋 Sample result:")
            sample = results[0]
            for key, value in sample.items():
                if value is not None:
                    logger.info(f"   {key}: {value}")
        
        # Show summary statistics
        logger.info(f"\n📊 SUMMARY:")
        total_found = 0
        for domain_key in scraper.target_domains.values():
            count = sum(1 for result in results if result.get(f'{domain_key}_price') is not None)
            total_found += count
            logger.info(f"   {domain_key}: {count}/{len(results)} products")
        logger.info(f"   TOTAL: {total_found} prices found across all competitors")
        logger.info(f"🛡️ Anti-detection system successfully completed {scraper.searches_count} searches")
        
    except Exception as e:
        logger.error(f"❌ Error saving results: {e}")

if __name__ == "__main__":
    main()