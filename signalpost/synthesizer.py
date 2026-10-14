from .schemas import CompanyProfile, ResultStatus

class ProfileSynthesizer:
    @staticmethod
    def build_narrative(profile: CompanyProfile) -> str:
        if profile.status != ResultStatus.AVAILABLE or not profile.identity:
            return f"Company research concluded with status '{profile.status.value}'. {profile.error_message or 'No legal entity information accessible.'}"
        ident = profile.identity
        text = f"{ident.legal_name or 'The company'} (Orgnr: {ident.org_number}) is a registered Norwegian {ident.company_type or 'entity'}."
        if ident.business_activity_description: text += f" Declared activity: {ident.business_activity_description.strip()}"
        if profile.financials and profile.financials.revenue_nok is not None:
            f = profile.financials
            text += f" Financial summary ({f.reporting_year or 'latest period'}): revenue {f.revenue_nok:,.0f} NOK."
        else: text += " Verified annual accounts were not available in the retrieved response."
        text += f" Registered management roles found: {len(profile.people)}. Active public vacancies found: {len(profile.job_vacancies)}."
        return text
