from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.commerce import Product, StoreProduct
from app.models.orders import Order, OrderItem, OrderStatus


def _sold_quantity(
    db: Session,
    store_id: uuid.UUID,
    product_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
) -> int:
    value = db.scalar(
        select(func.coalesce(func.sum(OrderItem.quantity), 0))
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.store_id == store_id,
            OrderItem.product_id == product_id,
            Order.status != OrderStatus.CANCELLED,
            Order.created_at >= start_at,
            Order.created_at < end_at,
        )
    )
    return int(value or 0)


def forecast_store_demand(
    db: Session,
    store_id: uuid.UUID,
    *,
    window_days: int = 28,
    horizon_days: int = 7,
) -> dict:
    now = datetime.now(timezone.utc)
    start_at = now - timedelta(days=window_days)
    recent_start = now - timedelta(days=min(7, window_days))
    previous_recent_start = recent_start - timedelta(days=min(7, max(window_days - 7, 0)))

    listings = db.execute(
        select(StoreProduct, Product)
        .join(Product, Product.id == StoreProduct.product_id)
        .where(StoreProduct.store_id == store_id)
        .order_by(Product.name)
    ).all()

    results: list[dict] = []
    for listing, product in listings:
        total_sold = _sold_quantity(db, store_id, product.id, start_at, now)
        recent_sold = _sold_quantity(db, store_id, product.id, recent_start, now)
        previous_sold = _sold_quantity(db, store_id, product.id, previous_recent_start, recent_start) if previous_recent_start < recent_start else 0

        baseline_daily = total_sold / max(window_days, 1)
        recent_days = min(7, window_days)
        recent_daily = recent_sold / max(recent_days, 1)
        weighted_daily = (recent_daily * 0.65) + (baseline_daily * 0.35)
        forecast_units = int(math.ceil(weighted_daily * horizon_days))
        safety_stock = int(math.ceil(weighted_daily * 2))
        reorder_units = max(0, forecast_units + safety_stock - int(listing.stock_quantity))

        if previous_sold == 0:
            trend = "new_or_flat" if recent_sold > 0 else "flat"
            trend_ratio = None
        else:
            ratio = recent_sold / previous_sold
            trend_ratio = round(ratio, 3)
            trend = "rising" if ratio >= 1.2 else "falling" if ratio <= 0.8 else "stable"

        sample_strength = total_sold
        confidence = "high" if sample_strength >= 20 else "medium" if sample_strength >= 5 else "low"
        if reorder_units > 0:
            recommendation = "reorder"
            reason = f"Projected {forecast_units} units over {horizon_days} days plus {safety_stock} safety stock exceeds current stock."
        elif forecast_units == 0 and listing.stock_quantity > 0:
            recommendation = "hold"
            reason = "No recent demand signal; avoid increasing inventory until sales data appears."
        else:
            recommendation = "maintain"
            reason = "Current stock covers the transparent forecast and safety-stock target."

        results.append(
            {
                "store_product_id": str(listing.id),
                "product_id": str(product.id),
                "product_name": product.name,
                "unit": product.unit,
                "stock_quantity": int(listing.stock_quantity),
                "sold_window": total_sold,
                "sold_recent_7d": recent_sold,
                "sold_previous_7d": previous_sold,
                "daily_demand_rate": round(weighted_daily, 3),
                "forecast_units": forecast_units,
                "safety_stock_units": safety_stock,
                "recommended_reorder_units": reorder_units,
                "trend": trend,
                "trend_ratio": trend_ratio,
                "confidence": confidence,
                "recommendation": recommendation,
                "reason": reason,
            }
        )

    return {
        "store_id": str(store_id),
        "generated_at": now,
        "window_days": window_days,
        "horizon_days": horizon_days,
        "method": "weighted_recent_sales_velocity_v1",
        "products": results,
    }
