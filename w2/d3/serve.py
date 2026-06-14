import time
import logging
from typing import List, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
import os

# --- CẤU HÌNH LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aiops_serving")

# --- KHỞI TẠO APP & BIẾN TOÀN CỤC ---
app = FastAPI(title="AIOps RCA Pipeline")

# Giả lập load Graph và History (Thực tế bạn sẽ load file json ở đây)
GRAPH = {"nodes": [1, 2, 3]} # Thay bằng networkx.DiGraph thật
HISTORY = [{"incident_id": "inc-001"}] # Thay bằng list data thật

# --- ĐỊNH NGHĨA SCHEMAS (PYDANTIC) ---
class Alert(BaseModel):
    id: str
    ts: int
    service: str
    metric: str
    severity: str
    value: float
    threshold: float
    labels: Dict[str, str] = Field(default_factory=dict)

class IncidentRequest(BaseModel):
    alerts: List[Alert]

class IncidentResponse(BaseModel):
    clusters: List[Dict[str, Any]]
    root_cause: str
    confidence: float
    recommended_actions: List[str]
    similar_incidents: List[str]

# --- MIDDLEWARE: ĐO LATENCY ---
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    # Gắn vào header
    response.headers["X-Response-Time-Ms"] = str(round(process_time * 1000, 2))
    # Ghi log dạng cấu trúc (JSON-like)
    logger.info(
        f"{request.method} {request.url.path} - Status: {response.status_code} - "
        f"Duration: {round(process_time * 1000, 2)}ms"
    )
    return response

# --- ENDPOINTS: HEALTH & READINESS ---
@app.get("/healthz")
async def healthz():
    """Kiểm tra Liveness: Process còn sống không"""
    return {"status": "ok"}

@app.get("/readyz")
async def readyz():
    """Kiểm tra Readiness: Đã load đủ dữ liệu nền tảng chưa"""
    if len(GRAPH) == 0 or len(HISTORY) == 0:
        raise HTTPException(status_code=503, detail="Graph or History not loaded yet")
    return {"status": "ready"}

# --- IMPORT HÀM TỪ D1 & D2 ---
# GHI CHÚ: Hãy uncomment và import hàm thật của bạn từ D1, D2
# from aiops_xxx.w2.d1.correlate import correlate
# from aiops_xxx.w2.d2.rca import run_rca

# Hàm giả lập (Mock) để file chạy được luôn nếu chưa có D1, D2
def mock_correlate(alerts, graph, gap_sec, max_hop):
    return [{"cluster_id": 1, "alerts": alerts}]

def mock_run_rca(primary_cluster, alerts, graph, history):
    return {
        "root_cause": "payment-service",
        "confidence": 0.85,
        "actions": ["Restart payment-service pod", "Check DB connection"],
        "similar_incidents": ["inc-001"]
    }

# --- MAIN ENDPOINT: XỬ LÝ SỰ CỐ ---
@app.post("/incident", response_model=IncidentResponse)
async def process_incident(request_data: IncidentRequest):
    # 1. Bắt lỗi input rỗng
    if not request_data.alerts:
        raise HTTPException(status_code=400, detail="Alerts array cannot be empty")
    
    # 2. Xử lý logic trong Try/Except để chặn rò rỉ mã lỗi
    try:
        # Convert objects từ Pydantic sang plain Dict để đưa vào hàm xử lý
        alerts_dict = [alert.model_dump() for alert in request_data.alerts]
        
        # Chạy Layer 1: Correlate
        # Thực tế: clusters = correlate(alerts_dict, GRAPH, gap_sec=120, max_hop=2)
        clusters = mock_correlate(alerts_dict, GRAPH, gap_sec=120, max_hop=2)
        
        if not clusters:
            return IncidentResponse(
                clusters=[], root_cause="unknown", confidence=0.0, 
                recommended_actions=[], similar_incidents=[]
            )

        # Chạy Layer 2: RCA (Lấy cluster bự nhất làm primary)
        primary_cluster = clusters[0] 
        
        # Check công tắc khẩn cấp Feature Flag
        use_llm = os.getenv("AIOPS_USE_LLM", "true").lower() == "true"
        if not use_llm:
            logger.warning("Feature Flag AIOPS_USE_LLM is FALSE. Running graph-only fallback.")
            rca_result = mock_run_rca(primary_cluster, alerts_dict, GRAPH, HISTORY) # Graph only
        else:
            rca_result = mock_run_rca(primary_cluster, alerts_dict, GRAPH, HISTORY) # Có LLM
        
        # Trả về kết quả
        return IncidentResponse(
            clusters=clusters,
            root_cause=rca_result["root_cause"],
            confidence=rca_result["confidence"],
            recommended_actions=rca_result["actions"],
            similar_incidents=rca_result["similar_incidents"]
        )
        
    except Exception as e:
        logger.error(f"Internal Pipeline Error: {str(e)}", exc_info=True)
        # Chỉ ném lỗi 500 chung chung cho user, giữ traceback lại trong log
        raise HTTPException(status_code=500, detail="Internal server error during RCA processing")