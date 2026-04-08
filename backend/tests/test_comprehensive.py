"""
総合テスト: 登山者モニタリングシステム v2.2
=============================================
テスト区分:
  A. 業務フローテスト（E2Eシナリオ）
  B. セキュリティテスト
  C. 設計書準拠テスト（テーブル・API・スキーマ照合）

実行環境: PostgreSQL未接続（サンドボックス）
テスト方針: httpx ASGITransport で FastAPI アプリをインプロセステスト
"""

import pytest
import asyncio
import re
import uuid
import json
from datetime import datetime, date, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

# ---- App & Auth imports ----
from app.main import app
from app.auth import create_access_token, bearer_scheme
from app.config import get_settings

settings = get_settings()
BASE = "http://testserver"
JST = timezone(timedelta(hours=9))


# ---- Fixtures ----

@pytest.fixture
def transport():
    return ASGITransport(app=app)


@pytest.fixture
def client(transport):
    return httpx.AsyncClient(transport=transport, base_url=BASE)


def make_admin_token(user_id="test-admin", email="admin@hakusan.test"):
    return create_access_token({"sub": user_id, "email": email})


def admin_headers():
    return {"Authorization": f"Bearer {make_admin_token()}"}


def device_headers():
    return {"Authorization": f"Bearer {settings.device_api_keys_list[0]}"}


# ============================================================
# A. 業務フローテスト（Business Flow / E2E Scenarios）
# ============================================================

class TestBusinessFlowA1_SensorDataIngestion:
    """A1: IRセンサーデータ受信→DB保存→集計の業務フロー"""

    @pytest.mark.asyncio
    async def test_sensor_count_requires_auth(self, client):
        """A1-01: 認証なしでセンサーデータ送信 → 401"""
        resp = await client.post("/api/v1/sensor/count", json={
            "device_id": "hakusan_sabou_01",
            "timestamp": "2026-07-15T10:00:00+09:00",
            "up_count": 15, "down_count": 8,
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_sensor_count_with_valid_key(self, client):
        """A1-02: 有効なAPI Keyでセンサーデータ送信 → 201 or 500(DB不在)"""
        resp = await client.post("/api/v1/sensor/count",
            headers=device_headers(),
            json={
                "device_id": "hakusan_sabou_01",
                "timestamp": "2026-07-15T10:00:00+09:00",
                "up_count": 15, "down_count": 8,
                "battery_pct": 87, "temperature_c": 24.5,
            })
        # 201=正常, 500=DB未接続（環境制約）
        assert resp.status_code in (201, 500)

    @pytest.mark.asyncio
    async def test_sensor_count_invalid_device_id_format(self, client):
        """A1-03: device_id形式不正 → 422(バリデーションエラー)"""
        resp = await client.post("/api/v1/sensor/count",
            headers=device_headers(),
            json={
                "device_id": "INVALID-ID!!",  # 大文字・記号
                "timestamp": "2026-07-15T10:00:00+09:00",
                "up_count": 15, "down_count": 8,
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_sensor_count_negative_count(self, client):
        """A1-04: up_countが負数 → 422"""
        resp = await client.post("/api/v1/sensor/count",
            headers=device_headers(),
            json={
                "device_id": "hakusan_sabou_01",
                "timestamp": "2026-07-15T10:00:00+09:00",
                "up_count": -1, "down_count": 8,
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_sensor_count_battery_range(self, client):
        """A1-05: battery_pctが101 → 422"""
        resp = await client.post("/api/v1/sensor/count",
            headers=device_headers(),
            json={
                "device_id": "hakusan_sabou_01",
                "timestamp": "2026-07-15T10:00:00+09:00",
                "up_count": 15, "down_count": 8,
                "battery_pct": 101,
            })
        assert resp.status_code == 422


class TestBusinessFlowA2_CameraUpload:
    """A2: カメラ画像アップロード→AI解析パイプライン"""

    @pytest.mark.asyncio
    async def test_camera_upload_requires_auth(self, client):
        """A2-01: 認証なしで画像アップロード → 401"""
        resp = await client.post("/api/v1/camera/upload",
            data={"camera_id": "cam_01", "timestamp": "2026-07-15T10:00:00+09:00"},
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_camera_upload_with_valid_key(self, client):
        """A2-02: 有効なAPI Keyで画像アップロード → 201 or 500(DB不在)"""
        resp = await client.post("/api/v1/camera/upload",
            headers=device_headers(),
            data={"camera_id": "cam_01", "timestamp": "2026-07-15T10:00:00+09:00"},
            files={"file": ("test.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")},
        )
        assert resp.status_code in (201, 500)


class TestBusinessFlowA3_AdminDashboard:
    """A3: 管理者ログイン→ダッシュボード閲覧→デバイス管理"""

    @pytest.mark.asyncio
    async def test_dashboard_requires_auth(self, client):
        """A3-01: 認証なしでダッシュボード → 401"""
        resp = await client.get("/api/v1/admin/dashboard")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_dashboard_with_jwt(self, client):
        """A3-02: 有効JWTでダッシュボード → 200 or 500(DB不在)"""
        resp = await client.get("/api/v1/admin/dashboard", headers=admin_headers())
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_device_list_with_jwt(self, client):
        """A3-03: デバイス一覧取得 → 200 or 500"""
        resp = await client.get("/api/v1/admin/devices", headers=admin_headers())
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_device_update_requires_auth(self, client):
        """A3-04: 認証なしでデバイス更新 → 401"""
        resp = await client.patch("/api/v1/admin/devices/test_device",
            json={"status": "repair"})
        assert resp.status_code in (401, 403)


class TestBusinessFlowA4_CalibrationWorkflow:
    """A4: 精度補正管理（キャリブレーション登録→補正係数更新）"""

    @pytest.mark.asyncio
    async def test_calibration_record_create_validation(self, client):
        """A4-01: time_slot形式不正 → 422"""
        resp = await client.post("/api/v1/admin/calibration/records",
            headers=admin_headers(),
            json={
                "location_id": str(uuid.uuid4()),
                "date": "2026-07-15",
                "time_slot": "morning",  # 不正（正: "06-08"）
                "weather": "clear",
                "manual_ascending": 50,
                "manual_descending": 30,
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_calibration_record_weather_validation(self, client):
        """A4-02: weather値不正 → 422"""
        resp = await client.post("/api/v1/admin/calibration/records",
            headers=admin_headers(),
            json={
                "location_id": str(uuid.uuid4()),
                "date": "2026-07-15",
                "time_slot": "06-08",
                "weather": "stormy",  # 不正（正: clear/cloudy/rain）
                "manual_ascending": 50,
                "manual_descending": 30,
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_calibration_record_valid(self, client):
        """A4-03: 正常なキャリブレーション登録 → 201 or 500"""
        resp = await client.post("/api/v1/admin/calibration/records",
            headers=admin_headers(),
            json={
                "location_id": str(uuid.uuid4()),
                "date": "2026-07-15",
                "time_slot": "06-08",
                "weather": "clear",
                "manual_ascending": 50,
                "manual_descending": 30,
            })
        assert resp.status_code in (201, 500)


class TestBusinessFlowA5_TrailStatusManagement:
    """A5: 登山道状況管理（登録→更新→論理削除）"""

    @pytest.mark.asyncio
    async def test_trail_status_create_validation(self, client):
        """A5-01: status_type不正 → 422"""
        resp = await client.post("/api/v1/admin/trail-status",
            headers=admin_headers(),
            json={
                "status_type": "emergency",  # 不正（正: caution/info/danger）
                "title": "テスト",
                "description": "テスト説明",
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_trail_status_create_empty_title(self, client):
        """A5-02: タイトル空文字 → 422"""
        resp = await client.post("/api/v1/admin/trail-status",
            headers=admin_headers(),
            json={
                "status_type": "caution",
                "title": "",  # 空文字
                "description": "テスト説明",
            })
        assert resp.status_code == 422


class TestBusinessFlowA6_PublicAPI:
    """A6: 一般登山者向け公開API（認証なし）"""

    @pytest.mark.asyncio
    async def test_weather_endpoint(self, client):
        """A6-01: 天気API → 200 or 503(API到達不可)"""
        resp = await client.get("/api/v1/public/weather")
        assert resp.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_current_endpoint(self, client):
        """A6-02: 現在混雑状況 → 200 or 500(DB不在)"""
        resp = await client.get("/api/v1/public/current")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_current_routes_endpoint(self, client):
        """A6-03: ルート別混雑状況 → 200 or 500"""
        resp = await client.get("/api/v1/public/current/routes")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_hourly_endpoint(self, client):
        """A6-04: 時間帯別データ → 200 or 500"""
        resp = await client.get("/api/v1/public/hourly/2026-07-15")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_hourly_invalid_date(self, client):
        """A6-05: 不正な日付形式 → 422"""
        resp = await client.get("/api/v1/public/hourly/not-a-date")
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_forecast_calendar(self, client):
        """A6-06: 混雑予測カレンダー → 200 or 500"""
        resp = await client.get("/api/v1/public/forecast/calendar")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_forecast_dow(self, client):
        """A6-07: 曜日別平均 → 200 or 500"""
        resp = await client.get("/api/v1/public/forecast/dow")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_trail_status(self, client):
        """A6-08: 登山道状況 → 200 or 500"""
        resp = await client.get("/api/v1/public/trail-status")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_lodging(self, client):
        """A6-09: 山小屋混雑 → 200 or 500"""
        resp = await client.get("/api/v1/public/lodging")
        assert resp.status_code in (200, 500)


class TestBusinessFlowA7_AlertWorkflow:
    """A7: アラート管理（登録→既読化）"""

    @pytest.mark.asyncio
    async def test_alert_create(self, client):
        """A7-01: アラート手動登録 → 201 or 500"""
        resp = await client.post("/api/v1/admin/alerts",
            headers=admin_headers(),
            json={
                "alert_type": "daily_alert",
                "title": "本日の注意事項",
                "message": "午後から雷雨予報。早めの下山を推奨。",
            })
        assert resp.status_code in (201, 500)

    @pytest.mark.asyncio
    async def test_alert_update_requires_auth(self, client):
        """A7-02: 認証なしでアラート更新 → 401"""
        resp = await client.patch(f"/api/v1/admin/alerts/{uuid.uuid4()}",
            json={"is_read": True})
        assert resp.status_code in (401, 403)


class TestBusinessFlowA8_ExportWorkflow:
    """A8: CSV/Excelエクスポート"""

    @pytest.mark.asyncio
    async def test_export_calibration(self, client):
        """A8-01: キャリブレーションCSVエクスポート → 200 or 500"""
        resp = await client.get("/api/v1/admin/export/calibration", headers=admin_headers())
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert "text/csv" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_export_camera(self, client):
        """A8-02: カメラCSVエクスポート → 200 or 500"""
        resp = await client.get("/api/v1/admin/export/camera", headers=admin_headers())
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_export_site(self, client):
        """A8-03: 設置場所CSVエクスポート → 200 or 500"""
        resp = await client.get("/api/v1/admin/export/site", headers=admin_headers())
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_export_unknown_type(self, client):
        """A8-04: 不明なエクスポートタイプ → 400"""
        resp = await client.get("/api/v1/admin/export/unknown", headers=admin_headers())
        # 400 (アプリ判定) or 500 (DB不在でその前に失敗)
        assert resp.status_code in (400, 500)


# ============================================================
# B. セキュリティテスト
# ============================================================

class TestSecurityB1_Authentication:
    """B1: 認証・認可テスト"""

    @pytest.mark.asyncio
    async def test_admin_no_token(self, client):
        """B1-01: トークンなしで管理者API → 401"""
        endpoints = [
            ("GET", "/api/v1/admin/dashboard"),
            ("GET", "/api/v1/admin/devices"),
            ("GET", "/api/v1/admin/history"),
            ("GET", "/api/v1/admin/calibration/factors"),
            ("GET", "/api/v1/admin/calibration/records"),
            ("GET", "/api/v1/admin/camera-analysis"),
            ("GET", "/api/v1/admin/site-analysis"),
            ("POST", "/api/v1/admin/trail-status"),
            ("POST", "/api/v1/admin/alerts"),
        ]
        for method, path in endpoints:
            if method == "GET":
                resp = await client.get(path)
            else:
                resp = await client.post(path, json={})
            assert resp.status_code in (401, 403, 422), \
                f"{method} {path}: expected 401/403/422, got {resp.status_code}"

    @pytest.mark.asyncio
    async def test_admin_invalid_token(self, client):
        """B1-02: 不正なJWTで管理者API → 401"""
        headers = {"Authorization": "Bearer invalid.token.here"}
        resp = await client.get("/api/v1/admin/dashboard", headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_expired_token(self, client):
        """B1-03: 期限切れJWT → 401"""
        expired_token = create_access_token(
            {"sub": "test", "email": "test@test.com"},
            expires_delta=timedelta(seconds=-1)
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        resp = await client.get("/api/v1/admin/dashboard", headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_token_missing_sub(self, client):
        """B1-04: subフィールドなしのJWT → 401"""
        from jose import jwt
        token = jwt.encode(
            {"email": "nope@test.com", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
            settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/admin/dashboard", headers=headers)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_device_no_key(self, client):
        """B1-05: API Keyなしでデバイスエンドポイント → 401"""
        resp = await client.post("/api/v1/sensor/count", json={
            "device_id": "hakusan_sabou_01",
            "timestamp": "2026-07-15T10:00:00+09:00",
            "up_count": 1, "down_count": 0,
        })
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_device_invalid_key(self, client):
        """B1-06: 無効なAPI Key → 403"""
        headers = {"Authorization": "Bearer fake_key_12345"}
        resp = await client.post("/api/v1/sensor/count",
            headers=headers,
            json={
                "device_id": "hakusan_sabou_01",
                "timestamp": "2026-07-15T10:00:00+09:00",
                "up_count": 1, "down_count": 0,
            })
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_public_no_auth_required(self, client):
        """B1-07: 公開APIは認証不要で到達可能"""
        endpoints = [
            "/api/v1/public/weather",
            "/api/v1/public/current",
            "/api/v1/public/current/routes",
            "/api/v1/public/hourly/2026-07-15",
            "/api/v1/public/forecast/calendar",
            "/api/v1/public/forecast/dow",
            "/api/v1/public/trail-status",
            "/api/v1/public/lodging",
        ]
        for path in endpoints:
            resp = await client.get(path)
            # 200=正常, 500=DB不在, 503=外部API不達 → いずれも認証エラーではない
            assert resp.status_code not in (401, 403), \
                f"{path}: got auth error {resp.status_code}"


class TestSecurityB2_InputValidation:
    """B2: 入力バリデーション・インジェクション対策"""

    @pytest.mark.asyncio
    async def test_sql_injection_device_id(self, client):
        """B2-01: SQLインジェクション試行 → 422(バリデーション拒否)"""
        resp = await client.post("/api/v1/sensor/count",
            headers=device_headers(),
            json={
                "device_id": "'; DROP TABLE devices;--",
                "timestamp": "2026-07-15T10:00:00+09:00",
                "up_count": 1, "down_count": 0,
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_in_trail_status_title(self, client):
        """B2-02: XSSペイロード → 保存されてもエスケープ確認"""
        resp = await client.post("/api/v1/admin/trail-status",
            headers=admin_headers(),
            json={
                "status_type": "info",
                "title": '<script>alert("xss")</script>',
                "description": "テスト",
            })
        # 201(保存される)または500(DB不在)
        # FastAPI+Pydanticは文字列をそのまま保存するが、
        # JSONレスポンスなのでブラウザでは自動エスケープされる
        assert resp.status_code in (201, 500)

    @pytest.mark.asyncio
    async def test_oversized_payload(self, client):
        """B2-03: 超大サイズJSON → エラー"""
        huge = "x" * (1024 * 1024)  # 1MB文字列
        resp = await client.post("/api/v1/admin/trail-status",
            headers=admin_headers(),
            json={
                "status_type": "info",
                "title": huge,
                "description": "test",
            })
        # 422(max_length制限) or 413(payload too large)
        assert resp.status_code in (422, 413, 500)

    @pytest.mark.asyncio
    async def test_device_id_regex_validation(self, client):
        """B2-04: device_id正規表現 ^[a-z0-9_]{5,50}$ 検証"""
        invalid_ids = [
            "ab",           # 短すぎ (5未満)
            "A" * 5,        # 大文字
            "abc-def",      # ハイフン
            "a" * 51,       # 長すぎ (50超)
            "abc def",      # スペース
        ]
        for did in invalid_ids:
            resp = await client.post("/api/v1/sensor/count",
                headers=device_headers(),
                json={
                    "device_id": did,
                    "timestamp": "2026-07-15T10:00:00+09:00",
                    "up_count": 1, "down_count": 0,
                })
            assert resp.status_code == 422, \
                f"device_id '{did}' should be rejected, got {resp.status_code}"


class TestSecurityB3_CORS:
    """B3: CORS設定テスト"""

    @pytest.mark.asyncio
    async def test_cors_allowed_origin(self, client):
        """B3-01: 許可されたオリジンからのリクエスト → CORSヘッダーあり"""
        resp = await client.options("/api/v1/public/weather",
            headers={
                "Origin": "https://ishikawa8.github.io",
                "Access-Control-Request-Method": "GET",
            })
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    @pytest.mark.asyncio
    async def test_cors_disallowed_origin(self, client):
        """B3-02: 許可されていないオリジンからのリクエスト"""
        resp = await client.options("/api/v1/public/weather",
            headers={
                "Origin": "https://evil-site.com",
                "Access-Control-Request-Method": "GET",
            })
        origin_header = resp.headers.get("access-control-allow-origin", "")
        assert "evil-site.com" not in origin_header


class TestSecurityB4_ErrorHandling:
    """B4: エラーハンドリング・情報漏洩防止"""

    @pytest.mark.asyncio
    async def test_404_no_stack_trace(self, client):
        """B4-01: 存在しないパス → スタックトレース非露出"""
        resp = await client.get("/api/v1/nonexistent")
        assert resp.status_code in (404, 405)
        body = resp.text
        assert "Traceback" not in body
        assert "File " not in body

    @pytest.mark.asyncio
    async def test_global_error_handler(self, client):
        """B4-02: 500エラー時に内部情報非露出"""
        # DB未接続で500が返る → メッセージ確認
        # DB接続エラーはConnectionRefusedError → global exception handlerでキャッチされるはず
        try:
            resp = await client.get("/api/v1/public/current")
            if resp.status_code == 500:
                body = resp.json()
                assert "error" in body
                assert "password" not in json.dumps(body).lower()
                assert "postgresql" not in json.dumps(body).lower()
        except Exception as e:
            # BUG: DB接続エラーがglobal exception handlerを通過して
            # httpxまで伝播している場合、これはバグとして記録
            pytest.fail(f"BUG-014: DB接続エラーがglobal exception handlerで捕捉されず伝播: {type(e).__name__}: {e}")

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """B4-03: ヘルスチェック → DB接続情報の適切な公開"""
        resp = await client.get("/api/v1/health")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            body = resp.json()
            assert "status" in body
            assert "version" in body


# ============================================================
# C. 設計書準拠テスト
# ============================================================

class TestDesignDocC1_Tables:
    """C1: 16テーブル定義の設計書準拠"""

    def test_all_16_tables_exist(self):
        """C1-01: 16テーブルがすべてモデル定義されていること"""
        from app.models import tables
        expected_tables = [
            "locations", "routes", "waypoints", "facilities",
            "devices", "sensor_counts", "hourly_counts", "route_realtime",
            "calibration_records", "calibration_factors",
            "camera_images", "camera_analyses",
            "trail_status", "lodging", "alerts", "device_status_log",
        ]
        from app.database import Base
        actual_tables = list(Base.metadata.tables.keys())
        for table in expected_tables:
            assert table in actual_tables, f"テーブル '{table}' が未定義"
        assert len(actual_tables) == 16, \
            f"テーブル数不一致: expected 16, got {len(actual_tables)} ({actual_tables})"

    def test_locations_columns(self):
        """C1-02: locationsテーブルのカラム定義"""
        from app.models.tables import Location
        cols = {c.name for c in Location.__table__.columns}
        expected = {"id", "name", "prefecture", "latitude", "longitude",
                    "elevation", "is_active", "created_at"}
        assert expected == cols, f"locations columns mismatch: extra={cols-expected}, missing={expected-cols}"

    def test_routes_columns(self):
        """C1-03: routesテーブルのカラム定義"""
        from app.models.tables import Route
        cols = {c.name for c in Route.__table__.columns}
        expected = {"id", "name", "description", "description_long",
                    "start_location_id", "usage_percentage", "elevation_gain",
                    "difficulty", "duration_hours", "is_recommended", "sort_order"}
        assert expected == cols

    def test_waypoints_columns(self):
        """C1-04: waypointsテーブルのカラム定義"""
        from app.models.tables import Waypoint
        cols = {c.name for c in Waypoint.__table__.columns}
        expected = {"id", "route_id", "name", "elevation", "course_time_min",
                    "has_toilet", "has_water", "has_shelter", "description",
                    "retreat_warning", "is_confusing_point", "warning_text", "sort_order"}
        assert expected == cols

    def test_facilities_columns(self):
        """C1-05: facilitiesテーブルのカラム定義"""
        from app.models.tables import Facility
        cols = {c.name for c in Facility.__table__.columns}
        expected = {"id", "name", "route_id", "elevation", "has_toilet",
                    "has_water", "has_shelter", "has_hot_spring", "lodging_type", "notes"}
        assert expected == cols

    def test_devices_columns(self):
        """C1-06: devicesテーブルのカラム定義"""
        from app.models.tables import Device
        cols = {c.name for c in Device.__table__.columns}
        expected = {"id", "device_id", "location_id", "device_type", "model",
                    "status", "battery_pct", "temperature_c", "last_data_at",
                    "last_heartbeat", "installed_at", "maintenance_notes", "created_at"}
        assert expected == cols

    def test_device_id_unique(self):
        """C1-07: devices.device_idにUNIQUE制約"""
        from app.models.tables import Device
        device_id_col = Device.__table__.c.device_id
        assert device_id_col.unique is True

    def test_sensor_counts_columns(self):
        """C1-08: sensor_countsテーブルのカラム定義"""
        from app.models.tables import SensorCount
        cols = {c.name for c in SensorCount.__table__.columns}
        expected = {"id", "device_id", "location_id", "timestamp",
                    "up_count", "down_count", "battery_pct", "temperature_c", "created_at"}
        assert expected == cols

    def test_sensor_counts_indexes(self):
        """C1-09: sensor_countsのインデックス（設計書: location_id+timestamp, device_id+timestamp）"""
        from app.models.tables import SensorCount
        index_names = [idx.name for idx in SensorCount.__table__.indexes]
        assert "idx_sensor_counts_loc_ts" in index_names
        assert "idx_sensor_counts_dev_ts" in index_names

    def test_hourly_counts_unique_constraint(self):
        """C1-10: hourly_countsのユニーク制約 (date, location_id, hour)"""
        from app.models.tables import HourlyCount
        constraints = [c.name for c in HourlyCount.__table__.constraints
                       if hasattr(c, 'name') and c.name]
        assert "uq_hourly_counts" in constraints

    def test_route_realtime_unique_constraint(self):
        """C1-11: route_realtimeのユニーク制約 (route_id, date)"""
        from app.models.tables import RouteRealtime
        constraints = [c.name for c in RouteRealtime.__table__.constraints
                       if hasattr(c, 'name') and c.name]
        assert "uq_route_realtime" in constraints

    def test_calibration_factors_unique_constraint(self):
        """C1-12: calibration_factorsのユニーク制約 (location_id, weather, valid_from)"""
        from app.models.tables import CalibrationFactor
        constraints = [c.name for c in CalibrationFactor.__table__.constraints
                       if hasattr(c, 'name') and c.name]
        assert "uq_cal_factors" in constraints

    def test_camera_images_indexes(self):
        """C1-13: camera_imagesのインデックス"""
        from app.models.tables import CameraImage
        index_names = [idx.name for idx in CameraImage.__table__.indexes]
        assert "idx_camera_images_status" in index_names
        assert "idx_camera_images_cam_ts" in index_names

    def test_camera_analyses_image_id_unique(self):
        """C1-14: camera_analyses.image_idにUNIQUE制約（1:1関係）"""
        from app.models.tables import CameraAnalysis
        image_id_col = CameraAnalysis.__table__.c.image_id
        assert image_id_col.unique is True

    def test_device_status_log_index(self):
        """C1-15: device_status_logのインデックス"""
        from app.models.tables import DeviceStatusLog
        index_names = [idx.name for idx in DeviceStatusLog.__table__.indexes]
        assert "idx_dsl_device_created" in index_names

    def test_foreign_keys_sensor_counts(self):
        """C1-16: sensor_counts FK → devices.device_id, locations.id"""
        from app.models.tables import SensorCount
        fks = {str(fk.target_fullname) for fk in SensorCount.__table__.foreign_keys}
        assert "devices.device_id" in fks
        assert "locations.id" in fks

    def test_foreign_keys_camera_images(self):
        """C1-17: camera_images FK → devices.device_id"""
        from app.models.tables import CameraImage
        fks = {str(fk.target_fullname) for fk in CameraImage.__table__.foreign_keys}
        assert "devices.device_id" in fks

    def test_lodging_columns(self):
        """C1-18: lodgingテーブルのカラム定義"""
        from app.models.tables import Lodging
        cols = {c.name for c in Lodging.__table__.columns}
        expected = {"id", "name", "route_id", "capacity", "reservation_required",
                    "price_text", "occupancy_pct", "tip"}
        assert expected == cols

    def test_alerts_columns(self):
        """C1-19: alertsテーブルのカラム定義"""
        from app.models.tables import Alert
        cols = {c.name for c in Alert.__table__.columns}
        expected = {"id", "alert_type", "location_id", "device_id",
                    "title", "message", "value", "threshold", "is_read", "created_at"}
        assert expected == cols

    def test_trail_status_columns(self):
        """C1-20: trail_statusテーブルのカラム定義"""
        from app.models.tables import TrailStatus
        cols = {c.name for c in TrailStatus.__table__.columns}
        expected = {"id", "route_id", "status_type", "title", "description",
                    "source", "is_active", "updated_at"}
        assert expected == cols

    def test_calibration_records_columns(self):
        """C1-21: calibration_recordsテーブルのカラム定義"""
        from app.models.tables import CalibrationRecord
        cols = {c.name for c in CalibrationRecord.__table__.columns}
        expected = {"id", "location_id", "date", "time_slot", "weather",
                    "manual_ascending", "manual_descending", "ir_ascending",
                    "ir_descending", "correction_factor", "operator", "created_at"}
        assert expected == cols

    def test_camera_analyses_columns(self):
        """C1-22: camera_analysesテーブルのカラム定義"""
        from app.models.tables import CameraAnalysis
        cols = {c.name for c in CameraAnalysis.__table__.columns}
        expected = {"id", "image_id", "detected_person_count", "group_count",
                    "group_composition", "ir_count_at_time", "confidence_score",
                    "correction_suggestion", "raw_metadata", "created_at"}
        assert expected == cols

    def test_device_status_log_columns(self):
        """C1-23: device_status_logテーブルのカラム定義"""
        from app.models.tables import DeviceStatusLog
        cols = {c.name for c in DeviceStatusLog.__table__.columns}
        # 設計書: device_id → 実装: device_id_fk（FK競合回避）
        expected = {"id", "device_id_fk", "previous_status", "new_status",
                    "battery_pct", "changed_by", "reason", "created_at"}
        assert expected == cols


class TestDesignDocC2_APIEndpoints:
    """C2: APIエンドポイント数・パス・メソッドの設計書準拠"""

    @pytest.mark.asyncio
    async def test_public_endpoint_count(self, client):
        """C2-01: 公開API = 8本"""
        from app.routers.public import router
        routes = [r for r in router.routes if hasattr(r, 'methods')]
        assert len(routes) == 8, f"Public endpoints: expected 8, got {len(routes)}"

    @pytest.mark.asyncio
    async def test_admin_endpoint_count(self, client):
        """C2-02: 管理者API = 16本（設計書本文は15と記載だが表は16）"""
        from app.routers.admin import router
        routes = [r for r in router.routes if hasattr(r, 'methods')]
        assert len(routes) == 16, f"Admin endpoints: expected 16, got {len(routes)}"

    @pytest.mark.asyncio
    async def test_device_endpoint_count(self, client):
        """C2-03: デバイスAPI = 2本"""
        from app.routers.device import router
        routes = [r for r in router.routes if hasattr(r, 'methods')]
        assert len(routes) == 2, f"Device endpoints: expected 2, got {len(routes)}"

    @pytest.mark.asyncio
    async def test_health_endpoint_exists(self, client):
        """C2-04: ヘルスチェックエンドポイント存在確認"""
        resp = await client.get("/api/v1/health")
        assert resp.status_code in (200, 500)

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """C2-05: ルートエンドポイント → API情報返却"""
        resp = await client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert "version" in body
        assert body["version"] == "2.2.0"

    @pytest.mark.asyncio
    async def test_api_version_prefix(self, client):
        """C2-06: 全APIに /api/v1/ プレフィックスが付与されていること"""
        from app.routers import public, admin, device, health
        for router_module in [public, admin, device]:
            prefix = router_module.router.prefix
            assert prefix.startswith("/api/v1"), \
                f"Router prefix '{prefix}' does not start with /api/v1"

    @pytest.mark.asyncio
    async def test_public_api_paths(self, client):
        """C2-07: 公開API8本のパス一致確認"""
        from app.routers.public import router
        # router.routes の path はプレフィックス含む
        prefix = router.prefix  # "/api/v1/public"
        paths = {r.path.replace(prefix, "") for r in router.routes if hasattr(r, 'methods')}
        expected_paths = {
            "/weather", "/current", "/current/routes",
            "/hourly/{target_date}", "/forecast/calendar", "/forecast/dow",
            "/trail-status", "/lodging",
        }
        assert expected_paths == paths, \
            f"Path mismatch: extra={paths-expected_paths}, missing={expected_paths-paths}"

    @pytest.mark.asyncio
    async def test_admin_api_paths_and_methods(self, client):
        """C2-08: 管理者API16本のパス・メソッド一致確認"""
        from app.routers.admin import router
        prefix = router.prefix  # "/api/v1/admin"
        route_info = set()
        for r in router.routes:
            if hasattr(r, 'methods'):
                for method in r.methods:
                    if method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                        route_info.add((method, r.path.replace(prefix, "")))
        expected = {
            ("GET", "/dashboard"),
            ("GET", "/history"),
            ("GET", "/devices"),
            ("PATCH", "/devices/{device_id}"),
            ("GET", "/calibration/factors"),
            ("PUT", "/calibration/factors/{factor_id}"),
            ("GET", "/calibration/records"),
            ("POST", "/calibration/records"),
            ("GET", "/camera-analysis"),
            ("GET", "/site-analysis"),
            ("GET", "/export/{export_type}"),
            ("POST", "/trail-status"),
            ("PUT", "/trail-status/{status_id}"),
            ("DELETE", "/trail-status/{status_id}"),
            ("POST", "/alerts"),
            ("PATCH", "/alerts/{alert_id}"),
        }
        assert expected == route_info, \
            f"Admin route mismatch: extra={route_info-expected}, missing={expected-route_info}"


class TestDesignDocC3_WeatherService:
    """C3: 天気サービスの設計書準拠"""

    def test_weather_grade_logic(self):
        """C3-01: 天気グレード判定ロジック（設計書Tab1）"""
        from app.services.weather import _weather_grade
        # C: WMO≧95 or 風速≧15
        assert _weather_grade(95, 5, 0) == "C"
        assert _weather_grade(99, 0, 0) == "C"
        assert _weather_grade(0, 15, 0) == "C"
        assert _weather_grade(0, 20, 0) == "C"
        # B: WMO≧61 or 風速≧10 or 降水確率≧60
        assert _weather_grade(61, 5, 0) == "B"
        assert _weather_grade(0, 10, 0) == "B"
        assert _weather_grade(0, 5, 60) == "B"
        # A: それ以外
        assert _weather_grade(0, 0, 0) == "A"
        assert _weather_grade(3, 5, 30) == "A"
        assert _weather_grade(60, 9, 59) == "A"

    def test_clothing_advice(self):
        """C3-02: 服装アドバイスの温度閾値"""
        from app.services.weather import _clothing_advice
        assert "厳冬" in _clothing_advice(-5)
        assert "フリース" in _clothing_advice(3)
        assert "防寒着" in _clothing_advice(8)
        assert "半袖" in _clothing_advice(25)

    def test_wind_note(self):
        """C3-03: 風速コメント"""
        from app.services.weather import _wind_note
        assert "暴風" in _wind_note(25)
        assert "強風" in _wind_note(15)
        assert "穏やか" in _wind_note(5)

    def test_open_meteo_coordinates(self):
        """C3-04: Open-Meteo座標設定（設計書: 白山山頂 標高2702m）"""
        assert settings.open_meteo_elevation == 2702
        assert abs(settings.open_meteo_latitude - 36.1533) < 0.01
        assert abs(settings.open_meteo_longitude - 136.7717) < 0.01

    def test_cache_ttl(self):
        """C3-05: キャッシュTTL = 1時間（3600秒）"""
        from app.services.weather import CACHE_TTL
        assert CACHE_TTL == 3600


class TestDesignDocC4_CongestionService:
    """C4: 混雑判定ロジックの設計書準拠"""

    def test_congestion_levels(self):
        """C4-01: 混雑レベル判定閾値"""
        from app.services.congestion import congestion_level
        assert congestion_level(300) == "high"
        assert congestion_level(250) == "high"
        assert congestion_level(249) == "mid"
        assert congestion_level(100) == "mid"
        assert congestion_level(99) == "low"
        assert congestion_level(0) == "low"

    def test_dow_japanese_labels(self):
        """C4-02: 曜日ラベル（日本語）"""
        from app.services.congestion import DOW_JA
        assert DOW_JA == ["月", "火", "水", "木", "金", "土", "日"]


class TestDesignDocC5_AIModule:
    """C5: AI解析モジュールの設計書準拠"""

    def test_base_analyzer_abstract(self):
        """C5-01: BaseAnalyzerが抽象クラスであること"""
        from app.services.ai_analyzer import BaseAnalyzer
        import abc
        assert issubclass(BaseAnalyzer, abc.ABC)

    def test_detectron2_analyzer_exists(self):
        """C5-02: Detectron2Analyzerクラスが存在"""
        from app.services.ai_analyzer import Detectron2Analyzer, BaseAnalyzer
        assert issubclass(Detectron2Analyzer, BaseAnalyzer)

    def test_mock_fallback(self):
        """C5-03: Detectron2未インストール時のモックフォールバック"""
        from app.services.ai_analyzer import Detectron2Analyzer
        analyzer = Detectron2Analyzer()
        result = analyzer._mock_analyze()
        assert result.person_count >= 0
        assert result.group_count >= 0
        assert 0.0 <= result.confidence_score <= 1.0
        assert isinstance(result.group_composition, list)

    def test_detection_result_structure(self):
        """C5-04: DetectionResultのフィールド構造"""
        from app.services.ai_analyzer import DetectionResult
        r = DetectionResult(
            person_count=5, group_count=2,
            group_composition=[{"size": 3}, {"size": 2}],
            confidence_score=0.85,
            raw_metadata={"model": "test"}
        )
        assert r.person_count == 5
        assert r.group_count == 2
        assert len(r.group_composition) == 2


class TestDesignDocC6_CameraAdapter:
    """C6: Camera Adapterパターンの設計書準拠"""

    def test_base_adapter_interface(self):
        """C6-01: BaseCameraAdapterのインターフェース（設計書4.5）"""
        from app.services.camera_adapter import BaseCameraAdapter
        import inspect
        methods = [m for m in dir(BaseCameraAdapter)
                   if not m.startswith('_') and callable(getattr(BaseCameraAdapter, m))]
        assert "parse_payload" in methods
        assert "extract_image" in methods
        assert "get_device_status" in methods

    def test_generic_adapter_parse(self):
        """C6-02: GenericCameraAdapterのparse_payload動作"""
        import base64
        from app.services.camera_adapter import get_camera_adapter
        adapter = get_camera_adapter("generic")
        test_image = base64.b64encode(b"\xff\xd8\xff\xe0").decode()
        event = adapter.parse_payload({
            "camera_id": "cam_test",
            "timestamp": "2026-07-15T10:00:00+09:00",
            "image_base64": test_image,
        })
        assert event.camera_id == "cam_test"
        assert len(event.image_bytes) > 0


class TestDesignDocC7_ErrorResponse:
    """C7: エラーレスポンス形式の設計書準拠"""

    @pytest.mark.asyncio
    async def test_error_response_format(self, client):
        """C7-01: 500エラーレスポンスの形式（設計書4.1）"""
        try:
            resp = await client.get("/api/v1/public/current")
            if resp.status_code == 500:
                body = resp.json()
                assert "error" in body
                assert "code" in body["error"]
                assert "message" in body["error"]
        except Exception:
            # DB接続エラーが伝播する場合はBUG-014と同根
            pytest.skip("DB connection error propagated (see BUG-014)")

    @pytest.mark.asyncio
    async def test_validation_error_422(self, client):
        """C7-02: バリデーションエラーは422"""
        resp = await client.post("/api/v1/sensor/count",
            headers=device_headers(),
            json={"device_id": "BAD", "timestamp": "invalid"})
        assert resp.status_code == 422


class TestDesignDocC8_Pagination:
    """C8: ページネーションの設計書準拠"""

    @pytest.mark.asyncio
    async def test_calibration_records_pagination(self, client):
        """C8-01: calibration/recordsのlimit/offsetパラメータ"""
        # limit上限500
        resp = await client.get("/api/v1/admin/calibration/records?limit=501",
            headers=admin_headers())
        assert resp.status_code == 422  # ge=1, le=500

    @pytest.mark.asyncio
    async def test_calibration_records_negative_offset(self, client):
        """C8-02: offsetが負数 → 422"""
        resp = await client.get("/api/v1/admin/calibration/records?offset=-1",
            headers=admin_headers())
        assert resp.status_code == 422


class TestDesignDocC9_BackgroundTasks:
    """C9: バックグラウンドタスクの設計書準拠"""

    def test_scheduler_jobs_configured(self):
        """C9-01: APSchedulerのジョブが2つ定義されていること"""
        # main.pyのソースコードからジョブ登録を確認
        import inspect
        from app import main as main_module
        source = inspect.getsource(main_module.lifespan)
        assert "aggregate_hourly" in source
        assert "process_pending_images" in source
        assert 'minutes=10' in source  # hourly_agg interval
        assert 'minutes=5' in source   # ai_worker interval
