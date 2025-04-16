import os
import logging
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, HttpUrl
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()  # Load environment variables from .env file

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
HOARDER_API_KEY = os.getenv("HOARDER_API_KEY")
HOARDER_BASE_URL = os.getenv("HOARDER_API_BASE_URL", "https://hoarder.karakeep.app/api/v1")
SEARCH_ENDPOINT = f"{HOARDER_BASE_URL}/bookmarks/search"
BOOKMARKS_ENDPOINT = f"{HOARDER_BASE_URL}/bookmarks"

if not HOARDER_API_KEY:
    logger.error("FATAL: HOARDER_API_KEY environment variable not set.")
    # In a real scenario, you might exit or raise a more specific configuration error
    # For simplicity here, we'll let it proceed but API calls will fail.

# --- Pydantic Models for Request Validation ---

class SearchParams(BaseModel):
    query: str = Field(..., description="The search term for bookmarks.")

class CreateParams(BaseModel):
    url: HttpUrl = Field(..., description="The URL of the bookmark to create.")
    title: Optional[str] = Field(None, description="Optional title for the bookmark.")
    description: Optional[str] = Field(None, description="Optional description for the bookmark.")
    # Add other Hoarder fields if needed (e.g., tags, is_unread) based on API docs

class MCPRequest(BaseModel):
    action: str = Field(..., description="The action to perform ('search_bookmarks' or 'create_bookmark').")
    parameters: Dict[str, Any] = Field(..., description="Parameters specific to the action.")

# --- Hoarder API Client Logic ---

async def call_hoarder_api(
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Helper function to make asynchronous requests to the Hoarder API."""
    if not HOARDER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hoarder API key is not configured on the server."
        )

    headers = {
        "X-Api-Key": HOARDER_API_KEY,
        "Accept": "application/json",
    }
    if json_data:
        headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Calling Hoarder API: {method} {url}")
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses
            logger.info(f"Hoarder API response status: {response.status_code}")
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error(f"Hoarder API Error: {e.response.status_code} - {e.response.text}")
            # Try to parse error message from Hoarder if available
            error_detail = f"Hoarder API request failed with status {e.response.status_code}."
            try:
                error_body = e.response.json()
                if "message" in error_body:
                    error_detail += f" Message: {error_body['message']}"
                elif "error" in error_body:
                     error_detail += f" Error: {error_body['error']}"
                else:
                    error_detail += f" Body: {e.response.text[:200]}" # Limit body size
            except Exception:
                 error_detail += f" Body: {e.response.text[:200]}"

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY, # Indicate error is from upstream API
                detail=error_detail
            )
        except httpx.RequestError as e:
            logger.error(f"HTTP Request Error contacting Hoarder API: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Could not connect to Hoarder API: {e}"
            )
        except Exception as e:
             logger.exception(f"An unexpected error occurred during Hoarder API call: {e}")
             raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected server error occurred: {str(e)}"
            )


async def search_hoarder_bookmarks(query: str) -> List[Dict[str, Any]]:
    """Searches bookmarks in Hoarder."""
    params = {"q": query}
    results = await call_hoarder_api("GET", SEARCH_ENDPOINT, params=params)
    # Assuming the API returns a list directly based on docs example
    if isinstance(results, list):
        return results
    else:
        logger.warning(f"Hoarder search API did not return a list: {type(results)}")
        # Adapt if the API wraps the list in an object, e.g., return results.get('data', [])
        return []


async def create_hoarder_bookmark(url: str, title: Optional[str], description: Optional[str]) -> Dict[str, Any]:
    """Creates a bookmark in Hoarder."""
    payload = {"url": str(url)} # Ensure URL is a string
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description

    created_bookmark = await call_hoarder_api("POST", BOOKMARKS_ENDPOINT, json_data=payload)
    # Assuming the API returns the created bookmark object
    return created_bookmark

# --- FastAPI Application ---

app = FastAPI(
    title="Hoarder MCP Server",
    description="An MCP server to interact with the Hoarder bookmarking service API.",
    version="1.0.0"
)

@app.post("/mcp", tags=["MCP Actions"])
async def handle_mcp_request(request_body: MCPRequest):
    """
    Main endpoint to handle MCP requests for Hoarder.

    - **action**: `search_bookmarks` or `create_bookmark`
    - **parameters**:
        - For `search_bookmarks`: `{"query": "search term"}`
        - For `create_bookmark`: `{"url": "http://...", "title": "optional title", "description": "optional desc"}`
    """
    action = request_body.action
    params = request_body.parameters
    logger.info(f"Received MCP request: action={action}, params={params}")

    try:
        if action == "search_bookmarks":
            # Validate parameters for search
            search_input = SearchParams(**params)
            results = await search_hoarder_bookmarks(query=search_input.query)
            return {
                "status": "success",
                "action": action,
                "results_count": len(results),
                "data": results
            }

        elif action == "create_bookmark":
            # Validate parameters for create
            create_input = CreateParams(**params)
            created_bookmark = await create_hoarder_bookmark(
                url=create_input.url,
                title=create_input.title,
                description=create_input.description
            )
            return {
                "status": "success",
                "action": action,
                "data": created_bookmark
            }

        else:
            logger.warning(f"Invalid action received: {action}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action specified: '{action}'. Valid actions are 'search_bookmarks', 'create_bookmark'."
            )

    except HTTPException as e:
        # Re-raise HTTPExceptions directly (includes validation errors from Pydantic)
        raise e
    except Exception as e:
        # Catch any other unexpected errors during processing
        logger.exception(f"Error processing MCP request for action {action}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while processing the request: {str(e)}"
        )

@app.get("/", tags=["Status"])
async def root():
    """Basic health check endpoint."""
    return {"message": "Hoarder MCP Server is running."}


# --- Running the Server (for local development) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Hoarder MCP Server locally on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
