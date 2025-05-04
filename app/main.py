# app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()
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

NEWS_API_KEY = os.getenv("NEWS_API_KEY")  # Add your key to .env or system env

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


def fetch_news_sentiment(ticker: str) -> tuple[str, str]:
    if not NEWS_API_KEY:
        return "No API Key", "Unknown"

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

        # Example of keyword flagging
        political_keywords = ["china", "regulation", "ban", "sanction", "government"]
        joined_headlines = " ".join(headlines).lower()
        political_flags = [k for k in political_keywords if k in joined_headlines]
        risk_summary = ", ".join(political_flags).capitalize() if political_flags else "None"

        return risk_summary, sentiment
    except Exception:
        return "Error fetching news", "Unknown"


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
        market_cap = f"{market_cap_raw / 1e9:.2f}B" if market_cap_raw else "N/A"
        name = info.get("shortName") or ticker.upper()

        if pe_ratio < 15 and eps > 0:
            recommendation = "Buy"
        elif 15 <= pe_ratio <= 25:
            recommendation = "Hold"
        else:
            recommendation = "Sell"

        political_risk, news_sentiment = fetch_news_sentiment(ticker)

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
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")


@app.get("/stock/{ticker}", response_model=StockResponse)
def get_stock(ticker: str):
    return analyze_stock(ticker)
