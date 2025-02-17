import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from paddleocr import PaddleOCR, draw_ocr
from datetime import datetime


"""
SAINSBURY
- Market name
- Market address: text coming after "Good food for all of us"
- Vat number
- Item name
- Item price
- Total amount of items
- Total price
- Payment type: card or cash
- if it is card
    - ICC
    - AID
    - PAN SEQUENCE
    - MERCHANT
    - AUTH CODE
    - TID
- Change
- Savings called as "promotions"
- Savings amount
- check nectar: if it is nectar card
    - points earned total
    - previous balance
    - points earned
    - new points balance
    - points worth
- else:
    - pass
- shopID written #S____ 5 digit in total 1 letter and 4 digit number
- shopping time: hh:mm:ss
- shopping date: DDMONYYYY : month written in text format should be converted to number (January = 1, February = 2, etc.)
"""


@dataclass
class NectarDetails:
    card_number: str
    points_earned_on: float
    previous_balance: int
    points_earned: int
    new_balance: int
    points_worth: float

@dataclass
class CardPaymentDetails:
    icc: str
    aid: str
    pan_sequence: str
    merchant: str
    auth_code: str
    tid: str

@dataclass
class Item:
    name: str
    price: float
    is_savings: bool
    
@dataclass
class Receipt:
    market_address: str
    items: List[Item]
    total_items: int 
    total_price: float
    payment_type: str
    change: float
    promotions_savings: float
    meal_deal_items: List[Item]
    shop_id: str
    shopping_time: str
    shopping_date: datetime
    market_name: str = "Sainsbury's"
    vat_number: str = "660 4548 36"
    card_details: Optional[CardPaymentDetails] = None
    nectar_details: Optional[NectarDetails] = None


# OCR
# OCR
ocr = PaddleOCR(
    lang="en",
    use_angle_cls=True,  # Detect text orientation
    det_db_thresh=0.6,   # Adjust detection threshold
    det_db_box_thresh=0.5,  # Adjust box threshold
    det_db_unclip_ratio=1.8  # Adjust unclip ratio
)
result = ocr.ocr("receipts/sainsbury#8.jpeg", cls=True)

boxes = [line[0] for line in result[0]]
text = [line[1][0] for line in result[0]]
scores = [line[1][1] for line in result[0]]

def extract_nectar_details(receipt_lines: list[str]) -> NectarDetails:
    details = {}
    
    # Find points earned on (transaction amount)
    points_idx = receipt_lines.index('POINTS EARNED ON')
    details['points_earned_on'] = float(receipt_lines[points_idx + 1])
    
    # Find card number
    card_idx = [i for i, line in enumerate(receipt_lines) if '[C]' in line][0]
    details['card_number'] = receipt_lines[card_idx].replace('[C]', '')
    
    # Find previous balance
    prev_balance_idx = [i for i, line in enumerate(receipt_lines) if 'PREVIOUS POINTS BALANCE' in line][0]
    details['previous_balance'] = int(receipt_lines[prev_balance_idx + 1])
    
    # Find points earned
    points_earned_idx = [i for i, line in enumerate(receipt_lines) if 'POINTS EARNED' == line][0]
    details['points_earned'] = int(receipt_lines[points_earned_idx + 1])
    
    # Find new balance
    new_balance_idx = [i for i, line in enumerate(receipt_lines) if 'NEW POINTS BALANCE' in line][0]
    details['new_balance'] = int(receipt_lines[new_balance_idx + 1])
    
    # Find points worth
    points_worth_idx = [i for i, line in enumerate(receipt_lines) if 'YOUR POINTS ARE WORTH' in line][0]
    details['points_worth'] = float(receipt_lines[points_worth_idx + 1])
    
    return NectarDetails(**details)

def extract_card_details(receipt_lines: list[str]) -> CardPaymentDetails:
    details = {}
    
    # Find ICC
    icc_idx = [i for i, line in enumerate(receipt_lines) if '[ICC]' in line][0]
    details['icc'] = receipt_lines[icc_idx].replace('[ICC]', '')
    
    # Find AID
    aid_idx = [i for i, line in enumerate(receipt_lines) if 'AID:' in line][0]
    details['aid'] = receipt_lines[aid_idx + 1]
    
    # Find PAN SEQUENCE
    pan_idx = [i for i, line in enumerate(receipt_lines) if 'PAN SEQUENCE' in line][0]
    details['pan_sequence'] = receipt_lines[pan_idx + 1]
    
    # Find MERCHANT
    merchant_idx = [i for i, line in enumerate(receipt_lines) if 'MERCHANT:' in line][0]
    details['merchant'] = receipt_lines[merchant_idx + 1]
    
    # Find AUTH CODE
    auth_idx = [i for i, line in enumerate(receipt_lines) if 'AUTH CODE:' in line][0]
    details['auth_code'] = receipt_lines[auth_idx + 1]
    
    # Find TID
    tid_idx = [i for i, line in enumerate(receipt_lines) if 'TID:' in line][0]
    details['tid'] = receipt_lines[tid_idx + 1]
    
    return CardPaymentDetails(**details)


def find_first_price_index(receipt_list):
    import re
    
    # Pattern for prices: one digit, decimal point, two digits
    price_pattern = r'^\d\.\d{2}$'
    
    for i, item in enumerate(receipt_list):
        if re.match(price_pattern, item):
            return i
            
    return -1  # Return -1 if no price is found

def extract_items(receipt_lines: list[str]) -> Tuple[List[Item], List[Item]]:
    items = []
    meal_deal_items = []
    # First find the end index
    try:
        end = next(i for i, line in enumerate(receipt_lines) if 'BALANCE DUE' in line)
    except StopIteration:
        return [], []  # Return empty lists if no 'BALANCE DUE' found
        
    # Try to find start index using 'Vat Number'
    try:
        start = next(i for i, line in enumerate(receipt_lines) if 'Vat Number' in line)
        relevant_lines = receipt_lines[start+1:end]
    except StopIteration:
        # If no 'Vat Number', use first price index
        start = find_first_price_index(receipt_lines)
        if start == -1:  # If no price found
            return [], []
        relevant_lines = receipt_lines[start-1:end]

    i = 0
    while i < len(relevant_lines):
        line = relevant_lines[i]
        
        # Skip empty lines
        if not line.strip():
            i += 1
            continue
            
        # Check if it's a price (matches pattern £X.XX or just X.XX)
        if line.replace('£', '').replace('-', '').strip().replace('.', '').isdigit():
            price = float(line.replace('£', '').strip())
            # The item name should be the previous line
            if i > 0:
                name = relevant_lines[i-1].strip()
                
                # Check if it's a savings item (usually prefixed with -)
                is_savings = line.strip().startswith('-')
                
                item = Item(
                    name=name,
                    price=abs(price),  # Use absolute value since we track savings status separately
                    is_savings=is_savings
                )
                
                # Check if it's part of meal deal (usually contains "MEAL DEAL" in the name)
                if "MEAL DEAL" in name.upper():
                    meal_deal_items.append(item)
                else:
                    items.append(item)
        i += 1
    
    return items, meal_deal_items

"""
# Update the test code
items, meal_deal_items = extract_items(text)
print("Regular items:")
for item in items:
    print(f"- {item.name}: £{item.price:.2f} {'(Savings)' if item.is_savings else ''}")

print("\nMeal deal items:")
for item in meal_deal_items:
    print(f"- {item.name}: £{item.price:.2f}")
"""

#print(text)


"""
nectar_info = extract_nectar_details(text)
print(nectar_info)

print(text)

card_info = extract_card_details(text)
print(card_info)
"""

#print(text)

def extract_receipt_info(receipt_lines: list[str]) -> Receipt:
    # Extract market address (after "Good food for all of us")
    try:
        good_food_idx = receipt_lines.index("Good food for all of us")
        market_address = receipt_lines[good_food_idx + 1]
    except ValueError:
        market_address = "Address not found"

    # Extract items and meal deal items
    items, meal_deal_items = extract_items(receipt_lines)

    # Extract total price from BALANCE DUE
    total_price = 0.0
    try:
        balance_idx = [i for i, line in enumerate(receipt_lines) if "BALANCE DUE" in line][0]
        total_price = float(receipt_lines[balance_idx + 1].replace('£', ''))
    except (ValueError, IndexError):
        pass

    # Count total number of items
    total_items = int(text[balance_idx].split()[0])

    # Determine payment type and extract card details if applicable
    payment_type = "CARD" if any("Visa DEBIT" in line for line in receipt_lines) else "CASH"


    # Extract change amount
    change = 0.0
    try:
        change_idx = receipt_lines.index("CHANGE")
        change = float(receipt_lines[change_idx + 1].replace('£', ''))
    except ValueError:
        pass

    # Extract promotions savings
    promotions_savings = 0.0
    try:
        promo_idx = [i for i, line in enumerate(receipt_lines) if "PROMOTIONS" in line][0]
        promotions_savings = float(receipt_lines[promo_idx + 1].replace('£', '').replace('-', ''))
    except (IndexError, ValueError):
        pass

    # Extract nectar details if available
    nectar_details = None
    if any("NECTAR" in line for line in receipt_lines):
        try:
            nectar_details = extract_nectar_details(receipt_lines)
        except (ValueError, IndexError):
            pass

    # Extract shop ID (#SXXXX format)
    shop_id = ""
    for line in receipt_lines:
        if line.startswith("S") and len(line) == 5:
            shop_id = line
            break

    # Extract shopping time and date
    shopping_time = ""
    shopping_date = None

    # Look for time in HH:MM:SS format and date in DDMONYYYY format

    months = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    # First try to find combined date-time format
    for line in receipt_lines:
        # Try combined format (like '18:04:4916NOV2024')
        combined_match = re.search(r'(\d{2}:\d{2}:\d{2})?(\d{1,2})([A-Z]{3})(\d{4})', line)
        if combined_match:
            if combined_match.group(1):  # If time is part of the same string
                shopping_time = combined_match.group(1)
            day = combined_match.group(2)
            mon = combined_match.group(3)
            year = combined_match.group(4)
            if mon in months:
                shopping_date = datetime(int(year), months[mon], int(day))
            break
    
    # If time not found in combined format, look for it separately
    if not shopping_time:
        for line in receipt_lines:
            # Look for time format HH:MM:SS
            time_match = re.search(r'\d{2}:\d{2}:\d{2}', line)
            if time_match:
                shopping_time = time_match.group()
                break
            

    # If date not found in combined format, look for it separately
    if not shopping_date:
        for line in receipt_lines:
            # Handle date format with or without leading zeros (like '290CT2024')
            date_match = re.search(r'(\d{1,2})([A-Z]{3})(\d{4})', line)
            if date_match:
                day, mon, year = date_match.groups()
                if mon in months:
                    shopping_date = datetime(int(year), months[mon], int(day))
                break

    return Receipt(
        market_address=market_address,
        items=items,
        total_items=total_items,
        total_price=total_price,
        payment_type=payment_type,
        change=change,
        promotions_savings=promotions_savings,
        meal_deal_items=meal_deal_items,
        shop_id=shop_id,
        shopping_time=shopping_time,
        shopping_date=shopping_date
    )

# Example usage:

#"""
receipt = extract_receipt_info(text)
print(f"Market: {receipt.market_name}")
print(f"Address: {receipt.market_address}")
print(f"items: {receipt.items}")
print(f"Total Items: {receipt.total_items}")
print(f"Total Price: £{receipt.total_price:.2f}")
print(f"Payment Type: {receipt.payment_type}")
print(f"Promotions: £{receipt.promotions_savings:.2f}")
print(f"Shop ID: {receipt.shop_id}")
print(f"Shopping Time: {receipt.shopping_time}")
print(f"Shopping Date: {receipt.shopping_date.strftime('%d-%m-%Y') if receipt.shopping_date else None}")
#"""

print(text)