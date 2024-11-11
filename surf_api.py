from flask import Flask, request, jsonify
import requests
import logging
import pysurfline
from scrapingbee import ScrapingBeeClient
from datetime import datetime
import os
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ScrapingBee configuration - add your API key
client = ScrapingBeeClient(api_key=os.getenv('SCRAPING_BEE_API_KEY'))

app = Flask(__name__)

@app.route('/test/proxy')
def test_proxy():
    """Test the proxy configuration"""
    try:
        # Use ScrapingBee to get the URL
        url = 'https://api.ipify.org?format=json'
        result = client.get(url)
        
        return jsonify({
            'response': result.json(),
            'status_code': result.status_code,
            'headers': dict(result.headers)
        })
    except Exception as e:
        logger.error(f"Test error: {str(e)}")
        return jsonify({
            'error': str(e),
            'type': type(e).__name__,
        }), 500

@app.route('/api/surf')
def get_surf_data():
    spot_id = request.args.get('spotId')
    if not spot_id:
        return jsonify({"error": "Missing spotId parameter"}), 400
    
    try:
        original_get = requests.get

        def proxy_get(url, **kwargs):
            try:
                # Get original request params and headers
                orig_params = kwargs.get('params', {})
                
                # Construct the full URL with query parameters
                if orig_params:
                    url = f"{url}?{urlencode(orig_params)}"
                
                response = client.get(
                    url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                        'Referer': 'https://www.surfline.com/',
                    },
                    params={
                        'premium_proxy': 'false',
                        'render_js': 'false',
                        'country_code': 'us'
                    }
                )
                return response
            except Exception as e:
                raise Exception(f"Failed to fetch data: {str(e)}")

        requests.get = proxy_get
        
        try:
            spotforecasts = pysurfline.get_spot_forecasts(
                spot_id,
                days=1,
                intervalHours=1
            )
            
            data = {
                "current_conditions": {
                    "surf": {
                        "min": spotforecasts.waves[0].surf.min,
                        "max": spotforecasts.waves[0].surf.max,
                        "human_relation": spotforecasts.waves[0].surf.humanRelation
                    },
                    "wind": {
                        "speed": round(spotforecasts.wind[0].speed),
                        "direction": round(spotforecasts.wind[0].direction),
                        "type": spotforecasts.wind[0].directionType
                    },
                    "temperature": round(spotforecasts.weather[0].temperature)
                },
                "tides": [
                    {
                        "time": str(tide.timestamp),
                        "height": round(tide.height, 1),
                        "type": tide.type
                    }
                    for tide in spotforecasts.tides if tide.type in ['HIGH', 'LOW']
                ][:4],
                "location": spotforecasts.name
            }
            return jsonify(data)
        finally:
            requests.get = original_get
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "Surf API is running. Use /test/proxy to test proxy or /api/surf?spotId=<spot_id> for surf data"
    })

if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
