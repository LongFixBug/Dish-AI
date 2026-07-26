#!/usr/bin/env bash
# Kiểm tra nhanh các hành vi vừa được sửa. Chỉ gọi endpoint miễn phí —
# KHÔNG chạm /analyze để khỏi tốn lượt Vision API.
#
#   bash scripts/smoke_test.sh
set -uo pipefail

API="${API:-http://127.0.0.1:8000}"
PASS=0
FAIL=0

check() {
  local label=$1 expected=$2 actual=$3
  if [ "$expected" = "$actual" ]; then
    printf '  ✅ %-58s %s\n' "$label" "$actual"
    PASS=$((PASS + 1))
  else
    printf '  ❌ %-58s want=%s got=%s\n' "$label" "$expected" "$actual"
    FAIL=$((FAIL + 1))
  fi
}

status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
json_field() { python3 -c "import json,sys; print(json.load(sys.stdin).get('$1',''))"; }

echo "▶ Health"
check "/live trả 200" 200 "$(status "$API/live")"
check "/ready trả 200" 200 "$(status "$API/ready")"

echo
echo "▶ Đăng ký một tài khoản tạm"
EMAIL="smoke-$(date +%s)@foodai.test"
TOKEN=$(curl -s -X POST "$API/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"smoke-test-pw-123\",\"display_name\":\"Smoke Test\"}" \
  | json_field access_token)
if [ -z "$TOKEN" ]; then
  echo "  ❌ không lấy được token — dừng. Xem logs/api.log"
  exit 1
fi
echo "  ✅ có access token"

echo
echo "▶ Bug #30 — /dishes/lookup phải yêu cầu đăng nhập"
check "không token → 401" 401 "$(status "$API/api/v1/dishes/lookup?name=pho%20bo")"
check "có token → 200" 200 \
  "$(status -H "Authorization: Bearer $TOKEN" "$API/api/v1/dishes/lookup?name=pho%20bo")"

echo
echo "▶ Bug #12 — giảm 30kg/7 ngày phải bị đánh dấu review_required"
SAFETY=$(curl -s -X POST "$API/api/v1/nutrition-goals/preview" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"age":30,"sex":"male","height_cm":170,"weight_kg":70,
       "activity_level":"moderate","goal":"lose",
       "target_weight_kg":40,"target_days":7}' | json_field safety_status)
check "safety_status" "review_required" "$SAFETY"

echo
echo "▶ Bug #29 — /metrics với header non-ASCII phải 401, không phải 500"
METRICS_TOKEN="${METRICS_TOKEN:-$(
  grep -E '^METRICS_TOKEN=' .env 2>/dev/null | cut -d= -f2- | tr -d "\"'"
)}"
if [ -z "$METRICS_TOKEN" ]; then
  echo "  ⏭  bỏ qua: METRICS_TOKEN chưa đặt nên /metrics đang mở (mặc định dev)."
  echo "     Kiểm tra thật: METRICS_TOKEN=\$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))') \\"
  echo "                    uv run uvicorn backend.main:app --port 8001"
  echo "     rồi: API=http://127.0.0.1:8001 bash scripts/smoke_test.sh"
else
  check "Authorization rác" 401 \
    "$(status -H 'Authorization: Bearer ánh' "$API/metrics")"
fi

echo
echo "▶ Bug #27 — id sai định dạng phải 422, không phải 500"
check "DELETE feedback id='abc'" 422 \
  "$(status -X DELETE -H "Authorization: Bearer $TOKEN" \
      "$API/api/v1/feedback/training-data/abc")"

echo
echo "▶ Bug #2 — token không được cấp thêm hạn mức cho /login (chạy cuối)"
for _ in $(seq 10); do
  status -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
    -d '{"email":"nobody@foodai.test","password":"wrong-password"}' > /dev/null
done
check "lần thứ 11 kèm Bearer token → 429" 429 \
  "$(status -X POST "$API/api/v1/auth/login" \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d '{"email":"nobody@foodai.test","password":"wrong-password"}')"

echo
echo "──────────────────────────────────"
echo "  $PASS pass, $FAIL fail"
[ "$FAIL" = "0" ] || exit 1
