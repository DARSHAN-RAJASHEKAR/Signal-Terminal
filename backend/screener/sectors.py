"""Sector taxonomy for the Stocks Screener.

NSE's index constituent files only carry ~20 broad "Industry" buckets
(e.g. "Capital Goods" covers bearings, defence, transformers, pumps...).
The screener exposes a finer 60-sector taxonomy, so each company is mapped
in two steps:

  1. INDUSTRY_DEFAULTS  — NSE industry -> the most common screener sector
  2. SYMBOL_OVERRIDES   — per-company corrections where the default is wrong

Used only by build_universe.py; the server reads the already-resolved
sector from data/universe.json. Edit the overrides and re-run the build
script to reclassify a company.
"""

SECTORS = [
    "Agriculture & Allied Industries", "Apparel and Clothes", "Auto Ancillary",
    "Auto Manufacturers", "Auto Retail", "Aviation", "Banks", "Batteries",
    "Bearings", "Building Materials", "Cement", "Ceramic Products", "Chemicals",
    "Defence", "Distributors", "E-Commerce/App based Aggregator", "Education",
    "Electrical Appliances", "Electrical Equipment", "Electronic Manufacturers",
    "Engineering", "Financial Services", "FMCG", "Food & Beverages", "Footwear",
    "Furniture", "Gas Distribution", "Healthcare", "Hospitality", "Infrastructure",
    "Information Technology", "Insurance", "Jewellery", "Leather", "Logistics",
    "Maritime Industries", "Media & Entertainment", "Metals & Mining", "Oil",
    "Packaging", "Paints", "Paper", "Pharmaceuticals", "Plastic and Polymers",
    "Power", "Professional Services", "Railways", "Rating Agencies", "Real Estate",
    "Real Estate Investment Trusts", "Refractories", "Retail Chains",
    "Rubber Products", "Sugar", "Telecom", "Telecom Equipment & Infra Services",
    "Textiles", "Tyre", "Waste Management", "Water Distribution",
]

INDUSTRY_DEFAULTS = {
    "Automobile and Auto Components": "Auto Ancillary",
    "Capital Goods": "Engineering",
    "Chemicals": "Chemicals",
    "Construction": "Infrastructure",
    "Construction Materials": "Cement",
    "Consumer Durables": "Electrical Appliances",
    "Consumer Services": "Retail Chains",
    "Diversified": "Chemicals",
    "Fast Moving Consumer Goods": "FMCG",
    "Financial Services": "Financial Services",
    "Forest Materials": "Paper",
    "Healthcare": "Pharmaceuticals",
    "Information Technology": "Information Technology",
    "Media Entertainment & Publication": "Media & Entertainment",
    "Metals & Mining": "Metals & Mining",
    "Oil Gas & Consumable Fuels": "Oil",
    "Power": "Power",
    "Realty": "Real Estate",
    "Services": "Logistics",
    "Telecommunication": "Telecom",
    "Textiles": "Textiles",
    "Utilities": "Water Distribution",
}


def _group(sector, symbols):
    return {s: sector for s in symbols.split()}


SYMBOL_OVERRIDES = {
    # ── Capital Goods (default: Engineering) ──────────────────────────
    **_group("Defence", "AEQUS APOLLO ASTRAMICRO BEML BDL BEL DATAPATTNS GRSE HAL "
                        "MAZDOCK MIDHANI PTCIL PARAS SIGMAADV UNIMECH ZENTEC"),
    **_group("Electrical Equipment", "ABB APARINDS ATLANTAELE BHEL BORORENEW CGPOWER "
                                     "DIACABS EMMVEE FINCABLES UTLSOLAR GVT&D GENUSPOWER "
                                     "POWERINDIA HONAUT INOXWIND KEI POLYCAB POWERICA "
                                     "PRECWIRE PREMIERENE QPOWER RRKABEL SCHNEIDER SHILCTECH "
                                     "ENRIN SIEMENS SKIPPER SUZLON TDPOWERSYS TARIL VIKRAMSOLR "
                                     "VOLTAMP WAAREEENER WEBELSOLAR"),
    **_group("Electronic Manufacturers", "CPPLUS AVALON CENTUM KAYNES SYRMA "
                                         "AMBER DIXON PGEL"),
    **_group("Metals & Mining", "CMRGREEN ELECTCAST GALLANTT GPIL JAYNECOIND JINDALSAW "
                                "RATNAMANI SHYAMMETL SUNFLAG USHAMART WELCORP "
                                "COALINDIA BHARATCOAL"),
    **_group("Building Materials", "APLAPOLLO STYLAMIND"),
    **_group("Plastic and Polymers", "ASTRAL FINPIPE GRWRHITECH SUPREMEIND TIMETECHNO "
                                     "SPLPETRO CELLO SHAILY RESPONIND SAFARI VIPIND"),
    **_group("Auto Manufacturers", "ASHOKLEY ESCORTS SMLMAH TMCV "
                                   "ATHERENERG BAJAJ-AUTO EICHERMOT FORCEMOT HEROMOTOCO "
                                   "HYUNDAI M&M MARUTI OLAELEC OLECTRA TVSMOTOR TMPV"),
    **_group("Auto Ancillary", "HAPPYFORGE SUBROS"),
    **_group("Batteries", "HBLENGINE ARE&M EXIDEIND"),
    **_group("Bearings", "TIMKEN"),
    **_group("Railways", "JWL TEXRAIL TITAGARH IRCON RITES RVNL IRCTC"),
    **_group("Refractories", "RHIM VESUVIUS"),
    **_group("Packaging", "EPL"),
    **_group("Maritime Industries", "COCHINSHIP ADANIPORTS GPPL JSWINFRA GESHIP SCI "
                                    "SHREEJISPG KMEW"),
    **_group("Electrical Appliances", "SURYAROSNI"),
    **_group("Infrastructure", "TRANSRAILL"),
    **_group("Power", "WAAREERTL"),

    # ── Financial Services ────────────────────────────────────────────
    **_group("Banks", "AUBANK AXISBANK BANDHANBNK BANKBARODA BANKINDIA MAHABANK CSBBANK "
                      "CANBK CENTRALBK CUB DCBBANK EQUITASBNK FEDERALBNK HDFCBANK ICICIBANK "
                      "IDBI IDFCFIRSTB INDIANB IOB INDUSINDBK J&KBANK JSFB KTKBANK "
                      "KARURVYSYA KOTAKBANK PNB RBLBANK SOUTHBANK SBIN TMB UCOBANK "
                      "UJJIVANSFB UNIONBANK YESBANK"),
    **_group("Insurance", "CANHLIFE GICRE HDFCLIFE ICICILIFE ICICIGI LICI NIVABUPA SBILIFE "
                          "STARHEALTH NIACL MFSL POLICYBZR"),
    **_group("Rating Agencies", "CRISIL"),

    # ── Healthcare (default: Pharmaceuticals) ─────────────────────────
    **_group("Healthcare", "APOLLOHOSP ASTERDM LALPATHLAB FORTIS MEDANTA HCG KIMS MAXHEALTH "
                           "METROPOLIS NH NEPHROPLUS PARKHOSPS RAINBOW THYROCARE VIJAYA "
                           "YATHARTH POLYMED INDGN JSLL"),
    **_group("Pharmaceuticals", "SUDEEPPHRM"),

    # ── Auto (default: Auto Ancillary) ────────────────────────────────
    **_group("Tyre", "APOLLOTYRE BALKRISIND CEATLTD JKTYRE MRF"),

    # ── FMCG ──────────────────────────────────────────────────────────
    **_group("Food & Beverages", "ABDL BRITANNIA CCL HERITGFOOD IGLSPIRITS KRBL KWIL LTFOODS "
                                 "BECTORFOOD NESTLEIND PATANJALI PICCADIL RADICO TATACONSUM "
                                 "TI UBL UNITDSPR VBL AWL GOKULAGRO GAEL MANORAMA "
                                 "DEVYANI JUBLFOOD RBA SAPPHIRE WESTLIFE"),
    **_group("Sugar", "BALRAMCHIN RENUKA EIDPARRY"),
    **_group("Agriculture & Allied Industries", "AVANTIFEED GODREJAGRO KSCL "
                                                "CHAMBLFERT COROMANDEL DEEPAKFERT FACT GNFC "
                                                "GSFC MBAPL NFL PIIND PARADEEP RALLIS RCF "
                                                "SHARDACROP SUMICHEM UPL"),
    **_group("Chemicals", "INDIAGLYCO"),

    # ── Consumer Services (default: Retail Chains) ────────────────────
    **_group("Apparel and Clothes", "ABLBL ARVINDFASN MANYAVAR "
                                    "GOKEX KITEX PDSL PAGEIND PGIL RAYMONDLSL"),
    **_group("E-Commerce/App based Aggregator", "FIRSTCRY CARTRADE ETERNAL NYKAA INDIAMART "
                                                "NAUKRI JUSTDIAL IXIGO MEESHO SWIGGY URBANCO "
                                                "TBOTEK BLACKBUCK"),
    **_group("Hospitality", "CHALET EIHOTEL ITCHOTELS INDHOTEL THELEELA LEMONTREE SAMHI "
                            "THOMASCOOK"),
    **_group("Education", "PWL"),
    **_group("Distributors", "ENTERO MMTC MSTCLTD REDINGTON"),
    **_group("Professional Services", "BLS CMSINFO CMPDI FSL IGIL QUESS ECLERX"),

    # ── Consumer Durables (default: Electrical Appliances) ────────────
    **_group("Paints", "ASIANPAINT BERGEPAINT INDIGOPNTS KANSAINER"),
    **_group("Footwear", "BATAINDIA CAMPUS RELAXO"),
    **_group("Jewellery", "BLUESTONE GOLDIAM KALYANKJIL PNGJL PCJEWELLER SKYGOLD SENCO "
                          "THANGAMAYL TITAN VAIBHAVGBL TIMEX"),
    **_group("Ceramic Products", "CERA KAJARIACER"),
    **_group("Furniture", "SFL WAKEFIT"),

    # ── Services (default: Logistics) ─────────────────────────────────
    **_group("Aviation", "INDIGO GMRAIRPORT"),
    **_group("Real Estate", "WEWORK"),

    # ── Construction (default: Infrastructure) ────────────────────────
    **_group("Engineering", "ENGINERSIN"),

    # ── Realty (default: Real Estate) ─────────────────────────────────
    **_group("Real Estate Investment Trusts", "BAGMANE BIRET EMBASSY"),

    # ── Oil & Gas (default: Oil) ──────────────────────────────────────
    **_group("Gas Distribution", "ATGL GAIL IGL MGL PETRONET"),

    # ── Telecom (default: Telecom) ────────────────────────────────────
    **_group("Telecom Equipment & Infra Services", "HFCL ITI INDUSTOWER STLTECH TEJASNET"),

    # ── Utilities (default: Water Distribution) ───────────────────────
    **_group("Waste Management", "REFEX"),
}


def resolve_sector(symbol: str, nse_industry: str) -> str:
    sector = SYMBOL_OVERRIDES.get(symbol) or INDUSTRY_DEFAULTS.get(nse_industry)
    if sector is None:
        raise KeyError(f"No sector mapping for {symbol} (NSE industry: {nse_industry!r})")
    return sector


# Every override must point at a real taxonomy entry — catches typos at import.
_unknown = {v for v in list(SYMBOL_OVERRIDES.values()) + list(INDUSTRY_DEFAULTS.values())} - set(SECTORS)
assert not _unknown, f"Unknown sectors in mapping: {_unknown}"
assert len(SECTORS) == 60, len(SECTORS)
