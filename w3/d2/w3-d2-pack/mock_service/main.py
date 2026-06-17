import os
import time
import random
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

# Lấy tên service và danh sách các service cần gọi từ biến môi trường
SERVICE_NAME = os.getenv("SERVICE_NAME", "unknown-svc")
UPSTREAMS = [u for u in os.getenv("UPSTREAMS", "").split(",") if u]

@app.middleware("http")
async def simulate_processing(request: Request, call_next):
    # Giả lập thời gian xử lý nghiệp vụ bình thường (10ms - 50ms)
    time.sleep(random.uniform(0.01, 0.05))
    
    # 1% tỷ lệ rớt mạng ngẫu nhiên tự nhiên (Noise)
    if random.random() < 0.01:
        return JSONResponse(status_code=500, content={"detail": "Internal random glitch"})
        
    response = await call_next(request)
    return response

@app.api_route("/{path:path}", methods=["GET", "POST"])
def handle_all(path: str):
    upstream_results = {}
    
    # Gọi dây chuyền (Cascade) sang các service khác nếu được cấu hình
    for upstream in UPSTREAMS:
        try:
            # Timeout 2s để mô phỏng đứt kết nối nếu có Chaos
            resp = requests.get(f"http://{upstream}/health", timeout=2)
            upstream_results[upstream] = resp.status_code
        except Exception as e:
            upstream_results[upstream] = str(e)
            
    return {
        "service": SERVICE_NAME,
        "status": "ok",
        "upstreams": upstream_results
    }

# Gắn bộ công cụ tự động sinh metric cho Prometheus
Instrumentator().instrument(app).expose(app)