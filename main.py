import os
import logging
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field, HttpUrl
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
# NOTE: This variable now holds the BEARER TOKEN value
HOARDER_API_KEY_OR_TOKEN = os.getenv("HOARDER_API_KEY")
HOARDER_BASE_URL = os.getenv("HOARDER_API_BASE_URL", "https://hoarder.karakeep.app/api/v1") # Keep your self-hosted URL here if set in .env
SEARCH_ENDPOINT = f"{HOARDER_BASE_URL}/bookmarks/search"
BOOKMARKS_ENDPOINT = f"{HOARDER_BASE_URL}/bookmarks"

if not HOARDER_API_KEY_OR_TOKEN:
    logger.error("FATAL: HOARDER_API_KEY environment variable (used as Bearer Token) not set.")
    # In a real scenario, you might exit or raise a more specific configuration error

# --- Pydantic Models (remain the same) ---
# ... (SearchParams, CreateParams, MCPRequest models) ...

class SearchParams(BaseModel):
    query: str = Field(..., description="The search term for bookmarks.")

class CreateParams(BaseModel):
    url: HttpUrl = Field(..., description="The URL of the bookmark to create.")
    title: Optional[str] = Field(None, description="Optional title for the bookmark.")
    description: Optional[str] = Field(None, description="Optional description for the bookmark.")

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

    # --- BEGIN DEBUGGING (Optional but recommended for now) ---
    loaded_token = HOARDER_API_KEY_OR_TOKEN
    if loaded_token:
        token_preview = f"{loaded_token[:5]}...{loaded_token[-5:]}" if len(loaded_token) > 10 else loaded_token
        logger.info(f"DEBUG: Using Hoarder Bearer Token (Type: {type(loaded_token)}, Preview: {token_preview})")
    else:
        logger.error("DEBUG: HOARDER_API_KEY variable (used as Bearer Token) is None or Empty!")
    # --- END DEBUGGING ---

    if not HOARDER_API_KEY_OR_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Hoarder API key/token is not configured on the server."
        )

    # === CHANGE HERE ===
    headers = {
        # Use Authorization: Bearer header
        "Authorization": f"Bearer {HOARDER_API_KEY_OR_TOKEN}",
        "Accept": "application/json",
    }
    # ===================

    if json_data:
        headers["Content-Type"] = "application/json"

    # --- BEGIN DEBUGGING (Optional but recommended for now) ---
    # Log the actual headers being sent
    # Be cautious logging the full Authorization header if logs are public
    logged_headers = headers.copy()
    if "Authorization" in logged_headers:
         # Mask most of the token in logs
         auth_val = logged_headers["Authorization"]
         if len(auth_val) > 15: # Check length "Bearer " + token part
              logged_headers["Authorization"] = f"{auth_val[:12]}...{auth_val[-5:]}" # Show "Bearer " prefix and end of token
         else:
              logged_headers["Authorization"] = auth_val[:12] + "..."
    logger.info(f"DEBUG: Request Headers Sent to Hoarder: {logged_headers}")
    # --- END DEBUGGING ---

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            logger.info(f"Calling Hoarder API: {method} {url}") # Log URL without params
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params, # Params are added to URL by httpx for GET
                json=json_data # Body for POST/PUT etc
            )
            # Log the request URL with params for clarity
            request_url_with_params = response.request.url
            logger.info(f"HTTP Request: {method} {request_url_with_params} \"HTTP/{response.http_version} {response.status_code} {response.reason_phrase}\"")

            response.raise_for_status()
            logger.info(f"Hoarder API response status: {response.status_code}")
            return response.json()

        except httpx.HTTPStatusError as e:
            # Log the raw response body for debugging 4xx/5xx errors
            error_body_text = e.response.text
            logger.error(f"Hoarder API Error: {e.response.status_code} - Response Body: {error_body_text}")
            # Try to parse error message from Hoarder if available
            error_detail = f"Hoarder API request failed with status {e.response.status_code}."
            try:
                error_body = e.response.json()
                if "message" in error_body:
                    error_detail += f" Message: {error_body['message']}"
                elif "error" in error_body:
                     error_detail += f" Error: {error_body['error']}"
                elif "code" in error_body: # Added check for "code" field seen in previous log
                     error_detail += f" Code: {error_body['code']}"
                else:
                    error_detail += f" Body: {error_body_text[:200]}" # Limit body size
            except Exception:
                 error_detail += f" Body: {error_body_text[:200]}"

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


# --- Action Handlers (remain the same) ---
# ... (search_hoarder_bookmarks, create_hoarder_bookmark) ...

async def search_hoarder_bookmarks(query: str) -> List[Dict[str, Any]]:
    """Searches bookmarks in Hoarder."""
    params = {"q": query}
    # Ensure URL uses the configured base URL
    search_url = f"{HOARDER_BASE_URL}/bookmarks/search"
    results = await call_hoarder_api("GET", search_url, params=params)
    if isinstance(results, list):
        return results
    else:
        logger.warning(f"Hoarder search API did not return a list: {type(results)}")
        return [] # Or handle based on actual API response structure

async def create_hoarder_bookmark(url: str, title: Optional[str], description: Optional[str]) -> Dict[str, Any]:
    """Creates a bookmark in Hoarder."""
    # Ensure URL uses the configured base URL
    bookmarks_url = f"{HOARDER_BASE_URL}/bookmarks"
    payload = {"url": str(url)}
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description

    created_bookmark = await call_hoarder_api("POST", bookmarks_url, json_data=payload)
    return created_bookmark


# --- FastAPI Application (remains the same) ---
# ... (app = FastAPI(...), @app.post("/mcp"), @app.get("/")) ...

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
            search_input = SearchParams(**params)
            results = await search_hoarder_bookmarks(query=search_input.query)
            return {
                "status": "success",
                "action": action,
                "results_count": len(results),
                "data": results
            }

        elif action == "create_bookmark":
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
        raise e
    except Exception as e:
        logger.exception(f"Error processing MCP request for action {action}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while processing the request: {str(e)}"
        )

@app.get("/", tags=["Status"])
async def root():
    """Basic health check endpoint."""
    return {"message": "Hoarder MCP Server is running."}


# --- Running the Server ---
if __name__ == "__main__":
    import uvicorn
    # Determine host and port for uvicorn
    # Use environment variables if available (common in deployment), otherwise default
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8888")) # Using 8888 as you used it before
    reload = os.getenv("UVICORN_RELOAD", "true").lower() == "true" # Control reload via env var

    logger.info(f"Starting Hoarder MCP Server on http://{host}:{port} (Reload: {reload})")
    uvicorn.run("main:app", host=host, port=port, reload=reload)