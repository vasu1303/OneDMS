/**
 * OneDMS API Types & Contract Definitions
 * Produced by Person 5 for Person 4 (Frontend UI)
 */

export type DocumentStatus =
  "RECEIVED" | "PROCESSING" | "COMPLETED" | "REVIEW_REQUIRED" | "FAILED";
export type InvoiceValidationStatus =
  "PENDING" | "VALID" | "INVALID" | "REVIEW_REQUIRED";
export type InvoiceReviewStatus =
  "NOT_REQUIRED" | "PENDING" | "APPROVED" | "REJECTED";
export type OEMDeliveryStatus = "NOT_SENT" | "SENT" | "FAILED";

export interface DealerSummary {
  id: number;
  dealer_code: string;
  name: string;
}

export interface DmsSummary {
  id: number;
  name: string;
  integration_tier: number;
  integration_method: string;
  input_format: string;
}

export interface InvoiceSummary {
  id: number;
  invoice_number: string;
  total_amount: string | number;
  currency: string;
  validation_status: InvoiceValidationStatus;
  review_status: InvoiceReviewStatus;
  oem_delivery_status: OEMDeliveryStatus;
}

export interface InboundDocument {
  id: number;
  dealer_id: number;
  dms_id: number;
  document_type: string;
  original_file_name: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  storage_key: string | null;
  checksum_sha256: string | null;
  raw_payload: Record<string, unknown> | null;
  received_at: string;
  status: DocumentStatus;
  error_message: string | null;
  dealer?: DealerSummary | null;
  dms?: DmsSummary | null;
  invoice?: InvoiceSummary | null;
}

export interface DocumentListResponse {
  items: InboundDocument[];
  total: number;
  page: number;
  size: number;
}

export interface ValidationIssue {
  rule_code: string;
  rule_name: string;
  severity: "ERROR" | "WARNING";
  field?: string | null;
  line_number?: number | null;
  message: string;
}

export interface InvoiceLineItem {
  id: number;
  invoice_id: number;
  line_number: number;
  item_code: string | null;
  description: string;
  quantity: string | number;
  unit_price: string | number;
  discount_amount: string | number;
  taxable_amount: string | number;
  tax_rate: string | number | null;
  tax_amount: string | number;
  line_total: string | number;
  chassis_number: string | null;
}

export interface StandardizedInvoice {
  id: number;
  document_id: number;
  invoice_number: string;
  invoice_date: string;
  buyer_oem_id: string;
  currency: string;
  subtotal: string | number;
  tax_amount: string | number;
  total_amount: string | number;
  canonical_payload: Record<string, unknown>;
  validation_status: InvoiceValidationStatus;
  review_status: InvoiceReviewStatus;
  oem_delivery_status: OEMDeliveryStatus;
  created_at: string;
  updated_at: string;
  line_items: InvoiceLineItem[];
  validation_issues: ValidationIssue[];
}

export interface InvoiceListResponse {
  items: StandardizedInvoice[];
  total: number;
  page: number;
  size: number;
}

export interface LineItemPatch {
  line_number: number;
  item_code?: string | null;
  description?: string | null;
  quantity?: number | string | null;
  unit_price?: number | string | null;
  discount_amount?: number | string | null;
  taxable_amount?: number | string | null;
  tax_rate?: number | string | null;
  tax_amount?: number | string | null;
  line_total?: number | string | null;
  chassis_number?: string | null;
}

export interface InvoicePatchRequest {
  invoice_number?: string;
  invoice_date?: string;
  buyer_oem_id?: string;
  currency?: string;
  subtotal?: number | string;
  tax_amount?: number | string;
  total_amount?: number | string;
  reviewer_notes?: string;
  line_items?: LineItemPatch[];
}

export interface InvoiceReviewRequest {
  decision: "APPROVE" | "REJECT";
  notes?: string;
  force_override?: boolean;
}

export interface MockOEMResponse {
  is_mock: boolean;
  target_system: string;
  delivery_status: "NOT_SENT" | "SENT" | "FAILED";
  payload: Record<string, unknown>;
  disclaimer: string;
  timestamp: string;
}
