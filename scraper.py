from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import csv

# Function to scrape Google Scholar based on author's name
def scrape_scholar(author_name):
    # Set up the WebDriver (ensure chromedriver is in your PATH)
    driver = webdriver.Chrome()

    try:
        # Navigate to Google Scholar
        driver.get("https://scholar.google.com")

        # Find the search box and enter the author's name
        search_box = driver.find_element(By.NAME, 'q')
        search_box.send_keys(author_name)
        search_box.send_keys(Keys.RETURN)

        # Wait for the results to load
        time.sleep(3)

        # Locate the author profile link under the <h4 class="gs_rt2"> tag
        author_link_element = driver.find_element(By.CSS_SELECTOR, 'h4.gs_rt2 a')
        author_profile_link = author_link_element.get_attribute('href')

        # Navigate to the author's profile page
        driver.get(author_profile_link)

        # Wait for the profile page to load
        time.sleep(3)

        # Initialize page height before clicking "More results"
        last_height = driver.execute_script("return document.body.scrollHeight")

        # Keep clicking the "More results" button until the page height doesn't change
        while True:
            try:
                more_button = driver.find_element(By.ID, 'gsc_bpf_more')
                if more_button.is_displayed():
                    more_button.click()
                    time.sleep(3)  # Wait for the new articles to load
                else:
                    break

                # Measure the new page height after clicking the button
                new_height = driver.execute_script("return document.body.scrollHeight")

                # If the height didn't change, break the loop
                if new_height == last_height:
                    print("No more content to load. Stopping.")
                    break
                last_height = new_height  # Update last height to the new height

            except Exception as e:
                print("No more results button found, all articles are loaded.")
                break

        # Now scrape the links of the articles
        articles = driver.find_elements(By.CSS_SELECTOR, 'td.gsc_a_t a')

        # Collect the article titles and links
        article_data = [(article.text, article.get_attribute('href')) for article in articles]

        # Save the data to a CSV file
        with open('article_links.csv', 'w', newline='', encoding='utf-8') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['Title', 'link'])  # Write header
            csvwriter.writerows(article_data)  # Write article data

        print(f"Scraped {len(article_data)} articles and saved to 'article_links.csv'")

    except Exception as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the browser
        driver.quit()

# Ask the user for the author's name
author_name = input("Enter the author's name: ")
scrape_scholar(author_name)


'''import csv
import requests
from bs4 import BeautifulSoup

def scrape_google_scholar_info(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    def get_field_value(field_name):
        field = soup.find('div', text=field_name)
        if field:
            value_div = field.find_next_sibling('div', class_='gsc_oci_value')
            if value_div:
                return value_div.get_text(strip=True)
        return ''
    
    def get_citation_number():
        citation_div = soup.find('a', href=lambda href: href and "cites" in href)
        if citation_div:
            return citation_div.get_text(strip=True).replace('Cité', '').replace('fois', '').strip()
        return ''

    data = {
        "Auteurs": get_field_value("Auteurs"),
        "Date de publication": get_field_value("Date de publication"),
        "Revue": get_field_value("Revue"),
        "Volume": get_field_value("Volume"),
        "Numéro": get_field_value("Numéro"),
        "Pages": get_field_value("Pages"),
        "Éditeur": get_field_value("Éditeur"),
        "Description": get_field_value("Description"),
        "Nombre de citations": get_citation_number()
    }
    
    return data

# Function to process multiple URLs from a CSV and save results to a new CSV
def process_urls_from_csv(input_csv, output_csv):
    with open(input_csv, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        urls = [row[1] for row in reader]  # Assuming the URLs are in the first column
    
    with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Auteurs", "Date de publication", "Revue", "Volume", "Numéro", "Pages", "Éditeur", "Description", "Nombre de citations"])
        writer.writeheader()
        
        for url in urls:
            try:
                scraped_data = scrape_google_scholar_info(url)
                writer.writerow(scraped_data)
            except Exception as e:
                print(f"Error processing {url}: {e}")

# Example usage
process_urls_from_csv('article_links.csv', 'output_data.csv')
'''