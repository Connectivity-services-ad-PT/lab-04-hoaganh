# Hướng dẫn chạy Core Business Service — Lab 04

## Yêu cầu
- Docker Desktop đang chạy
- Git Bash hoặc PowerShell

---

## Chạy bằng Docker (3 bước)

### Bước 1 — Build image
```bash
docker build -t fit4110/core-business:lab04 .
```

### Bước 2 — Run container
```bash
docker run --rm \
  --name fit4110-core-lab04 \
  -p 8000:8000 \
  --env-file .env.example \
  fit4110/core-business:lab04
```

### Bước 3 — Kiểm tra
```bash
curl http://localhost:8000/health
```

Kết quả mong đợi:
```json
{"status": "ok", "service": "core-business", "time": "..."}
```

---

## Dừng container
```bash
docker stop fit4110-core-lab04
```

---

## Chạy Newman test trên container
Sau khi container đang chạy, mở terminal mới:
```bash
npx newman run postman/collections/FIT4110_lab04_core.postman_collection.json \
  -e postman/environments/FIT4110_lab04_local.postman_environment.json \
  -r cli,htmlextra \
  --reporter-htmlextra-export reports/newman-lab04-local.html
```

---

## Chạy không dùng Docker (Python local)
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn core_app.main:app --app-dir src --host 0.0.0.0 --port 8000
```
