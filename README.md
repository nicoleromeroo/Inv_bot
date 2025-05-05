# Bachelor Thesis: Investment GPT API

## Project Title

Investment Recommendation Chatbot with Financial and Political Context

## Purpose

This backend was developed as part of a bachelor thesis in Business Informatics. It serves as the foundation for a GPT-powered investment assistant capable of retrieving, analyzing, and explaining stock data. The application aims to reduce the research effort required by individual users and provide structured, data-driven investment insights.

## Technology Stack

* Language: Python 3
* Framework: FastAPI
* Financial Data: yfinance
* News Sentiment: NewsAPI (via REST)
* Deployment: Render.com
* Frontend: Custom GPT (OpenAI Assistants API)

## Features

### /stock/{ticker} Endpoint

Returns enhanced stock analysis including:

* Real-time financial metrics: P/E Ratio, EPS, Dividend Yield, Market Capitalization
* Target Price difference and recent trend analysis
* Political risk factors and current news sentiment
* Recommendation based on combined factors: Buy, Hold, or Sell

## File Overview

| File             | Description                                                            |
| ---------------- | ---------------------------------------------------------------------- |
| main.py          | Contains FastAPI routes, data processing logic, and analysis functions |
| requirements.txt | Defines the required Python dependencies                               |
| .env             | Stores environment variables such as the NewsAPI key                   |

## Local Deployment

Clone the repository and run the service locally:

```bash
git clone https://github.com/YOUR_USERNAME/Inv_bot.git
cd Inv_bot
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then access the application at:

```
http://127.0.0.1:8000/stock/AAPL
```

## Deployment on Render

The application is deployed via Render.com and is publicly accessible at:

```
https://inv-bot.onrender.com/stock/{ticker}
```

Deployment is integrated with GitHub for continuous deployment upon push.

## Integration with GPT

The backend is used by a custom GPT through the OpenAI Assistants API. The GPT:

* Sends a GET request to `/stock/{ticker}` to retrieve analysis
* Displays results in a structured, user-friendly markdown format

Output includes:

* Structured Key Metrics Table
* Analysis Summary with trend, valuation, and risk assessment
* Final Recommendation with brief rationale

## Validated Use Cases

* Stock analysis requests (e.g., "Analyze AAPL")
* Political influence recognition (e.g., companies impacted by China regulations)
* Input error handling (e.g., invalid or unknown tickers)

## Example API Responses

### Request:

```
GET /stock/AAPL
```

### Sample Response:

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "current_price": 205.35,
  "target_price": 233.36,
  "pe_ratio": 31.93,
  "eps": 6.43,
  "dividend_yield": 51.0,
  "market_cap": "3.07T",
  "recommendation": "Sell",
  "political_risk": "None",
  "news_sentiment": "Negative",
  "target_diff": 13.64,
  "pe_comment": "High – overvalued: expensive vs earnings",
  "target_comment": "Analysts expect 13.6% upside.",
  "recommendation_reason": "- P/E Insight: High – overvalued: expensive vs earnings\n- Earnings: High – strong profitability\n- Political Risk: None\n- Sentiment: Negative",
  "trend_comment": "Stock rose 5.4% over the past month.",
  "recent_headlines": ["Apple launches new iPhone", "Weak demand in China"],
  "eps_comment": "High – strong profitability",
  "dividend_comment": "High – good passive income",
  "market_cap_comment": "Large – stable company"
}
```

## System Architecture Overview

The diagram below describes how the overall system components interact:

1. **User** interacts via GPT chat interface.
2. **GPT** sends HTTP requests to the FastAPI backend.
3. **FastAPI** processes ticker via `yfinance`, retrieves news using NewsAPI.
4. Backend logic generates a structured response with recommendation.
5. GPT formats and presents the information to the user.

```
User → GPT → FastAPI (→ yfinance, NewsAPI) → Response → GPT → User
```

## For Thesis Documentation

The API and assistant are documented with:

* Technical implementation overview
* Sample requests and responses
* Integration demonstration with GPT
* User testing and feedback evaluation
* Potential extensions such as ETF analysis and advanced comparisons

## Author Information

Author: Nicole Romero

Institution: Hochschule München (HM)

Supervisor: Prof. Dr. Silja Grawert

## Acknowledgements

This project builds upon open source contributions from the yfinance community, NewsAPI, and FastAPI framework.
