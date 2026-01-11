import aiohttp
from app.config import CLOUDFLARE_API_KEY, CLOUDFLARE_ZONE_ID, CDN_PURGE_ENABLED


class CDNService:
    def __init__(self):
        self.api_key = CLOUDFLARE_API_KEY
        self.zone_id = CLOUDFLARE_ZONE_ID
        self.enabled = CDN_PURGE_ENABLED
        self.base_url = f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}"

    async def purge_cache(self, urls: list[str]) -> bool:
        """Purge URLs from Cloudflare cache."""
        if not self.enabled or not self.api_key or not self.zone_id:
            return True  # Silently pass if not configured

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                data = {"files": urls}
                
                async with session.post(
                    f"{self.base_url}/purge_cache",
                    json=data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return True
                    else:
                        print(f"CDN purge failed: {response.status}")
                        return False
        except Exception as e:
            print(f"Error purging cache: {e}")
            return False

    async def purge_by_prefix(self, prefixes: list[str]) -> bool:
        """Purge by URL prefix."""
        if not self.enabled or not self.api_key or not self.zone_id:
            return True

        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                data = {"prefixes": prefixes}
                
                async with session.post(
                    f"{self.base_url}/purge_cache",
                    json=data,
                    headers=headers
                ) as response:
                    return response.status == 200
        except Exception as e:
            print(f"Error purging by prefix: {e}")
            return False


cdn_service = CDNService()
