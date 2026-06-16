#!/usr/bin/env bash
# STUB — wire to your docker-compose. Pack does not ship a stack.
set -e
echo "--> Khởi động cụm 10 Microservices + Monitoring Stack..."
docker compose up -d

echo "--> Chờ các dịch vụ healthcheck OK (khoảng 30 giây)..."
sleep 30

echo "--> Kiểm tra trạng thái AIOps Pipeline FastAPI (Port 8000)..."
curl -s http://localhost:8000/alerts?since=0 > /dev/null
if [ $? -ne 0 ]; then
    echo "ERROR: Không kết nối được với FastAPI tại port 8000!"
    exit 1
fi

echo "--> Tất cả hệ thống đã sẵn sàng!"