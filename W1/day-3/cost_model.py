import pandas as pd

# Định nghĩa các cấp độ (Tiers) dựa trên yêu cầu bài toán
tiers = {
    "Small": {"services": 10, "log_gb_per_day": 50, "metric_events_per_sec": 100_000},
    "Medium": {"services": 100, "log_gb_per_day": 500, "metric_events_per_sec": 1_000_000},
    "Large": {"services": 1000, "log_gb_per_day": 5000, "metric_events_per_sec": 10_000_000},
}

def calculate_build_cost(tier_data):
    """
    Ước tính chi phí tự dựng (Self-host) dựa trên Volume.
    Giả định các đơn giá (đã làm tròn để mô phỏng):
    - Storage (Log + Metric): ~$9 cho mỗi GB log/ngày (bao gồm hot & cold tier)
    - Compute (Kafka + Processing): ~$25 cho mỗi 1,000 sự kiện/giây
    - Network (Egress/Cross-AZ): ~$1 cho mỗi GB log/ngày
    - SRE Team (Vận hành): Small (0 SRE), Medium (2 SRE = $5000/người), Large (5 SRE = $5000/người)
    """
    log_gb = tier_data["log_gb_per_day"]
    metric_eps = tier_data["metric_events_per_sec"]
    
    storage_cost = log_gb * 9
    compute_cost = (metric_eps / 1000) * 25
    network_cost = log_gb * 1
    
    # Chi phí nhân sự vận hành (SRE) - Ẩn số thường bị bỏ quên
    sre_cost = 0
    if tier_data["services"] == 100:
        sre_cost = 2 * 5000
    elif tier_data["services"] >= 1000:
        sre_cost = 5 * 5000
        
    total_infra = storage_cost + compute_cost + network_cost
    return storage_cost, compute_cost, network_cost, sre_cost, total_infra + sre_cost

def calculate_buy_cost(tier_data):
    """
    Ước tính chi phí mua SaaS (VD: Datadog).
    Giả định đơn giá SaaS (Thường đắt hơn Infra gốc 3-5 lần, nhưng không tốn SRE):
    - Log Ingest & Retain: ~$2.5 / GB
    - Metric & APM Host: ~$20 / Host (Giả sử 1 service chạy trên 2-10 hosts tùy scale)
    - Ở đây dùng hệ số nhân đơn giản dựa trên log_gb và metric_eps
    """
    log_gb = tier_data["log_gb_per_day"]
    metric_eps = tier_data["metric_events_per_sec"]
    
    # Phí subscription SaaS mô phỏng
    saas_log_cost = log_gb * 30 * 2.5  # 30 ngày
    saas_metric_cost = (metric_eps / 1000) * 60
    
    total_saas = saas_log_cost + saas_metric_cost
    return total_saas

def generate_cost_report():
    print("Đang tính toán chi phí...\n")
    results = []
    
    for tier_name, data in tiers.items():
        storage, compute, network, sre, total_build = calculate_build_cost(data)
        total_buy = calculate_buy_cost(data)
        
        results.append({
            "Scale Tier": tier_name,
            "Build: Storage ($)": f"${storage:,.0f}",
            "Build: Compute ($)": f"${compute:,.0f}",
            "Build: Network ($)": f"${network:,.0f}",
            "Build: SRE Ops ($)": f"${sre:,.0f}",
            "Total BUILD ($/mo)": f"${total_build:,.0f}",
            "Total BUY ($/mo)": f"${total_buy:,.0f}",
            "Recommendation": "Buy (SaaS)" if total_buy <= total_build else "Build (Self-host)"
        })
        
    df_report = pd.DataFrame(results)
    
    print("BẢNG ƯỚC TÍNH CHI PHÍ HÀNG THÁNG (USD)")
    print(df_report.to_markdown(index=False))
    print("\nLưu ý: Bạn có thể copy bảng Markdown này vào file SUBMIT.md")

if __name__ == "__main__":
    generate_cost_report()