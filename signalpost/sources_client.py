import httpx
from .schemas import JobPosting, ResultStatus

class SourcesClient:
    NAV_API_URL = "https://arbeidsplassen.nav.no/public-feed/api/v1/ads"
    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self.headers = {"User-Agent": "Signalpost-Company-Agent/1.0.0", "Accept": "application/json"}
    async def fetch_job_vacancies(self, client: httpx.AsyncClient, orgnr: str):
        url = f"{self.NAV_API_URL}?orgnr={orgnr}&size=10"
        try:
            response = await client.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code in (403, 429): return ResultStatus.BLOCKED, [], url
            if response.status_code == 404: return ResultStatus.NOT_AVAILABLE, [], url
            if response.status_code != 200: return ResultStatus.FAILED, [], url
            data = response.json()
            ads = data.get("content", []) if isinstance(data, dict) else []
            jobs = []
            for ad in ads:
                locations = ad.get("locationList") or []
                employer = ad.get("businessName") or (ad.get("employer") or {}).get("name") or "Unknown"
                jobs.append(JobPosting(title=ad.get("title", "Unknown Role"), employer=employer,
                    location=locations[0].get("city") if locations else None,
                    posted_date=ad.get("published"), job_url=ad.get("link") or f"https://arbeidsplassen.nav.no/stillinger/stilling/{ad.get('uuid', '')}"))
            return (ResultStatus.AVAILABLE if jobs else ResultStatus.NOT_AVAILABLE), jobs, url
        except (httpx.RequestError, ValueError, TypeError):
            return ResultStatus.FAILED, [], url
