from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import requests
import os

app = FastAPI()

# Allow all origins (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

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
    political_risk: str
    news_sentiment: str
    target_diff: float
    pe_comment: str
    target_comment: str
    recommendation_reason: str
    trend_comment: str
    recent_headlines: list[str]
    eps_comment: str
    dividend_comment: str
    market_cap_comment: str

def fetch_news_sentiment(ticker: str) -> tuple[str, str, list[str]]:
    if not NEWS_API_KEY:
        return "No API Key", "Unknown", []

    url = (
        f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&apiKey={NEWS_API_KEY}&language=en"
    )
    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])[:5]
        headlines = [a.get("title", "") for a in articles]
        sentiment_score = sum(
            1 if any(word in h.lower() for word in ["beat", "surge", "strong"]) else -1
            for h in headlines
        )
        sentiment = "Positive" if sentiment_score > 0 else "Negative" if sentiment_score < 0 else "Neutral"

        political_keywords = ["china", "regulation", "ban", "sanction", "government"]
        joined_headlines = " ".join(headlines).lower()
        political_flags = [k for k in political_keywords if k in joined_headlines]
        risk_summary = ", ".join(political_flags).capitalize() if political_flags else "None"

        return risk_summary, sentiment, headlines
    except Exception:
        return "Error fetching news", "Unknown", []

def analyze_stock(ticker: str):
    stock = yf.Ticker(ticker)
    info = stock.info

    try:
        current_price = info.get("currentPrice")
        target_price = info.get("targetMeanPrice") or 0.0
        pe_ratio = info.get("trailingPE") or 0.0
        eps = info.get("trailingEps") or 0.0
        dividend_yield = (info.get("dividendYield") or 0.0) * 100
        market_cap_raw = info.get("marketCap")
        market_cap = f"{market_cap_raw / 1e12:.2f}T" if market_cap_raw >= 1e12 else f"{market_cap_raw / 1e9:.2f}B" if market_cap_raw else "N/A"
        name = info.get("shortName") or ticker.upper()

        target_diff = ((target_price - current_price) / current_price) * 100 if current_price else 0

        history = stock.history(period="1mo")
        if len(history) > 0:
            change = ((history["Close"].iloc[-1] - history["Close"].iloc[0]) / history["Close"].iloc[0]) * 100
            trend_comment = f"Stock {'rose' if change > 0 else 'fell'} {abs(change):.1f}% over the past month."
        else:
            trend_comment = "No trend data available."

        if pe_ratio < 15:
            pe_comment = "Low – possibly undervalued"
        elif pe_ratio <= 25:
            pe_comment = "Moderate – fair value"
        else:
            pe_comment = "High – possibly overvalued"

        target_comment = f"Analysts expect {target_diff:.1f}% upside." if target_diff > 0 else f"Target is {abs(target_diff):.1f}% below current price."

        eps_comment = "High earnings performance" if eps > 5 else "Moderate earnings" if eps > 1 else "Low earnings"
        dividend_comment = "High income potential" if dividend_yield > 4 else "Moderate yield" if dividend_yield > 1 else "Low or no dividend"
        market_cap_comment = "Large-cap stability" if market_cap_raw >= 200e9 else "Mid-cap company" if market_cap_raw >= 10e9 else "Small-cap risk"

        political_risk, news_sentiment, headlines = fetch_news_sentiment(ticker)

        if pe_ratio < 15 and eps > 0 and news_sentiment == "Positive":
            recommendation = "Buy"
            recommendation_reason = "Strong earnings, good valuation, and positive sentiment."
        elif 15 <= pe_ratio <= 25 and news_sentiment == "Neutral":
            recommendation = "Hold"
            recommendation_reason = "Stable financials and neutral political impact."
        else:
            recommendation = "Sell"
            recommendation_reason = "Weak sentiment or overvaluation. Political factors: " + political_risk

        return StockResponse(
            symbol=ticker.upper(),
            name=name,
            current_price=current_price,
            target_price=target_price,
            pe_ratio=pe_ratio,
            eps=eps,
            dividend_yield=dividend_yield,
            market_cap=market_cap,
            recommendation=recommendation,
            political_risk=political_risk,
            news_sentiment=news_sentiment,
            target_diff=round(target_diff, 2),
            pe_comment=pe_comment,
            target_comment=target_comment,
            recommendation_reason=recommendation_reason,
            trend_comment=trend_comment,
            recent_headlines=headlines,
            eps_comment=eps_comment,
            dividend_comment=dividend_comment,
            market_cap_comment=market_cap_comment
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")

@app.get("/stock/{ticker}", response_model=StockResponse)
def get_stock(ticker: str):
    return analyze_stock(ticker)