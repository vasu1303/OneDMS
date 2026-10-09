# OneDMS: Intelligent Middleware Architecture

This document outlines the high-level architecture and data workflow for the OneDMS standardization layer.

## 1. High-Level Architecture

The system acts as a universal bridge between fragmented dealer systems and the Daimler OEM. It utilizes a cloud bucket for immutable raw storage and an LLM-powered pipeline for intelligent data standardization.

```mermaid

graph TD
    %% Define styles
    classDef dealer fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px,color:#000;
    classDef core fill:#fff3e0,stroke:#ff9800,stroke-width:2px,color:#000;
    classDef oem fill:#e8f5e9,stroke:#4caf50,stroke-width:2px,color:#000;
    classDef storage fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px,color:#000;

    subgraph INPUTS["1. Dealer Inputs (Bring Your Own Protocol)"]
        D_API["Modern DMS<br/>API / JSON"]:::dealer
        D_FILE["Legacy DMS<br/>CSV / Excel"]:::dealer
        D_MAIL["Extreme Legacy<br/>SMTP / PDF / Emails"]:::dealer
    end

    subgraph CORE["2. OneDMS Core Infrastructure"]
        IL["Lightweight Interface Layer<br/>Ingestion"]:::core
        Bucket[("Cloud Storage / Bucket<br/>Raw Files")]:::storage
        Pipeline["LLM Processing Pipeline"]:::core
        StdJSON{"Standardized<br/>Canonical JSON"}:::core
        ConfigMgr["Config Manager & Rules Engine<br/>Validation & Constraints"]:::core
    end

    subgraph OEM["3. OEM Consumption"]
        Dash["OEM Web Dashboard"]:::oem
        FinalDaimler["Daimler OEM Output Format<br/>ERP / SAP"]:::oem
    end

    D_API --> IL
    D_FILE --> IL
    D_MAIL --> IL

    IL -->|1. Store raw inputs| Bucket
    Bucket -->|2. Trigger processing| Pipeline
    Pipeline -->|3. Extract and normalize| StdJSON
    StdJSON -->|4. Validate structured data| ConfigMgr
    ConfigMgr -->|5. Map to OEM format| FinalDaimler

    ConfigMgr -.->|Structured invoice data| Dash
    Bucket -.->|Original document links| Dash
```

## 2. Detailed Data Workflow (Sequence)

This sequence diagram illustrates the lifecycle of a single data transmission (e.g., a PDF invoice sent via email or a CSV upload) through the OneDMS pipeline.

```mermaid
sequenceDiagram
    participant Dealer as Dealer (Legacy DMS)
    participant Interface as Ingestion Interface
    participant Bucket as Cloud Storage Bucket
    participant LLM as LLM Processing Pipeline
    participant Config as Config Manager
    participant Dashboard as OEM Dashboard
    participant Daimler as Daimler Systems

    Dealer->>Interface: Sends raw data (API, CSV, PDF, Email)
    Interface->>Bucket: Dumps original raw file for audit/backup
    Interface-->>Dealer: Ack: Received successfully (Zero friction)
    
    Bucket->>LLM: Trigger: New file uploaded
    Note over LLM: LLM parses file (OCR/Vision)<br/>Maps chaotic fields to standard schema
    LLM->>Config: Outputs Streamlined Standard JSON
    
    Note over Config: Validates against Daimler business rules<br/>Applies specific OEM constraints
    
    Config->>Dashboard: Updates UI with standardized data view
    Dashboard->>Bucket: Fetches original file for auditor view
    Note over Dashboard: Auditor sees side-by-side:<br/>Clean JSON data + Original File (PDF/CSV)
    
    Config->>Daimler: Pushes final converted payload to OEM Core Systems
```

## 3. Core Component Breakdown

1. **Lightweight Interface Layer:** A simple, unopinionated gateway accepting multiple protocols (REST API, Web Upload UI, SMTP/Email listeners). It does no processing; it only authenticates and routes the data.
2. **Cloud Storage / Bucket:** The single source of truth for all raw data. Every incoming file (JSON payload, CSV, Excel, PDF) is saved here identically before any processing begins. This guarantees no data is ever lost and provides a perfect audit trail.
3. **LLM Processing Pipeline:** The "Magic" layer. Instead of maintaining 80 different hardcoded parsers, we use an LLM (e.g., Gemini) to extract meaning from the raw files in the bucket and structure it into a unified, streamlined JSON schema.
4. **Config Manager & Rules Engine:** The gateway to Daimler. The LLM output goes here first. This component ensures the JSON meets strict constraints, applies business logic (e.g., checking if part numbers exist, validating formatting), and converts the standard JSON into the precise final format that Daimler's legacy ERPs expect.
5. **OEM Dashboard:** A modern UI that consumes data from the Config Manager. Crucially, it also links back to the **Cloud Bucket**, allowing Daimler auditors to view the exact original email, Excel, or PDF alongside the AI-extracted, standardized data.
