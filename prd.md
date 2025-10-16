# **Product Requirements Document (PRD)**

## **Project: Simple Order Tagger & Auditing Tool (Project TAG)**

Version: 1.3 (Concurrency & Test Mode Update)  

Date: October 2025  
Platform: Python 3.x (macOS / VENV)

## **1\. Goal**

The primary goal of Project TAG is to create a lightweight, performant, non-production utility that fetches all historical orders from the configured Shopify store using the **latest stable version of the GraphQL Admin API**, concurrently identifies the payment method used for each order, and adds a descriptive tag based on that method.

This tool is intended solely for personal data auditing and analysis.

## **2\. Key Features (User Stories)**

| ID | Feature Description | Acceptance Criteria |
| :---- | :---- | :---- |
| **F1** | **Secure API Authentication** | The application must load API credentials (e.g., Store URL, **Admin API Access Token**) exclusively from a local .env file. |
| **F2** | **Full Order Fetch (GraphQL)** | The application must successfully execute a paginated **GraphQL query** against the Shopify Admin API to retrieve *all* orders. The query must specifically fetch the transaction details required for payment gateway identification. |
| **F3** | **Payment Gateway Identification** | The core logic must inspect the raw order details, specifically the transaction's gateway field, and use the raw string directly as the tag. **No transformation, renaming, or modification of this string should occur.** |
| **F4** | **Non-Destructive Tagging** | The application must add the newly identified payment tag to the order's existing list of tags. **No existing tags or other order data may be modified or deleted.** |
| **F5** | **Local JSON Output** | Upon completion, all successfully fetched and tagged order objects must be written to a single, uniquely timestamped JSON file in the run directory. |
| **F6** | **Logging Management** | A comprehensive logging system must be in place for every execution run, utilizing persistent log files with clear run headers. (See Section 3.2). |
| **F7** | **Concurrency/Workers** | The application must utilize a pool of workers to process and update tags on multiple orders simultaneously, minimizing the overall runtime. |
| **F8** | **Test Run Mode** | The application must support a command-line argument to limit the processing scope for testing purposes. |

## **3\. Technical & Non-Functional Requirements**

### **3.1. Environment and Execution**

* **Language:** Python 3.x.  
* **Environment:** Must utilize a Python Virtual Environment (venv) for dependency isolation.  
* **Configuration:** API keys and environment variables must be loaded via a .env file (e.g., using python-dotenv).  
* **Command Line Arguments:** Must use a library (e.g., argparse) to support an optional argument like \--test N, where N is the integer limit of orders to process.

### **3.2. Logging (CRITICAL)**

The application must maintain two persistent log files: logs/general.log and logs/error.log.

For every new execution run, a clear separation must be made in both log files:

* **Run Header:** An empty line must precede a new header line stating "new run: \[Date and Time\]".  
1. **general.log (INFO Level):** Must capture detailed operational events, including:  
   * Start/End of the run.  
   * API requests sent (URL/endpoint).  
   * For each successfully processed order:  
     * Order ID (e.g., Shopify's GraphQL ID).  
     * Identified payment gateway name (transactions.gateway).  
     * The exact new tag being added.  
     * The final, complete list of tags on the order.  
2. **error.log (ERROR/WARNING Level):** Must capture all exceptions, failed API calls, and warnings, including:  
   * Details of failed API requests (status code, error message, GraphQL errors).  
   * Errors encountered during payment field parsing or tag processing.  
   * Any file I/O errors.

### **3.3. API Interaction (Shopify GraphQL)**

* **API Type:** Shopify GraphQL Admin API (latest stable version recommended). All schemas and documentation must refer to the official Shopify documentation.  
* **Endpoint:** All requests will target the single Shopify GraphQL endpoint (/admin/api/{version}/graphql.json).  
* **Data Flow:** Order fetching will be serial (to manage pagination cursors), but the subsequent steps of identifying the tag and applying the tag update (mutation) will be performed **concurrently** (F7).  
* **Concurrency:** Implement worker pools (e.g., using Python's concurrent.futures.ThreadPoolExecutor) to handle concurrent API tag update mutations, respecting Shopify's rate limits.  
* **Query Structure:** The application must construct a GraphQL query that adheres to the official Shopify schema. The query must use the orders connection with forward pagination (first: N, after: cursor) to fetch all records efficiently.  
* **Library:** The requests library will be used to send HTTP **POST** requests containing the JSON-encoded GraphQL query payload.  
* **Error Handling:** Implement exponential backoff for retries on transient API errors (e.g., 429 rate limit) and handle GraphQL-specific error arrays within the response.

## **4\. Proposed File Structure**

.  
├── .env                  \# API keys and config (ignored by git/sync)  
├── venv/                 \# Python virtual environment  
├── main.py               \# Main application logic  
├── requirements.txt      \# List of project dependencies (needs to include python-dotenv, requests, and argparse functionality)  
└── logs/  
    ├── general.log         \# Persistent log file, appended to on each run with run headers.  
    ├── error.log           \# Persistent error file, appended to on each run with run headers.  
    └── orders\_20251016\_133045.json \# Unique timestamped JSON output for each run.  
