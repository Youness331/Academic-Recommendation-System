"""
Web of Science Data Scraping Module

This module provides functionality to scrape Web of Science for author information,
publications, and journal metrics from SJR (SCImago Journal Rank).

Author: Data Integration Team
Date: 2025
"""

import json
import time
import csv
import re
import pandas as pd
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    TimeoutException, 
    NoSuchWindowException
)
from bs4 import BeautifulSoup


class WebOfScienceScraper:
    """
    A class to scrape Web of Science for author and publication information.
    """
    
    def __init__(self, edge_driver_path=None):
        """
        Initialize the Web of Science scraper.
        
        Args:
            edge_driver_path (str): Path to Edge WebDriver executable
        """
        self.driver = None
        self.wait = None
        self.edge_driver_path = edge_driver_path
        self._setup_driver()
    
    def _setup_driver(self):
        """Set up the Edge WebDriver."""
        try:
            if self.edge_driver_path:
                service = Service(executable_path=self.edge_driver_path)
                self.driver = webdriver.Edge(service=service)
            else:
                self.driver = webdriver.Edge()
            
            self.wait = WebDriverWait(self.driver, 10)
            print("Edge WebDriver initialized successfully.")
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            raise
    
    def login(self, email, password, login_url="https://www.webofscience.com.eressources.imist.ma/"):
        """
        Login to Web of Science.
        
        Args:
            email (str): Login email
            password (str): Login password
            login_url (str): Web of Science login URL
        """
        try:
            self.driver.get(login_url)
            
            # Wait for and fill email field
            email_field = self.wait.until(
                EC.visibility_of_element_located((By.ID, "email"))
            )
            password_field = self.wait.until(
                EC.visibility_of_element_located((By.ID, "password"))
            )
            
            email_field.send_keys(email)
            password_field.send_keys(password)
            password_field.send_keys(Keys.RETURN)
            
            print("Login successful")
            
        except TimeoutException:
            print("Email or password fields not found.")
            raise
    
    def get_author_information(self, author_id):
        """
        Get comprehensive author information from Web of Science.
        
        Args:
            author_id (str): The author's Web of Science ID
            
        Returns:
            tuple: (author_info_dict, co_author_ids_list)
        """
        url = f"https://www.webofscience.com.eressources.imist.ma/wos/author/record/{author_id}"
        self.driver.get(url)
        time.sleep(5)
        self._scroll_slowly()

        # Check if author not found
        if "authorNotFound" in self.driver.current_url:
            print(f"Author with ID {author_id} not found.")
            return None, []

        try:
            author_info = {
                'ID de l\'Auteur': author_id,
                'nom_complet': None,
                'pays_affiliation': None,
                'co_auteurs': [],
                'H-Index': 0,
                "FWCI": "0",
                'Sum of Times Cited': 0
            }

            # Get co-authors
            try:
                co_authors_elements = self.wait.until(
                    EC.visibility_of_all_elements_located((By.CLASS_NAME, 'authors-list-link'))
                )
                author_info['co_auteurs'] = [author.text for author in co_authors_elements]
                co_author_ids = [
                    author.get_attribute('href').split('/')[-1] 
                    for author in co_authors_elements
                ]
            except:
                author_info['co_auteurs'] = []
                co_author_ids = []
                print('Co-authors do not exist')

            # Get metrics
            try:
                metrics = self.wait.until(
                    EC.visibility_of_all_elements_located((By.CLASS_NAME, 'wat-author-metric-descriptor'))
                )
                for metric in metrics:
                    if metric.text in ['H-Index', 'Sum of Times Cited']:
                        value = metric.find_element(By.XPATH, './preceding-sibling::div').text
                        author_info[metric.text] = value
            except:
                print('H-index or citations do not exist')

            # Get affiliation country
            try:
                country = self.wait.until(
                    EC.visibility_of_element_located((By.CLASS_NAME, 'more-details'))
                ).text.split(',')[-1].strip()
                author_info['pays_affiliation'] = country
            except:
                print('Affiliation country does not exist')

            # Get full name
            try:
                name = self.wait.until(
                    EC.visibility_of_element_located((By.CLASS_NAME, 'wat-author-name'))
                ).text
                author_info['nom_complet'] = name
            except:
                print('Name does not exist')

            return author_info, co_author_ids

        except Exception as e:
            print(f'Error waiting for page to load: {e}')
            return None, []

    def extract_article_details(self, article_link):
        """
        Extract detailed information from a single article.
        
        Args:
            article_link (str): URL of the article
            
        Returns:
            dict: Dictionary containing article information
        """
        self.driver.get(article_link)
        time.sleep(4)
        self._scroll_slowly()
        
        article_info = {}

        # Article title
        try:
            article_info['Titre de l'article'] = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'title'))
            ).text
        except:
            article_info['Titre de l'article'] = None
            print("Error retrieving article title")

        # Authors
        try:
            authors = self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//a[starts-with(@id,'SumAuthTa-DisplayName-author-en-')]")
                )
            )
            article_info['Auteurs'] = ' ; '.join([element.text for element in authors])
        except:
            article_info['Auteurs'] = None
            print("Error retrieving authors")

        # Publication date
        date_class_names = ['FullRTa-pubdate', 'FullRTa-earlyAccess']
        for class_name in date_class_names:
            try:
                article_info['Date de publication'] = self.wait.until(
                    EC.presence_of_element_located((By.ID, class_name))
                ).text
                break
            except:
                article_info['Date de publication'] = None
        
        if article_info.get('Date de publication') is None:
            print("Error retrieving publication date")

        # Journal name
        journal_class_names = ['summary-source-title-link', 'summary-source-title']
        for class_name in journal_class_names:
            try:
                journal_text = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, class_name))
                ).text
                article_info['nom journal'] = journal_text.replace("arrow_drop_down", "").strip()
                break
            except:
                article_info['nom journal'] = None
        
        if article_info.get('nom journal') is None:
            print("Error retrieving journal name")

        # Keywords
        keywords = ''
        keyword_id_prefixes = ['FRkeywordsTa-keyWordsPlusLink-', 'FRkeywordsTa-authorKeywordLink-']
        for id_prefix in keyword_id_prefixes:
            try:
                keyword_elements = self.wait.until(
                    EC.presence_of_all_elements_located(
                        (By.XPATH, f"//a[starts-with(@id,'{id_prefix}')]")
                    )
                )
                keywords += ' ' + ' ; '.join([element.text for element in keyword_elements])
            except:
                pass
        
        article_info['Mots-clés'] = keywords.strip() if keywords else None

        # Citation count
        try:
            citation_info = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'citation-count'))
            ).text.split('\n')
            
            if len(citation_info) > 1 and citation_info[1] == 'Cited References':
                article_info['Nombre de citations'] = 0
            else:
                article_info['Nombre de citations'] = citation_info[0]
        except:
            article_info['Nombre de citations'] = None
            print("Error retrieving citation count")

        # DOI
        try:
            article_info['DOI'] = self.wait.until(
                EC.presence_of_element_located((By.ID, 'FullRTa-DOI'))
            ).text
        except:
            article_info['DOI'] = None
            print("Error retrieving DOI")

        # Abstract
        try:
            article_info['Résumé'] = self.wait.until(
                EC.presence_of_element_located((By.ID, 'FullRTa-abstract-basic'))
            ).text
        except:
            article_info['Résumé'] = None
            print("Error retrieving abstract")

        # Document type
        try:
            article_info['Type de document'] = self.wait.until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="FullRTa-doctype-0"]'))
            ).text
        except:
            article_info['Type de document'] = None
            print("Error retrieving document type")

        # ISSN
        try:
            article_info['issn'] = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, 'value.section-label-data.text-color'))
            ).text
        except:
            article_info['issn'] = None
            print("ISSN element not found")

        return article_info

    def get_article_titles(self):
        """
        Get article links from the current page, handling pagination.
        
        Returns:
            list: List of article URLs
        """
        titles = []
        
        while True:
            articles = self.driver.find_elements(By.CLASS_NAME, 'title')
            for article in articles:
                href = article.get_attribute('href')
                if href:
                    titles.append(href)
            
            try:
                next_button = self.driver.find_element(
                    By.XPATH, '//button[@data-ta="next-page-button"]'
                )
                if 'mat-button-disabled' in next_button.get_attribute('class'):
                    break
                else:
                    next_button.click()
                    self._scroll_slowly(scroll_pause_time=0.2, scroll_increment=100)
            except NoSuchElementException:
                break
        
        return titles

    def _scroll_slowly(self, scroll_pause_time=0.1, scroll_increment=100):
        """
        Scroll the page slowly to load dynamic content.
        
        Args:
            scroll_pause_time (float): Time to pause between scrolls
            scroll_increment (int): Pixels to scroll each time
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        current_scroll_position = 0

        while current_scroll_position < last_height:
            current_scroll_position += scroll_increment
            self.driver.execute_script(f"window.scrollTo(0, {current_scroll_position});")
            time.sleep(scroll_pause_time)
            last_height = self.driver.execute_script("return document.body.scrollHeight")

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            print("WebDriver closed successfully.")


class SJRJournalScraper:
    """
    A class to scrape SJR (SCImago Journal Rank) journal metrics.
    """
    
    def __init__(self, driver):
        """
        Initialize with an existing WebDriver instance.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)

    def search_journal_info(self, issn):
        """
        Search for journal information by ISSN on SJR website.
        
        Args:
            issn (str): The journal's ISSN
        """
        self.driver.get("https://www.scimagojr.com/")
        try:
            search_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "searchinput"))
            )
            search_input.clear()
            search_input.send_keys(issn)
            search_input.send_keys(Keys.RETURN)

            # Click on search result
            self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "search_results"))
            ).click()
            
        except Exception as e:
            print(f"Error searching for ISSN {issn}: {e}")

    def extract_publisher_and_journal_name(self, soup):
        """
        Extract publisher information from BeautifulSoup object.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            dict: Dictionary containing publisher information
        """
        publisher = None
        publisher_element = soup.find(
            'a', href=lambda href: href and "journalsearch.php?q=" in href
        )
        if publisher_element:
            publisher = publisher_element.text.strip()

        return {"publisher": publisher}

    def extract_quartile(self, soup):
        """
        Extract quartile information from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            dict: Dictionary containing quartile data
        """
        quartile_data = {}
        dashboards = soup.find_all('div', class_='dashboard')
        
        if dashboards:
            quartile_dashboard = dashboards[0].find_all('div', class_="cellslide")
            if quartile_dashboard and len(quartile_dashboard) > 1:
                try:
                    last_quartile_row = (
                        quartile_dashboard[1]
                        .find('tbody')
                        .find_all('tr')[-1]
                        .find_all('td')
                    )
                    if len(last_quartile_row) == 3:
                        quartile_data = {
                            "year": last_quartile_row[1].text,
                            "quartile_value": last_quartile_row[2].text
                        }
                except (IndexError, AttributeError):
                    pass
        
        return quartile_data

    def extract_sjr(self, soup):
        """
        Extract SJR score information from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            dict: Dictionary containing SJR data
        """
        sjr_data = {}
        dashboards = soup.find_all('div', class_='dashboard')
        
        if len(dashboards) > 1:
            try:
                sjr_dashboard = dashboards[1].find_all('div', class_="cellslide")[1]
                sjr_row = sjr_dashboard.find('tbody').find_all('tr')[-1].find_all('td')
                if len(sjr_row) == 2:
                    sjr_data = {
                        "year": sjr_row[0].text,
                        "sjr_value": sjr_row[1].text
                    }
            except (IndexError, AttributeError):
                pass
        
        return sjr_data

    def extract_impact_factor(self, soup):
        """
        Extract impact factor information from the page.
        
        Args:
            soup: BeautifulSoup object of the page
            
        Returns:
            dict: Dictionary containing impact factor data
        """
        impact_data = {}
        dashboards = soup.find_all('div', class_='dashboard')
        
        if len(dashboards) > 1:
            try:
                impact_dashboard = dashboards[1].find_all('div', class_="cellslide")[5]
                impact_row = impact_dashboard.find('tbody').find_all('tr')[-1].find_all('td')
                if len(impact_row) == 3:
                    impact_data = {
                        "year": impact_row[1].text,
                        "impact_factor_value": impact_row[2].text
                    }
            except (IndexError, AttributeError):
                pass
        
        return impact_data

    def extract_journal_metrics(self, issn_list):
        """
        Extract comprehensive journal metrics for a list of ISSNs.
        
        Args:
            issn_list (list): List of ISSNs to process
            
        Returns:
            list: List of dictionaries containing journal metrics
        """
        journals_info = []

        for issn in issn_list:
            if not issn:  # Skip None or empty ISSNs
                journals_info.append(self._create_empty_journal_data(issn))
                continue
                
            try:
                self.search_journal_info(issn)

                # Extract page content
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')

                # Extract journal metrics
                journal_data = {
                    "issn": issn,
                    "h_index": self._get_h_index(),
                    "scope": self._get_scope(),
                    "quartile": self.extract_quartile(soup),
                    "sjr": self.extract_sjr(soup),
                    "impact_factor": self.extract_impact_factor(soup)
                }

                # Add publisher information
                publisher_info = self.extract_publisher_and_journal_name(soup)
                journal_data.update(publisher_info)

                journals_info.append(journal_data)
                print(f"Retrieved info for ISSN: {issn}")

            except Exception as e:
                print(f"Error processing ISSN {issn}: {e}")
                journals_info.append(self._create_empty_journal_data(issn))

        return journals_info

    def _get_h_index(self):
        """Get H-index from the current page."""
        try:
            return self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "hindexnumber"))
            ).text
        except:
            return "N/A"

    def _get_scope(self):
        """Get journal scope from the current page."""
        try:
            scope_element = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "fullwidth"))
            )
            scope_text = scope_element.text.split("\n")
            return scope_text[1] if len(scope_text) > 1 else "N/A"
        except:
            return "N/A"

    def _create_empty_journal_data(self, issn):
        """Create empty journal data structure for failed lookups."""
        return {
            "issn": issn,
            "h_index": "N/A",
            "scope": "N/A",
            "quartile": "N/A",
            "sjr": {"sjr_value": "N/A", "year": "N/A"},
            "impact_factor": {"impact_factor_value": "N/A", "year": "N/A"},
            "publisher": "N/A"
        }


class WebOfScienceDataProcessor:
    """
    A class to process and organize Web of Science data.
    """
    
    def __init__(self):
        """Initialize the data processor."""
        self.all_data = []
        self.processed_authors = set()

    def fetch_author_data_with_articles(self, author_id, wos_scraper, sjr_scraper):
        """
        Fetch comprehensive author data including articles and journal metrics.
        
        Args:
            author_id (str): The author's Web of Science ID
            wos_scraper (WebOfScienceScraper): WoS scraper instance
            sjr_scraper (SJRJournalScraper): SJR scraper instance
        """
        # Get author information and co-author IDs
        author_data, co_author_ids = wos_scraper.get_author_information(author_id)
        
        if author_data:
            author_data['Articles'] = self._fetch_articles_with_journal_data(
                author_id, wos_scraper, sjr_scraper
            )

            # Add main author if not already processed
            if author_id not in self.processed_authors:
                self.all_data.append(author_data)
                self.processed_authors.add(author_id)

            # Process co-authors
            for co_author_id in co_author_ids:
                if co_author_id not in self.processed_authors:
                    co_author_data, _ = wos_scraper.get_author_information(co_author_id)
                    if co_author_data:
                        co_author_data['Articles'] = self._fetch_articles_with_journal_data(
                            co_author_id, wos_scraper, sjr_scraper
                        )
                        self.all_data.append(co_author_data)
                        self.processed_authors.add(co_author_id)

    def _fetch_articles_with_journal_data(self, author_id, wos_scraper, sjr_scraper):
        """
        Fetch articles and associated journal data for an author.
        
        Args:
            author_id (str): The author's Web of Science ID
            wos_scraper (WebOfScienceScraper): WoS scraper instance
            sjr_scraper (SJRJournalScraper): SJR scraper instance
            
        Returns:
            list: List of articles with journal data
        """
        all_articles_data = []

        # Get article titles with retry logic
        articles = []
        retry_count = 0
        while not articles and retry_count < 3:
            articles = wos_scraper.get_article_titles()
            if not articles:
                wos_scraper.driver.refresh()
                time.sleep(1)
                wos_scraper._scroll_slowly()
                retry_count += 1

        if articles:
            issns = []
            for article_link in articles:
                article_data = self._fetch_article_data(article_link, wos_scraper)
                all_articles_data.append(article_data)
                issns.append(article_data.get('issn'))

            # Get journal metrics for all ISSNs
            journals_data = sjr_scraper.extract_journal_metrics(issns)
            
            # Associate journal data with articles
            for article, journal in zip(all_articles_data, journals_data):
                if article.get('issn') == journal.get('issn'):
                    article['journal_data'] = journal
                # Remove ISSN after association
                article.pop('issn', None)

        return all_articles_data

    def _fetch_article_data(self, article_link, wos_scraper):
        """
        Fetch article data with retry logic for ISSN extraction.
        
        Args:
            article_link (str): URL of the article
            wos_scraper (WebOfScienceScraper): WoS scraper instance
            
        Returns:
            dict: Article data dictionary
        """
        retry_count = 0
        while retry_count < 2:
            article_data = wos_scraper.extract_article_details(article_link)
            if 'issn' in article_data:
                return article_data
            else:
                wos_scraper._scroll_slowly()
                retry_count += 1
        
        # If ISSN still not found, set to None
        article_data['issn'] = None
        return article_data

    def save_data(self, filename="wos_data.json"):
        """
        Save processed data to JSON file.
        
        Args:
            filename (str): Name of the output file
        """
        with open(filename, "w", encoding="utf-8") as json_file:
            json.dump(self.all_data, json_file, indent=4, ensure_ascii=False)
        
        print(f"Data saved to {filename}")

    def get_data(self):
        """
        Get the processed data.
        
        Returns:
            list: List of processed author and article data
        """
        return self.all_data


def main():
    """
    Main function to demonstrate Web of Science scraping.
    """
    # Configuration
    EDGE_DRIVER_PATH = r"C:\Users\Electro Fatal\Desktop\file\edgedriver_win64\msedgedriver.exe"
    LOGIN_EMAIL = 'israa.boudda@usms.ac.ma'
    LOGIN_PASSWORD = ''  # Add password here
    
    # List of author IDs to process
    author_ids = ["your_author_id_1", "your_author_id_2"]  # Add actual author IDs
    
    # Initialize scrapers
    wos_scraper = WebOfScienceScraper(EDGE_DRIVER_PATH)
    sjr_scraper = SJRJournalScraper(wos_scraper.driver)
    data_processor = WebOfScienceDataProcessor()
    
    try:
        # Login to Web of Science
        wos_scraper.login(LOGIN_EMAIL, LOGIN_PASSWORD)
        
        # Process each author
        for author_id in author_ids:
            if author_id not in data_processor.processed_authors:
                print(f"Processing author ID: {author_id}")
                data_processor.fetch_author_data_with_articles(
                    author_id, wos_scraper, sjr_scraper
                )
                print(f"Completed processing for author ID: {author_id}")
        
        # Save results
        data_processor.save_data("wos_complete_data.json")
        print(f"Total processed records: {len(data_processor.get_data())}")
        
    except NoSuchWindowException:
        print("Browser window was closed. Restarting session.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Clean up
        wos_scraper.close()


if __name__ == "__main__":
    main()
