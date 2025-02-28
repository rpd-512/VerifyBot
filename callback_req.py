#required to keep Render (hosting platform) away from inactivity
import requests
import time
from random import randint

# URL to send requests to
main_url = os.getenv("SITE_URL")
url = main_url+"/callback"

# Function to send the request
def send_request():
    try:
        response = requests.get(url)
        print(randint(10000,99999),"Response Code:", response.status_code)
    except Exception as e:
        print(f"An error occurred: {e}")

# Loop to send request every few seconds
def main():
    while True:
        send_request()
        time.sleep(randint(0,20))  # Delay for 5 seconds before sending the next request

if __name__ == "__main__":
    main()
