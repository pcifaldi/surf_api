#!/usr/bin/env python

import sys
import urllib.request
import ssl

print('If you get an error "ImportError: No module named \'six\'", install six:')
print('$ sudo pip install six')
print('To enable your free eval account and get CUSTOMER, YOURZONE, and YOURPASS, please contact sales@brightdata.com')

# Proxy credentials and URL
proxy_user = 'brd-customer-hl_05e0f25a-zone-residential_proxy1'
proxy_password = 'go7qdsqremvt'
proxy_host = 'brd.superproxy.io'
proxy_port = 22225

proxy_url = f'http://{proxy_user}:{proxy_password}@{proxy_host}:{proxy_port}'
proxies = {
    'http': proxy_url,
    'https': proxy_url
}

# URL to test the proxy
test_url = 'https://geo.brdtest.com/mygeo.json'

if sys.version_info[0] == 3:
    try:
        # Setting up proxy handler
        proxy_handler = urllib.request.ProxyHandler(proxies)
        opener = urllib.request.build_opener(proxy_handler)

        # Create an SSL context that does not verify the certificate
        ssl_context = ssl._create_unverified_context()

        # Making request with the custom SSL context
        response = opener.open(test_url, context=ssl_context).read()
        print("Proxy is working!")
        print(response.decode('utf-8'))
    except urllib.error.URLError as e:
        print("URL Error:", e.reason)
    except urllib.error.HTTPError as e:
        print("HTTP Error:", e.code, e.reason)
    except Exception as e:
        print("An unexpected error occurred:", e)
