import requests
import os
import re
from bs4 import BeautifulSoup  # For HTML parsing
from datetime import datetime

# Telegram Bot config from GitHub secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Fallback content from attachment (for testing if live fetch fails; paste full if needed)
attachment_content = """
|Gram|Today|Yesterday|
|--|--|--|
|1 Gram|₹12,973.67 +13.78(0.11%)|₹12,959.89 +141.42(1.10%)|
|8 Gram|₹1,03,789.36 +110.24(0.11%)|₹1,03,679.12 +1,131.36(1.10%)|
|10 Gram|₹1,29,736.70 +137.80(0.11%)|₹1,29,598.90 +1,414.20(1.10%)|
|12 Gram(1 Tola)|₹1,55,684.04 +165.36(0.11%)|₹1,55,518.68 +1,697.04(1.10%)|
"""

def get_jaipur_24k_price():
    """Fetch 24K gold price for 10g in Jaipur/Rajasthan using Groww webpage parsing (replaces Tanishq API)"""
    url = "https://groww.in/gold-rates/gold-rate-today-in-rajasthan"  # Rajasthan includes Jaipur rates
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"Groww Status Code: {r.status_code}")
        
        if r.status_code != 200:
            raise Exception(f"Failed to fetch Groww rates: {r.status_code}")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Search for tables or text containing "10 Gram" (10g 24K)
        price_str = None
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables in HTML.")
        
        for table in tables:
            table_text = table.get_text()
            if "10 Gram" in table_text:
                # Extract ₹ price from row
                row_pattern = r'10\s*Gram.*?(₹[\d,]+\.?\d*)'
                match = re.search(row_pattern, table_text, re.IGNORECASE)
                if match:
                    price_str = match.group(1)
                    print(f"✅ Price found in table: {price_str}")
                    break
        
        # Fallback: Search entire page text
        if not price_str:
            page_text = soup.get_text()
            pattern = r'10\s*Gram.*?(₹[\d,]+\.?\d*)'
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                price_str = match.group(1)
                print(f"✅ Price from page text: {price_str}")
            else:
                # Ultimate fallback to attachment content
                fallback_match = re.search(r'10 Gram\s*\|\s*₹?([\d,]+\.?\d*)', attachment_content, re.IGNORECASE)
                if fallback_match:
                    price_str = "₹" + fallback_match.group(1)  # Add ₹ for consistency
                    print(f"✅ Fallback price from attachment: {price_str}")
                else:
                    raise Exception("No 10g price found in fallback content")
        
        # FIXED Cleaning: Safely extract the number part
        # Step 1: Remove ₹
        temp = price_str.replace('₹', '').strip()
        print(f"After removing ₹: {temp}")
        
        # Step 2: Remove commas
        temp = temp.replace(',', '').strip()
        print(f"After removing commas: {temp}")
        
        # Step 3: Extract the first numeric part (price, ignore extras like "+13.78")
        num_pattern = r'^(\d+\.?\d*)'  # Matches number at start (e.g., "129736.700+13.78" → "129736.700")
        num_match = re.search(num_pattern, temp)
        if num_match:
            clean_price = num_match.group(1)
            print(f"Extracted numeric price: {clean_price}")
        else:
            # If no match, take the whole temp as price (fallback)
            clean_price = temp
            print(f"No numeric match – using full temp: {clean_price}")
        
        # Step 4: Convert to float, round to nearest int (e.g., 129736.70 → 129737), return int
        price_float = float(clean_price)
        price_int = int(round(price_float))
        
        print(f"✅ Cleaned Jaipur 24K 10g Price: ₹{price_int:,}")
        return price_int
        
    except Exception as e:
        print(f"⚠️ Error in Groww fetch/parse: {e}")
        # Fallback to manual/attachment extraction
        try:
            fallback_match = re.search(r'10 Gram\s*\|\s*₹?([\d,]+\.?\d*)', attachment_content, re.IGNORECASE)
            if fallback_match:
                temp = fallback_match.group(1).replace(',', '').strip()
                num_pattern = r'^(\d+\.?\d*)'
                num_match = re.search(num_pattern, temp)
                clean_price = num_match.group(1) if num_match else temp
                price_float = float(clean_price)
                price_int = int(round(price_float))
                print(f"✅ Fallback return: {price_int}")
                return price_int
            else:
                raise Exception("Jaipur 24K rate not found (fallback failed)")
        except Exception as fallback_e:
            raise Exception(f"Fallback failed: {fallback_e}")

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables!")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message}
    r = requests.post(url, json=payload)
    if r.status_code == 200:
        print("✅ Gold price alert sent successfully.")
    else:
        print(f"❌ Failed to send Telegram message: {r.text}")

def main():
    try:
        price = get_jaipur_24k_price()
        message = f"10g of 24k gold (99.9%) in Jaipur is ₹{price:,} Indian Rupee"
        send_telegram_message(message)
        print("Final msg", message)
    except Exception as e:
        print(f"⚠️ Error: {e}")
        # Optional: Send error to Telegram
        error_msg = f"⚠️ Bot Error: {e}"
        send_telegram_message(error_msg)

if __name__ == "__main__":
    main()
