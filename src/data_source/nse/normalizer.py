from datetime import date
from .models import Company


INDICES_MAP = {
   "LARGE": ["NIFTY 50", "NIFTY NEXT 50"],
   "MID": ["NIFTY MIDCAP 150"],
   "SMALL": ["NIFTY SMALLCAP 250"]
}

def derive_market_cap_category(symbol_indices: list[str]) -> str:
    for category, indices in INDICES_MAP.items():
        for idx in indices:
            if idx in symbol_indices:
                return category
    return "Unknown"

def normalize(raw: dict, as_of_date: date | None = None) -> Company:
    as_of_date = as_of_date or date.today()

    info = raw.get("info", {})
    metadata = raw.get("metadata", {})
    industry_info = raw.get("industryInfo", {})
    security_info = raw.get("securityInfo", {})
    indices = metadata.get("pdSectorIndAll", [])

    return Company(
        ticker=info["symbol"],
        company_name=info["companyName"],
        isin=info["isin"],
        is_fno=info["isFNOSec"],
        is_top_10=info["isTop10"],
        series=metadata["series"],
        listing_date=metadata["listingDate"],
        macro_sector=industry_info["macro"],
        sector=industry_info["sector"],
        industry=industry_info["industry"],
        basic_industry=industry_info["basicIndustry"],
        sector_pe=metadata["pdSectorPe"],
        symbol_pe=metadata["pdSymbolPe"],
        market_cap_category=derive_market_cap_category(indices),
        face_value=security_info["faceValue"],
        indices=indices,
        as_of_date=as_of_date
    )