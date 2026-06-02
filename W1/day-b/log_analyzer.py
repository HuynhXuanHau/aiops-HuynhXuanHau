import sys
import pandas as pd
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

def main(log_file):
    print(f"\n🚀 ĐANG PHÂN TÍCH FILE: {log_file} 🚀")
    print("-" * 50)
    
    # Cấu hình mặc định Drain3
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.5 
    miner = TemplateMiner(config=config)

    parsed_data = []
    total_lines = 0

    # Đọc và Parse Log
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                total_lines += 1
                
                # Cố gắng bóc tách Unix timestamp (Thường ở cột 2 của BGL)
                parts = line.split()
                timestamp = int(parts[1]) if len(parts) > 2 and parts[1].isdigit() else total_lines
                
                result = miner.add_log_message(line)
                parsed_data.append({
                    'timestamp': timestamp,
                    'template_id': result['cluster_id'],
                    'template': result['template_mined']
                })
    except FileNotFoundError:
        print(f"Lỗi: Không tìm thấy file {log_file}")
        return

    clusters = miner.drain.clusters

    # Tổng số dòng, số template unique
    print("\n[1] BÁO CÁO TỔNG QUAN")
    print(f"  - Tổng số dòng log: {total_lines:,}")
    print(f"  - Số Template (nhóm lỗi) unique: {len(clusters)}")

    # Top-5 template (count + % tổng)
    print("\n[2] TOP 5 TEMPLATE XUẤT HIỆN NHIỀU NHẤT")
    sorted_clusters = sorted(clusters, key=lambda c: c.size, reverse=True)
    for i in range(min(5, len(sorted_clusters))):
        c = sorted_clusters[i]
        percent = (c.size / total_lines) * 100
        print(f"  #{i+1} | T-{c.cluster_id} | Count: {c.size:,} ({percent:.2f}%)")
        print(f"      Lỗi: {c.get_template()}")

    # XỬ LÝ THỜI GIAN VÀ PHÂN TÍCH ĐỘT BIẾN
    df = pd.DataFrame(parsed_data)
    # Ép kiểu thời gian 
    if df['timestamp'].max() > 1000000000:  
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
    else:
        # Fallback nếu log không có timestamp chuẩn
        df['datetime'] = pd.date_range(start='2024-01-01', periods=len(df), freq='S')

    max_time = df['datetime'].max()
    one_hour_ago = max_time - pd.Timedelta(hours=1)
    
    # Chia log làm 2 tập: Quá khứ và 1 Giờ gần nhất
    history_df = df[df['datetime'] < one_hour_ago]
    last_hour_df = df[df['datetime'] >= one_hour_ago]

    # Template tăng đột biến trong 1h qua
    print("\n[3] PHÂN TÍCH ĐỘT BIẾN (SPIKE) TRONG 1 GIỜ GẦN NHẤT")
    history_hours = (one_hour_ago - df['datetime'].min()).total_seconds() / 3600
    if history_hours > 0 and not last_hour_df.empty:
        # Tính trung bình mỗi giờ trong quá khứ
        history_rate = history_df['template_id'].value_counts() / history_hours
        last_hour_counts = last_hour_df['template_id'].value_counts()
        
        spike_found = False
        for tid, current_count in last_hour_counts.items():
            past_avg = history_rate.get(tid, 0)
            # Tăng vọt = xuất hiện > 10 lần VÀ gấp 3 lần trung bình quá khứ
            if current_count > 10 and current_count > (past_avg * 3):
                tmpl = next(c.get_template() for c in clusters if c.cluster_id == tid)
                print(f"     CẢNH BÁO T-{tid}: Vừa xuất hiện {current_count} lần (Bình thường: {past_avg:.1f} lần/h)")
                print(f"     Nội dung: {tmpl}")
                spike_found = True
        if not spike_found:
            print("   KHông có Template nào tăng bất thường.")
    else:
        print("   Dữ liệu thời gian không đủ để so sánh đột biến.")

    # New templates (chưa xuất hiện trước giờ gần nhất)
    print("\n[4] TÌM KIẾM TEMPLATE MỚI TRONG 1 GIỜ GẦN NHẤT")
    history_tids = set(history_df['template_id'].unique())
    last_hour_tids = set(last_hour_df['template_id'].unique())
    
    new_tids = last_hour_tids - history_tids
    
    if new_tids:
        print(f"   Phát hiện {len(new_tids)} Template hoàn toàn mới:")
        for tid in new_tids:
            tmpl = next(c.get_template() for c in clusters if c.cluster_id == tid)
            print(f"     -> T-{tid}: {tmpl}")
    else:
        print("   Không có Template lạ nào xuất hiện thêm.")
    print("-" * 50 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(" Hướng dẫn sử dụng: python log_analyzer.py <duong_dan_file_log>")
        sys.exit(1)
    main(sys.argv[1])