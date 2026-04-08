"""Seed mock data matching frontend hardcoded values.

Usage: python -m scripts.seed_data
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from app.database import engine, async_session, Base
from app.models import (
    Location, Route, Waypoint, Facility, Device, SensorCount,
    HourlyCount, RouteRealtime, CalibrationRecord, CalibrationFactor,
    CameraImage, CameraAnalysis, TrailStatus, Lodging, Alert, DeviceStatusLog,
)

JST = timezone(timedelta(hours=9))


def uid():
    return uuid.uuid4()


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        # ===== 1. Locations (5 trailheads) =====
        locs = {}
        loc_data = [
            ("砂防新道", "石川", 36.1533, 136.7717, 1260),
            ("観光新道", "石川", 36.1520, 136.7700, 1260),
            ("平瀬道", "岐阜", 36.1300, 136.8100, 1230),
            ("市ノ瀬・別山道", "石川", 36.1400, 136.7500, 830),
            ("釈迦新道", "石川", 36.1450, 136.7400, 900),
        ]
        for name, pref, lat, lon, elev in loc_data:
            loc = Location(name=name, prefecture=pref, latitude=lat, longitude=lon, elevation=elev)
            db.add(loc)
            locs[name] = loc
        await db.flush()

        # ===== 2. Routes (5 routes) =====
        routes = {}
        route_data = [
            ("砂防新道", "別当出合→室堂", "最もポピュラーなルート。登山道が整備されており初心者にも安心。甚之助避難小屋で休憩可能。",
             "砂防新道", 72.9, 1450, "初級〜中級", 5.0, False, 1),
            ("観光新道", "別当出合→室堂", "花の多いルート。砂防新道より静かで展望が良い。下山に人気。",
             "観光新道", 10.9, 1450, "中級", 5.5, True, 2),
            ("平瀬道", "大白川→室堂", "岐阜県側からのルート。大白川ダムの絶景と温泉が魅力。",
             "平瀬道", 9.4, 1470, "中級", 6.0, True, 3),
            ("市ノ瀬・別山道", "市ノ瀬→別山→室堂", "別山経由の縦走ルート。上級者向け。",
             "市ノ瀬・別山道", 4.9, 1870, "上級", 8.0, False, 4),
            ("釈迦新道", "市ノ瀬→釈迦岳→室堂", "最も静かなルート。自然度が高い。",
             "釈迦新道", 1.9, 1800, "上級", 9.0, False, 5),
        ]
        for name, desc, desc_long, loc_name, pct, gain, diff, dur, rec, order in route_data:
            route = Route(
                name=name, description=desc, description_long=desc_long,
                start_location_id=locs[loc_name].id, usage_percentage=pct,
                elevation_gain=gain, difficulty=diff, duration_hours=dur,
                is_recommended=rec, sort_order=order,
            )
            db.add(route)
            routes[name] = route
        await db.flush()

        # ===== 3. Waypoints (砂防新道 timeline) =====
        wp_data = [
            ("別当出合", 1260, 0, False, True, False, False, None, 1),
            ("中飯場", 1520, 60, True, True, False, False, None, 2),
            ("甚之助避難小屋", 1970, 120, True, True, True, False, "天候悪化時はここで引き返す判断を", 3),
            ("南竜分岐", 2100, 150, False, False, False, False, None, 4),
            ("黒ボコ岩", 2320, 210, False, False, False, False, "ここから先は稜線。強風注意", 5),
            ("室堂", 2450, 270, True, True, True, False, None, 6),
        ]
        for name, elev, time, toilet, water, shelter, confuse, warn, order in wp_data:
            db.add(Waypoint(
                route_id=routes["砂防新道"].id, name=name, elevation=elev,
                course_time_min=time, has_toilet=toilet, has_water=water,
                has_shelter=shelter, is_confusing_point=confuse,
                warning_text=warn if confuse else None,
                retreat_warning=warn, sort_order=order,
            ))

        # ===== 4. Facilities =====
        fac_data = [
            ("別当出合休憩舎", "砂防新道", 1260, True, True, False, False, None),
            ("中飯場", "砂防新道", 1520, True, True, False, False, None),
            ("甚之助避難小屋", "砂防新道", 1970, True, True, True, False, None),
            ("白山室堂", "砂防新道", 2450, True, True, True, False, "要予約"),
            ("南竜山荘", "砂防新道", 2080, True, True, True, False, "要予約"),
            ("大白川露天風呂", "平瀬道", 1230, False, True, False, True, None),
        ]
        for name, rname, elev, toilet, water, shelter, spring, lodging_t in fac_data:
            db.add(Facility(
                name=name, route_id=routes[rname].id, elevation=elev,
                has_toilet=toilet, has_water=water, has_shelter=shelter,
                has_hot_spring=spring, lodging_type=lodging_t,
            ))

        # ===== 5. Devices (5 IR + 2 cameras = 7) =====
        dev_data = [
            ("hakusan_sabou_01", "砂防新道", "ir_sensor", "active", 87, 22.3),
            ("hakusan_kanko_01", "観光新道", "ir_sensor", "active", 92, 21.8),
            ("hakusan_hirase_01", "平瀬道", "ir_sensor", "active", 78, 20.1),
            ("hakusan_ichinose_01", "市ノ瀬・別山道", "ir_sensor", "active", 55, 19.4),
            ("hakusan_shaka_01", "釈迦新道", "ir_sensor", "active", 22, 18.7),
            ("hakusan_cam_sabou_A", "砂防新道", "camera_a", "active", 75, 22.0),
            ("hakusan_cam_sabou_B", "砂防新道", "camera_b", "active", 73, 21.5),
        ]
        for did, loc_name, dtype, status, batt, temp in dev_data:
            db.add(Device(
                device_id=did, location_id=locs[loc_name].id, device_type=dtype,
                status=status, battery_pct=batt, temperature_c=temp,
                last_heartbeat=datetime.now(JST),
                last_data_at=datetime.now(JST) - timedelta(minutes=30),
            ))

        # ===== 6. Sample sensor_counts (today, hourly) =====
        today = date.today()
        hours = list(range(4, 15))
        up_data = [8, 22, 35, 28, 20, 12, 8, 5, 2, 1, 1]
        dn_data = [0, 2, 5, 8, 12, 18, 22, 20, 15, 10, 8]
        for i, h in enumerate(hours):
            ts = datetime(today.year, today.month, today.day, h, 0, 0, tzinfo=JST)
            db.add(SensorCount(
                device_id="hakusan_sabou_01", location_id=locs["砂防新道"].id,
                timestamp=ts, up_count=up_data[i], down_count=dn_data[i],
                battery_pct=87, temperature_c=15 + i * 0.5,
            ))

        # ===== 7. Hourly counts =====
        cum_up = 0
        cum_dn = 0
        for i, h in enumerate(hours):
            cum_up += up_data[i]
            cum_dn += dn_data[i]
            db.add(HourlyCount(
                date=today, hour=h, location_id=locs["砂防新道"].id,
                ascending=up_data[i], descending=dn_data[i],
                cumulative_ascending=cum_up, cumulative_descending=cum_dn,
            ))

        # ===== 8. Route realtime =====
        route_rt = [
            ("砂防新道", 142, 38, "mid"),
            ("観光新道", 21, 8, "low"),
            ("平瀬道", 18, 5, "low"),
            ("市ノ瀬・別山道", 9, 3, "low"),
            ("釈迦新道", 4, 1, "low"),
        ]
        for rname, asc, desc, level in route_rt:
            db.add(RouteRealtime(
                route_id=routes[rname].id, date=today,
                ascending_count=asc, descending_count=desc,
                congestion_level=level,
            ))

        # ===== 9. Calibration factors =====
        for loc_name in ["砂防新道", "観光新道", "平瀬道"]:
            for weather, asc_f, desc_f, days, conf in [
                ("clear", 1.062, 1.045, 15, 88),
                ("cloudy", 0.985, 0.972, 12, 82),
                ("rain", 0.912, 0.895, 8, 71),
            ]:
                db.add(CalibrationFactor(
                    location_id=locs[loc_name].id, weather=weather,
                    ascending_factor=asc_f, descending_factor=desc_f,
                    sample_days=days, confidence_pct=conf,
                    valid_from=date(2026, 4, 1), valid_to=date(2026, 10, 31),
                ))

        # ===== 10. Sample calibration records =====
        for d in range(3):
            db.add(CalibrationRecord(
                location_id=locs["砂防新道"].id,
                date=today - timedelta(days=d),
                time_slot="08-10", weather="clear",
                manual_ascending=45, manual_descending=12,
                ir_ascending=42, ir_descending=11,
                correction_factor=1.062, operator="染谷",
            ))

        # ===== 11. Trail status =====
        ts_data = [
            ("砂防新道", "caution", "砂防新道：甚之助〜南竜分岐間に残雪",
             "アイゼン推奨。早朝は凍結注意。", "白山室堂管理事務所"),
            (None, "info", "白山室堂ビジターセンター 開館中",
             "開館時間 7:00〜17:00。飲料水・トイレあり。", "石川県"),
            ("平瀬道", "caution", "平瀬道：大倉山避難小屋付近 倒木あり",
             "通行可能だが注意。迂回路なし。", "岐阜県白川村"),
        ]
        for rname, stype, title, desc, source in ts_data:
            db.add(TrailStatus(
                route_id=routes[rname].id if rname else None,
                status_type=stype, title=title, description=desc, source=source,
            ))

        # ===== 12. Lodging =====
        lodging_data = [
            ("白山室堂山荘", "砂防新道", 750, True, "1泊2食 ¥9,500", 72, "夏季は混雑。予約は4月から受付"),
            ("南竜山荘", "砂防新道", 60, True, "1泊2食 ¥8,500", 45, "比較的空いている穴場"),
            ("南竜テント場", "砂防新道", 100, False, "1張 ¥500", 30, "水場・トイレ完備"),
        ]
        for name, rname, cap, res, price, occ, tip in lodging_data:
            db.add(Lodging(
                name=name, route_id=routes[rname].id, capacity=cap,
                reservation_required=res, price_text=price,
                occupancy_pct=occ, tip=tip,
            ))

        # ===== 13. Alerts =====
        alert_data = [
            ("congestion", "砂防新道", "砂防新道 混雑超過", "本日の入山者数が250人を超えました", 280, 250),
            ("battery", "釈迦新道", "釈迦新道センサー バッテリー低下", "バッテリー残量22%", 22, 30),
            ("ai_correction", "砂防新道", "AI解析完了 補正提案あり", "10:00-11:00帯でグループ補正+3の提案", None, None),
        ]
        for atype, loc_name, title, msg, val, thresh in alert_data:
            db.add(Alert(
                alert_type=atype, location_id=locs[loc_name].id,
                title=title, message=msg, value=val, threshold=thresh,
            ))

        await db.commit()
        print("Seed data inserted successfully!")
        print(f"  Locations: {len(loc_data)}")
        print(f"  Routes: {len(route_data)}")
        print(f"  Waypoints: {len(wp_data)}")
        print(f"  Facilities: {len(fac_data)}")
        print(f"  Devices: {len(dev_data)}")
        print(f"  Hourly counts: {len(hours)}")
        print(f"  Route realtime: {len(route_rt)}")
        print(f"  Calibration factors: 9")
        print(f"  Trail statuses: {len(ts_data)}")
        print(f"  Lodgings: {len(lodging_data)}")
        print(f"  Alerts: {len(alert_data)}")


if __name__ == "__main__":
    asyncio.run(seed())
