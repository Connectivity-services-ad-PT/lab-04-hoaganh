"""
Core Business Policy Service — FIT4110 Lab 04
Provider: Core Business Service (team-core)
Consumer: Access Gate Service
"""
from fastapi import FastAPI, HTTPException, Depends, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
import re
import uuid
from datetime import datetime, timezone

app = FastAPI(
    title="Smart Campus — Core Business Policy API (pair10)",
    description="Core Business Policy Engine cho Smart Campus",
    version="1.0.0",
)

security = HTTPBearer(auto_error=False)

# ── In-memory data ──────────────────────────────────────────────
POLICY_RULES = {
    "POL-2026-001": {
        "policyId": "POL-2026-001",
        "gateId": "GATE-01",
        "allowedRoles": ["STUDENT", "STAFF"],
        "timeRestriction": {
            "restrictionType": "TIME_WINDOW",
            "startTime": "07:00",
            "endTime": "22:00",
            "daysOfWeek": ["MON", "TUE", "WED", "THU", "FRI"],
        },
        "active": True,
        "updatedAt": "2026-05-01T00:00:00Z",
    },
    "POL-2026-002": {
        "policyId": "POL-2026-002",
        "gateId": "GATE-05",
        "allowedRoles": ["STAFF", "ADMIN"],
        "timeRestriction": None,
        "active": True,
        "updatedAt": "2026-05-01T00:00:00Z",
    },
}

CARD_ROLES = {
    "RFID-2026-001": "STUDENT",
    "RFID-2026-002": "STUDENT",
    "RFID-2026-003": "STAFF",
}

ACCESS_LOGS = []

# ── Schemas ──────────────────────────────────────────────────────
class AccessCheckRequest(BaseModel):
    cardId: str = Field(..., pattern=r"^RFID-\d{4}-\d{3}$")
    gateId: str = Field(..., pattern=r"^GATE-\d{2}$")
    direction: str = Field(..., pattern=r"^(ENTER|EXIT)$")
    timestamp: str

    @field_validator("cardId")
    @classmethod
    def validate_card_id(cls, v):
        if not re.match(r"^RFID-\d{4}-\d{3}$", v):
            raise ValueError("cardId phải có dạng RFID-YYYY-NNN")
        return v

class AccessCheckResult(BaseModel):
    cardId: str
    gateId: str
    decision: str
    reason: Optional[str]
    policyId: str
    checkedAt: str

class PolicyRule(BaseModel):
    policyId: str
    gateId: str
    allowedRoles: List[str]
    timeRestriction: Optional[dict]
    active: bool
    updatedAt: str

class PolicyRulePage(BaseModel):
    items: List[PolicyRule]
    nextCursor: Optional[str]
    hasMore: bool

class AccessLogEntry(BaseModel):
    cardId: str = Field(..., pattern=r"^RFID-\d{4}-\d{3}$")
    gateId: str = Field(..., pattern=r"^GATE-\d{2}$")
    direction: str = Field(..., pattern=r"^(ENTER|EXIT)$")
    decision: str = Field(..., pattern=r"^(ALLOW|DENY)$")
    reason: Optional[str]
    timestamp: str

class AccessLogAccepted(BaseModel):
    logId: str
    acceptedAt: str

class ProblemDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: Optional[str] = None
    instance: Optional[str] = None
    errors: Optional[List[dict]] = None

# ── Auth helper ────────────────────────────────────────────────
def require_auth(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "https://campus.local/errors/unauthorized",
                "title": "Chưa xác thực",
                "status": 401,
                "detail": "Thiếu Bearer token",
                "instance": "https://campus.local/policy",
                "errors": [],
            },
        )
    return credentials.credentials

# ── Problem response helper ────────────────────────────────────
def problem(status_code: int, title: str, detail: str, instance: str, errors=None):
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://campus.local/errors/{status_code}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
            "errors": errors or [],
        },
    )

# ── Endpoints ──────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "core-business",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/policy/access-check", response_model=AccessCheckResult)
def check_access(body: AccessCheckRequest, token: str = Depends(require_auth)):
    # Tìm policy cho gate này
    policy = next(
        (p for p in POLICY_RULES.values() if p["gateId"] == body.gateId and p["active"]),
        None,
    )
    if policy is None:
        return AccessCheckResult(
            cardId=body.cardId,
            gateId=body.gateId,
            decision="DENY",
            reason="Không tìm thấy policy cho cổng này",
            policyId="POL-0000-000",
            checkedAt=datetime.now(timezone.utc).isoformat(),
        )

    # Kiểm tra role của thẻ
    card_role = CARD_ROLES.get(body.cardId)
    if card_role is None or card_role not in policy["allowedRoles"]:
        return AccessCheckResult(
            cardId=body.cardId,
            gateId=body.gateId,
            decision="DENY",
            reason="Thẻ không có quyền vào khu vực này",
            policyId=policy["policyId"],
            checkedAt=datetime.now(timezone.utc).isoformat(),
        )

    return AccessCheckResult(
        cardId=body.cardId,
        gateId=body.gateId,
        decision="ALLOW",
        reason=None,
        policyId=policy["policyId"],
        checkedAt=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/policy/rules", response_model=PolicyRulePage)
def list_policy_rules(
    limit: int = 20,
    cursor: Optional[str] = None,
    gateId: Optional[str] = None,
    token: str = Depends(require_auth),
):
    if limit < 1 or limit > 100:
        return problem(400, "Tham số không hợp lệ", "limit phải từ 1 đến 100", "https://campus.local/policy/rules")

    rules = list(POLICY_RULES.values())
    if gateId:
        rules = [r for r in rules if r["gateId"] == gateId]

    items = [PolicyRule(**r) for r in rules[:limit]]
    return PolicyRulePage(items=items, nextCursor=None, hasMore=False)


@app.get("/policy/rules/{policyId}", response_model=PolicyRule)
def get_policy_rule(policyId: str, token: str = Depends(require_auth)):
    rule = POLICY_RULES.get(policyId)
    if rule is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "https://campus.local/errors/not-found",
                "title": "Không tìm thấy",
                "status": 404,
                "detail": f"Policy {policyId} không tồn tại",
                "instance": f"https://campus.local/policy/rules/{policyId}",
                "errors": [],
            },
        )
    return PolicyRule(**rule)


@app.post("/access-log", response_model=AccessLogAccepted, status_code=201)
def submit_access_log(body: AccessLogEntry, token: str = Depends(require_auth)):
    log_id = str(uuid.uuid4())
    accepted_at = datetime.now(timezone.utc).isoformat()
    ACCESS_LOGS.append({**body.model_dump(), "logId": log_id, "acceptedAt": accepted_at})
    return AccessLogAccepted(logId=log_id, acceptedAt=accepted_at)


# ── Exception handlers ─────────────────────────────────────────
@app.exception_handler(422)
async def validation_exception_handler(request, exc):
    errors = []
    if hasattr(exc, "errors"):
        for e in exc.errors():
            errors.append({
                "field": ".".join(str(x) for x in e.get("loc", [])),
                "code": e.get("type", "VALIDATION_ERROR").upper(),
                "message": e.get("msg", ""),
            })
    return JSONResponse(
        status_code=422,
        media_type="application/problem+json",
        content={
            "type": "https://campus.local/errors/validation",
            "title": "Dữ liệu không hợp lệ",
            "status": 422,
            "detail": "Payload không đúng định dạng",
            "instance": str(request.url.path),
            "errors": errors,
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            media_type="application/problem+json",
            content=exc.detail,
        )
    return JSONResponse(
        status_code=exc.status_code,
        media_type="application/problem+json",
        content={
            "type": f"https://campus.local/errors/{exc.status_code}",
            "title": str(exc.detail),
            "status": exc.status_code,
            "detail": str(exc.detail),
            "instance": str(request.url.path),
            "errors": [],
        },
    )
