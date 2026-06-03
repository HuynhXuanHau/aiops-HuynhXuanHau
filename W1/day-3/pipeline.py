import pandas as pd
import threading
import queue
import time
import numpy as np
from collections import deque

CSV_FILE = "machine_temperature_system_failure.csv"
OUTPUT_FILE = "features.parquet"
WINDOW_SIZE = 12 

def producer(data_queue, csv_path):
    print("Producer: Bắt đầu đọc CSV và emit data...")
    df = pd.read_csv(csv_path)
    
    # Giả lập streaming bằng cách ném từng dòng vào queue
    for _, row in df.iterrows():
        # Đưa vào queue dưới dạng dictionary
        data_queue.put({'timestamp': row['timestamp'], 'value': row['value']})
        # time.sleep(0.001) # Uncomment nếu muốn xem tiến trình chạy chậm lại
        
    # Gửi tín hiệu kết thúc (Poison pill)
    data_queue.put(None)
    print("Producer: Đã đẩy xong toàn bộ dữ liệu!")

def consumer(data_queue):
    print("Consumer: Bắt đầu xử lý luồng dữ liệu...")
    
    # State (Trạng thái) để tính rolling features
    window_values = deque(maxlen=WINDOW_SIZE)
    prev_value = None
    processed_data = []
    
    while True:
        item = data_queue.get()
        if item is None: # Nhận được tín hiệu kết thúc
            data_queue.task_done()
            break
            
        current_value = item['value']
        
        # 1. Cập nhật State
        window_values.append(current_value)
        
        # 2. Tính toán Features
        # Rolling Mean
        rolling_mean = np.mean(window_values)
        
        # Rolling Std (Cần ít nhất 2 điểm dữ liệu để tính độ lệch chuẩn)
        rolling_std = np.std(window_values) if len(window_values) > 1 else 0.0
        
        # Rate of Change (Tốc độ thay đổi so với mốc thời gian liền trước)
        rate_of_change = (current_value - prev_value) if prev_value is not None else 0.0
        
        # 3. Tạo record mới với features đã được enrich
        enriched_item = {
            'timestamp': item['timestamp'],
            'value': current_value,
            'rolling_mean_1h': rolling_mean,
            'rolling_std_1h': rolling_std,
            'rate_of_change': rate_of_change
        }
        processed_data.append(enriched_item)
        
        # Cập nhật giá trị prev_value cho vòng lặp tiếp theo
        prev_value = current_value
        data_queue.task_done()
        
    print(f"Consumer: Đã xử lý xong {len(processed_data)} records. Đang lưu file...")
    
    # Chuyển đổi thành DataFrame và lưu dạng Parquet
    df_features = pd.DataFrame(processed_data)
    df_features.to_parquet(OUTPUT_FILE, index=False)
    print(f"Consumer: Đã lưu kết quả ra {OUTPUT_FILE} thành công!")

if __name__ == "__main__":
    # 1. Tạo hàng đợi giao tiếp giữa 2 luồng
    q = queue.Queue(maxsize=1000) # Giới hạn size để Producer không chạy quá xa Consumer
    
    # 2. Định nghĩa các Threads
    prod_thread = threading.Thread(target=producer, args=(q, CSV_FILE))
    cons_thread = threading.Thread(target=consumer, args=(q,))
    
    # 3. Chạy
    prod_thread.start()
    cons_thread.start()
    
    # 4. Chờ hoàn thành
    prod_thread.join()
    cons_thread.join()
    
    print("Pipeline hoàn tất!")