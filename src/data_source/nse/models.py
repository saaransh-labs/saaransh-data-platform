from dataclasses import dataclass, field
from datetime import date

@dataclass
class Company:
    ticker: str
    company_name: str
    isin: str
    is_fno: bool
    is_top_10: bool
    series: str
    listing_date: str
    macro_sector: str
    sector: str
    industry: str
    basic_industry: str
    sector_pe: float
    symbol_pe: float
    market_cap_category: str
    face_value: float
    indices: list[str] = field(default_factory=list)
    as_of_date: date = field(default_factory=date.today)