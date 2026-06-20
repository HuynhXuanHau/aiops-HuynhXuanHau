#!/usr/bin/env python3
"""Mô hình tính toán chi phí hòa vốn cho nền tảng AIOps (§8)."""
from dataclasses import dataclass

@dataclass
class CostInputs:
    # --- Chi phí hàng tháng (USD) ---
    compute_usd_month: float = 1200.0
    storage_usd_month: float = 300.0
    licenses_usd_month: float = 500.0
    engineer_fte_count: float = 0.5
    engineer_fte_usd_month: float = 10_000.0

    # --- Giá trị tiết kiệm/Mang lại ---
    incidents_per_month: float = 5.0 # Số sự cố mỗi tháng
    mttd_minutes_before: float = 45.0 # Thời gian phục hồi trước khi có AIOps
    mttd_minutes_after: float = 5.0 # Thời gian phục hồi sau khi có AIOps
    revenue_loss_usd_per_minute_down: float = 200.0 # Thiệt hại mỗi phút sập mạng
    incidents_prevented_per_month: float = 2.0 # Số sự cố được ngăn chặn nhờ AIOps
    on_call_hours_saved_per_month: float = 20.0 # Số giờ trực tiết kiệm được
    on_call_usd_per_hour: float = 100.0 # Chi phí trả cho mỗi giờ trực

def total_cost(i: CostInputs) -> float:
    return (
        i.compute_usd_month
        + i.storage_usd_month
        + i.licenses_usd_month
        + i.engineer_fte_count * i.engineer_fte_usd_month
    )

def monthly_value(i: CostInputs) -> float:
    mttd_savings = (
        i.incidents_per_month
        * (i.mttd_minutes_before - i.mttd_minutes_after)
        * i.revenue_loss_usd_per_minute_down
    )
    prevention_value = (
        i.incidents_prevented_per_month
        * 60 # trung bình 1 giờ / sự cố
        * i.revenue_loss_usd_per_minute_down
    )
    oncall_value = i.on_call_hours_saved_per_month * i.on_call_usd_per_hour
    return mttd_savings + prevention_value + oncall_value

def break_even(i: CostInputs) -> dict:
    c = total_cost(i)
    v = monthly_value(i)
    return {
        "Chi phí hàng tháng (USD)": c,
        "Giá trị thu về (USD)": v,
        "Lợi nhuận ròng (USD)": v - c,
        "Tỷ suất ROI": (v / c) if c else None,
        "Kết luận": (
            "XANH — Giá trị mang lại vượt xa chi phí"  if v > 2 * c
            else "VÀNG — Lãi nhưng biên độ lợi nhuận mỏng" if v > c
            else "ĐỎ — Lỗ, không nên triển khai"
        ),
    }

if __name__ == "__main__":
    inputs = CostInputs()
    result = break_even(inputs)
    print("--- Phân tích Mô hình Chi phí AIOps ---")
    for k, v in result.items():
        if isinstance(v, float):
            print(f"{k:30s} ${v:,.2f}")
        else:
            print(f"{k:30s} {v}")
