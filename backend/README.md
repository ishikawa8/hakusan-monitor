# 登山者モニタリングシステム - バックエンドAPI

白山国立公園 登山者モニタリングシステムのバックエンドAPI (v2.2)

## 技術スタック

- **Python 3.12** / **FastAPI**
- **PostgreSQL** (Supabase)
- **SQLAlchemy 2.0** (async)
- **Detectron2** (AI画像解析)
- **APScheduler** (バックグラウンドタスク)

## セットアップ

### Docker (推奨)

```bash
cd backend
docker-compose up -d
# API: http://localhost:8000
# Docs: http://localhost:8000/docs

# モックデータ投入
docker-compose exec api python -m scripts.seed_data
```

### ローカル開発

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# .env設定
cp .env.example .env
# DATABASE_URL等を編集

# 起動
uvicorn app.main:app --reload

# モックデータ投入
python -m scripts.seed_data
```

## API エンドポイント一覧 (25本)

### 公開API (認証なし) - 8本
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/v1/public/weather` | 山岳気象情報 |
| GET | `/api/v1/public/current` | 全登山口の混雑状況 |
| GET | `/api/v1/public/current/routes` | ルート別混雑状況 |
| GET | `/api/v1/public/hourly/{date}` | 時間帯別入下山者数 |
| GET | `/api/v1/public/forecast/calendar` | 2週間混雑予測 |
| GET | `/api/v1/public/forecast/dow` | 曜日別平均 |
| GET | `/api/v1/public/trail-status` | 登山道状況 |
| GET | `/api/v1/public/lodging` | 山小屋混雑状況 |

### 管理者API (JWT認証) - 15本
| Method | Endpoint | 説明 |
|--------|----------|------|
| GET | `/api/v1/admin/dashboard` | ダッシュボード集計 |
| GET | `/api/v1/admin/history` | 過去データ分析 |
| GET | `/api/v1/admin/devices` | デバイス一覧 |
| PATCH | `/api/v1/admin/devices/{id}` | デバイス更新 |
| GET | `/api/v1/admin/calibration/factors` | 補正係数 |
| PUT | `/api/v1/admin/calibration/factors/{id}` | 補正係数更新 |
| GET | `/api/v1/admin/calibration/records` | 補正記録一覧 |
| POST | `/api/v1/admin/calibration/records` | 補正記録登録 |
| GET | `/api/v1/admin/camera-analysis` | AI解析結果 |
| GET | `/api/v1/admin/site-analysis` | 設置場所分析 |
| GET | `/api/v1/admin/export/{type}` | CSVエクスポート |
| POST | `/api/v1/admin/trail-status` | 登山道状況登録 |
| PUT | `/api/v1/admin/trail-status/{id}` | 登山道状況更新 |
| DELETE | `/api/v1/admin/trail-status/{id}` | 登山道状況削除 |
| POST | `/api/v1/admin/alerts` | アラート登録 |
| PATCH | `/api/v1/admin/alerts/{id}` | アラート更新 |

### デバイスAPI (API Key認証) - 2本
| Method | Endpoint | 説明 |
|--------|----------|------|
| POST | `/api/v1/sensor/count` | センサーデータ受信 |
| POST | `/api/v1/camera/upload` | カメラ画像アップロード |

## データベース (16テーブル)

locations, routes, waypoints, facilities, devices, sensor_counts,
hourly_counts, route_realtime, calibration_records, calibration_factors,
camera_images, camera_analyses, trail_status, lodging, alerts, device_status_log

## テスト

```bash
pytest tests/ -v
```

## Detectron2 インストール (AI解析用)

```bash
pip install 'git+https://github.com/facebookresearch/detectron2.git'
```
未インストール時はモック解析が自動的に使用されます。
