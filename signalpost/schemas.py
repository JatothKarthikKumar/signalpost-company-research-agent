from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field

class ResultStatus(str, Enum):
    AVAILABLE = "available"
    NOT_AVAILABLE = "not_available"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"
    AMBIGUOUS = "ambiguous"
    FAILED = "failed"

class Evidence(BaseModel):
    source_url: str
    retrieval_timestamp: str
    publication_date: Optional[str] = None
    reporting_period: Optional[str] = None
    source_name: str
    verification_status: str = "verified"
    metadata: dict[str, Any] = Field(default_factory=dict)

class Fact(BaseModel):
    fact_id: str
    category: str
    field_name: str
    value: Any
    status: ResultStatus = ResultStatus.AVAILABLE
    evidence: Optional[Evidence] = None

class ChangeRecord(BaseModel):
    field_name: str
    old_value: Any = None
    new_value: Any = None
    detected_at: str
    change_type: str

class CompanyIdentity(BaseModel):
    org_number: str
    legal_name: Optional[str] = None
    company_type: Optional[str] = None
    registration_status: Optional[str] = None
    registered_address: Optional[dict[str, Any]] = None
    industry_classification: Optional[dict[str, Any]] = None
    business_activity_description: Optional[str] = None

class FinancialSummary(BaseModel):
    reporting_year: Optional[int] = None
    revenue_nok: Optional[float] = None
    operating_profit_nok: Optional[float] = None
    net_result_nok: Optional[float] = None
    total_assets_nok: Optional[float] = None
    filing_date: Optional[str] = None

class PersonRole(BaseModel):
    name: str
    role_description: str
    birth_year: Optional[int] = None

class JobPosting(BaseModel):
    title: str
    employer: str
    location: Optional[str] = None
    posted_date: Optional[str] = None
    job_url: str
    status: str = "active"

class CompanyProfile(BaseModel):
    org_number: str
    status: ResultStatus
    identity: Optional[CompanyIdentity] = None
    financials: Optional[FinancialSummary] = None
    people: list[PersonRole] = Field(default_factory=list)
    website_url: Optional[str] = None
    business_summary: Optional[str] = None
    job_vacancies: list[JobPosting] = Field(default_factory=list)
    changes_detected: list[ChangeRecord] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    synthesis_narrative: str = ""
    error_message: Optional[str] = None

class CompanyResultEnvelope(BaseModel):
    input_orgnr: str
    resolved_orgnr: Optional[str] = None
    status: ResultStatus
    execution_time_ms: float
    data: Optional[CompanyProfile] = None
    error: Optional[str] = None
