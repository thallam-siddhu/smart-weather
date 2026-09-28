from flask import Flask, jsonify, render_template, request, Response
import requests
import time
import json
import os
from threading import Lock

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WTTR_URL = "https://wttr.in"

CACHE_SECONDS = 600  # 10 minutes
weather_cache = {}
cache_lock = Lock()

HEADERS = {
    "User-Agent": (
        "SiddhuWeather/2.0 "
        "(https://thallam-siddhu.github.io/siddhu-weather/)"
    ),
    "Accept": "application/json",
}

REQUEST_TIMEOUT = 15


# ============================================================
# WEATHER CODE MAPPING
# ============================================================

WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),

    45: ("Fog", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),

    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),

    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),

    61: ("Slight rain", "🌦️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),

    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),

    71: ("Slight snowfall", "🌨️"),
    73: ("Moderate snowfall", "🌨️"),
    75: ("Heavy snowfall", "❄️"),
    77: ("Snow grains", "❄️"),

    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),

    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),

    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


def weather_code_info(code):
    try:
        code = int(code)
    except (TypeError, ValueError):
        return "Unknown", "🌡️"

    return WEATHER_CODES.get(code, ("Unknown", "🌡️"))


# ============================================================
# CACHE FUNCTIONS
# ============================================================

def make_cache_key(lat, lon):
    """
    Round coordinates so repeated GPS requests for almost
    identical positions use the same cache entry.
    """
    return f"{round(float(lat), 3)},{round(float(lon), 3)}"


def get_cached_weather(key):
    with cache_lock:
        item = weather_cache.get(key)

        if not item:
            return None

        if time.time() - item["time"] > CACHE_SECONDS:
            weather_cache.pop(key, None)
            return None

        return item["data"]


def save_cached_weather(key, data):
    with cache_lock:
        weather_cache[key] = {
            "time": time.time(),
            "data": data,
        }


# ============================================================
# COMMON WEATHER PARAMETERS
# ============================================================

def open_meteo_params(lat, lon):
    return {
        "latitude": lat,
        "longitude": lon,

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation,"
            "rain,"
            "showers,"
            "snowfall,"
            "weather_code,"
            "cloud_cover,"
            "pressure_msl,"
            "surface_pressure,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "wind_gusts_10m,"
            "is_day"
        ),

        "hourly": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "precipitation_probability,"
            "precipitation,"
            "rain,"
            "showers,"
            "snowfall,"
            "weather_code,"
            "cloud_cover,"
            "wind_speed_10m"
        ),

        "daily": (
            "weather_code,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "apparent_temperature_max,"
            "apparent_temperature_min,"
            "precipitation_sum,"
            "rain_sum,"
            "showers_sum,"
            "snowfall_sum,"
            "precipitation_probability_max,"
            "wind_speed_10m_max,"
            "wind_gusts_10m_max,"
            "sunrise,"
            "sunset,"
            "uv_index_max"
        ),

        "timezone": "auto",
        "forecast_days": 7,
    }


# ============================================================
# OPEN-METEO RESPONSE CONVERSION
# ============================================================

def build_open_meteo_response(data, lat, lon):
    current = data.get("current", {})
    current_units = data.get("current_units", {})
    hourly = data.get("hourly", {})
    hourly_units = data.get("hourly_units", {})
    daily = data.get("daily", {})
    daily_units = data.get("daily_units", {})

    code = current.get("weather_code")
    condition, icon = weather_code_info(code)

    result_current = {
        "time": current.get("time"),

        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),

        "humidity": current.get("relative_humidity_2m"),
        "cloud_cover": current.get("cloud_cover"),

        "precipitation": current.get("precipitation"),
        "rain": current.get("rain"),
        "showers": current.get("showers"),
        "snowfall": current.get("snowfall"),

        "pressure": current.get("pressure_msl"),
        "surface_pressure": current.get("surface_pressure"),

        "wind_speed": current.get("wind_speed_10m"),
        "wind_direction": current.get("wind_direction_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),

        "is_day": current.get("is_day"),

        "weather_code": code,
        "condition": condition,
        "icon": icon,
    }

    daily_result = []

    dates = daily.get("time", [])

    for i, date in enumerate(dates):
        code = get_array_value(daily.get("weather_code"), i)
        condition, icon = weather_code_info(code)

        daily_result.append({
            "date": date,
            "weather_code": code,
            "condition": condition,
            "icon": icon,

            "temperature_max": get_array_value(
                daily.get("temperature_2m_max"), i
            ),
            "temperature_min": get_array_value(
                daily.get("temperature_2m_min"), i
            ),

            "feels_like_max": get_array_value(
                daily.get("apparent_temperature_max"), i
            ),
            "feels_like_min": get_array_value(
                daily.get("apparent_temperature_min"), i
            ),

            "precipitation": get_array_value(
                daily.get("precipitation_sum"), i
            ),
            "rain": get_array_value(
                daily.get("rain_sum"), i
            ),
            "showers": get_array_value(
                daily.get("showers_sum"), i
            ),
            "snowfall": get_array_value(
                daily.get("snowfall_sum"), i
            ),

            "rain_probability": get_array_value(
                daily.get("precipitation_probability_max"), i
            ),

            "wind_speed": get_array_value(
                daily.get("wind_speed_10m_max"), i
            ),

            "wind_gusts": get_array_value(
                daily.get("wind_gusts_10m_max"), i
            ),

            "sunrise": get_array_value(
                daily.get("sunrise"), i
            ),

            "sunset": get_array_value(
                daily.get("sunset"), i
            ),

            "uv_index": get_array_value(
                daily.get("uv_index_max"), i
            ),
        })

    return {
        "success": True,
        "source": "Open-Meteo",

        "location": {
            "latitude": lat,
            "longitude": lon,
            "timezone": data.get("timezone"),
            "timezone_abbreviation": data.get(
                "timezone_abbreviation"
            ),
            "elevation": data.get("elevation"),
        },

        "units": {
            "temperature": current_units.get(
                "temperature_2m", "°C"
            ),
            "humidity": current_units.get(
                "relative_humidity_2m", "%"
            ),
            "wind_speed": current_units.get(
                "wind_speed_10m", "km/h"
            ),
            "precipitation": current_units.get(
                "precipitation", "mm"
            ),
            "pressure": current_units.get(
                "pressure_msl", "hPa"
            ),
        },

        "current": result_current,

        "hourly": {
            "time": hourly.get("time", []),
            "temperature": hourly.get(
                "temperature_2m", []
            ),
            "humidity": hourly.get(
                "relative_humidity_2m", []
            ),
            "feels_like": hourly.get(
                "apparent_temperature", []
            ),
            "precipitation_probability": hourly.get(
                "precipitation_probability", []
            ),
            "precipitation": hourly.get(
                "precipitation", []
            ),
            "rain": hourly.get("rain", []),
            "showers": hourly.get("showers", []),
            "snowfall": hourly.get("snowfall", []),
            "weather_code": hourly.get(
                "weather_code", []
            ),
            "cloud_cover": hourly.get(
                "cloud_cover", []
            ),
            "wind_speed": hourly.get(
                "wind_speed_10m", []
            ),
        },

        "daily": {
            "time": [
                item["date"]
                for item in daily_result
            ],
            "weather_code": [
                item["weather_code"]
                for item in daily_result
            ],
            "temperature_2m_max": [
                item["temperature_max"]
                for item in daily_result
            ],
            "temperature_2m_min": [
                item["temperature_min"]
                for item in daily_result
            ],
            "precipitation_probability_max": [
                item["rain_probability"]
                for item in daily_result
            ],
            "precipitation_sum": [
                item["precipitation"]
                for item in daily_result
            ],
            "rain_sum": [
                item["rain"]
                for item in daily_result
            ],
            "sunrise": [
                item["sunrise"]
                for item in daily_result
            ],
            "sunset": [
                item["sunset"]
                for item in daily_result
            ],
            "uv_index_max": [
                item["uv_index"]
                for item in daily_result
            ]
        },

        "updated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        ),
    }


# ============================================================
# WTTR.IN FALLBACK
# ============================================================

def get_wttr_weather(lat, lon):
    """
    Fallback weather provider.

    wttr.in does not require an API key and can accept
    latitude/longitude coordinates.
    """

    url = f"{WTTR_URL}/{lat},{lon}"

    params = {
        "format": "j1"
    }

    response = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Fallback weather service returned "
            f"{response.status_code}"
        )

    data = response.json()

    current_list = data.get("current_condition", [])

    if not current_list:
        raise RuntimeError(
            "Fallback weather service returned no current data"
        )

    current = current_list[0]

    temperature = safe_float(
        current.get("temp_C")
    )

    feels_like = safe_float(
        current.get("FeelsLikeC")
    )

    humidity = safe_float(
        current.get("humidity")
    )

    wind_speed = safe_float(
        current.get("windspeedKmph")
    )

    wind_direction = safe_float(
        current.get("winddirDegree")
    )

    pressure = safe_float(
        current.get("pressure")
    )

    cloud_cover = safe_float(
        current.get("cloudcover")
    )

    precipitation = safe_float(
        current.get("precipMM")
    )

    condition_text = "Unknown"

    weather_desc = current.get(
        "weatherDesc",
        []
    )

    if weather_desc:
        condition_text = weather_desc[0].get(
            "value",
            "Unknown"
        )

    icon = get_fallback_icon(condition_text)

    weather = {
        "success": True,
        "source": "Fallback",

        "location": {
            "latitude": lat,
            "longitude": lon,
            "timezone": data.get("timezone"),
        },

        "units": {
            "temperature": "°C",
            "humidity": "%",
            "wind_speed": "km/h",
            "precipitation": "mm",
            "pressure": "hPa",
        },

        "current": {
            "temperature": temperature,
            "feels_like": feels_like,
            "humidity": humidity,
            "cloud_cover": cloud_cover,
            "precipitation": precipitation,
            "rain": precipitation,
            "showers": 0,
            "snowfall": 0,
            "pressure": pressure,
            "surface_pressure": pressure,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "wind_gusts": None,
            "is_day": 1,
            "weather_code": None,
            "condition": condition_text,
            "icon": icon,
        },

        "hourly": {
            "time": [],
            "temperature": [],
            "humidity": [],
            "feels_like": [],
            "rain_probability": [],
            "precipitation": [],
            "rain": [],
            "showers": [],
            "snowfall": [],
            "weather_code": [],
            "cloud_cover": [],
            "wind_speed": [],
        },

        "daily": [],

        "updated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        ),
    }

    # Build daily forecast from wttr.in
    for day in data.get("weather", []):
        date = day.get("date")

        max_temp = safe_float(
            day.get("maxtempC")
        )

        min_temp = safe_float(
            day.get("mintempC")
        )

        total_rain = safe_float(
            day.get("totalSnow_cm")
        )

        rain_probability = None

        hourly_data = day.get("hourly", [])

        if hourly_data:
            rain_values = []

            for hour in hourly_data:
                chance = safe_float(
                    hour.get("chanceofrain")
                )

                if chance is not None:
                    rain_values.append(chance)

            if rain_values:
                rain_probability = max(
                    rain_values
                )

        weather_condition = "Unknown"
        weather_icon = "🌡️"

        if hourly_data:
            middle_hour = hourly_data[
                len(hourly_data) // 2
            ]

            desc = middle_hour.get(
                "weatherDesc",
                []
            )

            if desc:
                weather_condition = desc[0].get(
                    "value",
                    "Unknown"
                )

            weather_icon = get_fallback_icon(
                weather_condition
            )

        weather["daily"].append({
            "date": date,
            "weather_code": None,
            "condition": weather_condition,
            "icon": weather_icon,

            "temperature_max": max_temp,
            "temperature_min": min_temp,

            "feels_like_max": None,
            "feels_like_min": None,

            "precipitation": None,
            "rain": None,
            "showers": None,
            "snowfall": total_rain,

            "rain_probability": rain_probability,

            "wind_speed": None,
            "wind_gusts": None,

            "sunrise": None,
            "sunset": None,

            "uv_index": None,
        })

    # Keep the fallback response shape identical to Open-Meteo so
    # the frontend can render the 7-day forecast from either provider.
    daily_items = weather.get("daily", [])

    weather["daily"] = {
        "time": [
            item["date"]
            for item in daily_items
        ],
        "weather_code": [
            item["weather_code"]
            for item in daily_items
        ],
        "temperature_2m_max": [
            item["temperature_max"]
            for item in daily_items
        ],
        "temperature_2m_min": [
            item["temperature_min"]
            for item in daily_items
        ],
        "precipitation_probability_max": [
            item["rain_probability"]
            for item in daily_items
        ],
        "precipitation_sum": [
            item["precipitation"]
            for item in daily_items
        ],
        "rain_sum": [
            item["rain"]
            for item in daily_items
        ],
        "sunrise": [
            item["sunrise"]
            for item in daily_items
        ],
        "sunset": [
            item["sunset"]
            for item in daily_items
        ],
        "uv_index_max": [
            item["uv_index"]
            for item in daily_items
        ]
    }

    return weather


def get_fallback_icon(condition):
    text = str(condition).lower()

    if "thunder" in text:
        return "⛈️"

    if "storm" in text:
        return "⛈️"

    if "heavy rain" in text:
        return "🌧️"

    if "rain" in text:
        return "🌦️"

    if "drizzle" in text:
        return "🌦️"

    if "cloud" in text:
        return "☁️"

    if "overcast" in text:
        return "☁️"

    if "fog" in text:
        return "🌫️"

    if "mist" in text:
        return "🌫️"

    if "snow" in text:
        return "❄️"

    if "clear" in text:
        return "☀️"

    if "sunny" in text:
        return "☀️"

    return "🌤️"


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def get_array_value(array, index):
    if not isinstance(array, list):
        return None

    if index < 0 or index >= len(array):
        return None

    return array[index]


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# WEATHER API
# ============================================================

@app.route("/weather")
def weather():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if lat is None or lon is None:
        return jsonify({
            "success": False,
            "error": "Latitude and longitude are required"
        }), 400

    try:
        lat = float(lat)
        lon = float(lon)

    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid latitude or longitude"
        }), 400

    if not (-90 <= lat <= 90):
        return jsonify({
            "success": False,
            "error": "Invalid latitude"
        }), 400

    if not (-180 <= lon <= 180):
        return jsonify({
            "success": False,
            "error": "Invalid longitude"
        }), 400

    cache_key = make_cache_key(lat, lon)

    # --------------------------------------------------------
    # CACHE
    # --------------------------------------------------------

    cached = get_cached_weather(cache_key)

    if cached:
        cached_copy = dict(cached)
        cached_copy["cached"] = True
        return jsonify(cached_copy)

    # --------------------------------------------------------
    # PRIMARY: OPEN-METEO
    # --------------------------------------------------------

    try:
        params = open_meteo_params(
            lat,
            lon
        )

        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        print(
            "Open-Meteo status:",
            response.status_code
        )

        if response.status_code == 200:
            data = response.json()

            result = build_open_meteo_response(
                data,
                lat,
                lon
            )

            save_cached_weather(
                cache_key,
                result
            )

            return jsonify(result)

        # 429 means rate limited.
        # We immediately use fallback instead of
        # returning an error to the frontend.
        if response.status_code == 429:
            print(
                "Open-Meteo rate limit reached. "
                "Using fallback provider."
            )

        else:
            print(
                "Open-Meteo error:",
                response.status_code,
                response.text[:500]
            )

    except requests.Timeout:
        print(
            "Open-Meteo request timed out. "
            "Using fallback provider."
        )

    except requests.RequestException as exc:
        print(
            "Open-Meteo request failed:",
            exc
        )

    except Exception as exc:
        print(
            "Open-Meteo unexpected error:",
            exc
        )

    # --------------------------------------------------------
    # FALLBACK: WTTR.IN
    # --------------------------------------------------------

    try:
        print(
            "Trying fallback weather provider..."
        )

        fallback = get_wttr_weather(
            lat,
            lon
        )

        save_cached_weather(
            cache_key,
            fallback
        )

        return jsonify(fallback)

    except requests.Timeout:
        print(
            "Fallback weather provider timed out."
        )

    except requests.RequestException as exc:
        print(
            "Fallback request failed:",
            exc
        )

    except Exception as exc:
        print(
            "Fallback weather error:",
            exc
        )

    # --------------------------------------------------------
    # BOTH PROVIDERS FAILED
    # --------------------------------------------------------

    return jsonify({
        "success": False,
        "error": (
            "Weather services are temporarily unavailable. "
            "Please try again in a few minutes."
        )
    }), 503


# ============================================================
# REVERSE GEOCODING
# ============================================================

@app.route("/location")
def location():
    lat = request.args.get("lat")
    lon = request.args.get("lon")

    if lat is None or lon is None:
        return jsonify({
            "success": False,
            "error": "Latitude and longitude are required"
        }), 400

    try:
        lat = float(lat)
        lon = float(lon)

    except ValueError:
        return jsonify({
            "success": False,
            "error": "Invalid coordinates"
        }), 400

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "addressdetails": 1,
                "zoom": 18,
                "accept-language": "en",
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code != 200:
            return jsonify({
                "success": False,
                "error": "Location service unavailable"
            }), 502

        data = response.json()

        address = data.get(
            "address",
            {}
        )

        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("county")
            or ""
        )

        result = {
            "success": True,

            "name": (
                city
                or data.get("name")
                or "Your Location"
            ),

            "display_name": data.get(
                "display_name",
                ""
            ),

            "road": address.get(
                "road",
                ""
            ),

            "locality": (
                address.get("suburb")
                or address.get("neighbourhood")
                or address.get("locality")
                or ""
            ),

            "city": city,

            "state": address.get(
                "state",
                ""
            ),

            "country": address.get(
                "country",
                ""
            ),

            "postcode": address.get(
                "postcode",
                ""
            ),

            "lat": lat,
            "lon": lon,
        }

        return jsonify(result)

    except requests.Timeout:
        return jsonify({
            "success": False,
            "error": "Location service timed out"
        }), 504

    except requests.RequestException as exc:
        print(
            "Nominatim error:",
            exc
        )

        return jsonify({
            "success": False,
            "error": "Location service unavailable"
        }), 502

    except Exception as exc:
        print(
            "Location unexpected error:",
            exc
        )

        return jsonify({
            "success": False,
            "error": "Unable to find location"
        }), 500


# ============================================================
# PWA MANIFEST
# ============================================================

@app.route("/manifest.json")
def manifest():
    manifest_data = {
        "name": "Siddhu Weather",
        "short_name": "Siddhu Weather",
        "description": (
            "Live weather information and "
            "location-based forecasts."
        ),
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "theme_color": "#07111f",
        "background_color": "#07111f",

        "icons": [
            {
                "src": "/static/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }

    return jsonify(manifest_data)


# ============================================================
# SERVICE WORKER
# ============================================================

@app.route("/service-worker.js")
def service_worker():
    service_worker_code = r"""
const CACHE_NAME = "siddhu-weather-v3";

const APP_SHELL = [
    "/",
    "/manifest.json",
    "/static/favicon.png",
    "/static/icon-180.png",
    "/static/icon-192.png",
    "/static/icon-512.png"
];

self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(APP_SHELL))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys
                    .filter(key => key !== CACHE_NAME)
                    .map(key => caches.delete(key))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", event => {
    const request = event.request;
    const url = new URL(request.url);

    // Never cache live weather requests.
    if (
        url.pathname === "/weather" ||
        url.pathname === "/location"
    ) {
        return;
    }

    if (request.method !== "GET") {
        return;
    }

    event.respondWith(
        fetch(request)
            .then(response => {

                if (
                    response &&
                    response.status === 200
                ) {
                    const copy = response.clone();

                    caches.open(CACHE_NAME)
                        .then(cache => {
                            cache.put(request, copy);
                        });
                }

                return response;
            })
            .catch(() => {
                return caches.match(request)
                    .then(cached => {
                        return cached || caches.match("/");
                    });
            })
    );
});
"""

    response = Response(
        service_worker_code,
        mimetype="application/javascript"
    )

    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"

    return response


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "Siddhu Weather is running",
        "success": True
    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Page not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )