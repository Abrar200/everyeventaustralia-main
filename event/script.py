import requests

# Your Google Maps API Key
API_KEY = 'AIzaSyD_jODWQ-KDeU65Sr4xOALQsZ7mwI3q7h4'
# Your business name as it appears on Google
business_name = "Every Event Australia - Wedding & Event Suppliers + Venue Directory"

# Construct the URL to find the place by text
url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={business_name}&inputtype=textquery&fields=place_id,name,formatted_address&key={API_KEY}"

# Send the request to Google Places API
response = requests.get(url)
data = response.json()

# Check if a valid Place ID is returned
if 'candidates' in data and len(data['candidates']) > 0:
    place_id = data['candidates'][0]['place_id']
    business_name = data['candidates'][0]['name']
    address = data['candidates'][0]['formatted_address']
    print(f"New Place ID: {place_id}")
    print(f"Business Name: {business_name}")
    print(f"Address: {address}")
else:
    # Print the full error response from the API
    print("Place ID not found.")
    print(f"Error Details: {data}")
