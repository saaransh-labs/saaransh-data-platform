# import requests

# url = "https://www.nseindia.com/api/quote-equity?symbol=ADANIENT"

# headers = {
#     "User-Agent": "Mozilla/5.0",
#     "Accept": "application/json",
#     "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=ADANIENT"
# }

# session = requests.Session()

# # Step 1: Get cookies
# session.get("https://www.nseindia.com", headers=headers)

# # Step 2: Call API
# response = session.get(url, headers=headers)

# data = response.json()
# print(data)

from src.common.path import CONFIG_DIR

print(f"Config directory: {CONFIG_DIR}")