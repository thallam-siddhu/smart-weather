from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)


# ============================================================
# APPLICATION SETTINGS
# ============================================================

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
LOCATION_API_URL = "https://nominatim.openstreetmap.org/reverse"

APP_USER_AGENT = (
    "SmartWeather/2.0 "
    "(real-time weather application)"
)


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# WEATHER CODE → REAL WEATHER CONDITION
# ============================================================

def weather_description(code):

    weather_codes = {

        0: {
            "condition": "Clear Sky",
            "icon": "☀️"
        },

        1: {
            "condition": "Mainly Clear",
            "icon": "🌤️"
        },

        2: {
            "condition": "Partly Cloudy",
            "icon": "⛅"
        },

        3: {
            "condition": "Overcast",
            "icon": "☁️"
        },

        45: {
            "condition": "Fog",
            "icon": "🌫️"
        },

        48: {
            "condition": "Depositing Rime Fog",
            "icon": "🌫️"
        },

        51: {
            "condition": "Light Drizzle",
            "icon": "🌦️"
        },

        53: {
            "condition": "Moderate Drizzle",
            "icon": "🌦️"
        },

        55: {
            "condition": "Heavy Drizzle",
            "icon": "🌧️"
        },

        56: {
            "condition": "Light Freezing Drizzle",
            "icon": "🌨️"
        },

        57: {
            "condition": "Heavy Freezing Drizzle",
            "icon": "🌨️"
        },

        61: {
            "condition": "Light Rain",
            "icon": "🌦️"
        },

        63: {
            "condition": "Moderate Rain",
            "icon": "🌧️"
        },

        65: {
            "condition": "Heavy Rain",
            "icon": "🌧️"
        },

        66: {
            "condition": "Light Freezing Rain",
            "icon": "🌨️"
        },

        67: {
            "condition": "Heavy Freezing Rain",
            "icon": "🌨️"
        },

        71: {
            "condition": "Light Snow",
            "icon": "🌨️"
        },

        73: {
            "condition": "Moderate Snow",
            "icon": "❄️"
        },

        75: {
            "condition": "Heavy Snow",
            "icon": "❄️"
        },

        77: {
            "condition": "Snow Grains",
            "icon": "❄️"
        },

        80: {
            "condition": "Light Rain Showers",
            "icon": "🌦️"
        },

        81: {
            "condition": "Moderate Rain Showers",
            "icon": "🌧️"
        },

        82: {
            "condition": "Heavy Rain Showers",
            "icon": "⛈️"
        },

        85: {
            "condition": "Light Snow Showers",
            "icon": "🌨️"
        },

        86: {
            "condition": "Heavy Snow Showers",
            "icon": "❄️"
        },

        95: {
            "condition": "Thunderstorm",
            "icon": "⛈️"
        },

        96: {
            "condition": "Thunderstorm with Hail",
            "icon": "⛈️"
        },

        99: {
            "condition": "Severe Thunderstorm with Hail",
            "icon": "⛈️"
        }

    }

    return weather_codes.get(
        code,
        {
            "condition": "Unknown Weather",
            "icon": "🌡️"
        }
    )


# ============================================================
# WEATHER API
# ============================================================

@app.route("/weather")
def weather():

    latitude = request.args.get("lat")
    longitude = request.args.get("lon")

    # --------------------------------------------------------
    # VALIDATE COORDINATES
    # --------------------------------------------------------

    if not latitude or not longitude:

        return jsonify({
            "success": False,
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)

    except ValueError:

        return jsonify({
            "success": False,
            "error": "Invalid coordinates"
        }), 400


    # --------------------------------------------------------
    # OPEN-METEO PARAMETERS
    # --------------------------------------------------------

    params = {

        "latitude": latitude,

        "longitude": longitude,

        "current": ",".join([

            "temperature_2m",

            "relative_humidity_2m",

            "apparent_temperature",

            "is_day",

            "precipitation",

            "rain",

            "showers",

            "snowfall",

            "weather_code",

            "cloud_cover",

            "pressure_msl",

            "surface_pressure",

            "wind_speed_10m",

            "wind_direction_10m",

            "wind_gusts_10m"

        ]),

        "hourly": ",".join([

            "temperature_2m",

            "relative_humidity_2m",

            "apparent_temperature",

            "precipitation_probability",

            "precipitation",

            "rain",

            "weather_code",

            "cloud_cover",

            "wind_speed_10m",

            "uv_index"

        ]),

        "daily": ",".join([

            "weather_code",

            "temperature_2m_max",

            "temperature_2m_min",

            "apparent_temperature_max",

            "apparent_temperature_min",

            "sunrise",

            "sunset",

            "daylight_duration",

            "sunshine_duration",

            "uv_index_max",

            "precipitation_sum",

            "rain_sum",

            "precipitation_probability_max",

            "wind_speed_10m_max",

            "wind_gusts_10m_max"

        ]),

        "timezone": "auto",

        "forecast_days": 7

    }


    # --------------------------------------------------------
    # REQUEST WEATHER
    # --------------------------------------------------------

    try:

        response = requests.get(

            WEATHER_API_URL,

            params=params,

            timeout=15

        )

        if response.status_code != 200:

            print(
                "Weather API status:",
                response.status_code
            )

            return jsonify({

                "success": False,

                "error":
                    "Weather service is temporarily unavailable"

            }), 502


        data = response.json()


        # ----------------------------------------------------
        # CURRENT WEATHER
        # ----------------------------------------------------

        current = data.get(
            "current",
            {}
        )


        weather_code = current.get(
            "weather_code"
        )


        description = weather_description(
            weather_code
        )


        # ----------------------------------------------------
        # ADD EASY-TO-USE CURRENT REPORT
        # ----------------------------------------------------

        current_report = {

            "temperature":
                current.get(
                    "temperature_2m"
                ),

            "feels_like":
                current.get(
                    "apparent_temperature"
                ),

            "humidity":
                current.get(
                    "relative_humidity_2m"
                ),

            "cloud_cover":
                current.get(
                    "cloud_cover"
                ),

            "precipitation":
                current.get(
                    "precipitation"
                ),

            "rain":
                current.get(
                    "rain"
                ),

            "showers":
                current.get(
                    "showers"
                ),

            "snowfall":
                current.get(
                    "snowfall"
                ),

            "pressure":
                current.get(
                    "pressure_msl"
                ),

            "surface_pressure":
                current.get(
                    "surface_pressure"
                ),

            "wind_speed":
                current.get(
                    "wind_speed_10m"
                ),

            "wind_direction":
                current.get(
                    "wind_direction_10m"
                ),

            "wind_gusts":
                current.get(
                    "wind_gusts_10m"
                ),

            "is_day":
                current.get(
                    "is_day"
                ),

            "weather_code":
                weather_code,

            "condition":
                description["condition"],

            "icon":
                description["icon"]

        }


        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "location": {

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "timezone":
                    data.get(
                        "timezone"
                    ),

                "timezone_abbreviation":
                    data.get(
                        "timezone_abbreviation"
                    ),

                "elevation":
                    data.get(
                        "elevation"
                    )

            },

            "units": {

                "temperature":
                    "°C",

                "wind_speed":
                    "km/h",

                "pressure":
                    "hPa",

                "precipitation":
                    "mm"

            },

            "current":
                current_report,

            "hourly":
                data.get(
                    "hourly",
                    {}
                ),

            "daily":
                data.get(
                    "daily",
                    {}

                ),

            "updated_at":
                current.get(
                    "time"
                )

        })


    except requests.RequestException as error:

        print(
            "Weather API error:",
            error
        )

        return jsonify({

            "success": False,

            "error":
                "Unable to connect to weather service"

        }), 503


# ============================================================
# REVERSE GEOCODING
# ============================================================

@app.route("/location")
def location():

    latitude = request.args.get("lat")
    longitude = request.args.get("lon")


    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not latitude or not longitude:

        return jsonify({

            "success": False,

            "error":
                "Coordinates not provided"

        }), 400


    try:

        latitude = float(latitude)
        longitude = float(longitude)

    except ValueError:

        return jsonify({

            "success": False,

            "error":
                "Invalid coordinates"

        }), 400


    # --------------------------------------------------------
    # NOMINATIM PARAMETERS
    # --------------------------------------------------------

    params = {

        "lat":
            latitude,

        "lon":
            longitude,

        "format":
            "json",

        "zoom":
            18,

        "addressdetails":
            1,

        "accept-language":
            "en"

    }


    headers = {

        "User-Agent":
            APP_USER_AGENT

    }


    # --------------------------------------------------------
    # REQUEST LOCATION
    # --------------------------------------------------------

    try:

        response = requests.get(

            LOCATION_API_URL,

            params=params,

            headers=headers,

            timeout=15

        )


        if response.status_code != 200:

            return jsonify({

                "success": False,

                "error":
                    "Location service unavailable"

            }), 502


        data = response.json()


        address = data.get(
            "address",
            {}
        )


        # ----------------------------------------------------
        # ROAD
        # ----------------------------------------------------

        road = (

            address.get("road")

            or address.get("pedestrian")

            or address.get("residential")

            or address.get("footway")

            or ""

        )


        # ----------------------------------------------------
        # LOCAL AREA
        # ----------------------------------------------------

        locality = (

            address.get("neighbourhood")

            or address.get("suburb")

            or address.get("quarter")

            or address.get("village")

            or ""

        )


        # ----------------------------------------------------
        # CITY
        # ----------------------------------------------------

        city = (

            address.get("city")

            or address.get("town")

            or address.get("village")

            or address.get("municipality")

            or ""

        )


        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        state = (

            address.get("state")

            or ""

        )


        # ----------------------------------------------------
        # COUNTRY
        # ----------------------------------------------------

        country = (

            address.get("country")

            or ""

        )


        # ----------------------------------------------------
        # POSTCODE
        # ----------------------------------------------------

        postcode = (

            address.get("postcode")

            or ""

        )


        # ----------------------------------------------------
        # BUILD HUMAN-READABLE LOCATION
        # ----------------------------------------------------

        parts = []


        for part in [

            road,

            locality,

            city,

            state,

            country

        ]:

            if part and part not in parts:

                parts.append(part)


        location_name = ", ".join(
            parts
        )


        if not location_name:

            location_name = (
                "Selected Location"
            )


        # ----------------------------------------------------
        # RETURN LOCATION
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "name":
                location_name,

            "display_name":
                data.get(
                    "display_name",
                    location_name
                ),

            "road":
                road,

            "locality":
                locality,

            "city":
                city,

            "state":
                state,

            "country":
                country,

            "postcode":
                postcode,

            "latitude":
                latitude,

            "longitude":
                longitude

        })


    except requests.RequestException as error:

        print(
            "Location API error:",
            error
        )

        return jsonify({

            "success": False,

            "error":
                "Unable to find selected location"

        }), 503


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status":
            "online",

        "application":
            "Smart Weather",

        "version":
            "2.0",

        "service":
            "Weather API"

    })


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return jsonify({

        "success": False,

        "error":
            "Page not found"

    }), 404


@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({

        "success": False,

        "error":
            "Internal server error"

    }), 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="0.0.0.0",

        port=5000

    )