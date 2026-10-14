import json, sqlite3
from datetime import datetime, timezone
from typing import Any
from .schemas import ChangeRecord, Fact, ResultStatus

class ResearchStorage:
    def __init__(self, db_path: str = "signalpost_research.db"):
        self.db_path = db_path
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS company_profiles (org_number TEXT PRIMARY KEY, legal_name TEXT, status TEXT NOT NULL, first_researched_at TEXT NOT NULL, last_updated_at TEXT NOT NULL, profile_json TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS company_facts (fact_id TEXT PRIMARY KEY, org_number TEXT NOT NULL, category TEXT NOT NULL, field_name TEXT NOT NULL, fact_value_json TEXT NOT NULL, status TEXT NOT NULL, source_url TEXT NOT NULL, retrieval_timestamp TEXT NOT NULL, publication_date TEXT, reporting_period TEXT, source_name TEXT NOT NULL, verification_status TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS fact_change_log (change_id INTEGER PRIMARY KEY AUTOINCREMENT, org_number TEXT NOT NULL, field_name TEXT NOT NULL, old_value_json TEXT, new_value_json TEXT, change_type TEXT NOT NULL, detected_at TEXT NOT NULL)")
    def _connect(self):
        db = sqlite3.connect(self.db_path); db.row_factory = sqlite3.Row; return db
    def get_existing_facts(self, orgnr: str) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute("SELECT field_name, fact_value_json FROM company_facts WHERE org_number=?", (orgnr,)).fetchall()
        result = {}
        for row in rows:
            try: result[row["field_name"]] = json.loads(row["fact_value_json"])
            except ValueError: result[row["field_name"]] = row["fact_value_json"]
        return result
    def persist_profile_and_facts(self, orgnr: str, legal_name: str | None, status: ResultStatus, profile_data: dict, facts: list[Fact]) -> list[ChangeRecord]:
        now = datetime.now(timezone.utc).isoformat(); existing = self.get_existing_facts(orgnr); changes = []
        with self._connect() as db:
            row = db.execute("SELECT first_researched_at FROM company_profiles WHERE org_number=?", (orgnr,)).fetchone()
            first = row[0] if row else now
            db.execute("INSERT INTO company_profiles VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(org_number) DO UPDATE SET legal_name=excluded.legal_name,status=excluded.status,last_updated_at=excluded.last_updated_at,profile_json=excluded.profile_json", (orgnr, legal_name, status.value, first, now, json.dumps(profile_data, ensure_ascii=False, default=str)))
            for fact in facts:
                value_json = json.dumps(fact.value, sort_keys=True, ensure_ascii=False, default=str)
                if fact.field_name in existing and json.dumps(existing[fact.field_name], sort_keys=True, ensure_ascii=False, default=str) != value_json:
                    change = ChangeRecord(field_name=fact.field_name, old_value=existing[fact.field_name], new_value=fact.value, detected_at=now, change_type="updated")
                    changes.append(change)
                    db.execute("INSERT INTO fact_change_log (org_number,field_name,old_value_json,new_value_json,change_type,detected_at) VALUES (?,?,?,?,?,?)", (orgnr, fact.field_name, json.dumps(existing[fact.field_name]), value_json, "updated", now))
                elif fact.field_name not in existing:
                    changes.append(ChangeRecord(field_name=fact.field_name, old_value=None, new_value=fact.value, detected_at=now, change_type="added"))
                ev = fact.evidence
                db.execute("INSERT INTO company_facts VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fact_id) DO UPDATE SET fact_value_json=excluded.fact_value_json,status=excluded.status,retrieval_timestamp=excluded.retrieval_timestamp,publication_date=excluded.publication_date,reporting_period=excluded.reporting_period,verification_status=excluded.verification_status", (fact.fact_id, orgnr, fact.category, fact.field_name, value_json, fact.status.value, ev.source_url if ev else "", ev.retrieval_timestamp if ev else now, ev.publication_date if ev else None, ev.reporting_period if ev else None, ev.source_name if ev else "System", ev.verification_status if ev else "unverified"))
        return changes
