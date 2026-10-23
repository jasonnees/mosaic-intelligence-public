"""
LEGACY compatibility catalog — not used by Market Risk Explorer.
Active definitions live in risk_catalog.py. Preset signals are historical only.
Ported from the NYT editorial JSX prototype.

Each indicator: [name, target_range, bullish, bearish, advisory, signal(-1/0/1)]
signal: 1=bullish, -1=bearish, 0=neutral/in-range
"""

# Palette (NYT editorial)
P = {
    "bg": "#faf9f6", "card": "#ffffff", "card2": "#f5f3ef",
    "rule": "#d4cfc7", "ruleLight": "#e8e4dd",
    "ink": "#1a1a1a", "inkMed": "#3d3d3d", "inkLight": "#6b6b6b", "inkFaint": "#999891",
    "accent": "#c41200", "accentLight": "#fff0ee",
    "green": "#15803d", "greenBg": "#f0fdf4",
    "red": "#b91c1c", "redBg": "#fef2f2",
    "amber": "#92400e", "amberBg": "#fffbeb",
    "blue": "#1e40af", "blueBg": "#eff6ff",
}

# Font stacks
FONTS = {
    "serif": "'Playfair Display', 'Georgia', 'Times New Roman', serif",
    "body": "'Source Serif 4', 'Georgia', 'Times New Roman', serif",
    "data": "'IBM Plex Mono', 'SF Mono', 'Consolas', monospace",
    "ui": "'IBM Plex Sans', 'Helvetica Neue', -apple-system, sans-serif",
}

FONT_IMPORT = "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Source+Serif+4:ital,wght@0,400;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap"

# ─────────────────────────────────────────────────────────────────────────────
# 300 INDICATOR CATEGORIES
# [name, target_range, bullish, bearish, advisory, signal]
# ─────────────────────────────────────────────────────────────────────────────

CAT = {
    "T1_RATES": {"t": 1, "l": "Interest rates & monetary policy", "m": "rates", "d": [
        ["Federal Funds Rate", "0.25–4.0%", "Rate cuts or dovish guidance (<3.0%)", "Aggressive hikes (>5.5%)", "Below 2.5% = add duration; Above 4.5% = cut growth", -1],
        ["CME FedWatch Probabilities", "<70% prob for 50+ bps", "High prob of cuts (>80%)", "High prob of hikes (>80%)", "Position ahead of FOMC meetings", 0],
        ["2Y–10Y Treasury Spread", "+20 to +190 bps", "Steepening from inversion (>+25 bps)", "Inversion (<0 bps) for 3+ months", "Inversion = cut cyclical, add defensive", 1],
        ["3M–10Y Treasury Spread", "+25 to +245 bps", "Steepening trend (>+150 bps)", "Sustained inversion (<0 bps)", "Confirm with 2Y–10Y for recession signal", 0],
        ["5Y5Y Forward Inflation", "2.0–2.5%", "Stable around 2.25%", ">3.0% or <1.5%", "Above 2.5% = cut duration; Below 2.0% = add TIPS", 0],
        ["10Y TIPS Breakeven", "1.9–2.4%", "Rising toward 2.5%", ">3.0% or <1.5%", "High = favor TIPS over nominal", 0],
        ["5Y TIPS Breakeven", "1.6–2.4%", "Stable in target range", "Rapid moves outside range", "Medium-term inflation hedge", 0],
        ["2Y TIPS Breakeven", "1.5–3.5%", "Declining from elevated", ">4.0% inflation spiral", "Short-term inflation decisions", 1],
        ["Real Yield Curve (TIPS)", "0.3–1.9%", "Positive and rising", "Deeply negative (<-1.0%)", "Negative real yields = favor real assets", 0],
        ["SOFR", "Fed Funds ±10 bps", "Stable near Fed Funds", "Deviation >25 bps", "Elevated = cut financial sector", 0],
        ["Atlanta Fed Probability Tracker", "Aligned with guidance", "Converging with Fed", "Large divergence from dots", "Tactical rate positioning", 0],
        ["30-Day Fed Funds Futures", "Fed Funds ±25 bps", "Pricing in cuts", "Pricing aggressive hikes", "Position duration on expectations", 1],
        ["Eurodollar Term Structure", "Upward sloping", "Steepening expectations", "Inverted curve", "Long-term rate positioning", 0],
        ["Fed Dot Plot", "Gradual changes Q/Q", "Dots moving lower", "Hawkish revision", "Position on median dot trajectory", 1],
        ["Treasury Bill-Bond Spreads", "Positive and stable", "Widening spreads", "Compression or inversion", "Compressed = cut duration risk", 0],
    ]},
    "T1_CREDIT": {"t": 1, "l": "Credit markets & default risk", "m": "credit", "d": [
        ["CDX NA Investment Grade", "100–170 bps", "<75 bps declining", ">200 bps or rapid widening", "Above 170 = cut credit exposure", 1],
        ["CDX High Yield", "360–640 bps", "<400 bps tightening", ">800 bps or rapid widening", "Above 640 = avoid HY bonds", 1],
        ["iTraxx Europe", "50–120 bps", "<80 bps", ">150 bps", "European credit allocation", 0],
        ["EM CDX", "200–400 bps", "<300 bps stable", ">500 bps spiking", "Above 400 = cut EM exposure", 0],
        ["VIX Index", "14–23", "<15 complacency watch", ">30 fear/crisis", ">25 = add hedging; <14 = consider protection", 1],
        ["MOVE Index", "80–120", "<100 declining", ">150 or spike", "Elevated = cut bond duration", 1],
        ["High Yield Spreads", "360–640 bps", "Tightening <400 bps", "Widening >800 bps", "Wide = avoid HY allocation", 1],
        ["Bank CDS Spreads", "50–150 bps", "<100 bps stable", ">200 bps widening", "Rising = cut financial weights", 0],
        ["Sovereign CDS Spreads", "<100 bps (DM)", "Stable or tightening", ">200 bps spiking", "Monitor country-specific risks", 0],
        ["Corporate Issuance Volume", "$100–200B monthly", "Strong, consistent", "Drought (<$50B)", "Low issuance = credit stress signal", 1],
    ]},
    "T1_EQUITY": {"t": 1, "l": "Equity market indicators", "m": "equity", "d": [
        ["S&P 500", "Above 200-day MA", "New highs with volume", "20%+ correction", "Below 200d MA = cut equity", 1],
        ["Put/Call Ratio", "0.7–1.1", ">1.2 excessive bearishness", "<0.5 excessive bullishness", "Extremes = contrarian positioning", 0],
        ["Equity Risk Premium", "2–4%", ">4% attractive valuations", "<2% expensive", "Low ERP = cut equity overweights", 0],
        ["Forward P/E", "15–20x", "<18x with growth", ">25x or declining earnings", "High P/E = quality and value styles", -1],
        ["Margin Debt", "2–3% of mkt cap", "Moderate with growth", ">4% leverage risk", "High margin = cut risk assets", 0],
        ["Insider Activity", "Buy/sell >0.3", "Buying >40%", "Selling >80%", "Follow insider sentiment for sectors", 0],
        ["Buyback Announcements", "$200–400B Q", "Strong activity", "Sharp decline", "Declining = growth headwinds", 1],
        ["IPO Volume", "30–60 per month", "Quality with strong perf", "Drought or poor perf", "Low = declining risk appetite", 0],
        ["Sector Rotation", "Balanced", "Cyclicals outperforming", "Flight to defensives", "Defensive rotation = cut cyclical", -1],
        ["Market Concentration", "20–30%", "Broadening leadership", ">35% concentration", "High concentration = diversify", -1],
    ]},
    "T1_GROWTH": {"t": 1, "l": "Economic growth", "m": "gdp", "d": [
        ["GDP Growth Rate", "1.1–3.5% real", ">2.5% with momentum", "<1% or negative 2Q", "Below 1.5% = add defensive", 1],
        ["Conference Board L.E.I.", "Positive 3mo change", "6-month increasing", "6+ months decline", "6mo decline = major risk-off", 0],
        ["Nonfarm Payrolls", "150K–300K", ">250K with wage growth", "<100K or negative", "Weak jobs = dovish pivot potential", 0],
        ["Unemployment Rate", "4.0–6.0%", "Stable low end", "Rising >0.5% in 3mo", "Sahm trigger = recession positioning", 0],
        ["Initial Claims (4-wk)", "240K–400K", "<250K declining", ">400K or 20%+ increase", "Rising = leading recession indicator", -1],
        ["Industrial Production", "1–3% YoY", ">2% with momentum", "Negative YoY", "Declining = cut cyclical sectors", 0],
        ["Capacity Utilization", "75.7–78.7%", "Rising toward 80%", "<75% declining", "Low utilization = deflationary", 0],
        ["ISM Manufacturing", "50–55", ">53 rising", "<50 for 2+ months", "Below 50 = cut manufacturing", -1],
        ["ISM Services", "52–58", ">55 stable", "<50 contraction", "Services <50 = major concern", 0],
        ["Consumer Confidence", "100–130", ">120 rising", "<90 or sharp decline", "Low = cut consumer discretionary", -1],
    ]},
    "T1_INFLATION": {"t": 1, "l": "Inflation & consumer activity", "m": "consumer", "d": [
        ["C.P.I. (year-over-year)", "2.0–2.5%", "Declining toward 2%", ">4% or reaccelerating", "Above 3% = cut long duration", 0],
        ["Core C.P.I.", "2.0–2.7%", "Steady decline toward 2%", ">3.5% or rising", "Sticky core = Fed hawkish bias", -1],
        ["P.C.E. Price Index", "2.0–2.5%", "Approaching 2%", ">3% sustained", "Fed preferred inflation gauge", 0],
        ["Personal Spending", "3–5% YoY", ">4% with real income", "Negative real growth", "Weak = recession risk rising", 0],
        ["Retail Sales", "3–5% YoY", ">5% broad-based", "Negative YoY", "Declining = cut consumer exposure", 0],
    ]},
    "T2_FI": {"t": 2, "l": "Fixed income & curves", "m": "rates", "d": [
        ["30Y Treasury", "3.0–4.8%", "Stable term premium", "Collapsing premium", "Long-term inflation expectations", 0],
        ["2Y Treasury", "0.7–3.8%", "Below FF (easing)", "Above FF+50", "Front-end positioning", 0],
        ["5Y Treasury", "1.6–4.0%", "Below historical avg", "Above cycle highs", "Medium-term expectations", 0],
        ["Municipal Yields", "80–90% of UST", "<85% munis cheap", ">95% credit stress", "Tax-equivalent analysis", 1],
        ["Agency MBS Spread", "100–175 bps", "<125 bps", ">200 bps", "MBS allocation", -1],
        ["CMBS Spreads", "150–250 bps", "<200 bps", ">300 bps", "CRE debt signal", -1],
        ["CLO Spreads (AAA)", "100–175 bps", "<125 bps", ">200 bps", "Leveraged loan health", 0],
        ["Swap Spreads", "0–30 bps", "Positive stable", "Negative/volatile", "Banking system stress", 0],
        ["Auction Demand", "Bid/cover >2.3", ">2.5 strong", "<2.0 weak", "Funding cost signal", 0],
        ["TED Spread", "20–45 bps", "<30 bps", ">100 bps systemic", "Interbank stress", 1],
        ["LIBOR-OIS Spread", "10–25 bps", "<15 bps", ">50 bps", "Funding stress", 1],
        ["Fed Balance Sheet", "Gradual normalization", "Stable/expanding", "Rapid reduction", "QE/QT signal", 0],
        ["Repo Rates", "FF ±5 bps", "Stable near target", ">25 bps deviation", "Overnight stress", 0],
        ["Treasury Volatility", "Swaption <80 bps", "<70 bps calm", ">120 bps", "Hedging costs", 0],
        ["Inflation Swaps 5Y", "2.0–2.5%", "Anchored 2.25%", ">3.0% de-anchoring", "Inflation pricing", 0],
        ["Bond Fund Flows", "Positive trend", "Strong inflows", "Outflows >$10B/wk", "FI sentiment", 0],
        ["Primary Dealer Positions", "Normal levels", "Building bullish", "Offloading", "Dealer sentiment", 0],
        ["Credit Curve Slope", "Positive term", "Normal upward", "Inverted", "Credit expectations", 0],
        ["TIPS Real Yield Curve", "Positive 0–2%", "Positive stable", "Deeply inverted", "Real return expectations", 0],
        ["3M–10Y Curve", "+25 to +245 bps", "Steepening", "Inversion", "Supplement primary curve", 0],
    ]},
    "T2_CREDIT_BANK": {"t": 2, "l": "Credit & banking health", "m": "credit", "d": [
        ["Bank Lending Standards", "-10 to +21% net", "<10% or easing", ">40% broad tightening", "Cut credit >30%", -1],
        ["C&I Loans", "3–6% YoY", "5–8% accelerating", "<2% or contraction", "Cyclical >5%; defensive <2%", 0],
        ["Consumer Delinquency", "2.3–3.4%", "<2.5% stable", ">4% rising", "Credit quality gauge", -1],
        ["Credit Card Delinquency", "2.5–4.4%", "<2.5%", ">5% accelerating", "Consumer stress", -1],
        ["Auto Delinquency", "1.5–2.5%", "<2%", ">3% rising", "Durables stress", -1],
        ["Student Default Rate", "8–12%", "<10% improving", ">15%", "Consumer burden", 0],
        ["Mortgage Delinquency", "1.8–5.9%", "<3%", ">6% rising", "Housing credit", 0],
        ["Bank Tier 1 Capital", ">10%", ">12% well-capitalized", "<8% stress", "System stability", 1],
        ["Net Interest Margins", "3.0–3.5%", ">3.5% expanding", "<2.5% compressed", "Bank profitability", 0],
        ["Loan Loss Provisions", "Moderate build", "Low and stable", "Rapid increase", "Forward credit losses", -1],
        ["FDIC Problem Banks", "<50", "<30 low stress", ">75 systemic", "System fragility", 0],
        ["Sr Loan Officer Survey", "-10 to +21% net", "Easing conditions", "Broad tightening", "Credit availability", -1],
        ["Leveraged Loan Index", "Positive returns", "Spread tightening", "Blowout >500 bps", "Leveraged credit", 0],
        ["ABS Spreads", "50–100 bps", "<75 bps", ">150 bps", "Structured credit", 0],
        ["Bank Deposit Flows", "Stable growth", "Strong inflows", "Flight >2%/mo", "Stability signal", 0],
    ]},
    "T2_EQUITY_DEPTH": {"t": 2, "l": "Equity market depth", "m": "equity", "d": [
        ["Nasdaq Composite", "10–20% annual", "Breaking resistance", "-20% or 200d break", "Tech allocation", 1],
        ["Russell 2000", "GDP correlated", "Outperf S&P >5%", "-30% or underperf >15%", "Small caps", -1],
        ["Dow Jones Industrial", "Above 200d MA", "New highs with breadth", "Below 200d MA", "Blue-chip gauge", 1],
        ["NYSE Advance/Decline", "Rising with market", "New highs in A/D", "Negative divergence", "Breadth confirmation", 0],
        ["New Highs vs. Lows", ">100 net new highs", ">200 net new highs", "Net new lows >200", "Breadth thrust", 0],
        ["Equal vs. Cap Weight", "Tracking within 5%", "Equal weight leading", "Cap weight leading >10%", "Concentration risk", -1],
        ["Small Value/Growth", "Cyclical", "Value in recovery", "Growth late cycle", "Style rotation", 0],
        ["Sector Relative Strength", "Balanced", "Cyclicals leading", "Defensives dominant", "Sector guide", 0],
        ["Stock Correlation", "0.3–0.5", "<0.3 picking env", ">0.7 macro", "Active vs passive", 0],
        ["Short Interest", "2–4 days", "<2 days bullish", ">5 days squeeze", "Contrarian", 0],
        ["ETF Flows", "Positive", ">$20B/wk inflows", "Sustained outflows", "Risk appetite", 1],
        ["Earnings Revisions", ">1.0", ">1.5 strong", "<0.7 deteriorating", "Forward earnings", 0],
        ["Earnings Surprise", "60–70% beat", ">75% strong", "<50% missing", "Corporate health", 0],
        ["Dividend Yield Spread", "S&P vs 10Y", "Stocks > bonds", "Bonds >> stocks", "Relative value", 0],
        ["Vol Term Structure", "Contango", "Steep contango", "Backwardation", "Hedging urgency", 0],
    ]},
    "T2_COMMODITIES": {"t": 2, "l": "Commodities & real assets", "m": "commodities", "d": [
        ["WTI Crude", "$45–82", "$55–65 demand recovery", ">$100 or <$40", "Add $50–60; hedge >$95", 0],
        ["Brent Crude", "$45–84", "Brent-WTI <$5", ">$105 demand destruction", "Global demand; mean reversion", 0],
        ["Gold", "$1,800–2,200/oz", ">$2,200 momentum", "<$1,600 deflation", "Above $2,200 = add to 5–7%", 1],
        ["Silver", "$22–28/oz", ">$28 industrial", "<$18 recession", "Gold/silver ratio", 0],
        ["Copper", "$5,600–8,300/mt", ">$8,300 demand", "<$5,000 recession", "Dr. Copper health gauge", 1],
        ["Nat Gas (Henry Hub)", "$2.80–5.30", "$3–4 balanced", ">$7 or <$2", "Utility sector", 0],
        ["Bloomberg Commodity", "Trend-following", "Broad rally", "Broad decline", "Real asset allocation", 0],
        ["Agricultural Index", "Seasonal", "Moderate levels", "30%+ YoY", "Staples; inflation signal", 0],
        ["Industrial Metals", "PMI correlated", "Rising with mfg", "Declining", "Global mfg health", 0],
        ["Lumber", "$300–500/MBF", "Rising with starts", ">$800 or <$200", "Housing leading", 0],
        ["Iron Ore", "$80–120/ton", "$90–110 balanced", ">$150 stimulus", "Steel/mining", 0],
        ["Platinum/Palladium", "0.5–1.5 ratio", "Platinum leading", "Extreme divergence", "Auto catalyst", 0],
        ["Commodity Curves", "Mild backwardation", "Contango", "Steep backwardation", "Physical tightness", 0],
        ["OPEC Spare Capacity", ">3M bpd", ">4M buffer", "<2M supply risk", "Oil shock risk", 0],
        ["Strategic Reserve", "Historical avg", "Building", "Emergency releases", "Gov't intervention", 0],
    ]},
    "T2_INTL": {"t": 2, "l": "International & currency", "m": "global", "d": [
        ["Dollar Index (DXY)", "94–117", "<100 with Fed pause", ">120 rapid", "Intl allocation; hedge >117", 0],
        ["Euro/Dollar", "1.09–1.30", ">1.15 ECB support", "<1.00 parity", "European hedging", 0],
        ["Dollar/Yen", "104–120", "105–115 balanced", ">145 BoJ risk", "Japan hedging", -1],
        ["Dollar/Yuan", "6.5–8.0", "<7.0 stable", ">7.5 capital flight", "China risk", 0],
        ["EM Currency Index", "Stable", "Broad appreciation", ">10% depreciation", "EM allocation", 0],
        ["Capital Flows", "Balanced", "Risk-on EM inflows", "Flight to safety", "Global risk appetite", 0],
        ["CB Reserves", "Growing", "Diversification", "Drawdowns", "Regime stability", 0],
        ["Carry Trade Index", "Positive", "Stable returns", "Unwinding >5%", "Currency strategy", 0],
        ["Trade-Weighted Dollar", "94–117", "<95 competitiveness", ">120 headwind", "Export impact", 0],
        ["Cross-Ccy Basis", "-20 to +10 bps", "Near zero", "<-50 bps", "USD funding stress", 0],
    ]},
    "T3_HOUSING": {"t": 3, "l": "Housing & real estate", "m": "housing", "d": [
        ["Existing Home Sales", "4.5–5.5M", ">5M rising", "<4M declining", "Sector allocation", -1],
        ["New Home Sales", "480–890K", ">700K with permits", "<480K", "Builder stocks", -1],
        ["Housing Starts", "1.0–1.6M", ">1.5M accelerating", "<1.0M recessionary", "Construction", -1],
        ["Building Permits", "1.1–1.7M", ">1.6M pipeline", "<1.1M weakness", "Forward construction", -1],
        ["Pending Home Sales", "100–120", ">110 rising", "<80 collapse", "Leading 1–2 month", 0],
        ["Case-Shiller Index", "3–5% YoY", "5–7% healthy", ">15% or negative", "Valuation gauge", 0],
        ["FHFA House Prices", "3–5% YoY", "Moderate broad", "Declining nationally", "Conforming market", 0],
        ["30Y Mortgage Rate", "4.0–6.3%", "<5% stimulus", ">7% affordability", "Demand driver", -1],
        ["Mortgage Applications", "Stable", ">10% sustained", ">20% decline", "Near-term demand", -1],
        ["Affordability Index", ">120", ">140 very affordable", "<100 unaffordable", "Sustainability", -1],
        ["Months Supply", "4.5–7.7 months", "3–4 sellers", ">8 oversupply", "Market balance", 0],
        ["NAHB Confidence", "45–65", ">55 positive", "<40 pessimism", "Forward sentiment", 0],
        ["Rental Vacancy", "6.9–9.6%", "<6% tight", ">10% oversupply", "Rental health", 0],
        ["Rent Prices", "3–5% YoY", "3–4% moderate", ">8% concern", "Shelter C.P.I.", -1],
        ["Commercial RE", "Stable", "Cap compression", "Rising caps >7%", "CRE allocation", -1],
        ["REIT Performance", "Positive", "Outperf bonds", "-15% declining", "Listed RE", -1],
        ["Mortgage Delinq 90+", "1.8–5.9%", "<2%", ">6% stress", "Credit quality", 0],
        ["Foreclosure Rate", "0.5–1.0%", "<0.7%", ">1.5% distress", "Distress gauge", 0],
        ["Home Equity Withdrawal", "Moderate", "Low", "Excessive", "Consumer leverage", 0],
        ["Construction Spending", "3–5% YoY", ">5% expansion", "Negative", "RE investment", -1],
    ]},
    "T3_MFG": {"t": 3, "l": "Manufacturing & industrial", "m": "gdp", "d": [
        ["Durable Goods Orders", "2–4% YoY", ">5% ex-aircraft", "Neg 3 consecutive", "Capital spending", 0],
        ["Factory Orders", "3–5% YoY", ">5% broad-based", "<0% sustained", "Mfg health", 0],
        ["Capacity Utilization (Mfg)", "74.6–77.7%", ">78% healthy", "<72% slack", "Pricing power", 0],
        ["Mfg Employment", "Positive", ">10K monthly", "Negative 3+mo", "Cycle gauge", 0],
        ["New Orders (ISM)", "50–58", ">55 pipeline", "<45 decline", "Forward activity", 0],
        ["Inventory/Sales", "1.29–1.40", "<1.27 lean", ">1.45 glut", "Supply chain", 0],
        ["Trade Balance", "-$61B to -$40B", "Narrowing", "Widening >-$70B", "Competitiveness", 0],
        ["Export Orders", "Growing", ">3% monthly", "Declining 3+mo", "Global demand", 0],
        ["Core CapEx Orders", "2–4% YoY", ">5% boom", "Negative", "Investment leading", 0],
        ["Productivity", "1–2% YoY", ">2% tech gains", "Negative", "Growth potential", 0],
        ["Unit Labor Costs", "1–3% YoY", "<2% contained", ">4% pressure", "Labor inflation", 0],
        ["Philly Fed Mfg", "-1.5 to +17", ">20 strong", "<-15 contraction", "Regional", -1],
        ["Empire State Mfg", "-4 to +18", ">20 strong", "<-15 contraction", "NY region", -1],
        ["KC Fed Mfg", ">0", ">10 healthy", "<-10 contraction", "Midwest", 0],
        ["Chicago PMI", "50–60", ">55 strong", "<45 contraction", "Major regional", 0],
    ]},
    "T3_CONSUMER": {"t": 3, "l": "Consumer & retail", "m": "consumer", "d": [
        ["Michigan Sentiment", "72–93", ">93 rising", "<60 deteriorating", "Discretionary weight", -1],
        ["Personal Income", "3–5% YoY", ">5% with low inflation", "<2% or neg real", "Consumption outlook", 0],
        ["Savings Rate", "4.4–6.2%", ">7% building", "<3% unsustainable", "Financial health", -1],
        ["Consumer Credit", "3–5% YoY", "Moderate with income", ">7% unsustainable", "Credit-driven", -1],
        ["Auto Sales", "15.2–17.5M SAAR", ">16M with financing", "<14M weakness", "Big-ticket", 0],
        ["Redbook Retail", "2–4% YoY", ">5% strong", "Negative", "Weekly pulse", 0],
        ["E-Commerce", "10–15% YoY", ">15%", "<5%", "Digital economy", 0],
        ["Restaurant Index", ">100", ">101 strong", "<99 contraction", "Discretionary", 0],
        ["Hotel Occupancy", "60–70%", ">70%", "<55%", "Travel", 0],
        ["CC Spending", "3–5% YoY", ">5% healthy", "Negative", "Real-time consumer", 0],
        ["Durable Orders (Consumer)", "2–4% YoY", ">5%", "Negative 2+mo", "Big-ticket", 0],
        ["Consumer Expectations", "80–100", ">95 optimistic", "<70 pessimistic", "Forward outlook", -1],
    ]},
    "T3_LABOR": {"t": 3, "l": "Labor markets", "m": "consumer", "d": [
        ["Participation Rate", "62.7–66.0%", ">63% rising", "<62% decline", "Supply constraints", 0],
        ["Hourly Earnings", "3–4% YoY", "3.5% with productivity", ">5% or <2%", "Margin pressure", 0],
        ["JOLTS Openings", "3.8–7.0M", ">7M strong", "<3.5M weakening", "Labor demand", -1],
        ["JOLTS Quits Rate", "1.8–2.2%", ">2.3% confidence", "<1.5% fear", "Worker gauge", -1],
        ["Employment Cost Index", "2–3% YoY", "3–3.5%", ">4% pressure", "Total compensation", 0],
        ["Temp Employment", "Growing", "Expanding", "3+mo decline", "Leading indicator", 0],
        ["Job Postings", "3–5% YoY", ">5% demand", "Declining >10%", "Forward employment", 0],
    ]},
    "T3_TECH": {"t": 3, "l": "Technology & innovation", "m": "global", "d": [
        ["Semiconductor Sales", "5–10% YoY", ">15% strong", "Negative", "Tech cycle", 1],
        ["Software Spending", "8–12% YoY", ">12%", "<5%", "Enterprise IT", 0],
        ["Cloud Revenue", "15–25% YoY", ">20%", "<10%", "Digital transformation", 1],
        ["VC Investment", "$50–80B Q", ">$70B quality", "<$30B winter", "Innovation pipeline", 0],
        ["AI/ML Investment", "Growing", "Enterprise acceleration", "Budget cuts", "Tech theme", 1],
    ]},
    "T3_ENERGY": {"t": 3, "l": "Energy & environment", "m": "commodities", "d": [
        ["Oil Rig Count", "400–600", "500–550 balanced", "<350 or >750", "Supply lag 6mo", 0],
        ["Gasoline Inventories", "5yr avg ±5%", "Normal seasonal", ">10% deviation", "Demand signal", 0],
        ["Crude Inventories", "5yr avg ±10%", "Draws below avg", "Builds >15%", "S&D balance", 0],
        ["Refinery Utilization", "88–94%", ">92% demand", "<85% weakness", "Product supply", 0],
        ["Nat Gas Storage", "5yr avg ±10%", "Normal pattern", ">20% surplus/deficit", "Winter cost", 0],
        ["Renewable Investment", "Growing", ">$100B Q globally", "Sharp decline", "Transition", 0],
        ["Carbon Credits", "€60–100/t", "Rising toward €100", "<€50", "Regulation", 0],
        ["US Gas Demand", "8.5–9.5M bpd", ">9M seasonal", "<8M destruction", "Consumer driving", 0],
        ["Global Oil Demand", "99–102M bpd", ">101M growth", "<98M recession", "Global activity", 0],
        ["LNG Exports", "Growing", "Record volumes", "Declining", "US energy", 0],
    ]},
    "T3_FISCAL": {"t": 3, "l": "Fiscal & government", "m": "global", "d": [
        ["Budget Deficit", "3–5% of GDP", "<3% improving", ">7% deteriorating", "Rates impact", -1],
        ["Debt-to-GDP", "62–105% GDP", "Stable/declining", ">120%", "Sovereign risk", -1],
        ["Tax Revenue", "16.0–17.3% GDP", ">GDP growth", "Declining", "Fiscal health", 0],
        ["Govt Spending", "2–4% real", "Targeted", ">6% unsustainable", "Stimulus/drag", 0],
        ["Treasury Issuance", "Manageable", "Absorbed", "LT surge", "Rate pressure", 0],
        ["Infrastructure", "Growing", "Accelerating", "Budget cuts", "Construction", 0],
        ["Defense Spending", "3–5% GDP", "Stable", "Sharp change", "Defense sector", 0],
    ]},
    "T3_HEALTH": {"t": 3, "l": "Healthcare & demographics", "m": "global", "d": [
        ["Healthcare Spending", "17–18% GDP", "Stable innovation", ">20%", "HC allocation", 0],
        ["FDA Approvals", "40–50/yr", ">50 breakthroughs", "<30 drought", "Biotech", 0],
        ["Biotech Index", "Relative to S&P", "Outperf pipeline", "-20% drawdown", "Sector", 0],
        ["Population Growth", "0.5–1.0%", ">0.7%", "<0.3%", "LT demand", 0],
    ]},
    "T4_MICRO": {"t": 4, "l": "Market microstructure", "m": "equity", "d": [
        ["Order Flow", "±20% daily", "Buy >25%", "Sell >30%", "Momentum", 0],
        ["Dark Pool Activity", "35–40%", "<35%", ">45%", "Institutional", 0],
        ["Bid-Ask Spreads", "Tight", "Tightening", "Widening >50%", "Liquidity", 0],
        ["AAII Sentiment", "30–40% bull", ">50% contrarian", "<20% contrarian", "Retail", 0],
        ["Fear & Greed", "40–60", ">80 greed", "<20 fear", "Composite", 0],
        ["CBOE Skew", "120–140", "<125 low tail", ">150 tail risk", "Black swan", 0],
        ["Gamma Exposure", "Balanced", "Positive", "Negative", "Options", 0],
        ["VIX Term Structure", "Contango", "Steep contango", "Backwardation", "Vol regime", 0],
        ["COT Positioning", "Balanced", "Commercial heavy", "Spec extreme", "Smart money", 0],
        ["Money Market Assets", "$4–5T", "Stable", ">$6T flight", "Risk appetite", 0],
        ["HF Leverage", "200–250%", "<200%", ">300%", "Institutional", 0],
        ["Cross-Asset Momentum", "Positive", "Broad risk-on", "Broad risk-off", "Trend", 0],
    ]},
    "T4_GLOBAL": {"t": 4, "l": "Global economic", "m": "global", "d": [
        ["China PMI", "50–52", "Both >52", "Both <49", "EM; commodities", 0],
        ["China Credit", "8–10% YoY", "9–11%", "<7% or >15%", "Credit impulse", 0],
        ["Eurozone PMI", "50–55", ">53", "<48", "European allocation", 0],
        ["Global Trade", "3–5% YoY", ">5%", "Negative", "Globalization", 0],
        ["Baltic Dry", "1,000–2,500", ">2,000", "<1,000", "Trade activity", 0],
        ["Global PMI", "50–54", ">53 healthy", "<48 contraction", "Worldwide", 0],
        ["OECD Leading", "Above 100", ">101", "<99", "Cycle positioning", 0],
        ["Copper/Gold Ratio", "Correlated w/ rates", "Rising", "Falling", "Growth vs safety", 0],
        ["Geopolitical Risk", "Below avg", "Low stable", ">2σ", "Risk premium", 0],
    ]},
    "T4_ALT": {"t": 4, "l": "Alternative data", "m": "global", "d": [
        ["Satellite Activity", "GDP correlated", "Increasing", "Declining", "Nowcasting", 0],
        ["Social Sentiment", "0.5–0.6", ">0.6", "<0.4", "Contrarian", 0],
        ["Search Trends", "Baseline", "Accelerating", "Sharp decline", "Interest", 0],
        ["Supply Chain Pressure", "0 avg", "<-0.5 easing", ">1.0 pressure", "Inflation", 0],
        ["Container Rates", "$1,500–3,000", "$2,000–2,500", ">$5,000", "Trade flow", 0],
        ["Electricity Consumption", "1–3% YoY", ">3%", "Negative", "RT activity", 0],
        ["CEO Confidence", "50–60%", ">60%", "<40%", "Corporate", 0],
    ]},
    "T4_RISK": {"t": 4, "l": "Systematic risk", "m": "global", "d": [
        ["Correlation Events", "<5%", "Stable", "Frequent >10%", "Stress testing", 0],
        ["Tail Risk Costs", "1–2%", "<1% cheap", ">3% expensive", "Protection", 0],
        ["Systemic Risk", "Below warning", "Declining", "Multiple warnings", "Stability", 0],
        ["Liquidity Premium", "Stable low", "Compression", "Widening >50bps", "Functioning", 0],
        ["Financial Stress", "-0.6 to +0.3", "Declining", ">1.0 elevated", "Comprehensive", 0],
        ["Regime Change", "Stable", "Confirmation", "Transition warnings", "Adaptation", 0],
    ]},
}

# ─────────────────────────────────────────────────────────────────────────────
# MODULES (groupings of categories)
# ─────────────────────────────────────────────────────────────────────────────

MODULES = [
    {"id": "rates_fi", "n": "Interest Rates & Fixed Income",
     "cats": ["T1_RATES", "T2_FI"], "c": P["blue"]},
    {"id": "credit_debt", "n": "Credit & Debt",
     "cats": ["T1_CREDIT", "T2_CREDIT_BANK"], "c": P["red"]},
    {"id": "equity", "n": "Equity Markets",
     "cats": ["T1_EQUITY", "T2_EQUITY_DEPTH", "T4_MICRO"], "c": P["green"]},
    {"id": "gdp_growth", "n": "GDP & Growth Indicators",
     "cats": ["T1_GROWTH", "T3_MFG"], "c": P["amber"]},
    {"id": "consumer_labor", "n": "Consumer, Labor & Inflation",
     "cats": ["T1_INFLATION", "T3_CONSUMER", "T3_LABOR"], "c": "#7c3aed"},
    {"id": "housing", "n": "Housing & Real Estate",
     "cats": ["T3_HOUSING"], "c": "#0891b2"},
    {"id": "commodities", "n": "Commodities & Energy",
     "cats": ["T2_COMMODITIES", "T3_ENERGY"], "c": "#ca8a04"},
    {"id": "global_special", "n": "Forex, Treasury & Specialized",
     "cats": ["T2_INTL", "T3_TECH", "T3_FISCAL", "T3_HEALTH", "T4_GLOBAL", "T4_ALT", "T4_RISK"], "c": "#4338ca"},
]

# ─────────────────────────────────────────────────────────────────────────────
# FRED SERIES MAPPING (indicator name → FRED series ID)
# ─────────────────────────────────────────────────────────────────────────────

SRC = {
    # ── T1_RATES: Interest rates & monetary policy ────────────────────────────
    "Federal Funds Rate": ["DFF", "https://fred.stlouisfed.org/series/DFF"],
    "2Y–10Y Treasury Spread": ["T10Y2Y", "https://fred.stlouisfed.org/series/T10Y2Y"],
    "3M–10Y Treasury Spread": ["T10Y3M", "https://fred.stlouisfed.org/series/T10Y3M"],
    "5Y5Y Forward Inflation": ["T5YIFR", "https://fred.stlouisfed.org/series/T5YIFR"],
    "10Y TIPS Breakeven": ["T10YIE", "https://fred.stlouisfed.org/series/T10YIE"],
    "5Y TIPS Breakeven": ["T5YIE", "https://fred.stlouisfed.org/series/T5YIE"],
    "Real Yield Curve (TIPS)": ["DFII10", "https://fred.stlouisfed.org/series/DFII10"],
    "SOFR": ["SOFR", "https://fred.stlouisfed.org/series/SOFR"],

    # ── T1_CREDIT: Credit markets & default risk ──────────────────────────────
    "CDX NA Investment Grade": ["BAMLC0A0CM", "https://fred.stlouisfed.org/series/BAMLC0A0CM"],
    "CDX High Yield": ["BAMLH0A0HYM2", "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"],
    "VIX Index": ["VIXCLS", "https://fred.stlouisfed.org/series/VIXCLS"],
    "High Yield Spreads": ["BAMLH0A0HYM2", "https://fred.stlouisfed.org/series/BAMLH0A0HYM2"],

    # ── T1_EQUITY: Equity market indicators ───────────────────────────────────
    "S&P 500": ["SP500", "https://fred.stlouisfed.org/series/SP500"],

    # ── T1_GROWTH: Economic growth ────────────────────────────────────────────
    "GDP Growth Rate": ["A191RL1Q225SBEA", "https://fred.stlouisfed.org/series/A191RL1Q225SBEA"],
    "Nonfarm Payrolls": ["PAYEMS", "https://fred.stlouisfed.org/series/PAYEMS"],
    "Unemployment Rate": ["UNRATE", "https://fred.stlouisfed.org/series/UNRATE"],
    "Initial Claims (4-wk)": ["ICSA", "https://fred.stlouisfed.org/series/ICSA"],
    "Industrial Production": ["INDPRO", "https://fred.stlouisfed.org/series/INDPRO"],
    "Capacity Utilization": ["TCU", "https://fred.stlouisfed.org/series/TCU"],

    # ── T1_INFLATION: Inflation & consumer activity ───────────────────────────
    "C.P.I. (year-over-year)": ["CPIAUCSL", "https://fred.stlouisfed.org/series/CPIAUCSL"],
    "Core C.P.I.": ["CPILFESL", "https://fred.stlouisfed.org/series/CPILFESL"],
    "P.C.E. Price Index": ["PCEPI", "https://fred.stlouisfed.org/series/PCEPI"],
    "Personal Spending": ["PCE", "https://fred.stlouisfed.org/series/PCE"],
    "Retail Sales": ["RSXFS", "https://fred.stlouisfed.org/series/RSXFS"],

    # ── T2_FI: Fixed income & curves ──────────────────────────────────────────
    "30Y Treasury": ["DGS30", "https://fred.stlouisfed.org/series/DGS30"],
    "2Y Treasury": ["DGS2", "https://fred.stlouisfed.org/series/DGS2"],
    "5Y Treasury": ["DGS5", "https://fred.stlouisfed.org/series/DGS5"],
    "TED Spread": ["TEDRATE", "https://fred.stlouisfed.org/series/TEDRATE"],
    "Fed Balance Sheet": ["WALCL", "https://fred.stlouisfed.org/series/WALCL"],
    "3M–10Y Curve": ["T10Y3M", "https://fred.stlouisfed.org/series/T10Y3M"],

    # ── T2_CREDIT_BANK: Credit & banking health ──────────────────────────────
    "Bank Lending Standards": ["DRTSCILM", "https://fred.stlouisfed.org/series/DRTSCILM"],
    "C&I Loans": ["BUSLOANS", "https://fred.stlouisfed.org/series/BUSLOANS"],
    "Consumer Delinquency": ["DRCLACBS", "https://fred.stlouisfed.org/series/DRCLACBS"],
    "Credit Card Delinquency": ["DRCCLACBS", "https://fred.stlouisfed.org/series/DRCCLACBS"],
    "Auto Delinquency": ["DRALACBS", "https://fred.stlouisfed.org/series/DRALACBS"],
    "Mortgage Delinquency": ["DRSFRMACBS", "https://fred.stlouisfed.org/series/DRSFRMACBS"],
    "Sr Loan Officer Survey": ["DRTSCILM", "https://fred.stlouisfed.org/series/DRTSCILM"],

    # ── T2_EQUITY_DEPTH: Equity market depth ──────────────────────────────────
    "Nasdaq Composite": ["NASDAQCOM", "https://fred.stlouisfed.org/series/NASDAQCOM"],
    "Dow Jones Industrial": ["DJIA", "https://fred.stlouisfed.org/series/DJIA"],

    # ── T2_COMMODITIES: Commodities & real assets ─────────────────────────────
    "WTI Crude": ["DCOILWTICO", "https://fred.stlouisfed.org/series/DCOILWTICO"],
    "Brent Crude": ["DCOILBRENTEU", "https://fred.stlouisfed.org/series/DCOILBRENTEU"],
    "Copper": ["PCOPPUSDM", "https://fred.stlouisfed.org/series/PCOPPUSDM"],
    "Nat Gas (Henry Hub)": ["DHHNGSP", "https://fred.stlouisfed.org/series/DHHNGSP"],

    # ── T2_INTL: International & currency ─────────────────────────────────────
    "Dollar Index (DXY)": ["DTWEXBGS", "https://fred.stlouisfed.org/series/DTWEXBGS"],
    "Euro/Dollar": ["DEXUSEU", "https://fred.stlouisfed.org/series/DEXUSEU"],
    "Dollar/Yen": ["DEXJPUS", "https://fred.stlouisfed.org/series/DEXJPUS"],
    "Dollar/Yuan": ["DEXCHUS", "https://fred.stlouisfed.org/series/DEXCHUS"],
    "Trade-Weighted Dollar": ["DTWEXBGS", "https://fred.stlouisfed.org/series/DTWEXBGS"],
    "Trade Balance": ["BOPGSTB", "https://fred.stlouisfed.org/series/BOPGSTB"],

    # ── T3_HOUSING: Housing & real estate ─────────────────────────────────────
    "Existing Home Sales": ["EXHOSLUSM495S", "https://fred.stlouisfed.org/series/EXHOSLUSM495S"],
    "New Home Sales": ["HSN1F", "https://fred.stlouisfed.org/series/HSN1F"],
    "Housing Starts": ["HOUST", "https://fred.stlouisfed.org/series/HOUST"],
    "Building Permits": ["PERMIT", "https://fred.stlouisfed.org/series/PERMIT"],
    "Case-Shiller Index": ["CSUSHPINSA", "https://fred.stlouisfed.org/series/CSUSHPINSA"],
    "FHFA House Prices": ["USSTHPI", "https://fred.stlouisfed.org/series/USSTHPI"],
    "30Y Mortgage Rate": ["MORTGAGE30US", "https://fred.stlouisfed.org/series/MORTGAGE30US"],
    "Affordability Index": ["FIXHAI", "https://fred.stlouisfed.org/series/FIXHAI"],
    "Months Supply": ["MSACSR", "https://fred.stlouisfed.org/series/MSACSR"],
    "Rental Vacancy": ["RRVRUSQ156N", "https://fred.stlouisfed.org/series/RRVRUSQ156N"],
    "Construction Spending": ["TTLCONS", "https://fred.stlouisfed.org/series/TTLCONS"],
    "Mortgage Delinq 90+": ["DRSFRMACBS", "https://fred.stlouisfed.org/series/DRSFRMACBS"],

    # ── T3_MFG: Manufacturing & industrial ────────────────────────────────────
    "Durable Goods Orders": ["DGORDER", "https://fred.stlouisfed.org/series/DGORDER"],
    "Factory Orders": ["AMTMNO", "https://fred.stlouisfed.org/series/AMTMNO"],
    "Capacity Utilization (Mfg)": ["MCUMFN", "https://fred.stlouisfed.org/series/MCUMFN"],
    "Mfg Employment": ["MANEMP", "https://fred.stlouisfed.org/series/MANEMP"],
    "Inventory/Sales": ["ISRATIO", "https://fred.stlouisfed.org/series/ISRATIO"],
    "Export Orders": ["BOPTEXP", "https://fred.stlouisfed.org/series/BOPTEXP"],
    "Core CapEx Orders": ["NEWORDER", "https://fred.stlouisfed.org/series/NEWORDER"],
    "Productivity": ["OPHPBS", "https://fred.stlouisfed.org/series/OPHPBS"],
    "Unit Labor Costs": ["ULCNFB", "https://fred.stlouisfed.org/series/ULCNFB"],
    "Philly Fed Mfg": ["GACDFSA066MSFRBPHI", "https://fred.stlouisfed.org/series/GACDFSA066MSFRBPHI"],
    "Empire State Mfg": ["GACDISA066MSFRBNY", "https://fred.stlouisfed.org/series/GACDISA066MSFRBNY"],
    "KC Fed Mfg": ["FRBKCLMCILA", "https://fred.stlouisfed.org/series/FRBKCLMCILA"],

    # ── T3_CONSUMER: Consumer & retail ────────────────────────────────────────
    "Michigan Sentiment": ["UMCSENT", "https://fred.stlouisfed.org/series/UMCSENT"],
    "Consumer Expectations": ["MICH", "https://fred.stlouisfed.org/series/MICH"],
    "Personal Income": ["PI", "https://fred.stlouisfed.org/series/PI"],
    "Savings Rate": ["PSAVERT", "https://fred.stlouisfed.org/series/PSAVERT"],
    "Consumer Credit": ["TOTALSL", "https://fred.stlouisfed.org/series/TOTALSL"],
    "Auto Sales": ["TOTALSA", "https://fred.stlouisfed.org/series/TOTALSA"],
    "Rent Prices": ["CUSR0000SEHA", "https://fred.stlouisfed.org/series/CUSR0000SEHA"],

    # ── T3_LABOR: Labor markets ───────────────────────────────────────────────
    "Participation Rate": ["CIVPART", "https://fred.stlouisfed.org/series/CIVPART"],
    "Hourly Earnings": ["CES0500000003", "https://fred.stlouisfed.org/series/CES0500000003"],
    "JOLTS Openings": ["JTSJOL", "https://fred.stlouisfed.org/series/JTSJOL"],
    "JOLTS Quits Rate": ["JTSQUR", "https://fred.stlouisfed.org/series/JTSQUR"],
    "Employment Cost Index": ["ECIWAG", "https://fred.stlouisfed.org/series/ECIWAG"],
    "Temp Employment": ["TEMPHELPS", "https://fred.stlouisfed.org/series/TEMPHELPS"],

    # ── T3_FISCAL: Fiscal & government ────────────────────────────────────────
    "Debt-to-GDP": ["GFDEGDQ188S", "https://fred.stlouisfed.org/series/GFDEGDQ188S"],
    "Tax Revenue": ["FYFRGDA188S", "https://fred.stlouisfed.org/series/FYFRGDA188S"],
    "Govt Spending": ["FGEXPND", "https://fred.stlouisfed.org/series/FGEXPND"],

    # ── T3_FISCAL: Fiscal & government (cont.) ──────────────────────────────
    "Budget Deficit": ["FYFSD", "https://fred.stlouisfed.org/series/FYFSD"],

    # ── T4_MICRO: Market microstructure ───────────────────────────────────────
    "Money Market Assets": ["RRPONTSYD", "https://fred.stlouisfed.org/series/RRPONTSYD"],

    # ── T4_RISK: Systematic risk ──────────────────────────────────────────────
    "Financial Stress": ["STLFSI4", "https://fred.stlouisfed.org/series/STLFSI4"],
    "Systemic Risk": ["NFCI", "https://fred.stlouisfed.org/series/NFCI"],

    # ── T3_HEALTH: Healthcare & demographics ──────────────────────────────────
    "Population Growth": ["POPTHM", "https://fred.stlouisfed.org/series/POPTHM"],

    # ── T3_ENERGY: Energy (EIA API) ──────────────────────────────────────────
    # Source type "eia" — 3rd element indicates non-FRED source
    "Crude Inventories": ["PET.WCESTUS1.W", "https://www.eia.gov/petroleum/supply/weekly/", "eia"],
    "Gasoline Inventories": ["PET.WGTSTUS1.W", "https://www.eia.gov/petroleum/supply/weekly/", "eia"],
    "Refinery Utilization": ["PET.WPULRL3S3.W", "https://www.eia.gov/petroleum/supply/weekly/", "eia"],
    "Nat Gas Storage": ["NG.NW2_EPG0_SWO_R48_BCF.W", "https://www.eia.gov/naturalgas/storage/", "eia"],
    "US Gas Demand": ["PET.WGFUPUS2.W", "https://www.eia.gov/petroleum/supply/weekly/", "eia"],
    "LNG Exports": ["NG.N9133US2.M", "https://www.eia.gov/naturalgas/data.php", "eia"],
}

# ─────────────────────────────────────────────────────────────────────────────
# YEAR-OVER-YEAR SERIES — display YoY % change instead of raw level
# ─────────────────────────────────────────────────────────────────────────────

YOY_SERIES = {
    # Equity indices (levels → YoY %)
    "SP500", "NASDAQCOM", "DJIA",
    # Price indices (levels → YoY %)
    "CPIAUCSL", "CPILFESL", "PCEPI", "CUSR0000SEHA",
    # Production & output indices
    "INDPRO",
    # Employment levels
    "PAYEMS", "MANEMP",
    # Spending & income levels
    "PCE", "RSXFS", "PI",
    # Credit levels
    "TOTALSL", "BUSLOANS",
    # Orders & manufacturing levels
    "DGORDER", "AMTMNO", "NEWORDER",
    # Construction & housing levels
    "TTLCONS", "CSUSHPINSA", "USSTHPI",
    # Commodity prices
    "PCOPPUSDM",
    # Fed balance sheet
    "WALCL",
}

# ─────────────────────────────────────────────────────────────────────────────
# REGIMES
# ─────────────────────────────────────────────────────────────────────────────

REGIMES = [
    {"n": "Risk-on", "t": "VIX <20, spreads tightening, curve steepening, PMIs >50", "a": "Add equity, extend duration, favor growth and cyclical sectors", "c": P["green"]},
    {"n": "Risk-off", "t": "VIX >30, spreads widening, curve inverting, PMIs <50", "a": "Cut equity, shorten duration, add defensive sectors", "c": P["red"]},
    {"n": "Recession warning", "t": "2Y–10Y inversion >3 months, L.E.I. decline 6+ months, Sahm Rule", "a": "Major defensive, high-quality bonds, cut cyclical", "c": P["red"]},
    {"n": "Inflation concern", "t": "C.P.I. >3%, breakevens >3%, commodity surge, wage acceleration", "a": "TIPS, cut long bonds, favor real assets", "c": P["amber"]},
    {"n": "Fed pivot", "t": "Unemployment rising, credit stress elevated, growth slowing", "a": "Position for cuts, extend duration, prep for recovery", "c": P["blue"]},
]

# ─────────────────────────────────────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────────────────────────────────────

TIER_WEIGHTS = {1: 3, 2: 2, 3: 1, 4: 0.5}

import re

def _parse_number(s):
    """Parse a number string with optional K/M/B suffix."""
    s = s.strip()
    multiplier = 1
    if s.endswith("e3"):
        s = s[:-2]
        multiplier = 1000
    elif s.endswith("e6"):
        s = s[:-2]
        multiplier = 1_000_000
    elif s.endswith("e9"):
        s = s[:-2]
        multiplier = 1_000_000_000
    return float(s) * multiplier


def parse_target_range(target_str):
    """Parse a target range string into (low, high) numeric bounds.
    Returns None if the range can't be parsed numerically."""
    s = target_str.strip()
    # Remove common units/prefixes but keep K/M/B attached to numbers
    s = s.replace("$", "").replace("%", "").replace(",", "")
    s = s.replace(" bps", "").replace(" GDP", "").replace(" real", "")
    s = s.replace("/oz", "").replace("/mt", "").replace("/MBF", "").replace("/ton", "")
    s = s.replace(" SAAR", "").replace(" months", "").replace(" monthly", "")
    s = s.replace(" avg", "").replace(" net", "").replace(" Q", "")
    # Convert K/M/B suffixes attached to numbers
    s = re.sub(r'(\d)K\b', r'\1e3', s)
    s = re.sub(r'(\d)M\b', r'\1e6', s)
    s = re.sub(r'(\d)B\b', r'\1e9', s)
    # Also handle standalone M/B after space (e.g., "15.2–17.5M")
    s = re.sub(r'(\d)\s*M(?:\s|$)', r'\1e6 ', s)
    s = re.sub(r'(\d)\s*B(?:\s|$)', r'\1e9 ', s)
    s = s.strip()
    # Match patterns like "X–Y", "X to Y", "<X", ">X", "X to +Y"
    m = re.match(r'([<>]?)\s*([+-]?\d*\.?\d+(?:e\d+)?)\s*[–—\-to]+\s*([+-]?\d*\.?\d+(?:e\d+)?)', s)
    if m:
        try:
            low = _parse_number(m.group(2))
            high = _parse_number(m.group(3))
            # If only the high has a multiplier (e.g. "15.2–17.5M"), apply same scale to low
            if high != 0 and abs(high / (low if low != 0 else 1)) > 100 and low < 1000:
                scale = 10 ** (len(str(int(abs(high)))) - len(str(int(abs(low)))) if low != 0 else 0)
                if scale >= 1000:
                    low = low * scale
            return (low, high)
        except (ValueError, ZeroDivisionError):
            pass
    # Single threshold: ">X" or "<X"
    m = re.match(r'>\s*([+-]?\d*\.?\d+(?:e\d+)?)', s)
    if m:
        try:
            return (_parse_number(m.group(1)), float('inf'))
        except ValueError:
            pass
    m = re.match(r'<\s*([+-]?\d*\.?\d+(?:e\d+)?)', s)
    if m:
        try:
            return (float('-inf'), _parse_number(m.group(1)))
        except ValueError:
            pass
    return None


def compute_module_score(mod):
    """Compute weighted score for a module (0 to 100, where 50 = neutral)"""
    ws, tw = 0, 0
    for cid in mod["cats"]:
        cat = CAT.get(cid)
        if not cat:
            continue
        w = TIER_WEIGHTS[cat["t"]]
        for d in cat["d"]:
            ws += d[5] * w
            tw += w
    # Convert from -1..+1 weighted average to 0..100 scale
    raw = (ws / tw) if tw else 0  # -1 to +1
    return round((raw + 1) * 50)  # 0 to 100


def compute_all_scores():
    """Compute scores for all modules"""
    return {mod["id"]: compute_module_score(mod) for mod in MODULES}


def compute_composite():
    """Compute overall composite score (0 to 100)"""
    scores = compute_all_scores()
    if not scores:
        return 50
    return round(sum(scores.values()) / len(scores))


def get_regime(composite):
    """Determine current market regime from composite score (0-100 scale)"""
    if composite > 58:
        return REGIMES[0]  # Risk-on
    elif composite < 35:
        return REGIMES[1]  # Risk-off
    elif composite < 42:
        return REGIMES[2]  # Recession warning
    else:
        return REGIMES[0]  # Default neutral/risk-on


def signal_color(signal):
    """Return (color, label) for a signal value"""
    if signal > 0:
        return P["green"], "Bullish"
    elif signal < 0:
        return P["red"], "Bearish"
    return P["inkLight"], "Neutral"


def total_indicator_count():
    """Count total indicators across all categories"""
    return sum(len(cat["d"]) for cat in CAT.values())
