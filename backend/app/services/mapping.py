import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from dateutil import parser

class MappingError(Exception):
    def __init__(self, message: str, path: str):
        super().__init__(message)
        self.path = path

def normalize_date(value: Any) -> str:
    if not value:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            return parser.parse(value).date().isoformat()
        except Exception:
            raise ValueError(f"Invalid date format: {value}")
    raise ValueError(f"Cannot parse date from {type(value)}")

def normalize_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            clean_val = re.sub(r'[^\d.-]', '', value)
            return Decimal(clean_val)
        except InvalidOperation:
            raise ValueError(f"Invalid numeric value: {value}")
    raise ValueError(f"Cannot parse decimal from {type(value)}")

def normalize_currency(value: Any) -> str:
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Currency must be string, got {type(value)}")
    val = value.strip().upper()
    return val

def resolve_path(data: dict, path: str) -> Any:
    keys = path.split('.')
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current

def map_source_to_canonical(source_data: dict, config: dict) -> dict:
    canonical = {}
    
    date_fields = {'invoice_date'}
    decimal_fields = {'subtotal', 'tax_amount', 'total_amount'}
    currency_fields = {'currency'}
    
    for canon_field, source_path in config.items():
        if canon_field == 'line_items':
            continue
            
        val = resolve_path(source_data, source_path)
        if val is None:
            raise MappingError(f"Missing required path for {canon_field}: {source_path}", source_path)
            
        try:
            if canon_field in date_fields:
                canonical[canon_field] = normalize_date(val)
            elif canon_field in decimal_fields:
                canonical[canon_field] = str(normalize_decimal(val))
            elif canon_field in currency_fields:
                canonical[canon_field] = normalize_currency(val)
            else:
                canonical[canon_field] = str(val).strip() if val else None
        except ValueError as e:
            raise MappingError(str(e), source_path)

    if 'line_items' in config:
        line_config = config['line_items']
        lines_source_path = line_config.get('source_field')
        if not lines_source_path:
            raise MappingError("Missing source_field for line_items", "line_items.source_field")
            
        lines_data = resolve_path(source_data, lines_source_path)
        if lines_data is None or not isinstance(lines_data, list):
            raise MappingError(f"Line items not found or not a list at {lines_source_path}", lines_source_path)
            
        canonical['line_items'] = []
        line_decimal_fields = {
            'quantity', 'unit_price', 'discount_amount', 
            'taxable_amount', 'tax_rate', 'tax_amount', 'line_total'
        }
        
        for idx, line_item in enumerate(lines_data):
            mapped_line = {}
            for canon_line_field, source_line_path in line_config.items():
                if canon_line_field == 'source_field':
                    continue
                
                val = resolve_path(line_item, source_line_path)
                try:
                    if val is not None:
                        if canon_line_field in line_decimal_fields:
                            mapped_line[canon_line_field] = str(normalize_decimal(val))
                        else:
                            mapped_line[canon_line_field] = str(val).strip()
                    else:
                        mapped_line[canon_line_field] = None
                except ValueError as e:
                    raise MappingError(f"Line {idx+1}: {str(e)}", f"{lines_source_path}[{idx}].{source_line_path}")
            
            canonical['line_items'].append(mapped_line)
            
    return canonical

def map_canonical_to_oem(canonical_data: dict, config: dict) -> dict:
    oem_data = {}
    
    for oem_field, canon_path in config.items():
        if oem_field == 'items':
            continue
            
        val = resolve_path(canonical_data, canon_path)
        oem_data[oem_field] = val
        
    if 'items' in config:
        item_config = config['items']
        canon_items_path = item_config.get('source_field', 'line_items')
        
        items_data = resolve_path(canonical_data, canon_items_path)
        oem_data['items'] = []
        if items_data and isinstance(items_data, list):
            for canon_item in items_data:
                oem_item = {}
                for oem_item_field, canon_item_path in item_config.items():
                    if oem_item_field == 'source_field':
                        continue
                    oem_item[oem_item_field] = resolve_path(canon_item, canon_item_path)
                oem_data['items'].append(oem_item)
                
    return oem_data
