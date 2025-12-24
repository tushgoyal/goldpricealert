import requests
import os
import re
from bs4 import BeautifulSoup
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# keep existing env-based fallback (comma-separated IDs)
CHAT_IDS = [cid.strip() for cid in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if cid.strip()]

JSONBIN_URL = os.getenv("JSONBIN_URL")
JSONBIN_KEY = os.getenv("JSONBIN_KEY")

# Fallback content from attachment (for testing if live fetch fails; paste full if needed)
attachment_content = """
No Price update today
"""

def fetch_chat_ids_from_jsonbin():
    """
    If JSONBIN_URL and JSONBIN_KEY are configured, fetch chat IDs from JSONBin.
    Returns a list of chat_id strings, or [] on failure.
    """
    if not JSONBIN_URL or not JSONBIN_KEY:
        return []

    try:
        headers = {"X-Master-Key": JSONBIN_KEY}
        resp = requests.get(JSONBIN_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        record = data.get("record", data)
        ids = record.get("chat_ids") or record.get("chatIds") or []
        normalized = [str(i).strip() for i in ids if i is not None]
        print(f"Fetched {len(normalized)} chat IDs from JSONBin.")
        return normalized
    except Exception as e:
        print(f"⚠️ Failed to fetch chat IDs from JSONBin: {e}")
        return []

def get_rajasthan_24k_gold_price():
    """Fetch 24K gold price for 10g in Rajasthan/Rajasthan using Groww webpage parsing"""
    url = "https://groww.in/gold-rates/gold-rate-today-in-rajasthan"
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
            raise Exception(f"Failed to fetch rates: {r.status_code}")
        
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
                # row_pattern = r'10\s*Gram.*?(₹[\d,]+\.?\d*)'
                row_pattern = r'10\s*Gram.*?(₹[\d,]+\.?\d*)\s*([+\-]?\d+\.?\d*\s*\([^)]*\))?'
                match = re.search(row_pattern, table_text, re.IGNORECASE)
                if match:
                    price_str = match.group(1)
                    change_str = match.group(2) or ""
                    print(f"✅ Price found in table: {price_str}, Change: {change_str}")
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
        
        print(f"✅ Cleaned Rajasthan 24K 10g Price: ₹{price_int:,}")
        # print(f"✅ Cleaned Rajasthan 24K 10g Price Change difference: ₹{change_str.strip():,}")
        return price_int, change_str.strip()
        
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
                raise Exception("Rates are not available today")
        except Exception as fallback_e:
            raise Exception(f"Fallback failed: {fallback_e}")

def send_telegram_message(message):
    # If JSONBin is configured, fetch chat IDs from it at runtime and override CHAT_IDS
    fetched_ids = fetch_chat_ids_from_jsonbin() if (JSONBIN_URL and JSONBIN_KEY) else []
    active_chat_ids = fetched_ids if fetched_ids else CHAT_IDS

    if not BOT_TOKEN or not active_chat_ids:
        print("⚠️ Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (or JSONBIN_URL/JSONBIN_KEY) environment variables!")
        return
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    for chat_id in active_chat_ids:
        payload = {"chat_id": chat_id.strip(), "text": message, "parse_mode": "Markdown"}
        r = requests.post(url, json=payload)
        if r.status_code == 200:
            print(f"✅ Gold price alert sent successfully to {chat_id}.")
        else:
            print(f"❌ Failed to send Telegram message to {chat_id}: {r.text}")

def main():
    try:
        # price = get_rajasthan_24k_gold_price()
        price, change = get_rajasthan_24k_gold_price()
        today = datetime.now().strftime("%A, %d %B %Y")
        trend_emoji = "📈" if "+" in change else ("📉" if "-" in change else "➖")

        message = (
            "🏆 *Daily Gold Price Alert*\n\n"
            f"📅 *{today}*\n"
            f"🏙️ *Rajasthan*\n\n"
            f"💰 *24K Gold (10g):* ₹{price:,}\n\n"
            f"{trend_emoji} *Change:* {change}\n\n"
            "✨ _Stay shining and invest wisely!_"
        )
        send_telegram_message(message)
        print("Final msg", message)
    except Exception as e:
        print(f"⚠️ Error: {e}")
        # Optional: Send error to Telegram
        error_msg = f"⚠️ Bot Error: {e}"
        send_telegram_message(error_msg)

if __name__ == "__main__":
    main()
