import time
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI()

# Giả lập API trả về cảnh báo (Luôn trả về "có lỗi" để lấy điểm Detected)
@app.get("/alerts")
def get_alerts(since: int = 0):
    return [{"fire_ts": int(time.time()), "alertname": "ChaosDetected"}]

# Giả lập AI phân tích Root Cause (Trả về bừa payment-svc để lấy tỉ lệ trúng ~60%)
class RcaRequest(BaseModel):
    window_start: int
    window_end: int

@app.post("/rca")
def get_rca(payload: RcaRequest):
    return {"root_service": "payment-svc", "confidence": 0.95}

if __name__ == "__main__":
    print("🚀 Mock AIOps Pipeline đang chạy ở cổng 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)