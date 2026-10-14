from datetime import datetime, timezone
from typing import Any, Optional
import httpx
from .schemas import ResultStatus

class BrregClient:
    ENHET_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
    ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
    REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.headers = {"User-Agent": "Signalpost-Company-Agent/1.0.0", "Accept": "application/json"}
    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
    async def _fetch(self, client: httpx.AsyncClient, url: str):
        try:
            response = await client.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code == 200:
                return ResultStatus.AVAILABLE, response.json(), url
            if response.status_code == 404:
                return ResultStatus.NOT_AVAILABLE, None, url
            if response.status_code in (403, 429):
                return ResultStatus.BLOCKED, None, url
            return ResultStatus.FAILED, None, url
        except httpx.RequestError:
            return ResultStatus.FAILED, None, url
    async def fetch_entity(self, client: httpx.AsyncClient, orgnr: str):
        return await self._fetch(client, f"{self.ENHET_URL}/{orgnr}")
    async def fetch_roles(self, client: httpx.AsyncClient, orgnr: str):
        return await self._fetch(client, self.ROLLER_URL.format(orgnr=orgnr))
    async def fetch_financials(self, client: httpx.AsyncClient, orgnr: str):
        return await self._fetch(client, self.REGNSKAP_URL.format(orgnr=orgnr))
