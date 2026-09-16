"""Calibrated, read-only backtesting for imported Kalshi observations."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class BacktestRow:
    ticker: str
    timestamp: str
    settlement_time: str
    outcome: int
    market_probability: float
    entry_price_cents: float
    spread_cents: float
    sky_signal: float
    sky_orb: float
    applying: float
    volume: float
    category: str = ""


@dataclass(frozen=True)
class Prediction:
    ticker: str
    timestamp: str
    actual: int
    market_probability: float
    model_probability: float
    edge: float
    entry_price_cents: float
    kelly_fraction: float
    profit_cents: float | None


class LogisticProbabilityModel:
    """Small dependency-free logistic model for reproducible offline research."""

    def __init__(self, learning_rate: float = 0.2, iterations: int = 2500, penalty: float = 0.1) -> None:
        self.learning_rate = learning_rate
        self.iterations = iterations
        self.penalty = penalty
        self.weights: list[float] = []
        self.categories: list[str] = []

    def _features(self, row: BacktestRow) -> list[float]:
        features = [
            1.0,
            row.market_probability,
            row.sky_signal / 100.0,
            min(row.sky_orb / 8.0, 2.0),
            row.applying,
            math.log1p(max(row.volume, 0.0)) / 10.0,
            min(max(row.spread_cents, 0.0) / 100.0, 1.0),
        ]
        features.extend(1.0 if row.category == category else 0.0 for category in self.categories)
        return features

    @staticmethod
    def _sigmoid(value: float) -> float:
        value = max(-35.0, min(35.0, value))
        return 1.0 / (1.0 + math.exp(-value))

    def fit(self, rows: Iterable[BacktestRow]) -> "LogisticProbabilityModel":
        training = list(rows)
        if not training:
            raise ValueError("at least one settled training observation is required")
        self.categories = sorted({row.category for row in training if row.category})
        vectors = [self._features(row) for row in training]
        self.weights = [0.0] * len(vectors[0])
        for _ in range(self.iterations):
            gradients = [0.0] * len(self.weights)
            for vector, row in zip(vectors, training):
                error = self._sigmoid(sum(weight * value for weight, value in zip(self.weights, vector))) - row.outcome
                for index, value in enumerate(vector):
                    gradients[index] += error * value
            for index, gradient in enumerate(gradients):
                regularization = 0.0 if index == 0 else self.penalty * self.weights[index]
                self.weights[index] -= self.learning_rate * (gradient / len(training) + regularization)
        return self

    def predict_probability(self, row: BacktestRow) -> float:
        if not self.weights:
            raise ValueError("model must be fitted before prediction")
        return self._sigmoid(sum(weight * value for weight, value in zip(self.weights, self._features(row))))


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _outcome(value: Any) -> int | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"yes", "y", "true", "1"}:
        return 1
    if normalized in {"no", "n", "false", "0"}:
        return 0
    return None


def load_rows(connection: sqlite3.Connection) -> list[BacktestRow]:
    query = """
        SELECT observations.ticker, observations.timestamp, results.settlement_time,
               results.outcome, observations.yes_price, observations.yes_bid,
               observations.yes_ask, observations.sky_signal, observations.sky_orb,
             observations.sky_direction, observations.volume, markets.category
        FROM market_observations AS observations
        JOIN market_results AS results ON results.ticker = observations.ticker
         LEFT JOIN markets ON markets.ticker = observations.ticker
        WHERE results.settlement_time IS NOT NULL
        ORDER BY results.settlement_time, observations.timestamp
    """
    rows: list[BacktestRow] = []
    for raw in connection.execute(query):
        outcome = _outcome(raw[3])
        if outcome is None:
            continue
        price = raw[6] if raw[6] is not None else raw[4]
        if price is None or raw[7] is None:
            continue
        bid = raw[5] if raw[5] is not None else price
        rows.append(BacktestRow(
            ticker=raw[0], timestamp=raw[1], settlement_time=raw[2], outcome=outcome,
            market_probability=max(0.0, min(1.0, float(price) / 100.0)),
            entry_price_cents=float(price), spread_cents=max(0.0, float(price) - float(bid)),
            sky_signal=float(raw[7]), sky_orb=float(raw[8] or 8.0),
            applying=1.0 if str(raw[9] or "").lower() == "applying" else 0.0,
            volume=float(raw[10] or 0.0), category=str(raw[11] or ""),
        ))
    return rows


def _brier(predictions: Iterable[Prediction], field: str) -> float:
    values = list(predictions)
    if not values:
        return 0.0
    return sum((getattr(item, field) - item.actual) ** 2 for item in values) / len(values)


def _log_loss(predictions: Iterable[Prediction]) -> float:
    values = list(predictions)
    if not values:
        return 0.0
    return -sum(item.actual * math.log(max(item.model_probability, 1e-12)) + (1 - item.actual) * math.log(max(1 - item.model_probability, 1e-12)) for item in values) / len(values)


def _calibration_error(predictions: Iterable[Prediction], bins: int = 10) -> float:
    values = list(predictions)
    if not values:
        return 0.0
    total = 0.0
    for bucket in range(bins):
        selected = [item for item in values if bucket / bins <= item.model_probability < (bucket + 1) / bins or bucket == bins - 1 and item.model_probability == 1.0]
        if selected:
            total += len(selected) / len(values) * abs(sum(item.model_probability for item in selected) / len(selected) - sum(item.actual for item in selected) / len(selected))
    return total


def _max_drawdown(profits: Iterable[float]) -> float:
    balance = peak = drawdown = 0.0
    for profit in profits:
        balance += profit
        peak = max(peak, balance)
        drawdown = max(drawdown, peak - balance)
    return drawdown


def _kelly(probability: float, entry_price_cents: float, fee_cents: float) -> float:
    cost = entry_price_cents + fee_cents
    payout = max(0.0, 100.0 - cost)
    if cost <= 0 or payout <= 0:
        return 0.0
    odds = payout / cost
    return max(0.0, (odds * probability - (1 - probability)) / odds)


def run_backtest(
    rows: Iterable[BacktestRow],
    cutoff: str,
    min_edge: float = 0.05,
    fee_cents: float = 0.0,
    max_fraction: float = 0.02,
) -> dict[str, Any]:
    cutoff_time = _parse_timestamp(cutoff)
    all_rows = list(rows)
    training = [row for row in all_rows if _parse_timestamp(row.settlement_time) <= cutoff_time]
    test = [row for row in all_rows if _parse_timestamp(row.settlement_time) > cutoff_time]
    if not training:
        raise ValueError("cutoff leaves no settled training observations")
    if not test:
        raise ValueError("cutoff leaves no later settled test observations")
    model = LogisticProbabilityModel().fit(training)
    predictions: list[Prediction] = []
    for row in test:
        probability = model.predict_probability(row)
        edge = probability - row.market_probability
        trade = edge >= min_edge
        profit = None
        if trade:
            profit = (100.0 - row.entry_price_cents - fee_cents) if row.outcome else -(row.entry_price_cents + fee_cents)
        predictions.append(Prediction(
            ticker=row.ticker, timestamp=row.timestamp, actual=row.outcome,
            market_probability=row.market_probability, model_probability=probability,
            edge=edge, entry_price_cents=row.entry_price_cents,
            kelly_fraction=min(max_fraction, _kelly(probability, row.entry_price_cents, fee_cents)) if trade else 0.0,
            profit_cents=profit,
        ))
    traded = [prediction for prediction in predictions if prediction.profit_cents is not None]
    return {
        "training_observations": len(training),
        "test_observations": len(test),
        "trades": len(traded),
        "market_brier": _brier(predictions, "market_probability"),
        "model_brier": _brier(predictions, "model_probability"),
        "model_log_loss": _log_loss(predictions),
        "calibration_error": _calibration_error(predictions),
        "paper_profit_cents_per_contract": round(sum(item.profit_cents or 0.0 for item in traded), 4),
        "max_drawdown_cents_per_contract": round(_max_drawdown(item.profit_cents or 0.0 for item in traded), 4),
        "average_edge": round(sum(item.edge for item in predictions) / len(predictions), 6),
        "predictions": [item.__dict__ for item in predictions],
    }