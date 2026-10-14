import asyncio, json, sys, time
from typing import Optional
import click, httpx
from rich.console import Console
from .brreg_client import BrregClient
from .entity_resolver import resolve_entity_input
from .schemas import (CompanyIdentity, CompanyProfile, CompanyResultEnvelope, Evidence, Fact, FinancialSummary, PersonRole, ResultStatus)
from .sources_client import SourcesClient
from .storage import ResearchStorage
from .synthesizer import ProfileSynthesizer

console = Console(stderr=True)

class SignalpostAgent:
    def __init__(self, db_path="signalpost_research.db", concurrency=8):
        self.storage = ResearchStorage(db_path)
        self.brreg = BrregClient(); self.sources = SourcesClient(); self.semaphore = asyncio.Semaphore(concurrency)
    @staticmethod
    def now_iso():
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
    async def research_single(self, raw_input, client):
        started = time.perf_counter(); orgnr, error = resolve_entity_input(raw_input)
        if not orgnr:
            status = ResultStatus.AMBIGUOUS if "checksum" in (error or "").lower() else ResultStatus.FAILED
            return CompanyResultEnvelope(input_orgnr=str(raw_input), status=status, execution_time_ms=(time.perf_counter()-started)*1000, error=error)
        async with self.semaphore:
            entity_status, entity, entity_url = await self.brreg.fetch_entity(client, orgnr)
            if entity_status != ResultStatus.AVAILABLE or not entity:
                profile = CompanyProfile(org_number=orgnr, status=entity_status, error_message=f"Entity lookup returned status: {entity_status.value}")
                return CompanyResultEnvelope(input_orgnr=str(raw_input), resolved_orgnr=orgnr, status=entity_status, execution_time_ms=(time.perf_counter()-started)*1000, data=profile)
            roles_task = self.brreg.fetch_roles(client, orgnr)
            fin_task = self.brreg.fetch_financials(client, orgnr)
            jobs_task = self.sources.fetch_job_vacancies(client, orgnr)
            (roles_status, roles, roles_url), (fin_status, fin, fin_url), (jobs_status, jobs, jobs_url) = await asyncio.gather(roles_task, fin_task, jobs_task)
            now = self.now_iso(); name = entity.get("navn"); org_type = (entity.get("organisasjonsform") or {}).get("kode")
            address = entity.get("forretningsadresse") or entity.get("postadresse"); industry = entity.get("naeringskode1")
            activity = (entity.get("aktivitet") or [None])[0]; website = entity.get("hjemmeside")
            evidence = Evidence(source_url=entity_url, retrieval_timestamp=now, publication_date=entity.get("registreringsdatoEnhetsregisteret"), source_name="Brønnøysund Enhetsregisteret")
            facts = [Fact(fact_id=f"{orgnr}_legal_name", category="identity", field_name="legal_name", value=name, evidence=evidence), Fact(fact_id=f"{orgnr}_company_type", category="identity", field_name="company_type", value=org_type, evidence=evidence)]
            people = []
            if roles_status == ResultStatus.AVAILABLE and isinstance(roles, dict):
                for group in roles.get("rollegrupper", []):
                    for role in group.get("roller", []):
                        person = role.get("person") or {}; pname = person.get("navn") or {}
                        full_name = f"{pname.get('fornavn','')} {pname.get('etternavn','')}".strip() or "Name not public"
                        people.append(PersonRole(name=full_name, role_description=(role.get("type") or {}).get("beskrivelse") or (group.get("type") or {}).get("beskrivelse") or "Role"))
            financials = None
            if fin_status == ResultStatus.AVAILABLE and fin:
                accounts = fin if isinstance(fin, list) else [fin]
                if accounts:
                    latest = accounts[0]; period = latest.get("regnskapsperiode") or {}; end = period.get("tilDato")
                    result = latest.get("resultatregnskapResultat") or {}; income = result.get("driftsinntekter") or {}; balance = latest.get("balanse") or {}
                    revenue = income.get("salgsinntekter") or income.get("sumDriftsinntekter")
                    financials = FinancialSummary(reporting_year=int(end[:4]) if end else None, revenue_nok=float(revenue) if revenue is not None else None, operating_profit_nok=float((result.get("driftsresultat") or {}).get("driftsresultat")) if (result.get("driftsresultat") or {}).get("driftsresultat") is not None else None, net_result_nok=float(result.get("aarsresultat")) if result.get("aarsresultat") is not None else None, total_assets_nok=float(balance.get("sumEiendeler")) if balance.get("sumEiendeler") is not None else None, filing_date=latest.get("avleveringstidspunkt"))
            profile = CompanyProfile(org_number=orgnr, status=ResultStatus.AVAILABLE, identity=CompanyIdentity(org_number=orgnr, legal_name=name, company_type=org_type, registration_status="inactive" if entity.get("slettedato") else "active", registered_address=address, industry_classification=industry, business_activity_description=activity), financials=financials, people=people, website_url=website, job_vacancies=jobs, facts=facts)
            profile.changes_detected = self.storage.persist_profile_and_facts(orgnr, name, ResultStatus.AVAILABLE, profile.model_dump(mode="json"), facts)
            profile.synthesis_narrative = ProfileSynthesizer.build_narrative(profile)
            return CompanyResultEnvelope(input_orgnr=str(raw_input), resolved_orgnr=orgnr, status=ResultStatus.AVAILABLE, execution_time_ms=(time.perf_counter()-started)*1000, data=profile)
    async def process_batch(self, org_numbers):
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await asyncio.gather(*(self.research_single(item, client) for item in org_numbers))

@click.command()
@click.option("--input", "input_file", type=click.Path(exists=True), help="File with one organization number per line or a JSON array.")
@click.option("--orgnr", type=str, help="Single Norwegian organization number.")
@click.option("--output", "output_file", type=click.Path(), help="Output JSON file.")
@click.option("--concurrency", type=int, default=8)
@click.option("--db", type=str, default="signalpost_research.db")
def main(input_file: Optional[str], orgnr: Optional[str], output_file: Optional[str], concurrency: int, db: str):
    inputs = []
    if orgnr: inputs = [orgnr]
    elif input_file:
        content = open(input_file, encoding="utf-8").read().strip()
        try:
            data = json.loads(content) if content.startswith("[") else None
            inputs = [str(item.get("orgnr", item) if isinstance(item, dict) else item) for item in data] if isinstance(data, list) else [line.strip() for line in content.splitlines() if line.strip()]
        except json.JSONDecodeError: inputs = [line.strip() for line in content.splitlines() if line.strip()]
    elif not sys.stdin.isatty(): inputs = [line.strip() for line in sys.stdin.read().splitlines() if line.strip()]
    if not inputs: raise click.ClickException("No organization numbers provided. Use --orgnr or --input.")
    results = asyncio.run(SignalpostAgent(db, concurrency).process_batch(inputs))
    output = json.dumps([r.model_dump(mode="json") for r in results], indent=2, ensure_ascii=False)
    if output_file: open(output_file, "w", encoding="utf-8").write(output)
    else: print(output)

if __name__ == "__main__": main()
