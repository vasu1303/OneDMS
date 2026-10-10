// Provisional frontend DTOs, not backend-confirmed. See frontend README
// for endpoint ownership, integer/decimal transport, and editable fields.
export type Id = number;

export type InputFormat = 'JSON' | 'CSV' | 'EXCEL' | 'PDF';
export interface DealerRegistryEntry {
  id: Id;
  dealer_code: string;
  name: string;
}
export interface SourceMapping {
  invoice_number: string;
  invoice_date: string;
  buyer_oem_id: string;
  currency: string;
  subtotal: string;
  tax_amount: string;
  total_amount: string;
  supplier_dealer_code?: string;
  line_items: {
    source_field: string;
    description: string;
    quantity: string;
    unit_price: string;
    taxable_amount: string;
    tax_amount: string;
    line_total: string;
    item_code?: string;
    chassis_number?: string;
    item_category?: string;
    discount_amount?: string;
    tax_rate?: string;
  };
}
export interface DmsRegistryEntry {
  id: Id;
  name: string;
  integration_tier: number;
  integration_method: string;
  input_format: InputFormat;
  active_mapping_version: number | null;
  active_mapping_config: Record<string, unknown> | null;
}
export interface CreateDmsPayload {
  name: string;
  integration_tier: number;
  integration_method: 'API' | 'UPLOAD';
  input_format: InputFormat;
  mapping_config?: SourceMapping;
}
export interface CreateDmsBatchPayload {
  profiles: CreateDmsPayload[];
}
export interface DmsBatchRegistryResult {
  profiles: DmsRegistryEntry[];
}
export interface MappingPreviewPayload {
  mapping_config: SourceMapping;
  payload: Record<string, unknown>;
}
export interface MappingPreviewResult {
  canonical_candidate: Record<string, unknown>;
}

export type SourceType = 'json' | 'xml' | 'csv' | 'excel' | 'pdf' | 'flatfile';

export type ProcessingStatus =
  | 'received'
  | 'processing'
  | 'processed'
  | 'failed'
  | 'review_required';

export type ValidationStatus = 'pending' | 'valid' | 'invalid' | 'warning';

export type ReviewStatus = 'pending' | 'in_review' | 'approved' | 'rejected';

export type DeliveryStatus = 'pending' | 'ready' | 'delivered' | 'failed';

export type FindingSeverity = 'error' | 'warning' | 'info';

export interface QueueFilters {
  processing_status?: ProcessingStatus | 'all';
  validation_status?: ValidationStatus | 'all';
  review_status?: ReviewStatus | 'all';
  dealer_code?: string;
  q?: string;
}

export interface DocumentQueueItem {
  id: Id;
  dealer_code: string;
  dealer_name?: string | null;
  dms_name?: string | null;
  source_type: SourceType;
  source_filename?: string | null;
  received_at: string;
  processing_status: ProcessingStatus;
  validation_status: ValidationStatus;
  review_status: ReviewStatus;
  summary?: string | null;
  has_findings?: boolean;
  findings_count?: number;
  invoice_id?: Id | null;
}

export interface DocumentDetail extends DocumentQueueItem {
  source_content_type?: string | null;
  source_size_bytes?: number | null;
  checksum_sha256?: string | null;
  last_error?: string | null;
}

export interface ValidationFinding {
  id?: Id;
  severity: FindingSeverity;
  field?: string | null;
  line_number?: number | null;
  message: string;
  confidence?: number | null;
  extracted_value?: string | number | null;
  approved_value?: string | number | null;
}

export interface InvoiceLineItem {
  id?: Id;
  line_number: number;
  part_number?: string | null;
  description?: string | null;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  tax_amount: number;
  line_total: number;
  vin?: string | null;
}

export interface InvoiceHeader {
  invoice_number: string;
  invoice_date?: string | null;
  dealer_invoice_ref?: string | null;
  currency_code: string;
  subtotal_amount: number;
  discount_amount: number;
  tax_amount: number;
  total_amount: number;
}

export interface InvoiceDetail {
  id: Id;
  document_id: Id;
  buyer_oem_id?: string | null;
  processing_status: ProcessingStatus;
  validation_status: ValidationStatus;
  review_status: ReviewStatus;
  delivery_status?: DeliveryStatus;
  header: InvoiceHeader;
  line_items: InvoiceLineItem[];
  findings: ValidationFinding[];
  updated_at?: string | null;
}

export interface DocumentUploadPayload {
  dealer_id: string;
  dms_id: string;
  source_type: SourceType;
  file: File;
}

export interface JsonDocumentSubmission {
  dealer_id: string;
  dms_id: string;
  payload: Record<string, unknown>;
}

export interface InvoicePatchPayload {
  header?: Partial<InvoiceHeader>;
  line_items?: Array<Partial<InvoiceLineItem> & { id?: Id; line_number: number }>;
}

export interface InvoiceReviewPayload {
  decision: 'approve' | 'reject';
  notes?: string;
}
