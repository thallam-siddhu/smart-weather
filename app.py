from flask import Flask, render_template, request, jsonify, Response
import requests
import time
from datetime import datetime, timezone


app = Flask(__name__)


# =========================================================
# CONFIGURATION
# =========================================================

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"


# =========================================================
# WEATHER CACHE
# =========================================================

# Simple in-memory cache.
# This prevents repeated requests for the same location.
weather_cache = {}

# Cache weather data for 5 minutes.
CACHE_SECONDS = 300


# =========================================================
# REQUEST HEADERS
# =========================================================

HEADERS = {
    "User-Agent": (
        "SiddhuWeather/1.0 "
        "(https://thallam-siddhu.github.io/smart-weather/)"
    )
}


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# PWA MANIFEST
# =========================================================

@app.route("/manifest.json")
def manifest():
    return jsonify({
        "name": "Siddhu Weather",
        "short_name": "Siddhu Weather",
        "description": "Live weather information and location-based forecasts.",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#07111f",
        "theme_color": "#07111f",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/static/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    })


# =========================================================
# SERVICE WORKER
# =========================================================

@app.route("/service-worker.js")
def service_worker():

    service_worker_code = """
const CACHE_NAME = "siddhu-weather-v2";

const APP_SHELL = [
    "/",
    "/manifest.json",
    "/static/favicon.png",
    "/static/icon-180.png",
    "/static/icon-192.png",
    "/static/icon-512.png"
];


// ---------------------------------------------------------
// INSTALL
// ---------------------------------------------------------

self.addEventListener("install", event => {

    event.waitUntil(

        caches.open(CACHE_NAME)

            .then(cache => {
                return cache.addAll(APP_SHELL);
            })

            .then(() => {
                return self.skipWaiting();
            })

    );

});


// ---------------------------------------------------------
// ACTIVATE
// ---------------------------------------------------------

self.addEventListener("activate", event => {

    event.waitUntil(

        caches.keys()

            .then(keys => {

                return Promise.all(

                    keys
                        .filter(key => key !== CACHE_NAME)
                        .map(key => caches.delete(key))

                );

            })

            .then(() => {
                return self.clients.claim();
            })

    );

});


// ---------------------------------------------------------
// FETCH
// ---------------------------------------------------------

self.addEventListener("fetch", event => {

    const request = event.request;

    // Only handle GET requests.
    if (request.method !== "GET") {
        return;
    }

    // Do not cache weather API responses.
    if (
        request.url.includes("/weather") ||
        request.url.includes("/location")
    ) {
        return;
    }

    event.respondWith(

        fetch(request)

            .then(response => {

                // Store successful response in cache.
                if (response && response.status === 200) {

                    const copy = response.clone();

                    caches.open(CACHE_NAME)
                        .then(cache => {
                            cache.put(request, copy);
                        });

                }

                return response;

            })

            .catch(() => {

                return caches.match(request);

            })

    );

});
"""

    return Response(
        service_worker_code,
        mimetype="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache"
        }
    )


# =========================================================
# WEATHER
# =========================================================

@app.route("/weather")
def weather():

    lat = request.args.get("lat")
    lon = request.args.get("lon")

    # -----------------------------------------------------
    # CHECK PARAMETERS
    # -----------------------------------------------------

    if not lat or not lon:

        return jsonify({
            "success": False,
            "error": "Latitude and longitude are required"
        }), 400


    # -----------------------------------------------------
    # CONVERT COORDINATES
    # -----------------------------------------------------

    try:

        lat = float(lat)
        lon = float(lon)

    except ValueError:

        return jsonify({
            "success": False,
            "error": "Invalid latitude or longitude"
        }), 400


    # -----------------------------------------------------
    # VALIDATE COORDINATES
    # -----------------------------------------------------

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


    # -----------------------------------------------------
    # CACHE KEY
    # -----------------------------------------------------

    # GPS can return many decimal places.
    # Rounding prevents unnecessary API requests.
    cache_key = (
        round(lat, 3),
        round(lon, 3)
    )


    # =====================================================
    # CHECK CACHE
    # =====================================================

    cached = weather_cache.get(cache_key)

    if cached:

        age = time.time() - cached["timestamp"]

        if age < CACHE_SECONDS:

            print(
                "Weather served from cache:",
                cache_key
            )

            return jsonify(cached["data"])


        # Remove expired cache.
        weather_cache.pop(cache_key, None)


    # =====================================================
    # OPEN-METEO REQUEST
    # =====================================================

    params = {

        "latitude": lat,

        "longitude": lon,


        # -------------------------------------------------
        # CURRENT WEATHER
        # -------------------------------------------------

        "current": (
            "temperature_2m,"
            "relative_humidity_2m,"
            "apparent_temperature,"
            "is_day,"
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
            "wind_gusts_10m"
        ),


        # -------------------------------------------------
        # HOURLY WEATHER
        # -------------------------------------------------

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
            "wind_speed_10m,"
            "uv_index"
        ),


        # -------------------------------------------------
        # DAILY WEATHER
        # -------------------------------------------------

        "daily": (
            "weather_code,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "apparent_temperature_max,"
            "apparent_temperature_min,"
            "precipitation_probability_max,"
            "precipitation_sum,"
            "rain_sum,"
            "showers_sum,"
            "snowfall_sum,"
            "sunrise,"
            "sunset,"
            "uv_index_max"
        ),


        "timezone": "auto",

        "forecast_days": 7
    }


    # =====================================================
    # SEND REQUEST
    # =====================================================

    try:

        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            headers=HEADERS,
            timeout=15
        )


        print(
            "Weather API status:",
            response.status_code
        )


        # -------------------------------------------------
        # RATE LIMIT
        # -------------------------------------------------

        if response.status_code == 429:

            # Use old cache if available.
            if cached:

                print(
                    "Open-Meteo rate limited. "
                    "Using old cache."
                )

                return jsonify(
                    cached["data"]
                )


            return jsonify({

                "success": False,

                "error": (
                    "Weather service is temporarily busy. "
                    "Please try again in a few minutes."
                )

            }), 503


        # -------------------------------------------------
        # OTHER API ERRORS
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                "Open-Meteo response:",
                response.text[:500]
            )

            return jsonify({

                "success": False,

                "error": (
                    "Weather service is temporarily unavailable"
                )

            }), 502


        # -------------------------------------------------
        # JSON RESPONSE
        # -------------------------------------------------

        data = response.json()


        if data.get("error"):

            return jsonify({

                "success": False,

                "error": data.get(
                    "reason",
                    "Weather service returned an error"
                )

            }), 502


        # =================================================
        # CURRENT WEATHER
        # =================================================

        current = data.get(
            "current",
            {}
        )


        weather_code = current.get(
            "weather_code"
        )


        condition, icon = get_weather_condition(
            weather_code
        )


        # =================================================
        # FINAL RESULT
        # =================================================

        result = {

            "success": True,


            # -------------------------------------------------
            # LOCATION
            # -------------------------------------------------

            "location": {

                "latitude": data.get(
                    "latitude"
                ),

                "longitude": data.get(
                    "longitude"
                ),

                "timezone": data.get(
                    "timezone"
                ),

                "timezone_abbreviation": data.get(
                    "timezone_abbreviation"
                ),

                "elevation": data.get(
                    "elevation"
                )

            },


            # -------------------------------------------------
            # UNITS
            # -------------------------------------------------

            "units": data.get(
                "current_units",
                {}
            ),


            # -------------------------------------------------
            # CURRENT
            # -------------------------------------------------

            "current": {

                "temperature": current.get(
                    "temperature_2m"
                ),

                "feels_like": current.get(
                    "apparent_temperature"
                ),

                "humidity": current.get(
                    "relative_humidity_2m"
                ),

                "cloud_cover": current.get(
                    "cloud_cover"
                ),

                "precipitation": current.get(
                    "precipitation"
                ),

                "rain": current.get(
                    "rain"
                ),

                "showers": current.get(
                    "showers"
                ),

                "snowfall": current.get(
                    "snowfall"
                ),

                "pressure": current.get(
                    "pressure_msl"
                ),

                "surface_pressure": current.get(
                    "surface_pressure"
                ),

                "wind_speed": current.get(
                    "wind_speed_10m"
                ),

                "wind_direction": current.get(
                    "wind_direction_10m"
                ),

                "wind_gusts": current.get(
                    "wind_gusts_10m"
                ),

                "is_day": current.get(
                    "is_day"
                ),

                "weather_code": weather_code,

                "condition": condition,

                "icon": icon

            },


            # -------------------------------------------------
            # HOURLY
            # -------------------------------------------------

            "hourly": data.get(
                "hourly",
                {}
            ),


            # -------------------------------------------------
            # DAILY
            # -------------------------------------------------

            "daily": data.get(
                "daily",
                {}
            ),


            # -------------------------------------------------
            # UPDATED TIME
            # -------------------------------------------------

            "updated_at": datetime.now(
                timezone.utc
            ).isoformat()

        }


        # =================================================
        # SAVE TO CACHE
        # =================================================

        weather_cache[cache_key] = {

            "timestamp": time.time(),

            "data": result

        }


        return jsonify(result)


    # =====================================================
    # TIMEOUT
    # =====================================================

    except requests.exceptions.Timeout:

        print(
            "Open-Meteo request timed out"
        )

        return jsonify({

            "success": False,

            "error": (
                "Weather service took too long to respond"
            )

        }), 504


    # =====================================================
    # REQUEST ERROR
    # =====================================================

    except requests.exceptions.RequestException as e:

        print(
            "Weather request error:",
            str(e)
        )


        # Use old cache if available.
        if cached:

            print(
                "Using old cached weather data"
            )

            return jsonify(
                cached["data"]
            )


        return jsonify({

            "success": False,

            "error": (
                "Unable to connect to weather service"
            )

        }), 502


    # =====================================================
    # UNKNOWN ERROR
    # =====================================================

    except Exception as e:

        print(
            "Unexpected weather error:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error": "Unable to load weather"

        }), 500


# =========================================================
# REVERSE LOCATION
# =========================================================

@app.route("/location")
def location():

    lat = request.args.get("lat")
    lon = request.args.get("lon")


    # -----------------------------------------------------
    # CHECK PARAMETERS
    # -----------------------------------------------------

    if not lat or not lon:

        return jsonify({

            "success": False,

            "error": (
                "Latitude and longitude are required"
            )

        }), 400


    try:

        params = {

            "lat": lat,

            "lon": lon,

            "format": "jsonv2",

            "zoom": 18,

            "addressdetails": 1

        }


        response = requests.get(

            NOMINATIM_URL,

            params=params,

            headers=HEADERS,

            timeout=10

        )


        # -------------------------------------------------
        # LOCATION API ERROR
        # -------------------------------------------------

        if response.status_code != 200:

            return jsonify({

                "success": False,

                "error": (
                    "Location service unavailable"
                )

            }), 502


        data = response.json()


        address = data.get(
            "address",
            {}
        )


        # -------------------------------------------------
        # FIND CITY
        # -------------------------------------------------

        city = (

            address.get("city")

            or address.get("town")

            or address.get("village")

            or address.get("municipality")

            or address.get("county")

            or ""

        )


        state = address.get(
            "state",
            ""
        )


        country = address.get(
            "country",
            ""
        )


        postcode = address.get(
            "postcode",
            ""
        )


        road = address.get(
            "road",
            ""
        )


        locality = (

            address.get("suburb")

            or address.get("neighbourhood")

            or address.get("city_district")

            or ""

        )


        # -------------------------------------------------
        # BUILD LOCATION NAME
        # -------------------------------------------------

        name_parts = []


        if locality:

            name_parts.append(
                locality
            )


        if city and city not in name_parts:

            name_parts.append(
                city
            )


        if state and state not in name_parts:

            name_parts.append(
                state
            )


        name = ", ".join(
            name_parts
        )


        if not name:

            name = data.get(
                "display_name",
                "Unknown location"
            )


        # -------------------------------------------------
        # RETURN LOCATION
        # -------------------------------------------------

        return jsonify({

            "success": True,

            "name": name,

            "display_name": data.get(
                "display_name",
                name
            ),

            "road": road,

            "locality": locality,

            "city": city,

            "state": state,

            "country": country,

            "postcode": postcode,

            "lat": data.get(
                "lat"
            ),

            "lon": data.get(
                "lon"
            )

        })


    # =====================================================
    # REQUEST ERROR
    # =====================================================

    except requests.exceptions.RequestException as e:

        print(
            "Location request error:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error": (
                "Unable to find location name"
            )

        }), 502


    # =====================================================
    # UNKNOWN ERROR
    # =====================================================

    except Exception as e:

        print(
            "Unexpected location error:",
            str(e)
        )

        return jsonify({

            "success": False,

            "error": "Location lookup failed"

        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    return jsonify({

        "success": True,

        "status": "Siddhu Weather is running"

    })


# =========================================================
# WEATHER CODE MAPPING
# =========================================================

def get_weather_condition(code):

    weather_map = {

        0: (
            "Clear Sky",
            "☀️"
        ),

        1: (
            "Mainly Clear",
            "🌤️"
        ),

        2: (
            "Partly Cloudy",
            "⛅"
        ),

        3: (
            "Overcast",
            "☁️"
        ),


        45: (
            "Foggy",
            "🌫️"
        ),

        48: (
            "Rime Fog",
            "🌫️"
        ),


        51: (
            "Light Drizzle",
            "🌦️"
        ),

        53: (
            "Moderate Drizzle",
            "🌦️"
        ),

        55: (
            "Dense Drizzle",
            "🌧️"
        ),


        56: (
            "Light Freezing Drizzle",
            "🌧️"
        ),

        57: (
            "Dense Freezing Drizzle",
            "🌧️"
        ),


        61: (
            "Light Rain",
            "🌦️"
        ),

        63: (
            "Moderate Rain",
            "🌧️"
        ),

        65: (
            "Heavy Rain",
            "🌧️"
        ),


        66: (
            "Light Freezing Rain",
            "🌧️"
        ),

        67: (
            "Heavy Freezing Rain",
            "🌧️"
        ),


        71: (
            "Light Snow",
            "🌨️"
        ),

        73: (
            "Moderate Snow",
            "🌨️"
        ),

        75: (
            "Heavy Snow",
            "❄️"
        ),


        77: (
            "Snow Grains",
            "🌨️"
        ),


        80: (
            "Light Rain Showers",
            "🌦️"
        ),

        81: (
            "Moderate Rain Showers",
            "🌧️"
        ),

        82: (
            "Violent Rain Showers",
            "⛈️"
        ),


        85: (
            "Light Snow Showers",
            "🌨️"
        ),

        86: (
            "Heavy Snow Showers",
            "❄️"
        ),


        95: (
            "Thunderstorm",
            "⛈️"
        ),

        96: (
            "Thunderstorm with Hail",
            "⛈️"
        ),

        99: (
            "Thunderstorm with Heavy Hail",
            "⛈️"
        )

    }


    return weather_map.get(

        code,

        (
            "Unknown Weather",
            "🌤️"
        )

    )


# =========================================================
# ERROR HANDLERS
# =========================================================

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


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )