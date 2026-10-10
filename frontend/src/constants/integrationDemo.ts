import type { SourceMapping } from '@/types';

export const jsonDemoMapping: SourceMapping = {
  invoice_number: 'billNo', invoice_date: 'billDate', buyer_oem_id: 'buyerCode',
  supplier_dealer_code: 'dealerCode', currency: 'currencyCode', subtotal: 'subTotal',
  tax_amount: 'taxTotal', total_amount: 'grandTotal',
  line_items: {
    source_field: 'items', item_code: 'sku', description: 'description', quantity: 'qty',
    unit_price: 'rate', discount_amount: 'discount', taxable_amount: 'taxableValue',
    tax_rate: 'taxRate', tax_amount: 'taxAmount', line_total: 'lineTotal',
    chassis_number: 'chassisNo', item_category: 'category',
  },
};

export const jsonDemoSource = {
  billNo: 'BILL-DEMO-1001', billDate: '2026-10-10', buyerCode: 'DAIMLER-DEMO',
  dealerCode: 'ONEDMS-DEMO-API', currencyCode: 'INR', subTotal: 1000, taxTotal: 180, grandTotal: 1180,
  items: [{ sku: 'FILTER-01', description: 'Service filter', qty: 2, rate: 500, discount: 0,
    taxableValue: 1000, taxRate: 18, taxAmount: 180, lineTotal: 1180, chassisNo: null, category: 'PART' }],
};

export const csvDemoMapping: SourceMapping = {
  invoice_number: 'InvoiceNumber', invoice_date: 'InvoiceDate', buyer_oem_id: 'BuyerCode',
  supplier_dealer_code: 'DealerCode', currency: 'Currency', subtotal: 'Subtotal',
  tax_amount: 'TaxTotal', total_amount: 'GrandTotal',
  line_items: {
    source_field: 'rows', item_code: 'SKU', description: 'Description', quantity: 'Qty',
    unit_price: 'UnitPrice', discount_amount: 'Discount', taxable_amount: 'TaxableValue',
    tax_rate: 'TaxRate', tax_amount: 'TaxAmount', line_total: 'LineTotal',
    chassis_number: 'ChassisNumber', item_category: 'Category',
  },
};

// Preview the wrapper produced by the current CSV adapter, not arbitrary CSV text.
export const csvDemoSource = {
  InvoiceNumber: 'CSV-DEMO-1001', InvoiceDate: '2026-10-10', BuyerCode: 'DAIMLER-DEMO',
  DealerCode: 'ONEDMS-DEMO-CSV', Currency: 'INR', Subtotal: 1000, TaxTotal: 180, GrandTotal: 1180,
  rows: [{ SKU: 'FILTER-01', Description: 'Service filter', Qty: 2, UnitPrice: 500, Discount: 0,
    TaxableValue: 1000, TaxRate: 18, TaxAmount: 180, LineTotal: 1180, ChassisNumber: null, Category: 'PART' }],
};