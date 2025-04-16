# Karakeep (Hoarder) MCP Server

This project provides a Mind Control Panel (MCP) compatible server that allows interactions (searching and creating bookmarks) with the [Karakeep](https://karakeep.app/) bookmarking service via its API.

It's designed to be used by Large Language Models (LLMs) or other clients capable of making HTTP requests according to the MCP protocol defined by services like [Glama.ai](https://glama.ai/).

## Features

*   **Search Bookmarks:** Find existing bookmarks in Karakeep based on a query string.
*   **Create Bookmarks:** Add new bookmarks to Karakeep with a URL and optional title/description.
*   **MCP Compatible Endpoint:** Exposes a single `/mcp` endpoint for actions.
*   **Environment Variable Configuration:** Securely configure your Hoarder API key.

## Prerequisites

*   Python 3.8+
*   A Karakeep account and API Key ([See Karakeep API Docs](https://docs.karakeep.app/API/hoarder-api))
*   Access to a hosting platform (e.g., Render, Heroku, Fly.io, VPS) or Docker for deployment.

## Setup and Local Development

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd hoarder-mcp-server
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   Create a file named `.env` in the project root.
    *   Add your Hoarder API key to it:
        ```env
        HOARDER_API_KEY="YOUR_HOARDER_API_KEY_HERE"
        ```
    *   **Important:** Make sure `.env` is listed in your `.gitignore` file to avoid committing secrets.

5.  **Run the server locally:**
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The server will be available at `http://127.0.0.1:8000`. The `--reload` flag automatically restarts the server when code changes are detected.

## API Usage

The server exposes a single POST endpoint: `/mcp`.

**Request Body (JSON):**

```json
{
  "action": "action_name",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
    // ... action-specific parameters
  }
}

<a href="https://glama.ai/mcp/servers/@jcrabapple/hoarder-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@jcrabapple/hoarder-mcp-server/badge" />
</a>
