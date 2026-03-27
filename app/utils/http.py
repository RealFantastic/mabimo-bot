#imports
import httpx

# app/utils/http.py
def get(url : str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = httpx.get(url, headers=headers, timeout=10.0)
    response.raise_for_status()
    return response.text