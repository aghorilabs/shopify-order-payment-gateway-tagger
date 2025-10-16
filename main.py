import os
import json
import logging
import argparse
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Configure logging
def setup_logging():
    """Set up logging configuration with run headers"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_header = f"\nnew run: [{timestamp}]"
    
    # Configure general logger
    general_logger = logging.getLogger('general')
    general_logger.setLevel(logging.INFO)
    
    # Configure error logger
    error_logger = logging.getLogger('error')
    error_logger.setLevel(logging.ERROR)
    
    # Create file handlers
    general_handler = logging.FileHandler('logs/general.log', mode='a')
    error_handler = logging.FileHandler('logs/error.log', mode='a')
    
    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    general_handler.setFormatter(formatter)
    error_handler.setFormatter(formatter)
    
    # Add handlers to loggers
    general_logger.addHandler(general_handler)
    error_logger.addHandler(error_handler)
    
    # Add run headers
    general_logger.info(run_header)
    error_logger.info(run_header)
    
    return general_logger, error_logger

# Initialize loggers
general_logger, error_logger = setup_logging()

# Shopify API configuration
SHOPIFY_STORE_NAME = os.getenv('SHOPIFY_STORE_NAME')
SHOPIFY_ACCESS_TOKEN = os.getenv('SHOPIFY_ACCESS_TOKEN')
API_VERSION = "2024-01"  # Using latest stable version
GRAPHQL_ENDPOINT = f"https://{SHOPIFY_STORE_NAME}/admin/api/{API_VERSION}/graphql.json"

# Headers for GraphQL requests
HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN
}

def execute_graphql_query(query, variables=None, max_retries=3):
    """Execute a GraphQL query with retry logic"""
    for attempt in range(max_retries):
        try:
            response = requests.post(
                GRAPHQL_ENDPOINT,
                json={"query": query, "variables": variables},
                headers=HEADERS
            )
            
            if response.status_code == 200:
                data = response.json()
                if "errors" in data:
                    error_logger.error(f"GraphQL errors: {data['errors']}")
                    return None
                return data
            elif response.status_code == 429:
                # Rate limited, implement exponential backoff
                retry_after = int(response.headers.get('Retry-After', 5))
                wait_time = retry_after * (2 ** attempt)
                general_logger.info(f"API Rate Limited | Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                error_logger.error(f"API request failed with status {response.status_code}: {response.text}")
                return None
        except Exception as e:
            error_logger.error(f"Exception during API request: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    
    return None

def fetch_all_orders(test_limit=None):
    """Fetch all orders from Shopify using GraphQL pagination"""
    orders = []
    cursor = None
    page_size = 50  # Shopify's maximum page size
    page_count = 0
    
    query = """
    query getOrders($first: Int!, $after: String) {
        orders(first: $first, after: $after) {
            pageInfo {
                hasNextPage
                endCursor
            }
            edges {
                node {
                    id
                    name
                    tags
                    transactions(first: 5) {
                        gateway
                        status
                    }
                }
            }
        }
    }
    """
    
    while True:
        variables = {"first": page_size}
        if cursor:
            variables["after"] = cursor
        
        result = execute_graphql_query(query, variables)
        
        if not result or "data" not in result:
            error_logger.error("Failed to fetch orders")
            break
        
        data = result["data"]["orders"]
        new_orders = [edge["node"] for edge in data["edges"]]
        orders.extend(new_orders)
        page_count += 1
        
        # Check if we've reached the test limit
        if test_limit and len(orders) >= test_limit:
            orders = orders[:test_limit]
            general_logger.info(f"Fetched orders: Page {page_count} | Retrieved {len(new_orders)} orders | Total: {len(orders)} | Status: Test limit reached")
            break
        
        # Check if there are more pages
        if not data["pageInfo"]["hasNextPage"]:
            general_logger.info(f"Fetched orders: Page {page_count} | Retrieved {len(new_orders)} orders | Total: {len(orders)} | Status: Complete")
            break
        
        cursor = data["pageInfo"]["endCursor"]
        general_logger.info(f"Fetched orders: Page {page_count} | Retrieved {len(new_orders)} orders | Total so far: {len(orders)} | Fetching next page...")
    
    return orders

def identify_payment_gateway(order):
    """Identify the payment gateway from order transactions"""
    try:
        transactions = order.get("transactions", [])
        if not transactions:
            return ""
        
        # Get the first transaction's gateway
        gateway = transactions[0].get("gateway", "")
        return gateway
    except Exception as e:
        error_logger.error(f"Error identifying payment gateway for order {order.get('id', 'unknown')}: {str(e)}")
        return ""

def update_order_tags(order_id, new_tag):
    """Update order tags with the new payment gateway tag"""
    # Get current tags
    get_tags_query = """
    query getOrder($id: ID!) {
        order(id: $id) {
            id
            tags
        }
    }
    """
    
    result = execute_graphql_query(get_tags_query, {"id": order_id})
    if not result or "data" not in result:
        error_logger.error(f"Failed to get current tags for order {order_id}")
        return False
    
    current_tags = result["data"]["order"]["tags"]
    if not current_tags:
        current_tags = []
    
    # Check if the tag already exists
    if new_tag in current_tags:
        # Tag already exists, no need to update
        return True
    
    # Add the new tag since it doesn't exist
    current_tags.append(new_tag)
    
    # Update the order with new tags
    update_tags_mutation = """
    mutation orderUpdate($input: OrderInput!) {
        orderUpdate(input: $input) {
            order {
                id
                tags
            }
            userErrors {
                field
                message
            }
        }
    }
    """
    
    variables = {
        "input": {
            "id": order_id,
            "tags": current_tags
        }
    }
    
    result = execute_graphql_query(update_tags_mutation, variables)
    if not result or "data" not in result:
        error_logger.error(f"Failed to update tags for order {order_id}")
        return False
    
    if result["data"]["orderUpdate"]["userErrors"]:
        error_logger.error(f"Error updating tags for order {order_id}: {result['data']['orderUpdate']['userErrors']}")
        return False
    
    return True

def process_order(order):
    """Process a single order to identify and tag payment gateway"""
    order_id = order.get("id")
    order_name = order.get("name", "Unknown")
    
    try:
        # Identify payment gateway
        gateway = identify_payment_gateway(order)
        
        # Skip if gateway is empty (unknown)
        if not gateway:
            current_tags = order.get("tags", [])
            current_tags_str = ', '.join(current_tags) if current_tags else "none"
            general_logger.info(f"Order: {order_name} (ID: {order_id}) | Gateway: empty | Current Tags: [{current_tags_str}] | Status: No tag added (unknown gateway)")
            return order
        
        # Use gateway directly as tag (no prefix)
        new_tag = gateway
        
        # Get current tags
        get_tags_query = """
        query getOrder($id: ID!) {
            order(id: $id) {
                id
                tags
            }
        }
        """
        
        result = execute_graphql_query(get_tags_query, {"id": order_id})
        if not result or "data" not in result:
            error_logger.error(f"Failed to get current tags for order {order_id}")
            return None
        
        current_tags = result["data"]["order"]["tags"]
        if not current_tags:
            current_tags = []
        
        current_tags_str = ', '.join(current_tags) if current_tags else "none"
        
        # Check if tag already exists
        if new_tag in current_tags:
            general_logger.info(f"Order: {order_name} (ID: {order_id}) | Gateway: {gateway} | Current Tags: [{current_tags_str}] | Status: Tag already exists, no update needed")
            # Update the order object with current tags
            order["tags"] = current_tags
            return order
        
        # Update order tags since tag doesn't exist
        success = update_order_tags(order_id, new_tag)
        
        if success:
            # Get updated tags for logging
            result = execute_graphql_query(get_tags_query, {"id": order_id})
            if result and "data" in result:
                final_tags = result["data"]["order"]["tags"]
                final_tags_str = ', '.join(final_tags)
                
                # Log all information in a single line
                general_logger.info(f"Order: {order_name} (ID: {order_id}) | Gateway: {gateway} | Current Tags: [{current_tags_str}] | Added Tag: {new_tag} | Final Tags: [{final_tags_str}]")
            
            # Update the order object with new tags
            order["tags"] = final_tags
            return order
        else:
            # Log failure in single line format
            general_logger.info(f"Order: {order_name} (ID: {order_id}) | Gateway: {gateway} | Current Tags: [{current_tags_str}] | Added Tag: {new_tag} | Status: FAILED to update tags")
            error_logger.error(f"Failed to update tags for order {order_name}")
            return None
    except Exception as e:
        # Log error in single line format
        general_logger.info(f"Order: {order_name} (ID: {order_id}) | Status: ERROR - {str(e)}")
        error_logger.error(f"Error processing order {order_name}: {str(e)}")
        return None

def save_orders_to_json(orders):
    """Save processed orders to a timestamped JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logs/orders_{timestamp}.json"
    
    try:
        with open(filename, 'w') as f:
            json.dump(orders, f, indent=2)
        return filename
    except Exception as e:
        error_logger.error(f"Error saving orders to JSON: {str(e)}")
        return None

def main():
    """Main function to run the order tagging process"""
    parser = argparse.ArgumentParser(description="Simple Order Tagger & Auditing Tool")
    parser.add_argument("--test", type=int, help="Limit processing to N orders for testing")
    args = parser.parse_args()
    
    mode = f"Test mode (limit: {args.test})" if args.test else "Full mode"
    general_logger.info(f"Order Tagger Started | Mode: {mode}")
    
    # Fetch all orders
    orders = fetch_all_orders(args.test)
    if not orders:
        error_logger.error("No orders fetched. Exiting.")
        return
    
    # Process orders concurrently
    processed_orders = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all orders for processing
        future_to_order = {executor.submit(process_order, order): order for order in orders}
        
        # Process completed orders
        for future in as_completed(future_to_order):
            result = future.result()
            if result:
                processed_orders.append(result)
    
    # Save results to JSON
    if processed_orders:
        filename = save_orders_to_json(processed_orders)
        general_logger.info(f"Summary | Total Orders: {len(orders)} | Processed: {len(processed_orders)} | Saved to: {filename}")
    else:
        general_logger.info(f"Summary | Total Orders: {len(orders)} | Processed: 0 | Status: No orders successfully processed")
    
    general_logger.info("Order Tagger Completed")

if __name__ == "__main__":
    main()