import os
import re
import unicodedata
from urllib.parse import urlparse, parse_qs, urlunparse
import secrets
import string
from itertools import islice
import random
from shared_state import log_terminal



def slugify(value):
    value = str(value)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = value.lower()
    value = value.replace("+", "-plus")
    value = re.sub(r'(\d+)\.(\d+)', r'\1_\2', value)
    value = re.sub(r'\s+', '-', value)
    value = re.sub(r'[^a-z0-9\-_]', '', value)
    value = re.sub(r'-{2,}', '-', value)
    return value.strip('-')

def clean_product_name(raw):
    """
    (FINAL ROBUST PIPELINE - 2-STAGE)
    This function first isolates the product name from sales "noise" (like price,
    percent, etc.), and THEN runs the keyword cleaner on the result.
    """
    if not isinstance(raw, str):
        return ""

    # --- STAGE 1: THE "NOISE ISOLATOR" ---
    # We will find the *first index* of any "noise" keyword and slice the string there.
    # This correctly handles "Galaxy Tab A9₱5560..."
    
    raw = re.sub(r'\[.*?\]', '', raw) # Remove bracketed terms first
    raw = re.sub(r'\(.*?\)', '', raw) # Remove parenthetical terms

    # Create a regex to find the first occurrence of any "noise" indicator
    # This looks for price (₱), percent (%), or sales metrics (K sold, sold, etc.)
    stop_pattern = re.compile(r'(₱|%|\d+K\s*sold|\d+\s*sold|Fast Shipping)', re.IGNORECASE)
    match = stop_pattern.search(raw)
    if match:
        # If we find noise, chop the string off right before it starts
        raw = raw[:match.start()]

    # --- STAGE 2: THE "MODEL CLEANER" ---
    # Now we run our keyword-based cleaner on the *result* of Stage 1.
    # This will clean our *other* test case ("...S24 Ultra + AI...")

    # Remove combo memory specs
    raw = re.sub(r'\b\d+\s*\+\s*\d+\s*(GB)?\b', '', raw, flags=re.IGNORECASE)
    # Remove standalone memory
    raw = re.sub(r'\b\d+\s*GB\b', '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'\b\d+\s*GB\s*RAM\b', '', raw, flags=re.IGNORECASE)

    # Remove various spec/marketing keywords
    spec_keywords = r'\b(RAM|ROM|Storage|Wi[- ]?Fi|Android|Tablet|Phone|Smartphone|Global Version|With Warranty|Online Exclusive|Official Store)\b'
    raw = re.sub(spec_keywords, '', raw, flags=re.IGNORECASE)
    raw = re.sub(r'With\s+\d+-year\s+Warranty', '', raw, flags=re.IGNORECASE)
    
    # Trim after the main model variant keywords (Pro, Ultra, 5G, etc.)
    variant_keywords = [
        'Pro Plus', 'Pro\+', 'Pro', 'Ultra', 'Plus', 'Lite', 'SE', '5G', '4G', 'LTE', 'FE'
    ]
    best_match_pos = -1
    last_keyword_found = None

    for kw in variant_keywords:
        matches = list(re.finditer(rf'\b{kw}\b', raw, re.IGNORECASE))
        if matches:
            last_match_end_pos = matches[-1].end()
            if last_match_end_pos > best_match_pos:
                best_match_pos = last_match_end_pos
                last_keyword_found = kw

    if best_match_pos > -1:
        raw = raw[:best_match_pos]

    # Final cleanup
    raw = re.sub(r'[-,.|+]', '', raw) 
    raw = re.sub(r'\s{2,}', ' ', raw).strip()

    return raw.strip()

def extract_prices_shopee(raw_text: str):
    """
    (FINAL, ROBUST SHOPEE VERSION)
    Correctly handles all 3 scenarios for Shopee data:
    1. Two explicit prices are found.
    2. One price and a discount percentage are found.
    3. Only one price with no discount is found.
    """
    if not raw_text or not isinstance(raw_text, str):
        return None, None

    # Pattern for prices explicitly prefixed by a '₱' symbol.
    price_pattern = r"₱\s*([\d,]+\.?\d*)"
    # Pattern for discount percentage like "-27%"
    discount_pattern = r"-(\d{1,2})%"

    try:
        amounts = sorted([
            float(price.replace(",", ""))
            for price in re.findall(price_pattern, raw_text)
        ])
        discount_match = re.search(discount_pattern, raw_text)

        sale_price = None
        regular_price = None

        if len(amounts) >= 2:
            # Scenario 1: Two explicit prices found (e.g., "₱10,000 ₱12,000").
            sale_price = amounts[0]
            regular_price = amounts[-1]

        elif len(amounts) == 1 and discount_match:
            # Scenario 2: One price and a discount found (e.g., "₱23,000-27%").
            # The found price is the SALE price.
            sale_price = amounts[0]
            discount_percentage = float(discount_match.group(1)) / 100
            if 0 < discount_percentage < 1:
                # Calculate the original price from the sale price and discount
                regular_price = round(sale_price / (1 - discount_percentage), 2)
        
        elif len(amounts) == 1:
            # Scenario 3: Only one price and NO discount was found.
            # The found price is the REGULAR price.
            sale_price = None
            regular_price = amounts[0]

        return sale_price, regular_price

    except Exception:
        # Fail gracefully on any parsing error
        return None, None

# def extract_prices_shopee(raw_text: str):
#     """
#     (FINAL, ROBUST SHOPEE VERSION)
#     Correctly handles all 3 scenarios:
#     1. Two explicit prices are found.
#     2. One price and a discount percentage are found.
#     3. Only one price with no discount is found.
#     """
#     if not raw_text or not isinstance(raw_text, str):
#         return None, None

#     # Pattern for 4+ digit numbers, with or without ₱
#     price_pattern = r"₱?\s*([\d,]{4,8})(?!\d)"
#     # Pattern for discount percentage like "-27%"
#     discount_pattern = r"-(\d{1,2})%"

#     try:
#         amounts = sorted([float(p.replace(",", "")) for p in re.findall(price_pattern, raw_text)])
#         discount_match = re.search(discount_pattern, raw_text)

#         sale_price = None
#         regular_price = None

#         if len(amounts) >= 2:
#             # Scenario 1: Two explicit prices found (e.g., "₱10,000 ₱12,000").
#             sale_price = amounts[0]
#             regular_price = amounts[-1]

#         elif len(amounts) == 1 and discount_match:
#             # Scenario 2: One price and a discount found (e.g., "₱23,000-27%").
#             # The found price is the SALE price.
#             sale_price = amounts[0]
#             discount_percentage = float(discount_match.group(1)) / 100
#             if 0 < discount_percentage < 1:
#                 # Calculate the original price from the sale price and discount
#                 regular_price = round(sale_price / (1 - discount_percentage), 2)
        
#         elif len(amounts) == 1:
#             # Scenario 3: Only one price and NO discount was found.
#             # The found price is the REGULAR price.
#             sale_price = None
#             regular_price = amounts[0]

#         return sale_price, regular_price

#     except Exception:
#         # Fail gracefully on any parsing error
#         return None, None

def extract_prices(raw_text: str):
    """
    (Robust Version)
    Parses raw text to find prices and discounts, handling all 3 scenarios:
    1. Two prices found (sale, regular)
    2. One price + discount % found (calculates regular)
    3. One price, no discount found (sets as regular_price)
    """
    # Regex to find all valid prices (4-8 digits, with or without '₱' and commas)
    price_pattern = r"₱?\s*([\d,]{4,8})(?!\d)"
    # Regex to find a discount percentage (e.g., "25% OFF", "25%", "-25%")
    discount_pattern = r"(\d{1,2})%\s*(?:OFF)?"

    try:
        amounts = [float(p.replace(",", "")) for p in re.findall(price_pattern, raw_text)]
        discount_match = re.search(discount_pattern, raw_text, re.IGNORECASE)

        sale_price = None
        regular_price = None

        if len(amounts) >= 2:
            # Scenario 1: Two prices found. Easy.
            sale_price = min(amounts)
            regular_price = max(amounts)

        elif len(amounts) == 1 and discount_match:
            # Scenario 2: One price + discount %.
            sale_price = amounts[0]
            discount_percentage = float(discount_match.group(1)) / 100
            if 0 < discount_percentage < 1:
                # Calculate the original price from the sale price and discount
                regular_price = round(sale_price / (1 - discount_percentage), 2)
            else:
                regular_price = None # Invalid discount like "0%"

        elif len(amounts) == 1:
            # Scenario 3: Our "Single Price" edge case. This item is NOT on sale.
            sale_price = None  # Setting to None (it will become "" in the API payload)
            regular_price = amounts[0] # The single price IS the regular price

        # If no amounts are found, both remain None, which is correct.
        return sale_price, regular_price

    except Exception:
        # Fail gracefully on any parsing error
        return None, None

def extract_hyperlink_from_cell(cell: dict):
    text = cell.get("formattedValue", "") or ""
    link = cell.get("hyperlink")
    if not link:
        for run in cell.get("textFormatRuns", []) or []:
            fmt = run.get("format", {})
            if fmt.get("link", {}).get("uri"):
                link = fmt["link"]["uri"]
                break
    return text.strip(), link

def generate_uls_trackid(length: int = 12) -> str:
    """
    Generate a Shopee-like uls_trackid string (12 chars, lowercase + digits).
    Example: '53llb9n700l0'
    """
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# --- NEW: Affiliate Link Generation Helpers (Your Code) ---
def _rand_lower_alnum(n: int) -> str:
    """Return n chars of [a-z0-9] using cryptographically secure randomness."""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def generate_shopee_trackid(length: int = 12) -> str:
    """Generates a Shopee-style uls_trackid."""
    return _rand_lower_alnum(length)

def generate_lazada_click_id(prefix: str = "clk") -> str:
    """Lazada-style click ID (mkttid)."""
    total_length = random.choice([20, 21])
    return prefix + _rand_lower_alnum(total_length - len(prefix))

def generate_utm_content(product_slug: str, max_len: int = 18) -> str:
    """
    Generate a Shopee-friendly utm_content value:
    - Alphanumeric only (no spaces or symbols).
    - Lowercased.
    - Truncated to max_len characters.
    - Falls back to "default" if empty.
    """
    if not isinstance(product_slug, str) or not product_slug.strip():
        return "default"

    # Keep only letters and numbers
    alnum_only = re.sub(r'[^A-Za-z0-9]', '', product_slug)

    # Apply length limit and fallback
    return (alnum_only.lower()[:max_len] or "gadgetph")

# --- FINAL, MULTI-SOURCE CONVERTER ---
def convert_to_affiliate_link(url: str, product_slug: str) -> str:
    """
    (FINAL, ROBUST VERSION)
    Converts a Shopee or Lazada product URL into a clean affiliate link,
    stripping any old tracking params and applying the correct new ones.
    """
    if not url:
        return None

    # 1. Get the "clean" base URL by stripping all existing query parameters.
    base_url = url.split('?')[0]
    
    # --- 2. Router: Apply the correct parameters based on the source ---
    
    if 'shopee.ph' in str(url):
        utm_content = generate_utm_content(product_slug)  # ✅ correct function call
        our_params = (
            f"?uls_trackid={generate_shopee_trackid()}"
            f"&utm_campaign=id_HURtY6Geqq"   # Your Shopee Campaign ID
            f"&utm_content={utm_content}"
            f"&utm_medium=affiliates"
            f"&utm_source=an_13327880016"    # Your Shopee Source ID
        )
        return base_url + our_params

    elif 'lazada.com.ph' in str(url):
        lazada_pid = os.getenv("LAZADA_AFFILIATE_PID")
        if not lazada_pid:
            # If PID is not set, we cannot generate a valid link. Return the clean URL.
            return base_url

        click_id = generate_lazada_click_id()
        our_params = (
            f"?laz_trackid=2:{lazada_pid}:{click_id}"
            f"&mkttid={click_id}"
        )
        return base_url + our_params
    
    else:
        # If it's not a known source, return the clean base URL
        return base_url

# def convert_to_affiliate_link(
#     url: str,
#     product_slug: str = "",
#     campaign_id: str = "id_HURtY6Geqq",  # <-- replace with your real Shopee campaign ID
#     source_id: str = "an_13327880016",   # <-- your affiliate source ID
#     term: str | None = None
#     ) -> str | None:
#     """
#     Convert a Shopee product URL into a clean affiliate link.
#     - Strips any old tracking/query params.
#     - Inserts a fresh uls_trackid and fixed utm_campaign each time.
#     - Passes through non-Shopee URLs unchanged.
#     """
#     if not url:
#         return None

#     if 'shopee.ph' not in str(url):
#         return url

#     # 1. Strip existing query parameters
#     base_url = url.split('?')[0]

#     # 2. Generate Shopee-style tracking ID
#     tracking_token = generate_uls_trackid()

#     # 3. Build affiliate parameters
#     params = (
#         f"?uls_trackid={tracking_token}"
#         f"&utm_campaign={campaign_id}"
#         f"&utm_content=----"
#         f"&utm_medium=affiliates"
#         f"&utm_source={source_id}"
#     )
#     if term:
#         params += f"&utm_term={term}"

#     # 4. Return final link
#     return base_url + params

def parse_ecommerce_url(url):
    """
    Parses a Shopee or Lazada URL to extract the product_id and shop_id.
    Returns a dictionary {'product_id': str, 'shop_id': str, 'source': str}.
    """
    if not isinstance(url, str):
        return {'product_id': None, 'shop_id': None, 'source': None}

    hostname = urlparse(url).hostname
    
    # Shopee Logic: ...name.i.SHOP_ID.PRODUCT_ID?sp_atk=...
    if 'shopee' in str(hostname):
        match = re.search(r'[-.]i\.(\d+)\.(\d+)', url)
        if match:
            shop_id, product_id = match.groups()
            return {'product_id': str(product_id), 'shop_id': str(shop_id), 'source': 'shopee'}
    
    # Lazada Logic: ...name-sPRODUCT_ID.html... OR ...?shop_id=...
    if 'lazada' in str(hostname):
        match = re.search(r'-i(\d+)\.html', url)
        product_id = match.group(1) if match else None
        
        query_params = parse_qs(urlparse(url).query)
        shop_id = query_params.get('shop_id', [None])[0]

        if product_id:
             return {'product_id': str(product_id), 'shop_id': str(shop_id) if shop_id else None, 'source': 'lazada'}

    return {'product_id': None, 'shop_id': None, 'source': None}

# --- NEW: LAZADA-SPECIFIC PARSERS ---
def clean_product_name_lazada(first_line_text: str) -> str:
    """
    (FINAL, ROBUST VERSION)
    This function first isolates the product name from sales "noise" (like specs,
    battery info, etc.), and THEN runs the keyword cleaner on the result.
    It's designed to handle the specific format of the Lazada sheet.
    """
    if not isinstance(first_line_text, str):
        return ""

    # --- STAGE 1: PRE-CLEANUP ---
    # Remove all types of bracketed text first, including full-width brackets
    name_part = re.sub(r'\[.*?\]', '', first_line_text)
    name_part = re.sub(r'\(.*?\)', '', name_part)
    name_part = re.sub(r'【.*?】', '', name_part)

    # --- STAGE 2: THE "NOISE ISOLATOR" ---
    # Find the *first occurrence* of a spec or noise keyword and chop the string there.
    # This handles both cases with the '丨' separator and those without.
    stop_pattern = re.compile(r'(丨|\d{4,5}mAh|\d+W Fast Charge|IP\d+)', re.IGNORECASE)
    match = stop_pattern.search(name_part)
    if match:
        # If we find noise, chop the string off right before it starts
        name_part = name_part[:match.start()]

    # --- STAGE 3: FINAL KEYWORD CLEANUP ---
    # Now, run a final cleanup on the isolated name to remove generic words.
    generic_keywords = r'\b(cellphone|phone|smartphone)\b'
    name_part = re.sub(generic_keywords, '', name_part, flags=re.IGNORECASE)
    
    # Final whitespace trim
    return name_part.strip()

def extract_prices_lazada(price_lines: list) -> tuple:
    """
    (V5 - FINAL CORRECTED VERSION)
    Uses the original working logic and applies a minimal fix at the end to correctly
    assign the variables in a single-price scenario.
    """
    sale_price = None
    regular_price = None

    price_pattern = r"([\d,]+\.?\d*)"
    
    candidate_lines = [line for line in price_lines if '₱' in line]
    
    for line in candidate_lines:
        match = re.search(price_pattern, line)
        if not match:
            continue
        
        price_val = float(match.group(1).replace(",", ""))
        
        # This part correctly identifies which price is which when two are present
        text_part = re.sub(r"₱?\s*[\d,]+\.?\d*", "", line).strip()
        if len(text_part) > 2:  
            regular_price = price_val
        else:
            sale_price = price_val
            
    # This sanity check also remains correct
    if regular_price and sale_price and regular_price < sale_price:
        sale_price, regular_price = regular_price, sale_price

    # --- THE MINIMAL FIX IS HERE ---
    # After the loop, if we only found a sale_price but no regular_price,
    # it means we found a single price on a clean line. This should be the regular price.
    if sale_price is not None and regular_price is None:
        # Re-assign the single found price to be the regular_price.
        regular_price = sale_price
        sale_price = None
            
    return sale_price, regular_price

# def extract_prices_lazada(price_lines: list) -> tuple:
#     """
#     (Smarter Version)
#     Extracts sale and regular price from a list of 2-3 text lines
#     from the Lazada sheet by identifying which lines contain extra text.
#     """
#     sale_price = None
#     regular_price = None

#     price_pattern = r"([\d,]+\.?\d*)"
    
#     # --- FIX 1: Only look at lines that actually contain a price symbol ---
#     candidate_lines = [line for line in price_lines if '₱' in line]
    
#     for line in candidate_lines:
#         match = re.search(price_pattern, line)
#         if not match:
#             continue
        
#         price_val = float(match.group(1).replace(",", ""))
        
#         # --- FIX 2: Check if the line contains significant text besides the price ---
#         # We strip the price, symbol, and whitespace to see what's left.
#         text_part = re.sub(r"₱?\s*[\d,]+\.?\d*", "", line).strip()
        
#         # If there are more than 2 characters of leftover text (like "Voucher..."), it's the regular price.
#         if len(text_part) > 2:  
#             regular_price = price_val
#         else: # Otherwise, the line is basically just the price, so it's the sale price.
#             sale_price = price_val
            
#     # Final sanity check: If for some reason regular price is less than sale price, swap them.
#     if regular_price and sale_price and regular_price < sale_price:
#         sale_price, regular_price = regular_price, sale_price

#     # This handles our "single price" logic from before. If only a regular price is found,
#     # it means the item is not on sale.
#     if regular_price and not sale_price:
#         # Check if the text implies a discount. If not, it's a regular price item.
#         has_discount_text = any("%" in line or "Voucher" in line.title() for line in candidate_lines)
#         if not has_discount_text:
#             # This was a single, non-sale price.
#             # sale_price should be None. regular_price is correct.
#             pass
#         else:
#             # This was likely a sale price that we miscategorized.
#             sale_price = regular_price
#             regular_price = None
            
#     return sale_price, regular_price

