from flask import Flask, jsonify
import pysurfline
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

def adjust_time(timestamp, utc_offset):
    """Adjust time using UTC offset and format as HH:MM"""
    if hasattr(timestamp, 'timestamp'):
        time_str = str(timestamp)
        base_time = datetime.strptime(time_str, "Time(%Y-%m-%d %H:%M:%S)")
    else:
        base_time = timestamp
    
    adjusted_time = base_time + timedelta(hours=utc_offset)
    return adjusted_time.strftime("%I:%M %p").lstrip('0')

def create_surf_data(spot_id):
    """Generate surf data for a given spot ID"""
    try:
        # Validate spot_id format (assuming it's a hex string)
        if not spot_id.strip() or not all(c in '0123456789abcdefABCDEF' for c in spot_id):
            return None, "Invalid spot ID format"
        
        # Attempt to get forecast data
        try:
            spotforecasts = pysurfline.get_spot_forecasts(
                spot_id,
                days=1,
                intervalHours=1,
            )
        except Exception as e:
            # Check if it's a spot not found error
            if "404" in str(e) or "not found" in str(e).lower():
                return None, f"Spot ID {spot_id} not found"
            # Check if it's an authentication error
            elif "401" in str(e) or "unauthorized" in str(e).lower():
                return None, "API authentication error"
            # Handle rate limiting
            elif "429" in str(e) or "too many requests" in str(e).lower():
                return None, "Rate limit exceeded. Please try again later"
            else:
                return None, f"Error fetching surf data: {str(e)}"

        # Verify we got valid data
        if not spotforecasts.waves or not spotforecasts.wind or not spotforecasts.tides:
            return None, "Incomplete data received from surf API"
        
        # Get current wave data
        current_wave = spotforecasts.waves[0]
        current_weather = spotforecasts.weather[0]
        sunlight = spotforecasts.sunlightTimes[0]
        
        # Filter only HIGH and LOW tides
        extreme_tides = [tide for tide in spotforecasts.tides if tide.type in ['HIGH', 'LOW']][:4]
        
        # Prepare tide data
        tide_data = {}
        for i, tide in enumerate(extreme_tides, 1):
            adjusted_time = adjust_time(tide.timestamp, tide.utcOffset)
            tide_data.update({
                f'tide{i}_time': adjusted_time,
                f'tide{i}_height': round(tide.height, 1),
                f'tide{i}_type': tide.type
            })
        
        # Fill in any missing tide slots
        for i in range(len(extreme_tides) + 1, 5):
            tide_data.update({
                f'tide{i}_time': '',
                f'tide{i}_height': '',
                f'tide{i}_type': ''
            })

        # Create data structure
        data = {
            "surf_height": f"{current_wave.surf.min}-{current_wave.surf.max}",
            "surf_condition": current_wave.surf.humanRelation,
            "swell_height": round(current_wave.swells[0].height, 1),
            "swell_period": current_wave.swells[0].period,
            "swell_direction": round(current_wave.swells[0].direction),
            "wind_speed": round(spotforecasts.wind[0].speed),
            "wind_direction": round(spotforecasts.wind[0].direction),
            "wind_type": spotforecasts.wind[0].directionType,
            "temperature": round(current_weather.temperature),
            "location": spotforecasts.name,
            "sunrise": adjust_time(sunlight.sunrise, sunlight.sunriseUTCOffset),
            "sunset": adjust_time(sunlight.sunset, sunlight.sunsetUTCOffset),
            **tide_data
        }
        return data, None
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"

@app.route('/api/surf/<spot_id>')
def get_surf_data(spot_id):
    """API endpoint that returns JSON data for a given spot ID"""
    data, error = create_surf_data(spot_id)
    
    if error:
        error_response = {
            'error': error,
            'status': 'error'
        }
        # Choose appropriate HTTP status code based on error
        if "not found" in error.lower():
            return jsonify(error_response), 404
        elif "invalid spot id format" in error.lower():
            return jsonify(error_response), 400
        elif "rate limit" in error.lower():
            return jsonify(error_response), 429
        elif "authentication" in error.lower():
            return jsonify(error_response), 401
        else:
            return jsonify(error_response), 500
    
    return jsonify({
        'status': 'success',
        'data': data
    })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Route not found', 'status': 'error'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error', 'status': 'error'}), 500

if __name__ == '__main__':
    # Get port from environment variable (Heroku sets this automatically)
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)