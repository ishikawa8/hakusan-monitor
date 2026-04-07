"""Open-Meteo weather service with 1-hour cache (design doc 4.6)."""

import time
import asyncio
import aiohttp
from typing import Optional
from app.config import get_settings

settings = get_settings()

# WMO Weather Code → Japanese description
WMO_JA = {
    0: "快晴", 1: "晴れ", 2: "一部曇り", 3: "曇り",
    45: "霧", 48: "着氷性の霧",
    51: "弱い霧雨", 53: "霧雨", 55: "強い霧雨",
    61: "弱い雨", 63: "雨", 65: "強い雨",
    71: "弱い雪", 73: "雪", 75: "強い雪",
    80: "にわか雨", 81: "強いにわか雨", 82: "激しいにわか雨",
    85: "にわか雪", 86: "強いにわか雪",
    95: "雷雨", 96: "雹を伴う雷雨", 99: "激しい雷雨",
}

# Cache
_cache: dict = {}
CACHE_TTL = 3600  # 1 hour


def _weather_grade(wmo: int, wind: float, precip: int) -> str:
    """Determine weather grade A/B/C per design doc Tab1 logic."""
    if wmo >= 95 or wind >= 15:
        return "C"
    if wmo >= 61 or wind >= 10 or precip >= 60:
        return "B"
    return "A"


def _clothing_advice(temp: float) -> str:
    if temp < 0:
        return "厳冬装備（ダウン+防風+手袋+バラクラバ）"
    if temp < 5:
        return "フリース+防風ジャケット+手袋"
    if temp < 10:
        return "長袖+防寒着"
    if temp < 15:
        return "長袖+薄手フリース"
    if temp < 20:
        return "長袖シャツ"
    return "半袖OK（日焼け注意）"


def _wind_note(speed: float) -> str:
    if speed >= 20:
        return "暴風注意。稜線歩行は極めて危険"
    if speed >= 15:
        return "強風。稜線では体が煽られる可能性あり"
    if speed >= 10:
        return "やや強い風。帽子が飛ばされやすい"
    return "穏やか"


async def fetch_weather() -> dict:
    """Fetch mountain weather from Open-Meteo API with caching."""
    now = time.time()
    if "data" in _cache and (now - _cache.get("fetched_at", 0)) < CACHE_TTL:
        return _cache["data"]

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={settings.open_meteo_latitude}"
        f"&longitude={settings.open_meteo_longitude}"
        f"&elevation={settings.open_meteo_elevation}"
        f"&current=temperature_2m,apparent_temperature,wind_speed_10m,"
        f"precipitation_probability,weather_code"
        f"&daily=sunrise,sunset"
        f"&timezone=Asia/Tokyo"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    if "data" in _cache:
                        return _cache["data"]
                    raise Exception(f"Open-Meteo returned {resp.status}")
                raw = await resp.json()
    except Exception:
        if "data" in _cache:
            return _cache["data"]
        raise

    current = raw.get("current", {})
    daily = raw.get("daily", {})

    mountain_temp = current.get("temperature_2m", 0)
    wind = current.get("wind_speed_10m", 0)
    precip = current.get("precipitation_probability", 0)
    wmo = current.get("weather_code", 0)
    feels_like = current.get("apparent_temperature", mountain_temp)

    # Trailhead temp: elevation correction -0.65°C/100m
    trailhead_elevation = 1260  # Approximate Bettoudeguchi elevation
    elevation_diff = settings.open_meteo_elevation - trailhead_elevation
    trailhead_temp = round(mountain_temp + (elevation_diff / 100) * 0.65, 1)

    sunrise = daily.get("sunrise", [""])[0].split("T")[-1] if daily.get("sunrise") else ""
    sunset = daily.get("sunset", [""])[0].split("T")[-1] if daily.get("sunset") else ""

    data = {
        "mountain_top": {
            "temperature_c": mountain_temp,
            "feels_like_c": feels_like,
            "wind_speed_kmh": wind,
            "precipitation_pct": precip,
            "wmo_code": wmo,
            "wmo_description": WMO_JA.get(wmo, f"コード{wmo}"),
            "sunrise": sunrise,
            "sunset": sunset,
        },
        "trailhead": {"temperature_c": trailhead_temp},
        "grade": _weather_grade(wmo, wind, precip),
        "clothing": _clothing_advice(mountain_temp),
        "wind_note": _wind_note(wind),
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
    }

    _cache["data"] = data
    _cache["fetched_at"] = now
    return data
