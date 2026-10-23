"""Curated historical case studies; descriptive regimes, not live classifications."""
from dataclasses import dataclass

@dataclass(frozen=True)
class HistorySeries:
    name: str
    unit: str
    transform: str = 'level'
    frequency: str = 'monthly'
    role: str = 'Economic context'

SERIES = {
    'CPIAUCNS':HistorySeries('Consumer price inflation','% year over year','yoy',role='Purchasing power'),
    'CPIAUCSL':HistorySeries('Consumer price inflation · adjusted','% year over year','yoy',role='Purchasing power'),
    'PCEPI':HistorySeries('PCE inflation','% year over year','yoy',role='Inflation pressure'),
    'INDPRO':HistorySeries('Industrial production','% year over year','yoy',role='Activity confirmation'),
    'UNRATE':HistorySeries('Unemployment rate','%',role='Lagging labor confirmation'),
    'PERMIT':HistorySeries('Housing permits','% year over year','yoy',role='Rate-sensitive demand'),
    'HOUST':HistorySeries('Housing starts','% year over year','yoy',role='Rate-sensitive demand'),
    'IC4WSA':HistorySeries('Initial claims · four-week average','people','level','weekly','Labor deterioration'),
    'NFCI':HistorySeries('Chicago Fed financial conditions','index; positive = tighter','level','weekly','Funding and risk appetite'),
    'STLFSI4':HistorySeries('St. Louis Fed financial stress','index; positive = above-average stress','level','weekly','Stress confirmation'),
    'GS10':HistorySeries('10-year Treasury yield','%',role='Discount-rate pressure'),
    'TB3MS':HistorySeries('3-month Treasury bill rate','%',role='Short-term funding'),
    'DGS10':HistorySeries('10-year Treasury yield · daily','%','level','daily','Discount-rate pressure'),
    'T10Y2Y':HistorySeries('10-year minus 2-year Treasury','percentage points','level','daily','Curve and policy pressure'),
    'T10Y3M':HistorySeries('10-year minus 3-month Treasury','percentage points','level','daily','Curve and policy pressure'),
    'DFF':HistorySeries('Effective federal funds rate','%','level','daily','Policy stance'),
    'BUSLOANS':HistorySeries('Commercial & industrial loans','% year over year','yoy',role='Credit transmission'),
    'TEMPHELPS':HistorySeries('Temporary-help employment','% year over year','yoy',role='Labor demand'),
    'PAYEMS':HistorySeries('Payroll employment','% year over year','yoy',role='Broad labor demand'),
    'DRTSCILM':HistorySeries('Banks tightening large-firm C&I standards','net % of banks','level','quarterly','Credit supply'),
}

@dataclass(frozen=True)
class Regime:
    id: str
    button: str
    title: str
    kind: str
    start: str
    end: str
    view_start: str
    view_end: str
    context: str
    stresses: tuple
    investigate: str
    blind_spot: str
    indicators: tuple
    source_title: str
    source_url: str
    archive_peak: str = ''

REGIMES = (
    Regime('depression','1929–32 · Depression','The crash and the Depression','Deflation & banking contraction',
        '1929-09-03','1932-07-08','1928-01-01','1933-12-31',
        'The stock-market crash was followed by banking panics and deflation. The economic collapse extended beyond the initial equity selloff.',
        ('Deflation raises the real burden of nominal debt.','Bank runs and credit contraction can amplify lost income.','A rebound during a crisis need not mark the final low.'),
        'Compare industrial production with consumer prices as the equity decline deepens. These charts document transmission into the economy, not a verified advance warning.',
        'Modern unemployment, yield-curve and financial-stress series do not cover this period. The two available macro histories cannot reconstruct the full banking system.',
        ('INDPRO','CPIAUCNS','UNRATE','NFCI'),
        'Federal Reserve History · Great Depression','https://www.federalreservehistory.org/essays/great-depression'),
    Regime('stagflation','1973–74 · Stagflation','Inflation meets weakening growth','Inflation & supply shock',
        '1973-01-11','1974-10-03','1971-01-01','1976-12-31',
        'The Great Inflation combined persistent price pressure with economic weakness. The oil shock intensified the strains during the 1973–74 bear market.',
        ('Inflation erodes real income even when nominal activity grows.','Higher rates pressure housing and long-duration assets.','Weak growth does not guarantee that inflation immediately falls.'),
        'Read inflation, Treasury yields and housing together; then compare production and unemployment. The oil shock is historical context, not a variable directly measured here.',
        'Neither a single inflation level nor an isolated rate increase identifies an equity peak. The archived sample here is limited.',
        ('CPIAUCNS','GS10','HOUST','PERMIT','INDPRO','UNRATE'),
        'Federal Reserve History · Great Inflation','https://www.federalreservehistory.org/essays/great-inflation','1973-01-11'),
    Regime('volcker','1980–82 · Disinflation','The cost of breaking inflation','Policy tightening & recession',
        '1980-01-01','1982-11-30','1978-01-01','1984-12-31',
        'Restrictive monetary policy during the Volcker era brought inflation down while the economy experienced two recessions.',
        ('Restrictive funding costs hit housing and investment.','Falling inflation can coexist with rising unemployment.','A lower inflation rate does not restore the old price level.'),
        'Follow the policy rate, inflation and housing before checking production and unemployment. This interval spans two recessions and is not one continuous equity crash.',
        'The 10-year/2-year spread is a pressure indicator, not a countdown. Rate cuts can arrive while economic losses are still accumulating.',
        ('DFF','CPIAUCNS','HOUST','T10Y2Y','INDPRO','UNRATE'),
        'Federal Reserve History · Recession of 1981–82','https://www.federalreservehistory.org/essays/recession-of-1981-82'),
    Regime('crash1987','1987 · Crash','A crash without a recession signal','Market liquidity & feedback',
        '1987-08-25','1987-12-04','1986-01-01','1989-12-31',
        'The 1987 crash exposed market-structure and liquidity problems. Trading feedback and difficulties meeting liquidity needs helped amplify the price decline.',
        ('Selling strategies can reinforce one another when liquidity disappears.','Rising yields can pressure valuations.','Healthy employment does not rule out a sudden market crash.'),
        'Compare Treasury yields, housing and unemployment with the speed of the equity drawdown. Macro series cannot measure the intraday trading feedback in this episode.',
        'Unemployment was not a crash alarm. Current financial-conditions histories can be reconstructed later and should not be read as contemporaneous trading signals.',
        ('DGS10','UNRATE','PERMIT','INDPRO','NFCI','T10Y3M'),
        'Federal Reserve · History of the 1987 stock-market crash','https://www.federalreserve.gov/pubs/feds/2007/200713/index.html','1987-08-25'),
    Regime('ltcm','1998 · Liquidity','Russia, contagion and LTCM','Leverage & funding shock',
        '1998-07-01','1998-10-31','1997-01-01','1999-12-31',
        'International financial turmoil intensified in 1998. Losses and large leveraged positions brought Long-Term Capital Management close to failure.',
        ('Leverage makes forced selling more likely.','Assets expected to diversify can fall together during liquidation.','A funding crisis can develop without a domestic recession.'),
        'Compare financial-stress indexes and the equity drawdown with claims and unemployment. The domestic macro panel does not measure Russian sovereign risk or LTCM positions.',
        'Broad economic strength can coexist with counterparty distress. A later easing in conditions cannot validate an earlier all-clear.',
        ('STLFSI4','NFCI','T10Y2Y','DFF','IC4WSA','UNRATE'),
        'Federal Reserve History · Near failure of LTCM','https://www.federalreservehistory.org/essays/ltcm-near-failure'),
    Regime('dotcom','2000–02 · Dot-com','Valuations unwind and investment slows','Valuation & investment bust',
        '2000-03-24','2002-10-09','1998-01-01','2004-12-31',
        'The technology boom gave way to falling equity prices and a pullback in business investment. Broader labor weakness emerged as activity slowed.',
        ('Expensive assets can reprice before unemployment rises.','Investment cuts can spread to production and labor demand.','A broad-market benchmark can understate damage to a concentrated technology portfolio.'),
        'Compare both yield curves, temporary-help employment and industrial production. Observe whether labor deterioration leads or follows the equity decline.',
        'Curve measures need not invert at the same time. This panel has no sector valuation or technology earnings data; it cannot establish how expensive the market was.',
        ('T10Y2Y','T10Y3M','TEMPHELPS','INDPRO','IC4WSA','UNRATE'),
        'Federal Reserve · Monetary Policy Report, July 2001','https://www.federalreserve.gov/boarddocs/hh/2001/july/fullreport.htm','2000-03-24'),
    Regime('gfc','2007–09 · Credit crisis','Housing weakness becomes a credit crisis','Housing, leverage & banking',
        '2007-10-09','2009-03-09','2005-01-01','2011-12-31',
        'Residential construction weakened before mortgage losses strained financial institutions. Funding stress and tighter credit then spread through the economy.',
        ('Falling housing activity can impair collateral and credit.','A curve that steepens after inversion may reflect rate cuts during deterioration.','Bank credit tightening can reinforce losses in jobs and spending.'),
        'Start with permits and starts, then the yield curve, lending standards, financial stress and claims. Keep the early housing deterioration separate from later crisis confirmation.',
        'A positive curve or low unemployment near the equity peak did not erase earlier housing weakness. Revised charts alone cannot establish what investors knew.',
        ('PERMIT','HOUST','T10Y2Y','DRTSCILM','STLFSI4','IC4WSA'),
        'Federal Reserve History · Great Recession','https://www.federalreservehistory.org/essays/great-recession-and-its-aftermath','2007-10-09'),
    Regime('euro','2011 · Sovereign stress','Sovereign risk crosses borders','Sovereign debt & contagion',
        '2011-04-01','2011-10-31','2010-01-01','2013-12-31',
        'European sovereign funding pressures and concerns over U.S. fiscal policy and global growth unsettled financial markets in 2011.',
        ('Sovereign exposures can transmit stress through banks.','Foreign funding problems can affect domestic risk appetite.','A U.S. equity correction need not imply a new U.S. recession.'),
        'Compare U.S. financial stress and Treasury yields with production, claims and unemployment. These are transmission indicators; European spreads are not included.',
        'Domestic series alone cannot locate the original foreign shock. No European bank or sovereign exposure is measured by this page.',
        ('STLFSI4','NFCI','GS10','INDPRO','IC4WSA','UNRATE'),
        'Federal Reserve · February 2012 Monetary Policy Report','https://www.federalreserve.gov/publications/annual-report/2011-Monetary-Policy-Report-of-February-2012.htm'),
    Regime('tightening2018','2018 · Tightening','A sharp repricing amid strong employment','Policy & growth repricing',
        '2018-09-01','2018-12-31','2017-01-01','2019-12-31',
        'Financial conditions tightened late in 2018 as risk appetite weakened and investors reassessed growth and policy. Labor-market conditions remained strong.',
        ('Tighter conditions can reprice assets before labor data weakens.','Interest-sensitive housing can provide a different view from payrolls.','A selloff and an economic recession are separate events.'),
        'Compare the policy rate, Treasury curve and housing with financial stress and claims. Evaluate the divergence between market prices and employment.',
        'Strong jobs data is not protection against a valuation adjustment. These charts do not isolate monetary policy from trade or global-growth concerns.',
        ('DFF','T10Y2Y','PERMIT','NFCI','STLFSI4','IC4WSA'),
        'Federal Reserve · February 2019 Monetary Policy Report','https://www.federalreserve.gov/monetarypolicy/2019-02-mpr-part1.htm'),
    Regime('pandemic','2020 · Pandemic','An external shock outruns monthly data','Shutdown & liquidity shock',
        '2020-02-19','2020-03-23','2019-01-01','2021-12-31',
        'The pandemic and shutdowns abruptly interrupted employment and activity. Financial markets deteriorated before monthly economic releases could describe the full disruption.',
        ('An external shock can invalidate an otherwise benign macro picture.','Cash-flow interruption and liquidity demand can reinforce one another.','Claims can respond faster than monthly labor statistics.'),
        'Look at the archived pre-peak readings first, then compare claims, employment and financial stress with the daily equity drawdown.',
        'Low unemployment and calm conditions before the shock were not protection. Later unemployment readings describe the impact, not an advance warning.',
        ('IC4WSA','PAYEMS','UNRATE','STLFSI4','NFCI','T10Y3M'),
        'Federal Reserve · June 2020 Monetary Policy Report','https://www.federalreserve.gov/monetarypolicy/2020-06-mpr-part1.htm','2020-02-19'),
    Regime('inflation2022','2022 · Inflation & rates','Inflation forces a rate reset','Inflation & duration risk',
        '2021-11-08','2022-10-14','2020-01-01','2023-12-31',
        'Elevated inflation and a shift toward tighter monetary policy pushed Treasury yields higher and changed the discount-rate environment for financial assets.',
        ('Rising yields pressure long-duration bond and equity values.','Inflation can weaken purchasing power while nominal wages or sales rise.','Traditional stock/bond diversification can be less helpful during a rate shock.'),
        'Compare inflation, the policy rate and Treasury yields; then inspect housing and both curves. The broad-market benchmark used here begins this stress window in late 2021.',
        'A yield curve still above zero did not rule out a rate-driven equity selloff. There is no bond total-return series here; yields alone do not measure realized bond losses.',
        ('CPIAUCNS','PCEPI','DFF','DGS10','PERMIT','T10Y2Y'),
        'Federal Reserve · June 2022 Monetary Policy Report','https://www.federalreserve.gov/monetarypolicy/2022-06-mpr-part1.htm','2021-11-08'),
    Regime('banks2023','2023 · Bank runs','Bond losses meet rapid withdrawals','Bank funding & concentration',
        '2023-03-01','2023-05-31','2022-01-01','2024-12-31',
        'Silicon Valley Bank exposed the interaction of interest-rate risk, concentrated uninsured deposits and inadequate liquidity management. Stress spread to other banks.',
        ('Long-maturity assets and runnable funding can create a dangerous mismatch.','Depositor concentration can accelerate a run.','A contained broad-market drawdown can hide severe sector losses.'),
        'Compare the preceding rise in rates with financial stress, bank lending standards and commercial loans. Bank-specific balance sheets and deposit flows are outside this dataset.',
        'Broad-market returns do not measure regional-bank losses. Aggregate financial indexes and lending data cannot detect a particular bank’s solvency or liquidity needs.',
        ('DFF','DGS10','T10Y2Y','STLFSI4','DRTSCILM','BUSLOANS'),
        'Federal Reserve · SVB review, April 2023','https://www.federalreserve.gov/publications/2023-april-svb-executive-summary.htm'),
)
BY_REGIME = {r.id:r for r in REGIMES}
DEFAULT_REGIME = 'gfc'
