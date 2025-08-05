import requests
from bs4 import BeautifulSoup
import pgeocode

zip_code = "19320"

url = f"https://www.airbnb.com/s/{zip_code}/homes?refinement_paths%5B%5D=%2Fhomes&flexible_trip_lengths%5B%5D=one_week&monthly_start_date=2025-09-01&monthly_length=3&monthly_end_date=2025-12-01&rank_mode=default&service_type_tag=Tag%3A8950&source=structured_search_input_header&search_type=search_query&price_filter_input_type=2&price_filter_num_nights=5&channel=EXPLORE&acp_id=127c9b07-f720-4b4f-a81d-10d1a1dc63b8&date_picker_type=calendar&zoom_level=13&query={zip_code}"

# Step 2: Fetch the page content using requests
response = requests.get(url)
html_content = response.text

# Step 3: Parse the HTML using BeautifulSoup
soup = BeautifulSoup(html_content, "html.parser")

# Step 4: Find all the <a> tags (links)
links = soup.find_all("a")

# Step 5: Print out the href attribute of each link
for link in links:
    href = link.get("href")
    print(href)


# Scraper steps:
# Make a zip code variable to locate an area - Done
# This specifically means I need to turn a zip code into all the listing ids in that area (store as a list)
# Start by scraping one of the found listing ids
# Loop that code to scrape all listings in the area
# Scrape all reviews for listings in the area
# Use AI to summarize pros and cons
# Spent hundreds of thousands of dollars on a house