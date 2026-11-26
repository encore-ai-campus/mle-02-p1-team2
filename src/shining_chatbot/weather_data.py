"""Optional location-based forecast context for the field dashboard."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from datetime import date, datetime
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from shining_chatbot.work_plan import WorkItem


@dataclass(frozen=True)
class WeatherLocation:
    name: str
    region: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class HourlyForecast:
    at: datetime
    weather_code: int | None
    temperature: float | None
    apparent_temperature: float | None
    precipitation_probability: int | None
    wind_gusts: float | None
    wind_speed: float | None


@dataclass(frozen=True)
class WorkWindowSummary:
    time_label: str
    activity: str
    detail: str
    checks: tuple[str, ...]


@dataclass(frozen=True)
class DailyForecast:
    day: date
    weather_code: int | None
    temperature_max: float | None
    apparent_temperature_max: float | None
    precipitation_probability_max: int | None
    precipitation_sum: float | None
    wind_gusts_max: float | None
    hours: tuple[HourlyForecast, ...] = ()


def _api_url(service: str) -> str:
    key = os.getenv("OPEN_METEO_API_KEY", "").strip()
    host = f"customer-{service}" if key else service
    return f"https://{host}.open-meteo.com/v1/{'search' if service == 'geocoding-api' else 'forecast'}"


def _get_json(service: str, params: dict) -> dict:
    key = os.getenv("OPEN_METEO_API_KEY", "").strip()
    if key:
        params = {**params, "apikey": key}
    try:
        with urlopen(f"{_api_url(service)}?{urlencode(params)}", timeout=7) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        if service == "geocoding-api":
            raise ValueError("위치 검색 서비스에 연결할 수 없습니다. 네트워크 연결을 확인한 뒤 다시 시도하세요.") from exc
        raise ValueError("기상 정보를 불러오지 못했습니다. 잠시 뒤 다시 시도하세요.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("기상 서비스가 요청을 처리하지 못했습니다.")
    return payload


_CITY_SEARCH_ALIASES = {
    "용인": ("용인시", "Yongin-si"),
    "성남": ("성남시",),
    "고양": ("고양시",),
    "서울": ("서울특별시", "서울시"),
    "부산": ("부산광역시", "부산시"),
    "대구": ("대구광역시", "대구시"),
    "인천": ("인천광역시", "인천시"),
    "광주": ("광주광역시", "광주시"),
    "대전": ("대전광역시", "대전시"),
    "울산": ("울산광역시", "울산시"),
    "세종": ("세종특별자치시", "세종시"),
    "제주": ("제주시", "제주특별자치도"),
}
_CITY_CENTER_FALLBACKS = {
    # Coarse city-center references for common city queries when geocoding fails.
    # Names are labeled as reference points; they do not identify a worksite.
    "서울": WeatherLocation("서울특별시 · 도심 참고 위치", "서울특별시", 37.566300, 126.977900),
    "부산": WeatherLocation("부산광역시 · 도심 참고 위치", "부산광역시", 35.179600, 129.075600),
    "대구": WeatherLocation("대구광역시 · 도심 참고 위치", "대구광역시", 35.871400, 128.601400),
    "인천": WeatherLocation("인천광역시 · 도심 참고 위치", "인천광역시", 37.456300, 126.705200),
    "광주": WeatherLocation("광주광역시 · 도심 참고 위치", "광주광역시", 35.159500, 126.852600),
    "대전": WeatherLocation("대전광역시 · 도심 참고 위치", "대전광역시", 36.350400, 127.384500),
    "울산": WeatherLocation("울산광역시 · 도심 참고 위치", "울산광역시", 35.538400, 129.311400),
    "세종": WeatherLocation("세종특별자치시 · 도심 참고 위치", "세종특별자치시", 36.480000, 127.289000),
    "제주": WeatherLocation("제주시 · 도심 참고 위치", "제주특별자치도", 33.499600, 126.531200),
    "수원": WeatherLocation("수원시 · 도심 참고 위치", "경기도", 37.263600, 127.028600),
    "용인": WeatherLocation("용인시 · 도심 참고 위치", "경기도", 37.241100, 127.177600),
    "성남": WeatherLocation("성남시 · 도심 참고 위치", "경기도", 37.438610, 127.137780),
    "고양": WeatherLocation("고양시 · 도심 참고 위치", "경기도", 37.656390, 126.835000),
    "군포": WeatherLocation("군포시 · 도심 참고 위치", "경기도", 37.361724, 126.935154),
    "시흥": WeatherLocation("시흥시 · 도심 참고 위치", "경기도", 37.380500, 126.806500),
    "의왕": WeatherLocation("의왕시 · 도심 참고 위치", "경기도", 37.344829, 126.968325),
    "안성": WeatherLocation("안성시 · 도심 참고 위치", "경기도", 37.010833, 127.270278),
}
_KOREAN_ADMIN_SUFFIXES = (
    "특별자치도", "특별자치시", "특별시", "광역시", "자치도", "자치시", "시", "군", "구", "도",
)


def weather_query_from_site_location(value: str) -> str:
    """Keep only Korean administrative-area names before sending a plan location to geocoding."""
    if not isinstance(value, str) or len(value) > 200:
        return ""
    parts = [part.strip(".,()[]") for part in re.split(r"[\s,，/]+", value.strip()) if part.strip(".,()[]")]
    administrative = [
        part for part in parts
        if part.endswith((*_KOREAN_ADMIN_SUFFIXES, "읍", "면"))
    ]
    if administrative:
        return " ".join(administrative[:3])[:80]
    if len(parts) == 1 and (parts[0] in _CITY_CENTER_FALLBACKS or parts[0] in _CITY_SEARCH_ALIASES):
        return parts[0][:80]
    return ""


def _location_query_variants(query: str) -> tuple[str, ...]:
    """Try common Korean short names and admin-qualified forms after an exact miss."""
    normalized = " ".join(query.replace("，", ",").split())
    candidates = [normalized]
    if "," in normalized:
        place, region = (part.strip() for part in normalized.split(",", 1))
        suffix = next((suffix for suffix in _KOREAN_ADMIN_SUFFIXES if place.endswith(suffix)), "")
        stem = place[:-len(suffix)] if suffix else place
        if stem and stem != place:
            candidates.append(f"{stem}, {region}")
        candidates.append(place)
    elif " " in normalized:
        parts = normalized.split()
        region = next((part for part in parts if part.endswith(("도", "자치도"))), "")
        places = [part for part in parts if part != region]
        if region and len(places) >= 2:
            # Prefer the most specific administrative pair, then the city/province pair.
            candidates.extend((f"{places[-1]}, {places[-2]}", f"{places[-2]}, {region}"))
        elif region and places:
            candidates.extend((f"{places[-1]}, {region}", places[-1]))
        elif len(parts) >= 2:
            candidates.extend((f"{parts[-1]}, {parts[-2]}", parts[-1]))
            city = next((part for part in parts if part.endswith(("시", "군"))), "")
            if city and any(part.endswith(("구", "읍", "면", "동")) for part in parts):
                candidates.append(city)
    elif re.fullmatch(r"[가-힣]{2,12}", normalized):
        suffix = next((suffix for suffix in _KOREAN_ADMIN_SUFFIXES if normalized.endswith(suffix)), "")
        stem = normalized[:-len(suffix)] if suffix else normalized
        if stem != normalized:
            if suffix not in {"도", "자치도", "특별자치도"} or stem in _CITY_SEARCH_ALIASES:
                aliases = _CITY_SEARCH_ALIASES.get(stem, (f"{stem}시",))
                candidates.extend(alias for alias in aliases if alias != normalized)
                candidates.append(stem)
        else:
            candidates = [*_CITY_SEARCH_ALIASES.get(normalized, (f"{normalized}시",)), normalized]
    return tuple(dict.fromkeys(candidate for candidate in candidates if candidate))[:3]


def _qualified_city_matches(query: str, locations: list[WeatherLocation]) -> list[WeatherLocation]:
    normalized = " ".join(query.replace("，", ",").split())
    if "," in normalized or " " in normalized:
        return []
    suffix = next((suffix for suffix in _KOREAN_ADMIN_SUFFIXES if normalized.endswith(suffix)), "")
    stem = normalized[:-len(suffix)] if suffix else normalized
    expected_names = {
        *_CITY_SEARCH_ALIASES.get(stem, ()),
        f"{stem}시", f"{stem}군", f"{stem}구",
    }
    if suffix:
        expected_names.add(normalized)
    return [location for location in locations if location.name in expected_names]


def _qualified_place_matches(query: str, locations: list[WeatherLocation]) -> list[WeatherLocation]:
    """Prefer the most specific Korean administrative unit typed by the user."""
    parts = [part for part in re.split(r"[\s,]+", query.replace("，", ",").strip()) if part]
    if len(parts) < 2:
        return []
    province_suffixes = ("도", "자치도", "특별시", "광역시", "자치시", "특별자치시")
    unit_ranks = {"리": 5, "동": 4, "읍": 4, "면": 4, "구": 3, "군": 2, "시": 2}
    units = [
        (unit_ranks[suffix], index, part)
        for index, part in enumerate(parts)
        if not part.endswith(province_suffixes)
        for suffix in unit_ranks
        if part.endswith(suffix) and len(part) > len(suffix)
    ]
    if not units:
        return []
    _, _, target = max(units)
    return [location for location in locations if location.name == target]


def _city_center_fallback(query: str) -> WeatherLocation | None:
    """Resolve a small set of common city names absent from the upstream index."""
    parts = [part for part in re.split(r"[\s,]+", query.strip()) if part]
    if not 1 <= len(parts) <= 4:
        return None
    has_province = any(
        part.endswith(("도", "광역시", "특별시", "특별자치도", "자치도"))
        for part in parts
    )
    cities = []
    for part in parts:
        suffix = next((suffix for suffix in _KOREAN_ADMIN_SUFFIXES if part.endswith(suffix)), "")
        city = part[:-len(suffix)] if suffix else part
        if city in _CITY_CENTER_FALLBACKS and city not in cities:
            cities.append(city)
    has_city_district = bool(cities) and any(part.endswith("구") for part in parts)
    if len(parts) > 1 and not has_province and not has_city_district:
        return None
    return _CITY_CENTER_FALLBACKS[cities[0]] if cities else None


def search_locations(query: str) -> tuple[WeatherLocation, ...]:
    query = query.strip()
    if len(query) < 2 or len(query) > 80:
        raise ValueError("시·군·구 이름을 두 글자 이상 입력하세요.")
    query_parts = [part for part in re.split(r"[\s,]+", query.replace("，", ",")) if part]
    asks_for_subcity = len(query_parts) > 1 and any(part.endswith("구") for part in query_parts)
    fallback = _city_center_fallback(query)
    matches: list[WeatherLocation] = []
    search_errors: list[ValueError] = []
    matched_specific_place = False
    for search_term in _location_query_variants(query):
        try:
            payload = _get_json("geocoding-api", {
                "name": search_term, "count": 10, "language": "ko", "countryCode": "KR",
            })
        except ValueError as exc:
            # A temporary failure for one spelling should not hide results from
            # the other administrative-name variants.
            search_errors.append(exc)
            if fallback is not None:
                break
            continue
        results = payload.get("results", [])
        if not isinstance(results, list):
            raise ValueError("위치 검색 결과를 읽을 수 없습니다.")
        locations = []
        for result in results:
            try:
                name = str(result["name"])
                for aliases in _CITY_SEARCH_ALIASES.values():
                    if name in aliases:
                        name = next(
                            (alias for alias in aliases if any("\uAC00" <= char <= "\uD7A3" for char in alias)),
                            name,
                        )
                        break
                result = {**result, "name": name}
                location = WeatherLocation(
                    name=str(result["name"]), region=str(result.get("admin1") or result.get("country") or "대한민국"),
                    latitude=float(result["latitude"]), longitude=float(result["longitude"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            if 33 <= location.latitude <= 39.5 and 124 <= location.longitude <= 132:
                if location not in matches:
                    matches.append(location)
                locations.append(location)
        # A qualified city name is enough to answer a short-name query. Stop
        # here so we do not wait for broad aliases that can add same-name villages.
        preferred = _qualified_city_matches(query, locations)
        if preferred:
            matches = preferred + [place for place in matches if place not in preferred]
            break
        preferred_place = _qualified_place_matches(query, locations)
        if preferred_place:
            matches = preferred_place + [place for place in matches if place not in preferred_place]
            matched_specific_place = True
            break
    if not matches:
        if fallback is not None:
            return (fallback,)
        if search_errors:
            raise search_errors[-1]
        return ()
    # If a district was requested but the geocoder only knows its parent city,
    # label the city-center reference instead of implying district precision.
    if asks_for_subcity and fallback is not None and not matched_specific_place:
        return (fallback,)
    return tuple(matches[:10])


def fetch_forecast(location: WeatherLocation) -> tuple[DailyForecast, ...]:
    if not (-90 <= location.latitude <= 90 and -180 <= location.longitude <= 180):
        raise ValueError("현장 위치의 좌표를 확인하세요.")
    payload = _get_json("api", {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "daily": "weather_code,temperature_2m_max,apparent_temperature_max,precipitation_probability_max,precipitation_sum,wind_gusts_10m_max",
        "hourly": "weather_code,temperature_2m,apparent_temperature,precipitation_probability,wind_gusts_10m,wind_speed_10m",
        "timezone": "Asia/Seoul",
        "forecast_days": 16,
    })
    daily = payload.get("daily", {})
    hourly = payload.get("hourly", {})
    days = daily.get("time", []) if isinstance(daily, dict) else []
    if not isinstance(days, list) or not days:
        raise ValueError("선택한 위치의 예보 날짜가 없습니다.")

    def number(key: str, index: int, convert: type) -> int | float | None:
        values = daily.get(key, [])
        if not isinstance(values, list) or index >= len(values) or values[index] is None:
            return None
        try:
            return convert(values[index])
        except (TypeError, ValueError):
            return None

    def hourly_number(key: str, index: int, convert: type) -> int | float | None:
        values = hourly.get(key, []) if isinstance(hourly, dict) else []
        if not isinstance(values, list) or index >= len(values) or values[index] is None:
            return None
        try:
            return convert(values[index])
        except (TypeError, ValueError):
            return None

    hourly_times = hourly.get("time", []) if isinstance(hourly, dict) else []
    hours = []
    if isinstance(hourly_times, list):
        for index, value in enumerate(hourly_times):
            try:
                at = datetime.fromisoformat(value)
            except (TypeError, ValueError):
                continue
            hours.append(HourlyForecast(
                at=at,
                weather_code=hourly_number("weather_code", index, int),
                temperature=hourly_number("temperature_2m", index, float),
                apparent_temperature=hourly_number("apparent_temperature", index, float),
                precipitation_probability=hourly_number("precipitation_probability", index, int),
                wind_gusts=hourly_number("wind_gusts_10m", index, float),
                wind_speed=hourly_number("wind_speed_10m", index, float),
            ))

    try:
        return tuple(
            DailyForecast(
                day=date.fromisoformat(value),
                weather_code=number("weather_code", index, int),
                temperature_max=number("temperature_2m_max", index, float),
                apparent_temperature_max=number("apparent_temperature_max", index, float),
                precipitation_probability_max=number("precipitation_probability_max", index, int),
                precipitation_sum=number("precipitation_sum", index, float),
                wind_gusts_max=number("wind_gusts_10m_max", index, float),
                hours=tuple(hour for hour in hours if hour.at.date() == date.fromisoformat(value)),
            )
            for index, value in enumerate(days)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("예보 날짜 형식을 읽을 수 없습니다.") from exc


def forecast_label(code: int | None) -> str:
    if code is None:
        return "예보 정보 없음"
    if code in (0, 1):
        return "맑음"
    if code in (2, 3):
        return "구름"
    if code in (45, 48):
        return "안개"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "비"
    if code in (71, 73, 75, 77, 85, 86):
        return "눈"
    if code in (95, 96, 97, 99):
        return "뇌우"
    return "기상 변화"


def forecast_summary(location: WeatherLocation, forecast: DailyForecast) -> str:
    values = [f"{location.region} {location.name}", forecast_label(forecast.weather_code)]
    if forecast.temperature_max is not None:
        values.append(f"최고 기온 {forecast.temperature_max:.1f}°C")
    if forecast.apparent_temperature_max is not None:
        values.append(f"모델 체감 최고 {forecast.apparent_temperature_max:.1f}°C")
    if forecast.precipitation_probability_max is not None:
        values.append(f"최대 강수확률 {forecast.precipitation_probability_max}%")
    if forecast.wind_gusts_max is not None:
        values.append(f"최대 순간풍속 {forecast.wind_gusts_max:.0f} km/h")
    return " · ".join(values)


def work_weather_notes(activities: tuple[str, ...], forecast: DailyForecast) -> tuple[str, ...]:
    text = " ".join(activities)
    notes = []
    wet = forecast.weather_code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 97, 99)
    if wet:
        notes.append("강수 예보가 있습니다. 작업 구역의 미끄럼과 전기 설비 상태를 현장에서 확인하세요.")
    if any(word in text for word in ("양중", "크레인", "타워크레인", "비계", "고소", "철골")):
        notes.append("양중·고소 작업은 예보와 별도로 현장 실측 풍속 및 장비·작업 기준을 확인하세요.")
    if any(word in text for word in ("굴착", "터파기", "흙막이")) and wet:
        notes.append("굴착 작업은 강수 이후 지반·사면·배수 상태를 다시 확인하세요.")
    apparent = forecast.apparent_temperature_max
    if apparent is not None and apparent >= 31:
        notes.append(
            f"모델 체감 최고 {apparent:.1f}°C 예보입니다. 옥외·고온 작업이 있으면 현장 체감온도를 직접 측정하고 물·그늘·냉방·휴식 조치를 확인하세요."
        )
    if apparent is not None and apparent >= 33:
        notes.append(
            "예보상 모델 체감온도가 33°C 이상입니다. 이는 확인 알림이며 법정 기준 판정값이 아닙니다. "
            "현장 체감온도 측정값과 폭염작업 해당 여부를 확인하세요. 현장 체감온도가 33°C 이상인 폭염작업은 "
            "매 2시간 이내 20분 이상 휴식이 원칙입니다(법령상 예외 확인). 33°C 미만이라도 폭염작업이면 "
            "현행 예방조치를 확인하세요."
        )
    if (apparent is not None and apparent < 0) or forecast.weather_code in (71, 73, 75, 77, 85, 86):
        notes.append("영하·눈 예보입니다. 옥외·저온 작업의 방한복, 따뜻한 쉼터와 물, 작업시간대 조정을 확인하세요.")
    return tuple(notes)


def summarize_work_window(item: WorkItem, forecast: DailyForecast) -> WorkWindowSummary:
    """Summarize model values only for the scheduled hours of one work item."""
    start = datetime.combine(item.day, item.start)
    end = datetime.combine(item.day, item.end)
    hours = [hour for hour in forecast.hours if start <= hour.at < end]
    time_label = f"{item.start:%H:%M}–{item.end:%H:%M}"
    if not hours:
        return WorkWindowSummary(
            time_label, item.activity,
            "해당 작업 시간의 시간별 예보 없음 · 현장 기상과 기상특보 직접 확인",
            (),
        )
    codes = list(dict.fromkeys(forecast_label(hour.weather_code) for hour in hours if hour.weather_code is not None))
    precipitation = [hour.precipitation_probability for hour in hours if hour.precipitation_probability is not None]
    temperatures = [hour.temperature for hour in hours if hour.temperature is not None]
    apparent = [hour.apparent_temperature for hour in hours if hour.apparent_temperature is not None]
    gusts = [hour.wind_gusts for hour in hours if hour.wind_gusts is not None]
    details = []
    if codes:
        details.append(" / ".join(codes[:2]))
    if precipitation:
        details.append(f"시간별 최대 강수확률 {max(precipitation)}%")
    if temperatures:
        details.append(f"기온 {min(temperatures):.1f}–{max(temperatures):.1f}°C")
    if apparent:
        details.append(f"모델 체감 {min(apparent):.1f}–{max(apparent):.1f}°C")
    if gusts:
        details.append(f"순간풍속 예보 최고 {max(gusts):.0f} km/h")
    activity = item.activity + " " + item.equipment
    checks = []
    rain_codes = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 97, 99}
    height_work = ("양중", "크레인", "타워크레인", "비계", "고소", "철골")
    # A 50% forecast is a reminder threshold, not a site-specific risk rating.
    rain_probability = max(precipitation, default=0)
    if any(hour.weather_code in rain_codes for hour in hours) or rain_probability >= 50:
        checks.append("강수 예보·가능성에 따른 미끄럼·전기설비·자재 보양 상태를 현장에서 확인")
    if gusts and any(word in activity for word in height_work):
        checks.append("현장 풍속계와 작업·장비별 허용 기준을 대조")
    if apparent and max(apparent) >= 31 and any(word in activity for word in ("옥외", "외부", "지붕", "철골", "비계", "굴착")):
        checks.append("현장 체감온도를 직접 측정하고 물·그늘·휴식 조치를 확인")
    return WorkWindowSummary(time_label, item.activity, " · ".join(details) or "시간별 변수 없음", tuple(checks))
