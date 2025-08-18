# Stocks REST API 

This project implements a **Python REST API** for retrieving and managing stock data.
It aggregates data from two sources:

* **Polygon.io** (Daily Open/Close stock data)
* **MarketWatch** (scraped performance data)

The API also allows users to **track positions** in stocks with simple `LONG / SHORT / NEUTRAL` logic.

Built with **FastAPI**, **httpx (async)**, and **BeautifulSoup**. Includes **unit tests (157)** and a **Dockerfile**.

---

## 📌 Features

* **GET /stock/{symbol}** → Returns combined stock data (Polygon + MarketWatch + tracked amount)
* **POST /stock/{symbol}** → Updates stock position (buy/sell) and returns current amount with LONG/SHORT/NEUTRAL status

### Stock Model (as required in assignment)

Each stock contains:

* `afterHours: float`
* `close: float`
* `from: str`
* `high: float`
* `low: float`
* `open: float`
* `preMarket: float`
* `status: str`
* `symbol: str`
* `volume: int`
* `performance: dict` (scraped from MarketWatch under "PERFORMANCE")
* `amount: int` (user-tracked, default `0`)

---

## ⚙️ Setup & Installation

Before running the project, you must create a **`.env` file** in the project root containing your Polygon.io API key and HTTP client settings:

```bash
POLYGON_API_KEY=your_key_here
HTTP_TIMEOUT_SECONDS=10.0
HTTP_MAX_RETRIES=2
```

You can then run the project in **two different ways**: either with a **Local Setup** or using **Docker**.

### Option 1: Local Setup

#### Requirements

* Python **3.12+**
* Polygon.io API key

#### Steps

```bash
# 1. Clone repo & install dependencies
pip install -r requirements.txt

# 2. Ensure .env is in project root
# 3. Run API
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Option 2: Docker Setup

```bash
docker build -t stocks-api .

docker run --rm -p 8000:8000 stocks-api
```

---

## Accessing the API

Now visit:

* Swagger UI → [http://localhost:8000/docs](http://localhost:8000/docs)

* ReDoc → [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🚀 Usage Examples

**Get stock data (latest trading day):**

```bash
curl http://localhost:8000/stock/AAPL
```

**Get stock data for a specific date:**

```bash
curl "http://localhost:8000/stock/AAPL?date=2024-01-15"
```

**Update stock position:**

```bash
curl -X POST http://localhost:8000/stock/AAPL      -H "Content-Type: application/json"      -d '{"amount": 5}'
```

Response example:

```json
{
  "symbol": "AAPL",
  "final_amount": 5,
  "action": "LONG"
}
```

---

## 🧪 Testing

Run all tests:

```bash
pytest -v
```

Run with coverage:

```bash
pytest --cov=.
```

Tests cover:

* Stock service & controller logic
* Polygon + MarketWatch data providers (mocked)
* Logging & error handling
* Async/concurrency scenarios

---

## 📂 Project Structure

```
├── main.py                     # FastAPI entrypoint
├── services/                   # Business logic
├── providers/                  # External API & scraper
├── repository/                 # In-memory stock repo
├── tests/                      # 157 test cases
├── Dockerfile
└── README.md
```

---

## 📝 Notes

* Stock amounts are **in-memory only** (reset on restart). Replace repository with a DB-backed implementation for persistence.
* MarketWatch scraping may break if site structure changes. The scraper fails gracefully and logs warnings.
* Logging is saved in `logs/general.log` and `logs/error.log`.
