# app/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
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

    closes = history["Close"].round(-1)
    price_counts = closes.value_counts().sort_index()

    midpoint = len(price_counts) // 2
    support = price_counts.iloc[:midpoint].idxmax()
    resistance = price_counts.iloc[midpoint:].idxmax()
    return f"${support}", f"${resistance}"

def analyze_stock(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        name = info.get("shortName", ticker.upper())
        current_price = info.get("currentPrice", 0.0)
        target_price = info.get("targetMeanPrice", 0.0)
        pe = info.get("trailingPE", 0.0)
        eps = info.get("trailingEps", 0.0)

        div = round(info.get("dividendYield", 0.0), 4)

        cap_raw = info.get("marketCap", 0.0)
        market_cap = (
            f"{cap_raw / 1e12:.2f}T" if cap_raw >= 1e12 else
            f"{cap_raw / 1e9:.2f}B" if cap_raw >= 1e9 else
            f"{cap_raw / 1e6:.2f}M" if cap_raw > 0 else "N/A"
        )

        target_diff = ((target_price - current_price) / current_price) * 100 if current_price else 0

        history = stock.history(period="1y")
        weekly = monthly = yearly = 0.0
        if len(history) >= 7:
            weekly = ((history["Close"][-1] - history["Close"][-7]) / history["Close"][-7]) * 100
        if len(history) >= 30:
            monthly = ((history["Close"][-1] - history["Close"][-30]) / history["Close"][-30]) * 100
        if len(history) >= 2:
            yearly = ((history["Close"][-1] - history["Close"][0]) / history["Close"][0]) * 100

        trend_comment = (
            f"Weekly: {'Up' if weekly > 0 else 'Down'} {abs(weekly):.1f}% | "
            f"Monthly: {'Up' if monthly > 0 else 'Down'} {abs(monthly):.1f}% | "
            f"Yearly: {'Up' if yearly > 0 else 'Down'} {abs(yearly):.1f}%"
        )

        pe_comment = (
            "Low – undervalued (Value Buy)" if pe < 15 else
            "Moderate – fair value" if pe <= 25 else
            "High – overvalued (Caution)"
        )

        eps_comment = "Strong earnings" if eps > 5 else "Moderate" if eps > 1 else "Weak or negative"
        if div > 0:
            annual_income = div * 10000
            monthly_income = annual_income / 12
            dividend_comment = (
                f"Dividend Yield: {div:.2f}% — with $10.000 investment, approx. ${monthly_income:.2f}/month or ${annual_income:.2f}/year"
            )
        else:
            dividend_comment = "No dividend paid"
        market_cap_comment = (
            "Large cap – stable" if cap_raw >= 200e9 else
            "Mid cap – balanced" if cap_raw >= 10e9 else
            "Small cap – higher risk"
        )
        target_comment = (
            f"Analysts expect {target_diff:.1f}% upside." if target_diff > 0
            else f"{abs(target_diff):.1f}% downside potential."
        )

        recommendation = "Buy" if pe < 15 and eps > 0 else "Hold" if 15 <= pe <= 25 else "Sell"

        pb = info.get("priceToBook", 0.0)
        debt = info.get("debtToEquity", 0.0)
        roe = (info.get("returnOnEquity") or 0.0) * 100

        next_earnings = info.get("earningsTimestamp", None)
        next_dividend = info.get("exDividendDate", None)

        recommendation_reason = "\n".join([
            f"{grade_metric(pe, 15, 25)} P/E Insight: {pe_comment}",
            f"{grade_metric(eps, 5, 1)} EPS Analysis: {eps_comment}",
            f"{grade_metric(div, 3, 1)} Annual Dividend Overview: {dividend_comment}"
        ])

        kpi_summary = summarize_kpis(pe, eps, div, pb, debt, roe)
        support, resistance = find_support_resistance(stock)

        return StockResponse(
            symbol=ticker.upper(),
            name=name,
            current_price=current_price,
            target_price=target_price,
            pe_ratio=pe,
            eps=eps,
            dividend_yield=div,
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
            next_dividend=str(next_dividend) if next_dividend else "N/A"
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")