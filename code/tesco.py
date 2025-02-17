import re
from Levenshtein import ratio
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from paddleocr import PaddleOCR, draw_ocr
from datetime import datetime


"""
TESCO
- Market name
- Market address: text coming after "Tesco"
- Vat number
- Item name
- Item price
- Cc if it is written
- Meal deal if it is written
- Total amount of items hint: after finding the all itesm we need to write item.count() or something like that
- Subtotal if it is written
- Total price (written as Total)
- Payment type: Card or Cash
- Savings called as "Savings"
- Savings amount
- check Clubcard: if it is Clubcard
    - points earned total
    - points balance
- else:
    - pass
- shopID written #Store____ Store and 4 digit number
- shopping time: hh:mm:ss if it is written
- shopping date: DD/MM/YYYY : if it is written
"""


@dataclass
class ClubcardInfo:
    points_earned: int
    points_balance: int

@dataclass
class Item:
    name: str
    price: float
    discount: float # if 'Cc' or 'Meal Deal' is written then it is the discount
    is_meal_deal: bool # if meal deal is written then it is true else false

@dataclass
class TescoReceipt:
    # Store Information
    market_address: str
    total_price: float
    store_id: str
    shopping_time: Optional[datetime] = None
    shopping_date: Optional[datetime] = None
    items: List[Item] = None
    subtotal: Optional[float] = None
    savings: Optional[float] = None
    clubcard_info: Optional[ClubcardInfo] = None
    market_name: str = "Tesco"
    vat_number: str = "220 4302 31"
    payment_type: str  = "Card" #default is card


# OCR
ocr = PaddleOCR(
    lang="en",
    use_angle_cls=True,  # Detect text orientation
    det_db_thresh=0.6,   # Adjust detection threshold
    det_db_box_thresh=0.5,  # Adjust box threshold
    det_db_unclip_ratio=1.8  # Adjust unclip ratio
)
result = ocr.ocr("test.jpeg", cls=True)

boxes = [line[0] for line in result[0]]
text = [line[1][0] for line in result[0]]
scores = [line[1][1] for line in result[0]]

print(text)


def is_similar_to_clubcard_points_earned(word, threshold=0.9):
    target = "Clubcard points earned:"
    similarity = ratio(target.lower(), word.lower())
    return similarity >= threshold and "balance" not in word.lower()

def is_similar_to_clubcard_points_balance(word, threshold=0.9):
    target = "Clubcard points balance:"
    similarity = ratio(target.lower(), word.lower())
    return similarity >= threshold

def extract_clubcard_info(text: List[str]) -> Optional[ClubcardInfo]:
    points_earned = None
    points_balance = None
    
    for i, line in enumerate(text):
        try:
            if is_similar_to_clubcard_points_earned(line):
                # First check the next line
                if i + 1 < len(text) and text[i + 1].strip().isdigit():
                    points_earned = int(text[i + 1])
                # If next line is not suitable, check previous line
                elif i > 0 and text[i - 1].strip().isdigit():
                    points_earned = int(text[i - 1])
                    
            elif is_similar_to_clubcard_points_balance(line):
                # First check the next line
                if i + 1 < len(text) and text[i + 1].strip().isdigit():
                    points_balance = int(text[i + 1])
                # If next line is not suitable, check previous line
                elif i > 0 and text[i - 1].strip().isdigit():
                    points_balance = int(text[i - 1])
                    
        except (ValueError, IndexError):
            continue
    
    return ClubcardInfo(points_earned=points_earned, points_balance=points_balance)

#print(extract_clubcard_info(text))

def reprinted_to_reprinted(text: List[str]) -> List[str]:
    """
    Extracts the portion of text between REPRINTED RECEIPT to REPRINTED RECEIPT,
    handling REPRINTED RECEIPT cases appropriately.
    """
    start_index = None
    end_index = None
    
    for i, line in enumerate(text):
        if 'REPRINTED RECEIPT' in line:
            if start_index is None:
                start_index = i + 1
            else:
                end_index = i
                break
    
    return text[start_index+1:end_index] if start_index is not None and end_index is not None else []

def vat_to_subtotal(text: List[str]) -> List[str]:
    """
    Extracts the portion of text between Vat and Subtotal,
    handling Vat cases appropriately.
    """
    start_index = None
    end_index = None

    for i, line in enumerate(text):
        if 'VAT' in line:
            start_index = i + 1
        elif 'Subtotal' in line:
            end_index = i
            break
    
    return text[start_index:end_index] if start_index is not None and end_index is not None else []

def vat_to_total(text: List[str]) -> List[str]:
    """
    Extracts the portion of text between Vat and Subtotal,
    handling Vat cases appropriately.
    """
    start_index = None
    end_index = None

    for i, line in enumerate(text):
        if 'VAT' in line:
            start_index = i + 1
        elif 'TOTAL' in line:
            end_index = i
            break
    return text[start_index:end_index] if start_index is not None and end_index is not None else []


def clean_data(text: List[str]) -> List[str]:
    # First handle if there's a REPRINTED RECEIPT
    if any('REPRINTED RECEIPT' in line for line in text):
        text = reprinted_to_reprinted(text)
    # Only try VAT to Subtotal/TOTAL if there was no REPRINTED RECEIPT
    elif any('VAT' in line for line in text):
        if any('Subtotal' in line for line in text):
            text = vat_to_subtotal(text)
        else:
            text = vat_to_total(text)
    
    # Remove '1's and clean up the data
    cleaned_data = [item for item in text if not item.isdigit()]
    return cleaned_data

#print(clean_data(text))


def extract_items_and_prices(cleaned_data: List[str]) -> Tuple[List[Tuple[str, float]], float]:
    items = []
    # List of keywords to exclude
    exclude_keywords = ['Subtotal:', 'TOTAL:', 'Savings:', 'Promotions:', 'Card']
    
    for i in range(len(cleaned_data) - 1):
        current = cleaned_data[i]
        next_item = cleaned_data[i + 1]
        
        # Skip if current item contains any of the exclude keywords
        if any(keyword in current for keyword in exclude_keywords):
            continue
            
        try:
            # Format the price with exactly 2 decimal places
            price = float(format(float(next_item), '.2f'))
            if isinstance(current, str) and '.' in next_item:
                items.append((current, price))

        except ValueError:
            continue
    return items


def combine_entries(data):
    result = []
    current_item = None
    
    for item, price in data:
        # Handle special cases (Cc or Meal Deal)
        if 'Cc' in item or item == 'Meal Deal':
            if current_item:
                current_item[2] += abs(price)  # Add to discount (use absolute value)
                if item == 'Meal Deal':
                    current_item[3] = True  # Set meal deal flag
            continue
            
        # Add previous item to result if exists
        if current_item:
            result.append(Item(
                name=current_item[0],
                price=current_item[1],
                discount=current_item[2],
                is_meal_deal=current_item[3]
            ))
            
        # Start new item: [name, price, discount, is_meal_deal]
        current_item = [item, price, 0, False]
        
    # Add the last item if exists
    if current_item:
        result.append(Item(
            name=current_item[0],
            price=current_item[1],
            discount=current_item[2],
            is_meal_deal=current_item[3]
        ))
        
    return result

print(combine_entries(extract_items_and_prices(clean_data(text))))
        
def extract_datetime(text: List[str]) -> tuple:
    """
    Extract shopping date and time from Tesco receipt text.
    Returns tuple of (shopping_date, shopping_time)
    """
    # Default values
    shopping_date = None
    shopping_time = None
    
    # Pattern to match date and time: DD/MM/YYYY HH:MM
    datetime_pattern = r'(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2})'
    
    # Look through each line in reverse since date/time is usually at the bottom
    for line in reversed(text):
        match = re.search(datetime_pattern, line)
        if match:
            date_str, time_str = match.groups()
            try:
                # Parse the date string
                date_obj = datetime.strptime(date_str, '%d/%m/%Y')
                shopping_date = date_obj.date()
                
                # Parse the time string
                time_obj = datetime.strptime(time_str, '%H:%M')
                shopping_time = time_obj.time()
                
                break
            except ValueError:
                continue
    
    return shopping_date, shopping_time


def extract_receipt_info(text: List[str]) -> TescoReceipt:
    # Extract market address
    try:
        tesco_idx = text.index("TESCO")
        market_address = text[tesco_idx + 1]
    except ValueError:
        market_address = "Address not found"

    total_price = 0.0
    try:
        # Try to find index of "TOTAL" first
        try:
            total_price_idx = text.index("TOTAL")
        except ValueError:
            # If "TOTAL" not found, try "TOTAL:"
            total_price_idx = text.index("TOTAL:")
        
        # Get the next value and convert to float
        next_value = text[total_price_idx + 1]
        if next_value.replace('.', '').isdigit():  # Check if it's a valid number
            total_price = float(next_value)
    except (ValueError, IndexError):
        pass

    # Extract store ID using pattern matching
    store_id = None
    for item in text:
        if 'Store' in item:
            # Extract the numeric part after 'Store'
            match = re.search(r'Store(\d+)', item)
            if match:
                store_id = match.group(1)
                break

    shopping_date, shopping_time = extract_datetime(text)

    # Initialize subtotal and savings
    subtotal = None
    savings = None

    # Extract subtotal and savings
    try:
        for i, item in enumerate(text):
            if 'Subtotal:' in item and i + 1 < len(text):
                try:
                    subtotal = float(text[i + 1])
                except (ValueError, IndexError):
                    pass
            elif 'Savings:' in item and i + 1 < len(text):
                try:
                    savings = abs(float(text[i + 1]))
                except (ValueError, IndexError):
                    pass
    except Exception:
        pass

    # Extract clubcard info
    clubcard_info = extract_clubcard_info(text)

    return TescoReceipt(
        market_address=market_address,
        total_price=total_price,
        store_id=store_id if store_id else None,
        shopping_time=shopping_time,
        shopping_date=shopping_date,
        subtotal=subtotal,
        savings=savings,
        clubcard_info=clubcard_info
    )


print(extract_receipt_info(text))