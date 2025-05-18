# app/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import numpy as np
import traceback

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StockResponse(BaseModel):
    symbol: str
    name: str
    current_price: float
    target_price: float
    pe_ratio: float
    eps: float
    dividend_yield: float
    market_cap: str
    recommendation: str
    target_diff: float
    pe_comment: str
    target_comment: str
    recommendation_reason: str
    trend_comment: str
    eps_comment: str
    dividend_comment: str
    market_cap_comment: str
    kpi_summary: str
    support_level: str
    resistance_level: str
    next_earnings: str
    next_dividend: str

    # added fundamental metrics
    revenue_yoy: float
    fcf: float
    debt_to_equity: float
    roe: float
    ev_ebitda: float

    # added technical metrics
    ma50: float
    ma200: float
    beta: float
    rsi: float
    volatility: float
    var: float
    drawdown: float

@app.api_route("/stock/{ticker}", methods=["GET", "HEAD"], response_model=StockResponse)
async def get_stock(ticker: str, request: Request):
    if request.method == "HEAD":
        return {}
    return analyze_stock(ticker)

def grade_metric(value: float, good: float, bad: float) -> str:
    if value >= good:
        return "🟢"
    elif value <= bad:
        return "🔴"
    else:
        return "🟡"

def summarize_kpis(pe, eps, div, pb, debt, roe):
    return "\n".join([
        f"{grade_metric(pe, 15, 25)} P/E Ratio: {pe} → Lower = cheaper. Ideal: under 20–25, sector-relative.",
        f"{grade_metric(eps, 5, 1)} EPS: {eps} → Company profit per share.",
        f"{grade_metric(div, 3, 1)} Annual Dividend Yield: {div:.2f}% → Passive income return.",
        f"{grade_metric(pb, 1.5, 3)} Price/Book: {pb} → Asset value vs. market value.",
        f"{grade_metric(debt, 0.5, 1)} Debt/Equity: {debt} → Lower = less risk.",
        f"{grade_metric(roe, 15, 5)} Return on Equity: {roe:.2f}% → Profitability efficiency."
    ])

def find_support_resistance(stock: yf.Ticker):
    history = stock.history(period="6mo")
    if history.empty:
        return "N/A", "N/A"

    low52 = history["Close"].min()
    high52 = history["Close"].max()
    return f"${low52:.2f}", f"${high52:.2f}"

def compute_rsi(arr: np.ndarray, period: int = 14) -> float:
    deltas = np.diff(arr)
    ups = np.maximum(deltas, 0)
    downs = -np.minimum(deltas, 0)
    roll_up = ups[-period:].mean() if len(ups) >= period else 0.0
    roll_down = downs[-period:].mean() if len(downs) >= period else 1.0
    rs = roll_up / roll_down if roll_down else 0.0
    return 100 - (100 / (1 + rs))

def analyze_stock(ticker: str) -> StockResponse:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        symbol = ticker.upper()

        # Core fields
        name = info.get("shortName", symbol)
        current_price = info.get("currentPrice", 0.0)
        target_price = info.get("targetMeanPrice", 0.0)
        target_diff = ((target_price - current_price) / current_price * 100) if current_price else 0.0

        pe = info.get("trailingPE", 0.0)
        eps = info.get("trailingEps", 0.0)

        # --- NEW: Separate forward dividend & yield ---
        forward_div = info.get("dividendRate", 0.0)           # e.g. 1.04 $/share
        div_yield   = info.get("dividendYield", 0.0)          # e.g. 0.0049 or 0.49

        investment        = 10_000
        shares_bought     = investment / current_price if current_price else 0
        income_from_rate  = shares_bought * forward_div
        income_from_yield = investment * div_yield

        if forward_div > 0 or div_yield > 0:
            dividend_comment = (
                f"Forward Dividend: ${forward_div:.2f}/share → "
                f"${income_from_rate:,.2f}/year on ${investment:,}\n"
                f"Dividend Yield: {div_yield:.2f}% → "
                f"${income_from_yield:,.2f}/year on ${investment:,}"
            )
        else:
            dividend_comment = "No dividend"

        cap_raw = info.get("marketCap", 0.0)
        market_cap = (
            f"{cap_raw/1e12:.2f}T" if cap_raw >= 1e12 else
            f"{cap_raw/1e9:.2f}B"  if cap_raw >= 1e9  else
            f"{cap_raw/1e6:.2f}M"  if cap_raw > 0     else
            "N/A"
        )

        # Fundamental metrics
        revenue_yoy    = (info.get("revenueGrowth") or 0.0) * 100
        fcf            = info.get("freeCashflow", 0.0) or 0.0
        debt_to_equity = info.get("debtToEquity", 0.0)
        roe            = (info.get("returnOnEquity") or 0.0) * 100
        ev_ebitda      = info.get("enterpriseToEbitda", 0.0)

        # Fundamental comments
        revenue_comment   = "Healthy growth" if revenue_yoy > 10 else "Moderate growth"
        fcf_comment       = "Positive FCF" if fcf > 0 else "Negative / N/A"
        debt_comment      = "Low leverage" if debt_to_equity < 1 else "High leverage"
        roe_comment       = "Efficient" if roe > 15 else "Moderate"
        ev_ebitda_comment = "Cheap EV/EBITDA" if ev_ebitda < 10 else "Expensive"

        # Comments
        pe_comment         = "Low – undervalued" if pe < 15 else "Moderate – fair value" if pe <= 25 else "High – overvalued"
        eps_comment        = "Strong earnings" if eps > 5 else "Moderate" if eps > 1 else "Weak or negative"
        market_cap_comment = (
            "Large cap" if cap_raw >= 200e9 else
            "Mid cap"   if cap_raw >= 10e9  else
            "Small cap"
        )
        target_comment     = f"Analysts expect {target_diff:.1f}% upside." if target_diff > 0 else f"{abs(target_diff):.1f}% downside potential."
        recommendation     = "Buy" if pe < 15 and eps > 0 else "Hold" if pe <= 25 else "Sell"

        # Recommendation reason & KPI summary
        recommendation_reason = "\n".join([
            f"{grade_metric(pe, 15, 25)} P/E: {pe_comment}",
            f"{grade_metric(eps, 5, 1)} EPS: {eps_comment}",
            f"{grade_metric(div_yield, 3, 1)} Div: {dividend_comment}"
        ])
        pb = info.get("priceToBook", 0.0)
        kpi_summary = summarize_kpis(pe, eps, div_yield, pb, debt_to_equity, roe)

        # Next dates
        next_earnings = info.get("earningsTimestamp", None)
        next_dividend = info.get("exDividendDate", None)

        # Historical for trend & technicals
        hist = stock.history(period="1y")["Close"]
        def pct_change(n):
            return ((hist.iloc[-1] - hist.iloc[-n]) / hist.iloc[-n] * 100) if len(hist) >= n else 0.0
        trend_comment = (
            f"Weekly: {'Up' if pct_change(7)>0 else 'Down'} {abs(pct_change(7)):.1f}% | "
            f"Monthly: {'Up' if pct_change(30)>0 else 'Down'} {abs(pct_change(30)):.1f}% | "
            f"Yearly: {'Up' if pct_change(len(hist))>0 else 'Down'} {abs(pct_change(len(hist))):.1f}%"
        )

        # Technicals
        ma50       = float(hist.rolling(50).mean().iloc[-1])   if len(hist)>=50  else 0.0
        ma200      = float(hist.rolling(200).mean().iloc[-1])  if len(hist)>=200 else 0.0
        beta       = info.get("beta", 0.0)
        rsi        = compute_rsi(hist.values) if len(hist)>=15 else 0.0
        rets       = hist.pct_change().dropna()
        volatility = float(rets.std() * np.sqrt(252) * 100)
        var        = float(np.percentile(rets, 5) * 100)
        drawdown   = float((hist / hist.cummax() - 1).min() * 100)

        support, resistance = find_support_resistance(stock)

        return StockResponse(
            symbol=symbol,
            name=name,
            current_price=current_price,
            target_price=target_price,
            pe_ratio=pe,
            eps=eps,
            dividend_yield=div_yield,
            market_cap=market_cap,
            recommendation=recommendation,
            target_diff=round(target_diff, 2),
            pe_comment=pe_comment,
            target_comment=target_comment,
            recommendation_reason=recommendation_reason,
            trend_comment=trend_comment,
            eps_comment=eps_comment,
            dividend_comment=dividend_comment,
            market_cap_comment=market_cap_comment,
            kpi_summary=kpi_summary,
            support_level=support,
            resistance_level=resistance,
            next_earnings=str(next_earnings) if next_earnings else "Not announced",
            next_dividend=str(next_dividend) if next_dividend else "N/A",
            revenue_yoy=round(revenue_yoy, 2),
            fcf=round(fcf, 2),
            debt_to_equity=round(debt_to_equity, 2),
            roe=round(roe, 2),
            ev_ebitda=round(ev_ebitda, 2),
            ma50=round(ma50, 2),
            ma200=round(ma200, 2),
            beta=round(beta, 2),
            rsi=round(rsi, 2),
            volatility=round(volatility, 2),
            var=round(var, 2),
            drawdown=round(drawdown, 2),
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {e}")
