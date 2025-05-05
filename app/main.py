from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yfinance as yf
import requests
import os
from transformers import pipeline
from collections import Counter

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
sentiment_analysis = pipeline("sentiment-analysis")


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


def fetch_news_sentiment(ticker: str) -> tuple[str, str, list[str]]:
    if not NEWS_API_KEY:
        return "No API Key", "Unknown", []

    url = (
        f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&apiKey={NEWS_API_KEY}&language=en&pageSize=50"
    )
    try:
        response = requests.get(url)
        articles = response.json().get("articles", [])
        headlines = [a.get("title", "") for a in articles]

        # Use sentiment analysis on each article to determine sentiment
        sentiment_score = sum(
            1 if sentiment_analysis(headline)[0]['label'] == 'POSITIVE' else -1 for headline in headlines
        )
        sentiment = "Positive" if sentiment_score > 0 else "Negative" if sentiment_score < 0 else "Neutral"

        # Using NLP to analyze political context (no keywords, full analysis of the articles)
        political_context = analyze_political_risk(articles)

        return political_context, sentiment, headlines
    except Exception as e:
        return "Error fetching news", "Unknown", []


def analyze_political_risk(articles: list) -> str:
    """
    Analyzes political risk based on the headlines and article content.
    We use NLP techniques to extract the political state.
    """
    political_issues = []

    # Extract content from articles and analyze using sentiment analysis or topic modeling
    for article in articles:
        title = article.get("title", "")
        description = article.get("description", "")
        content = title + " " + description

        # Use sentiment analysis or classify the content based on topics
        sentiment_result = sentiment_analysis(content)
        sentiment = sentiment_result[0]['label']

        if sentiment == 'NEGATIVE':
            political_issues.append("Negative political sentiment detected.")

    # Deduplicate and summarize
    political_counter = Counter(political_issues)
    summarized_political_risk = "\n".join([f"- {item}" for item, count in political_counter.items()])

    return summarized_political_risk or "No significant political risk detected."


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
            pe_comment = "Low – undervalued: cheaper vs earnings"
        elif pe_ratio <= 25:
            pe_comment = "Moderate – fair value"
        else:
            pe_comment = "High – overvalued: expensive vs earnings"

        target_comment = f"Analysts expect {target_diff:.1f}% upside." if target_diff > 0 else f"Target is {abs(target_diff):.1f}% below current price."

        eps_comment = "High – strong profitability" if eps > 5 else "Moderate – some profit" if eps > 1 else "Low – weak profit/losses"
        dividend_comment = "High – good passive income" if dividend_yield > 4 else "Moderate – some dividends" if dividend_yield > 1 else "Low – no dividend income"
        market_cap_comment = "Large – stable company" if market_cap_raw >= 200e9 else "Mid – medium size" if market_cap_raw >= 10e9 else "Small – higher risk"

        political_risk, news_sentiment, headlines = fetch_news_sentiment(ticker)

        if pe_ratio < 15 and eps > 0 and news_sentiment == "Positive":
            recommendation = "Buy"
        elif 15 <= pe_ratio <= 25 and news_sentiment == "Neutral":
            recommendation = "Hold"
        else:
            recommendation = "Sell"

        def color_text(label: str, value: str, sentiment: str) -> str:
            color = "🟥" if sentiment.lower() in ["high", "negative", "ban"] else "🟩"
            return f"- {color} **{label}:** {value}"

        recommendation_reason = "\n".join([
            color_text("P/E Insight", pe_comment, pe_comment.split(" – ")[0]),
            color_text("Earnings", eps_comment, eps_comment.split(" – ")[0]),
            color_text("Political Risk", political_risk, political_risk),
            color_text("Sentiment", news_sentiment, news_sentiment)
        ])

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
