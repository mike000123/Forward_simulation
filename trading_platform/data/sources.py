from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass
class MarketDataRequest:
    ticker: str
    interval: str
    start: pd.Timestamp
    end: pd.Timestamp


def _canonicalize_column(name: str) -> str:
    return "".join(ch for ch in name.lower().strip() if ch.isalnum())


def _to_numeric(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce", utc=True).dt.tz_localize(None)
    for col in ["open", "high", "low", "close"]:
        normalized[col] = pd.to_numeric(normalized[col], errors="coerce")
    normalized = normalized[["date", "open", "high", "low", "close"]].dropna()
    normalized = normalized.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return normalized


def load_price_data_from_csv(file_buffer) -> pd.DataFrame:
    raw = file_buffer.read()
    if not raw:
        raise ValueError("The uploaded file is empty.")

    df = pd.read_csv(io.BytesIO(raw))
    canonical_to_original = {_canonicalize_column(c): c for c in df.columns}

    aliases = {
        "date": ["date", "datetime", "time", "timestamp"],
        "open": ["open", "openingprice"],
        "high": ["high", "max"],
        "low": ["low", "min"],
        "close": ["close", "closelast", "closeprice", "last"],
    }

    resolved = {}
    missing = []
    for target, candidates in aliases.items():
        matched = next((canonical_to_original[c] for c in candidates if c in canonical_to_original), None)
        if matched is None:
            missing.append(target)
        else:
            resolved[target] = matched

    if missing:
        raise ValueError(
            "CSV is missing required price columns: "
            + ", ".join(sorted(missing))
            + ". Accepted names include Date/Datetime, Open, High/Max, Low/Min, Close/Last."
        )

    converted = pd.DataFrame(
        {
            "date": df[resolved["date"]],
            "open": _to_numeric(df[resolved["open"]]),
            "high": _to_numeric(df[resolved["high"]]),
            "low": _to_numeric(df[resolved["low"]]),
            "close": _to_numeric(df[resolved["close"]]),
        }
    )
    normalized = normalize_ohlc(converted)
    if normalized.empty:
        raise ValueError("No valid rows found in CSV.")
    return normalized


def fetch_price_data(request: MarketDataRequest) -> pd.DataFrame:
    if not request.ticker.strip():
        raise ValueError("Ticker cannot be empty.")
    if request.end < request.start:
        raise ValueError("End date must be on or after start date.")

    data = yf.download(
        request.ticker.strip(),
        start=request.start.strftime("%Y-%m-%d"),
        end=(request.end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        interval=request.interval,
        auto_adjust=False,
        progress=False,
    )

    if data is None or data.empty:
        raise ValueError("No market data returned for the selected query.")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    required_cols = ["Open", "High", "Low", "Close"]
    for col in required_cols:
        if col not in data.columns:
            raise ValueError(f"Fetched data missing required column: {col}")

    normalized = normalize_ohlc(
        pd.DataFrame(
            {
                "date": data.index,
                "open": data["Open"],
                "high": data["High"],
                "low": data["Low"],
                "close": data["Close"],
            }
        )
    )
    if normalized.empty:
        raise ValueError("No valid rows after normalization.")
    return normalized
