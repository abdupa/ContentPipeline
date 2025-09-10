import re
import unicodedata
from urllib.parse import urlparse, parse_qs
import secrets
import string


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

def convert_to_affiliate_link(
    url: str,
    product_slug: str = "",
    campaign_id: str = "id_HURtY6Geqq",  # <-- replace with your real Shopee campaign ID
    source_id: str = "an_13327880016",   # <-- your affiliate source ID
    term: str | None = None
) -> str | None:
    """
    Convert a Shopee product URL into a clean affiliate link.
    - Strips any old tracking/query params.
    - Inserts a fresh uls_trackid and fixed utm_campaign each time.
    - Passes through non-Shopee URLs unchanged.
    """
    if not url:
        return None

    if 'shopee.ph' not in str(url):
        return url

    # 1. Strip existing query parameters
    base_url = url.split('?')[0]

    # 2. Generate Shopee-style tracking ID
    tracking_token = generate_uls_trackid()

    # 3. Build affiliate parameters
    params = (
        f"?uls_trackid={tracking_token}"
        f"&utm_campaign={campaign_id}"
        f"&utm_content=----"
        f"&utm_medium=affiliates"
        f"&utm_source={source_id}"
    )
    if term:
        params += f"&utm_term={term}"

    # 4. Return final link
    return base_url + params

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
        match = re.search(r'-s(\d+)\.html', url)
        product_id = match.group(1) if match else None
        
        query_params = parse_qs(urlparse(url).query)
        shop_id = query_params.get('shop_id', [None])[0]

        if product_id:
             return {'product_id': str(product_id), 'shop_id': str(shop_id) if shop_id else None, 'source': 'lazada'}

    return {'product_id': None, 'shop_id': None, 'source': None}

# def convert_to_affiliate_link(url, product_slug, tracking_token='d4uxpm5eb2rd', campaign_id='id_DefaultCampaign'):
#     if not url:
#         return None
    
#     # Per our plan, we only modify Shopee links. All others (Lazada, etc.) pass through untouched.
#     if 'shopee.ph' not in str(url):
#         return url

#     # 1. Get the "clean" base URL by splitting at the FIRST '?' and taking only the part before it.
#     # This strips ALL existing query parameters (like gads_t_sig=, old utm_source, etc.)
#     base_url = url.split('?')[0]

#     # 2. Build our new, correct affiliate parameter string
#     our_params = (
#         f"?uls_trackid={tracking_token}"
#         f"&utm_campaign={campaign_id}"
#         f"&utm_content=----"
#         f"&utm_medium=affiliates"
#         f"&utm_source=an_13327880016"
#     )
    
#     # 3. Combine them. This guarantees we replace all old tracking data with our own.
#     return base_url + our_params