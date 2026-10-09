/** Canonical transaction statuses across all DMS systems */
export type TransactionStatus =
  | 'pending'
  | 'quoted'
  | 'negotiating'
  | 'accepted'
  | 'invoiced'
  | 'completed'
  | 'rejected';

/** Dealer tiers based on integration capability */
export type DealerTier = 'api' | 'sftp' | 'upload';

/** Supported DMS data source formats */
export type SourceFormat = 'json' | 'xml' | 'csv' | 'excel' | 'pdf' | 'flatfile';

/** Core dealer entity */
export interface Dealer {
  id: string;
  name: string;
  dmsName: string;
  tier: DealerTier;
  sourceFormat: SourceFormat;
  isActive: boolean;
  createdAt: string;
}

/** Canonical transaction record */
export interface Transaction {
  id: string;
  dealerId: string;
  type: 'order' | 'quote' | 'invoice';
  status: TransactionStatus;
  rawData: Record<string, unknown>;
  canonicalData: Record<string, unknown>;
  confidenceScore: number;
  createdAt: string;
  updatedAt: string;
}

/** Exception queue item for human review */
export interface ExceptionItem {
  id: string;
  transactionId: string;
  reason: string;
  confidenceScore: number;
  status: 'pending' | 'approved' | 'rejected';
  reviewedBy?: string;
  createdAt: string;
}

/** API response wrapper */
export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

/** Paginated response */
export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  total: number;
  page: number;
  pageSize: number;
}
