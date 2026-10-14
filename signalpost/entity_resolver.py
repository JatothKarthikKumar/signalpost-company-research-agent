import re
from typing import Optional

def normalize_org_number(raw_input: str | int) -> str:
    return re.sub(r"[^0-9]", "", str(raw_input))

def validate_norwegian_orgnr(orgnr: str) -> bool:
    if len(orgnr) != 9 or not orgnr.isdigit():
        return False
    weights = [3, 2, 7, 6, 5, 4, 3, 2]
    remainder = sum(int(d) * w for d, w in zip(orgnr[:8], weights)) % 11
    control = 0 if remainder == 0 else 11 - remainder
    return control != 10 and control == int(orgnr[8])

def resolve_entity_input(raw_input: str | int) -> tuple[Optional[str], Optional[str]]:
    normalized = normalize_org_number(raw_input)
    if not normalized:
        return None, "Empty or non-numeric organization identifier provided."
    if len(normalized) != 9:
        return None, f"Invalid length: Norwegian org numbers must be 9 digits (received '{normalized}')."
    if not validate_norwegian_orgnr(normalized):
        return None, f"Modulus 11 checksum failure for organization number '{normalized}'."
    return normalized, None
