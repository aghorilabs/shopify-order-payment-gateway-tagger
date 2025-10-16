# Payment Gateway Order Tagger

A Python tool that automatically tags Shopify orders with their payment gateway information. This tool fetches all historical orders from your Shopify store, identifies the payment method used for each order, and adds a descriptive tag based on that method.

## Overview

This project consists of two main components:

1. **Python Script (`main.py`)**: A batch processing tool that can tag all historical orders in your Shopify store
2. **Flow File (`Tag orders by payment gateway.flow`)**: A Shopify Flow workflow that can automatically tag future orders as they come in

## Features

- Fetches all historical orders from Shopify using GraphQL Admin API
- Identifies payment gateway from order transactions
- Adds payment gateway as a tag to existing orders
- Processes orders concurrently for faster execution
- Supports test mode for limited processing
- Comprehensive logging system
- Saves processed orders data to timestamped JSON files

## Prerequisites

- Python 3.x installed
- Shopify store with Admin API access
- Shopify Admin API access token with appropriate permissions

## Installation

1. Clone or download this project to your local machine
2. Create a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the example:
   ```bash
   cp .env.example .env
   ```

5. Edit the `.env` file and add your Shopify credentials:
   ```
   SHOPIFY_STORE_NAME=your-store-name.myshopify.com
   SHOPIFY_ACCESS_TOKEN=your-admin-api-access-token
   ```

## Usage

### Running the Python Script

#### Full Mode (Process All Orders)
```bash
python main.py
```

#### Test Mode (Process Limited Number of Orders)
```bash
python main.py --test 50
```
This will process only the first 50 orders for testing purposes.

### Understanding the Logs

The tool creates two log files in the `logs/` directory:

1. **general.log**: Contains detailed operational information including:
   - Start/end of the run
   - API request details
   - Order processing information (ID, gateway, tags added)
   - Summary statistics

2. **error.log**: Contains any errors or exceptions that occur during processing

Both log files include timestamps and run headers to separate different execution sessions.

### Output Files

After each run, the tool creates a timestamped JSON file in the `logs/` directory (e.g., `orders_20251016_133045.json`) containing all processed orders with their updated tags.

## Shopify Flow Integration

The `Tag orders by payment gateway.flow` file can be imported into Shopify Flow to create an automated workflow that tags new orders as they come in:

1. Go to your Shopify Admin
2. Navigate to Apps > Shopify Flow
3. Click "Create workflow"
4. Select "Import" and upload the `.flow` file
5. The workflow will automatically trigger when new orders are created and tag them with their payment gateway

## Technical Details

### API Authentication

The tool uses Shopify's GraphQL Admin API (version 2024-01) with the following permissions:
- Read orders
- Write orders

### Rate Limiting

The tool implements:
- Exponential backoff for rate-limited requests
- Concurrent processing with ThreadPoolExecutor (max 5 workers)
- Proper retry logic for failed requests

### Payment Gateway Tagging

The tool:
- Extracts the payment gateway name directly from the transaction data
- Uses the raw gateway string as the tag (no transformation)
- Preserves all existing tags on orders
- Only adds the new tag if it doesn't already exist

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify your SHOPIFY_STORE_NAME and SHOPIFY_ACCESS_TOKEN in the `.env` file
   - Ensure your API token has the required permissions

2. **Rate Limiting**
   - The tool automatically handles rate limiting with exponential backoff
   - If you experience consistent rate limiting, try reducing the number of concurrent workers in the script

3. **Missing Logs Directory**
   - The script will create the `logs/` directory if it doesn't exist
   - Ensure you have write permissions in the project directory

### Debug Mode

For detailed debugging, check the `logs/error.log` file which contains:
- API request failures
- GraphQL errors
- Exception details
- Failed order processing information

## Project Structure

```
.
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore file
├── main.py                   # Main Python script
├── requirements.txt          # Python dependencies
├── prd.md                    # Product Requirements Document
├── Tag orders by payment gateway.flow  # Shopify Flow workflow
└── logs/                     # Directory for logs and output files
    ├── general.log           # General operation logs
    ├── error.log             # Error logs
    └── orders_*.json         # Timestamped output files
```

## Security Notes

- Never commit your `.env` file to version control
- Keep your Shopify API access token secure
- The tool only reads and modifies order tags, not other order data
- All processing is logged for audit purposes

## Support

For issues or questions:
1. Check the log files for detailed error information
2. Verify your API credentials and permissions
3. Ensure your Shopify store meets the API requirements