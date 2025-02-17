import re
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from paddleocr import PaddleOCR, draw_ocr
from datetime import datetime


@dataclass
class Item:
    name: str
    price: str # now it is a string because it contains A or B

@dataclass
class LidlReceipt:
    market_address: str
    total_price: float
    items: List[Item]
    payment_type: str
    shopping_time: str
    shopping_date: datetime
    market_name: str = "Lidl"
    vat_number: str = "GB 341 8559 95"

# OCR
ocr = PaddleOCR(lang="en", use_angle_cls=True)
result = ocr.ocr("receipts/lidl#3.jpeg", cls=True)

boxes = [line[0] for line in result[0]]
text = [line[1][0] for line in result[0]]
scores = [line[1][1] for line in result[0]]

print("--------------------------------")
print(text)
print("--------------------------------")




def receipt_info(text: List[str]) -> LidlReceipt:
    # Extract market address
    market_address = text[1]  # 'LON-Stratford'

    # Extract total price
    try:
        total_idx = text.index("TOTAL")
        total_price = float(text[total_idx + 1])
    except ValueError:
        total_price = 0.0

    # Extract payment type
    payment_type = "CARD" if "CARD" in text else "CASH"

    # Extract shopping time
    time_idx = [i for i, s in enumerate(text) if s.startswith("Time:")][0]
    shopping_time = text[time_idx].replace("Time:", "").strip()

    # Extract shopping date
    date_idx = [i for i, s in enumerate(text) if s.startswith("Date:")][0]
    date_str = text[date_idx].replace("Date:", "").strip()
    shopping_date = datetime.strptime(date_str, "%d/%m/%y")

    # Extract items using the existing extract_items function
    #items = extract_items(text)

    return LidlReceipt(
        market_address=market_address,
        total_price=total_price,
        items=0,
        payment_type=payment_type,
        shopping_time=shopping_time,
        shopping_date=shopping_date
    )


#print(receipt_info(text))


# Pattern for combined string (e.g., "1.65A")
combined_pattern = r'^(\d+\.\d+)([A-Z])$'

# Pattern for float number
float_pattern = r'^\d+\.\d+$'

def extract_items(text_list: List[str]) -> List[Item]:
    items = []
    i = 0
    while i < len(text_list):
        current = text_list[i]
        
        # Remove any spaces in the current text
        current_no_space = current.replace(" ", "")
        
        # Check for combined format (e.g., "1.99A" or "1.99 A")
        if bool(re.match(combined_pattern, current_no_space)):
            # Look for item name in the next entry
            if i + 1 < len(text_list):
                items.append(Item(name=text_list[i+1], price=current_no_space))
            i += 2
        # Check for separate format (e.g., "1.99", "A")
        elif (i + 1 < len(text_list) and 
              bool(re.match(float_pattern, current)) and 
              text_list[i + 1].strip() in ['A', 'B']):
            # Look for item name in the next entry after the price+VAT
            if i + 2 < len(text_list):
                items.append(Item(
                    name=text_list[i + 2],
                    price=current_no_space + text_list[i + 1].strip()
                ))
            i += 3
        else:
            i += 1
    return items

#"""
# Example usage:
items = extract_items(text)
for item in items:
    print(f"Item: {item.name}, Price: {item.price}")
#"""

#print(receipt_info(text))


