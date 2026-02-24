"""
Jarvis Skills — Online Operations

Provides web search, scraping, and downloading capabilities,
giving Max omniscient access to the internet for real-time data.
"""

import logging
import os
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
import warnings
warnings.filterwarnings("ignore", module="duckduckgo_search")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*duckduckgo_search.*")

from skills import skill

logger = logging.getLogger("jarvis.skills.online")


@skill(
    name="search_web",
    description="Searches the web for real-time information using DuckDuckGo.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (max 10). Default: 5.",
            },
        },
        "required": ["query"],
    },
)
def search_web(query: str, num_results: int = 5, **kwargs) -> str:
    """Perform a web search."""
    if not query.strip():
        return "Search query cannot be empty."
    
    num_results = max(1, min(10, num_results))
    logger.info("Searching web for: %s (limit: %d)", query, num_results)
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
            
        if not results:
            return f"No results found for '{query}'."
            
        output = [f"Search results for '{query}':\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No Title")
            body = r.get("body", "No Description")
            url = r.get("href", "")
            output.append(f"{i}. {title}")
            output.append(f"   URL: {url}")
            output.append(f"   Summary: {body}\n")
            
        return "\n".join(output)
    except Exception as e:
        logger.error("Web search failed: %s", e)
        return f"Web search failed: {e}"


@skill(
    name="read_webpage",
    description=(
        "Extracts and reads the main text content from a webpage URL. "
        "Useful for getting the full details after a web search."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to read.",
            },
        },
        "required": ["url"],
    },
)
def read_webpage(url: str, **kwargs) -> str:
    """Extract text from a webpage."""
    if not url.startswith("http"):
        url = "https://" + url
        
    logger.info("Reading webpage: %s", url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove noisy elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
            element.decompose()
            
        text = soup.get_text(separator="\n", strip=True)
        
        # Clean up empty lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)
        
        if len(cleaned_text) > 4000:
            cleaned_text = cleaned_text[:4000] + "\n... (Content truncated, too long to read completely)"
            
        return f"Content of {url}:\n\n{cleaned_text}"
        
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch webpage %s: %s", url, e)
        return f"Failed to access webpage: {e}"
    except Exception as e:
        return f"Error parsing webpage: {e}"


@skill(
    name="download_file",
    description="Downloads a file from a URL to the local disk.",
    parameters={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the file to download.",
            },
            "destination": {
                "type": "string",
                "description": "The local path to save the file. If directory, keeps original filename.",
            },
        },
        "required": ["url", "destination"],
    },
)
def download_file(url: str, destination: str, **kwargs) -> str:
    """Download a file from the web."""
    if not url.startswith("http"):
        url = "https://" + url
        
    destination = os.path.expanduser(destination)
    if os.path.isdir(destination):
        filename = os.path.basename(urlparse(url).path)
        if not filename:
            filename = "downloaded_file"
        destination = os.path.join(destination, filename)
        
    logger.info("Downloading %s to %s", url, destination)
    
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        file_size = os.path.getsize(destination) / (1024 * 1024)  # MB
        return f"Successfully downloaded file to {destination} ({file_size:.2f} MB)."
    except Exception as e:
        logger.error("Download failed: %s", e)
        return f"Download failed: {e}"
