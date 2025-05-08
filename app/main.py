from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import requests
import os
from transformers import pipeline
from collections import Counter
import pandas as pd
import traceback

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

# Initialize a transformer pipeline for sentiment analysis
sentiment_analysis = pipeline(
    "sentiment-analysis",
    model="distilbert/distilbert-base-uncased-finetuned-sst-2-english",
    revision="714eb0f"
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


@app.api_route("/stock/{ticker}", methods=["GET", "HEAD"], response_model=StockResponse)
async def get_stock(ticker: str, request: Request):
    if request.method == "HEAD":
        return {}  # Return empty for HEAD request (only headers)
    return analyze_stock(ticker)


# COMPLETELY REWRITTEN TO AVOID TUPLE UNPACKING ISSUES
def get_news_sentiment(ticker: str):
    """
    Get news sentiment and headlines for a stock ticker.
    Returns a dictionary instead of a tuple to avoid unpacking errors.
    """
    default_response = {
        "political_risk": "No significant political risk detected.",
        "sentiment": "Unknown",
        "headlines": []
    }

    if not NEWS_API_KEY:
        return default_response

    try:
        url = f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&apiKey={NEWS_API_KEY}&language=en&pageSize=20"
        response = requests.get(url)
        if response.status_code != 200:
            return default_response

        data = response.json()
        articles = data.get("articles", [])

        if not articles:
            return default_response

        # Extract headlines
        headlines = []
        for a in articles:
            if a.get("title"):
                headlines.append(a.get("title", ""))

        # Calculate sentiment
        pos_count = 0
        neg_count = 0

        for headline in headlines:
            if not headline.strip():
                continue

            try:
                result = sentiment_analysis(headline)
                if result and result[0]["label"] == "POSITIVE":
                    pos_count += 1
                else:
                    neg_count += 1
            except:
                continue

        # Determine overall sentiment
        if pos_count > neg_count:
            sentiment = "Positive"
        elif neg_count > pos_count:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        # Calculate political risk
        political_risk = "No significant political risk detected."
        if neg_count > pos_count * 2:  # Simple heuristic
            political_risk = "Negative political sentiment detected."

        return {
            "political_risk": political_risk,
            "sentiment": sentiment,
            "headlines": headlines[:10]  # Limit to 10
        }

    except Exception as e:
        print(f"News API error: {str(e)}")
        return default_response


def analyze_stock(ticker: str):
    """Completely rewritten to avoid tuple unpacking issues"""
    try:
        # Get stock data
        stock = yf.Ticker(ticker)
        info = stock.info

        # Basic stock info with defaults
        name = info.get("shortName", ticker.upper())
        current_price = info.get("currentPrice", 0.0) or 0.0
        target_price = info.get("targetMeanPrice", 0.0) or 0.0
        pe_ratio = info.get("trailingPE", 0.0) or 0.0
        eps = info.get("trailingEps", 0.0) or 0.0
        dividend_yield = (info.get("dividendYield", 0.0) or 0.0) * 100
        market_cap_raw = info.get("marketCap", 0) or 0

        # Format market cap
        if market_cap_raw >= 1e12:
            market_cap = f"{market_cap_raw / 1e12:.2f}T"
        elif market_cap_raw >= 1e9:
            market_cap = f"{market_cap_raw / 1e9:.2f}B"
        else:
            market_cap = f"{market_cap_raw / 1e6:.2f}M" if market_cap_raw > 0 else "N/A"

        # Calculate target difference
        target_diff = ((target_price - current_price) / current_price) * 100 if current_price > 0 else 0

        # Get price history
        history = stock.history(period="1y")

        # Price trends - safely calculate
        weekly_change = 0
        monthly_change = 0
        yearly_change = 0

        if not history.empty and len(history) >= 7:
            weekly_change = ((history["Close"].iloc[-1] - history["Close"].iloc[-7]) / history["Close"].iloc[-7]) * 100

        if not history.empty and len(history) >= 30:
            monthly_change = ((history["Close"].iloc[-1] - history["Close"].iloc[-30]) / history["Close"].iloc[
                -30]) * 100

        if not history.empty and len(history) >= 2:
            yearly_change = ((history["Close"].iloc[-1] - history["Close"].iloc[0]) / history["Close"].iloc[0]) * 100

        # Format trend comments
        trend_comment = f"Weekly trend: {'Up' if weekly_change > 0 else 'Down'} {abs(weekly_change):.1f}%\n"
        trend_comment += f"Monthly trend: {'Up' if monthly_change > 0 else 'Down'} {abs(monthly_change):.1f}%\n"
        trend_comment += f"Yearly trend: {'Up' if yearly_change > 0 else 'Down'} {abs(yearly_change):.1f}%"

        # Analysis comments
        pe_comment = "Low – undervalued: cheaper vs earnings" if pe_ratio < 15 else \
            "Moderate – fair value" if pe_ratio <= 25 else \
                "High – overvalued: expensive vs earnings"

        eps_comment = "High – strong profitability" if eps > 5 else \
            "Moderate – some profit" if eps > 1 else \
                "Low – weak profit/losses"

        dividend_comment = "High – good passive income" if dividend_yield > 4 else \
            "Moderate – some dividends" if dividend_yield > 1 else \
                "Low – no dividend income"

        market_cap_comment = "Large – stable company" if market_cap_raw >= 200e9 else \
            "Mid – medium size" if market_cap_raw >= 10e9 else \
                "Small – higher risk"

        target_comment = f"Analysts expect {target_diff:.1f}% upside." if target_diff > 0 else \
            f"Target is {abs(target_diff):.1f}% below current price."

        # Get news data - NO TUPLE UNPACKING
        news_data = get_news_sentiment(ticker)
        political_risk = news_data["political_risk"]
        news_sentiment = news_data["sentiment"]
        headlines = news_data["headlines"]

        # Determine recommendation
        recommendation = "Buy" if pe_ratio < 15 and eps > 0 and news_sentiment == "Positive" else \
            "Hold" if 15 <= pe_ratio <= 25 and news_sentiment == "Neutral" else \
                "Sell"

        # Build recommendation reasons
        recommendation_items = []

        def add_recommendation_item(label, value, category):
            color = "🟩" if category.lower() not in ["high", "negative", "ban", "low"] else "🟥"
            recommendation_items.append(f"- {color} **{label}:** {value}")

        add_recommendation_item("P/E Insight", pe_comment, pe_comment.split(" – ")[0] if " – " in pe_comment else "")
        add_recommendation_item("Earnings", eps_comment, eps_comment.split(" – ")[0] if " – " in eps_comment else "")
        add_recommendation_item("Political Risk", political_risk, political_risk)
        add_recommendation_item("Sentiment", news_sentiment, news_sentiment)

        recommendation_reason = "\n".join(recommendation_items)

        # Return complete response
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
        # Full error traceback for debugging
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing data: {str(e)}")
