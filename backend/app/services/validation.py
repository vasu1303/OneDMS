from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel

class ValidationResult(BaseModel):
    rule_code: str
    severity: str
    message: str
    is_valid: bool
    field: Optional[str] = None
    line_number: Optional[int] = None

class ValidationContext(BaseModel):
    is_registered_dealer: Callable[[str], bool]
    is_duplicate_invoice: Callable[[str, str, str], bool]

def validate_canonical_payload(
    canonical_data: dict, 
    rules: List[Dict[str, Any]], 
    context: ValidationContext
) -> List[ValidationResult]:
    results = []

    for rule in rules:
        code = rule['rule_code']
        severity = rule['severity']
        config = rule['rule_config']
        rule_type = config.get('type')
        
        if rule_type == 'REQUIRED_FIELDS':
            fields = config.get('fields', [])
            for field in fields:
                val = canonical_data.get(field)
                if val is None or str(val).strip() == '':
                    results.append(ValidationResult(
                        rule_code=code, severity=severity,
                        message=f"Missing required field: {field}",
                        is_valid=False, field=field
                    ))
        
        elif rule_type == 'REGISTERED_DEALER':
            dealer_code = canonical_data.get('supplier_dealer_code')
            if dealer_code and not context.is_registered_dealer(dealer_code):
                results.append(ValidationResult(
                    rule_code=code, severity=severity,
                    message=f"Dealer {dealer_code} is not registered",
                    is_valid=False, field='supplier_dealer_code'
                ))
        
        elif rule_type == 'NUMERIC_BOUNDS':
            collection = config.get('collection')
            fields_config = config.get('fields', {})
            
            items = canonical_data.get(collection, []) if collection else [canonical_data]
            
            for idx, item in enumerate(items):
                line_no = idx + 1 if collection == 'line_items' else None
                for field, bounds in fields_config.items():
                    val = item.get(field)
                    if val is not None and str(val).strip() != '':
                        try:
                            dec_val = Decimal(str(val))
                            if 'minimum' in bounds and dec_val < Decimal(str(bounds['minimum'])):
                                results.append(ValidationResult(
                                    rule_code=code, severity=severity,
                                    message=f"{field} must be >= {bounds['minimum']}, got {val}",
                                    is_valid=False, field=field, line_number=line_no
                                ))
                            if 'exclusive_minimum' in bounds and dec_val <= Decimal(str(bounds['exclusive_minimum'])):
                                results.append(ValidationResult(
                                    rule_code=code, severity=severity,
                                    message=f"{field} must be > {bounds['exclusive_minimum']}, got {val}",
                                    is_valid=False, field=field, line_number=line_no
                                ))
                        except InvalidOperation:
                            results.append(ValidationResult(
                                rule_code=code, severity=severity,
                                message=f"{field} must be numeric, got {val}",
                                is_valid=False, field=field, line_number=line_no
                            ))
                            
        elif rule_type == 'ALLOWED_VALUES':
            field = config.get('field')
            values = config.get('values', [])
            val = canonical_data.get(field)
            if val is not None and val not in values:
                results.append(ValidationResult(
                    rule_code=code, severity=severity,
                    message=f"Invalid {field}: {val}. Allowed: {values}",
                    is_valid=False, field=field
                ))
                
        elif rule_type == 'TOTAL_RECONCILIATION':
            try:
                subtotal = Decimal(str(canonical_data.get(config['subtotal_field'], 0) or 0))
                tax = Decimal(str(canonical_data.get(config['tax_field'], 0) or 0))
                total = Decimal(str(canonical_data.get(config['total_field'], 0) or 0))
                tolerance = Decimal(str(config.get('tolerance', '0.01')))
                
                if abs((subtotal + tax) - total) > tolerance:
                    results.append(ValidationResult(
                        rule_code=code, severity=severity,
                        message=f"Header total {total} does not match subtotal {subtotal} + tax {tax}",
                        is_valid=False, field=config['total_field']
                    ))
                
                lines = canonical_data.get(config.get('line_collection', 'line_items'), [])
                calc_subtotal = Decimal('0')
                calc_tax = Decimal('0')
                
                for idx, line in enumerate(lines):
                    l_sub = Decimal(str(line.get(config['line_subtotal_field'], 0) or 0))
                    l_tax = Decimal(str(line.get(config['line_tax_field'], 0) or 0))
                    l_tot = Decimal(str(line.get(config['line_total_field'], 0) or 0))
                    
                    if abs((l_sub + l_tax) - l_tot) > tolerance:
                        results.append(ValidationResult(
                            rule_code=code, severity=severity,
                            message=f"Line {idx+1} total {l_tot} != subtotal {l_sub} + tax {l_tax}",
                            is_valid=False, field=config['line_total_field'], line_number=idx+1
                        ))
                        
                    calc_subtotal += l_sub
                    calc_tax += l_tax
                    
                if abs(calc_subtotal - subtotal) > tolerance:
                    results.append(ValidationResult(
                        rule_code=code, severity=severity,
                        message=f"Calculated lines subtotal {calc_subtotal} != header subtotal {subtotal}",
                        is_valid=False, field=config['subtotal_field']
                    ))
                    
                if abs(calc_tax - tax) > tolerance:
                    results.append(ValidationResult(
                        rule_code=code, severity=severity,
                        message=f"Calculated lines tax {calc_tax} != header tax {tax}",
                        is_valid=False, field=config['tax_field']
                    ))

            except (InvalidOperation, TypeError):
                results.append(ValidationResult(
                    rule_code=code, severity=severity,
                    message="Error performing total reconciliation due to non-numeric values",
                    is_valid=False
                ))
                
        elif rule_type == 'DUPLICATE_INVOICE':
            dealer = canonical_data.get('supplier_dealer_code')
            inv_no = canonical_data.get('invoice_number')
            inv_date = canonical_data.get('invoice_date')
            if dealer and inv_no and inv_date:
                if context.is_duplicate_invoice(dealer, inv_no, inv_date):
                    results.append(ValidationResult(
                        rule_code=code, severity=severity,
                        message=f"Duplicate invoice detected for {dealer} {inv_no} on {inv_date}",
                        is_valid=False, field='invoice_number'
                    ))
                    
        elif rule_type == 'CONDITIONAL_REQUIRED_FIELD':
            collection = config.get('collection')
            field = config.get('field')
            when = config.get('when', {})
            
            items = canonical_data.get(collection, []) if collection else [canonical_data]
            
            for idx, item in enumerate(items):
                line_no = idx + 1 if collection == 'line_items' else None
                
                condition_met = True
                for cond_k, cond_v in when.items():
                    if item.get(cond_k) != cond_v:
                        condition_met = False
                        break
                        
                if condition_met:
                    val = item.get(field)
                    if val is None or str(val).strip() == '':
                        results.append(ValidationResult(
                            rule_code=code, severity=severity,
                            message=f"Field {field} is required when condition {when} is met",
                            is_valid=False, field=field, line_number=line_no
                        ))
                        
    return results

def get_overall_status(results: List[ValidationResult]) -> str:
    has_error = any(r.severity == 'ERROR' and not r.is_valid for r in results)
    has_warning = any(r.severity == 'WARNING' and not r.is_valid for r in results)
    
    if has_error:
        return 'INVALID'
    if has_warning:
        return 'REVIEW_REQUIRED'
    return 'VALID'
