"""
Google Scholar Data Scraping Module

This module provides functionality to scrape Google Scholar for author profiles,
publications, and integrate with CrossRef DOI and SJR metrics.

Author: Data Integration Team
Date: 2025
"""

import os
import time
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup


class GoogleScholarScraper:
    """
    A class to scrape Google Scholar for author information and publications.
    """
    
    def __init__(self):
        """Initialize the scraper with a Chrome WebDriver."""
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Set up the Chrome WebDriver."""
        try:
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            print("Chrome WebDriver initialized successfully.")
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            raise
    
    def get_author_profile(self, name):
        """
        Retrieve author profile information from Google Scholar.
        
        Args:
            name (str): The author's name to search for
            
        Returns:
            tuple: (author_df, citation_df, co_authors_df) - DataFrames containing author info
        """
        search_url = f"https://scholar.google.com/scholar?q={name.replace(' ', '+')}"
        self.driver.get(search_url)
        time.sleep(2)

        try:
            # Click on the first profile link
            profile_link = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h4.gs_rt2 a'))
            )
            profile_link.click()
            time.sleep(20)

            # Basic author information
            author_data = {
                'Name': WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'gsc_prf_in'))
                ).text,
                'Affiliation': self.driver.find_element(By.CLASS_NAME, 'gsc_prf_il').text,
                'Research Interests': ", ".join([
                    interest.text for interest in 
                    self.driver.find_elements(By.CSS_SELECTOR, 'a.gsc_prf_inta')
                ])
            }
            author_df = pd.DataFrame([author_data])

            # Citation indices
            citation_data = []
            for row in self.driver.find_elements(By.CSS_SELECTOR, '#gsc_rsb_st tbody tr'):
                label = row.find_element(By.CSS_SELECTOR, 'td.gsc_rsb_sc1').text
                all_time = row.find_elements(By.CSS_SELECTOR, 'td.gsc_rsb_std')[0].text
                since_2019 = row.find_elements(By.CSS_SELECTOR, 'td.gsc_rsb_std')[1].text
                citation_data.append([label, all_time, since_2019])
            
            citation_df = pd.DataFrame(citation_data, columns=["Metric", "All Time", "Since 2019"])

            # Co-authors
            co_authors_data = []
            for co_author in self.driver.find_elements(By.CSS_SELECTOR, 'ul.gsc_rsb_a li'):
                name = co_author.find_element(By.CSS_SELECTOR, 'a').text
                affiliation = co_author.find_element(By.CLASS_NAME, 'gsc_rsb_a_ext').text
                co_authors_data.append([name, affiliation])
            
            co_authors_df = pd.DataFrame(
                co_authors_data, 
                columns=["Name", "Affiliation"]
            ) if co_authors_data else pd.DataFrame(columns=["Name", "Affiliation"])

            return author_df, citation_df, co_authors_df

        except Exception as e:
            print(f"Error retrieving author profile: {e}")
            return (
                pd.DataFrame(), 
                pd.DataFrame(columns=["Metric", "All Time", "Since 2019"]), 
                pd.DataFrame(columns=["Name", "Affiliation"])
            )

    def get_detailed_author_publications(self):
        """
        Extract detailed publication information for the current author.
        
        Returns:
            pd.DataFrame: DataFrame containing publication details
        """
        publications = []
        
        try:
            # Get all publication rows from the main profile page
            document_rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.gsc_a_tr')
            
            for row in document_rows:
                # Retrieve basic information from the list view
                title = row.find_element(By.CSS_SELECTOR, 'a.gsc_a_at').text
                citation_count = row.find_element(By.CSS_SELECTOR, 'a.gsc_a_ac.gs_ibl').text or "0"
                year = row.find_element(By.CSS_SELECTOR, 'span.gsc_a_h').text
                
                # Click to open the publication details
                row.find_element(By.CSS_SELECTOR, 'a.gsc_a_at').click()
                time.sleep(2)
                
                # Retrieve additional details
                publication_details = {
                    'Title': title,
                    'Year': year,
                    'Citation Count': citation_count,
                    'DOI': self._get_doi_from_crossref(title)
                }
                
                # Extract detailed fields with error handling
                detail_fields = {
                    'Authors': '//div[text()="Auteurs"]/following-sibling::div',
                    'Source Title': '//div[text()="Revue"]/following-sibling::div',
                    'Volume': '//div[text()="Volume"]/following-sibling::div',
                    'Issue': '//div[text()="Numéro"]/following-sibling::div',
                    'Pages': '//div[text()="Pages"]/following-sibling::div',
                    'Publisher': '//div[text()="Éditeur"]/following-sibling::div',
                    'Summary': '//div[text()="Description"]/following-sibling::div'
                }
                
                for field, xpath in detail_fields.items():
                    try:
                        publication_details[field] = self.driver.find_element(By.XPATH, xpath).text
                    except NoSuchElementException:
                        publication_details[field] = f"{field} not found"

                # Set default values for unavailable fields
                publication_details['Keywords'] = "Not available on Google Scholar"
                publication_details['Document Type'] = "Not specified on Google Scholar"

                publications.append(publication_details)
                
                # Return to the main profile page
                self.driver.back()
                time.sleep(2)

            return pd.DataFrame(publications)

        except Exception as e:
            print(f"Error retrieving detailed publications: {e}")
            return pd.DataFrame()

    def _get_doi_from_crossref(self, title):
        """
        Get DOI from CrossRef API for a given title.
        
        Args:
            title (str): The publication title
            
        Returns:
            str: The DOI or "DOI not found"
        """
        url = "https://api.crossref.org/works"
        params = {"query.title": title, "rows": 1}
        
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                items = response.json().get("message", {}).get("items", [])
                if items:
                    return items[0].get("DOI", "DOI not found")
        except Exception as e:
            print(f"Error fetching DOI for '{title}': {e}")
        
        return "DOI not found"

    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            print("WebDriver closed successfully.")


class SJRMetricsScraper:
    """
    A class to scrape SJR (SCImago Journal Rank) metrics.
    """
    
    def __init__(self, driver):
        """
        Initialize with an existing WebDriver instance.
        
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver

    def get_sjr_metrics_by_name(self, journal_name):
        """
        Get SJR metrics for a journal by its name.
        
        Args:
            journal_name (str): The journal name to search for
            
        Returns:
            dict: Dictionary containing SJR metrics
        """
        result = {
            "Journal Name": journal_name,
            "Country": "Country not found",
            "Subject Area and Category": "Subject area not found",
            "Publisher": "Publisher not found",
            "H-Index": "H-index not found",
            "Publication Type": "Publication type not found",
            "ISSN": "ISSN not found",
            "Coverage": "Coverage not found",
            "Scope": "Scope not found",
            "SJR Score": "SJR Score not found",
            "Quartile": "Quartile not found"
        }

        try:
            # Navigate to SJR search page
            sjr_url = "https://www.scimagojr.com/journalsearch.php"
            self.driver.get(sjr_url)

            # Search for journal
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "searchinput"))
            )
            search_box.clear()
            search_box.send_keys(journal_name)
            search_box.send_keys(Keys.RETURN)

            time.sleep(3)
            
            # Click on first result
            try:
                journal_link = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.jrnlname"))
                )
                result["Journal Name"] = journal_link.text
                journal_link.click()
            except:
                return result

            # Parse journal page
            time.sleep(3)
            body_html = self.driver.find_element(By.TAG_NAME, "body").get_attribute("outerHTML")
            soup = BeautifulSoup(body_html, 'html.parser')

            # Extract metrics using helper methods
            self._extract_basic_info(soup, result)
            self._extract_sjr_scores(soup, result)
            self._extract_quartile(soup, result)

            return result

        except Exception as e:
            print(f"Error occurred with journal '{journal_name}': {e}")
            return result

    def _extract_basic_info(self, soup, result):
        """Extract basic journal information."""
        info_fields = {
            "Country": "Country",
            "Subject Area and Category": "Subject Area and Category",
            "Publisher": "Publisher",
            "H-Index": "H-Index",
            "Publication Type": "Publication type",
            "ISSN": "ISSN",
            "Coverage": "Coverage",
            "Scope": "Scope"
        }
        
        for key, header in info_fields.items():
            try:
                if key == "H-Index":
                    result[key] = soup.find("h2", string=header).find_next("p", class_="hindexnumber").get_text(strip=True)
                elif key == "Subject Area and Category":
                    result[key] = soup.find("h2", string=header).find_next("ul").get_text(separator=", ", strip=True)
                elif key == "Scope":
                    result[key] = soup.find("h2", string=header).find_next("div").get_text(strip=True)
                else:
                    result[key] = soup.find("h2", string=header).find_next("p").get_text(strip=True)
            except:
                pass  # Keep default "not found" value

    def _extract_sjr_scores(self, soup, result):
        """Extract SJR scores from tables."""
        try:
            tables = soup.find_all("table")
            for table in tables:
                if "SJR" in table.get_text() and "Year" in table.get_text():
                    rows = table.find_all("tr")[1:]
                    sjr_data = {}
                    for row in rows:
                        columns = row.find_all("td")
                        if len(columns) >= 2:
                            year = columns[0].get_text(strip=True)
                            sjr_score = columns[1].get_text(strip=True)
                            sjr_data[year] = sjr_score
                    
                    if sjr_data:
                        latest_year = max(sjr_data.keys())
                        result["SJR Score"] = f"{latest_year}: {sjr_data[latest_year]}"
                    break
        except:
            pass

    def _extract_quartile(self, soup, result):
        """Extract quartile information."""
        try:
            quartile_table = soup.find("table")
            for row in quartile_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 3 and cells[2].text.startswith("Q"):
                    result["Quartile"] = cells[2].text.strip()
                    break
        except:
            pass

    def get_sjr_metrics_from_publications(self, publications_df):
        """
        Get SJR metrics for all journals in a publications DataFrame.
        
        Args:
            publications_df (pd.DataFrame): DataFrame with publication data
            
        Returns:
            pd.DataFrame: Merged DataFrame with SJR metrics
        """
        unique_journals = publications_df['Source Title'].dropna().unique()
        sjr_metrics = []

        for journal in unique_journals:
            journal_metrics = self.get_sjr_metrics_by_name(journal)
            sjr_metrics.append(journal_metrics)

        sjr_metrics_df = pd.DataFrame(sjr_metrics)
        merged_df = publications_df.merge(
            sjr_metrics_df, 
            left_on='Source Title', 
            right_on='Journal Name', 
            how='left'
        )

        return merged_df


class DataProcessor:
    """
    A class to process and organize scraped data.
    """
    
    @staticmethod
    def create_final_dataframe(author_df, citation_df, co_authors_df, merged_df):
        """
        Create a final organized DataFrame with all author and publication data.
        
        Args:
            author_df (pd.DataFrame): Author information
            citation_df (pd.DataFrame): Citation metrics
            co_authors_df (pd.DataFrame): Co-author information
            merged_df (pd.DataFrame): Publications with SJR metrics
            
        Returns:
            pd.DataFrame: Final organized DataFrame
        """
        # Extract author information
        author_name = author_df['Name'].iloc[0] if 'Name' in author_df.columns else "Author Name"
        author_affiliation = author_df['Affiliation'].iloc[0] if 'Affiliation' in author_df.columns else "Affiliation"
        research_interests = author_df['Research Interests'].iloc[0] if 'Research Interests' in author_df.columns else "Research Interests"

        # Add basic author information to each row
        merged_df['Author Name'] = author_name
        merged_df['Affiliation'] = author_affiliation
        merged_df['Research Interests'] = research_interests

        # Add co-authors
        if not co_authors_df.empty:
            co_authors_combined = co_authors_df['Name'].str.cat(
                co_authors_df['Affiliation'], sep=" - "
            ).str.cat(sep=", ")
            merged_df['Co-Authors'] = co_authors_combined
        else:
            merged_df['Co-Authors'] = ""

        # Add citation metrics
        if not citation_df.empty:
            citation_metrics = citation_df.set_index('Metric').T
            for metric in citation_metrics.columns:
                merged_df[metric + ' All Time'] = citation_metrics.loc['All Time', metric]
                merged_df[metric + ' Since 2019'] = citation_metrics.loc['Since 2019', metric]

        # Organize columns
        columns_order = [
            'Author Name', 'Affiliation', 'Research Interests', 'Co-Authors',
            'Citations All Time', 'Citations Since 2019', 'indice h All Time', 
            'indice h Since 2019', 'indice i10 All Time', 'indice i10 Since 2019',
            'Title', 'Year', 'Citation Count', 'DOI', 'Authors', 'Source Title', 
            'Volume', 'Issue', 'Pages', 'Publisher_x', 'Summary', 'Keywords', 'Document Type',
            'Journal Name', 'Country', 'Subject Area and Category', 'Publisher_y', 
            'H-Index', 'Publication Type', 'ISSN', 'Coverage', 'Scope', 'SJR Score', 'Quartile'
        ]
        
        existing_columns = [col for col in columns_order if col in merged_df.columns]
        final_df = merged_df[existing_columns].copy()
        
        return final_df

    @staticmethod
    def save_to_csv(final_df, file_path="google_scholar_dataset.csv"):
        """
        Save DataFrame to CSV file, handling duplicates.
        
        Args:
            final_df (pd.DataFrame): DataFrame to save
            file_path (str): Path to save the CSV file
        """
        if os.path.isfile(file_path):
            existing_data = pd.read_csv(file_path)
            combined_data = pd.concat([existing_data, final_df], ignore_index=True)
            combined_data.drop_duplicates(
                subset=['Title', 'Author Name'], 
                keep='last', 
                inplace=True
            )
        else:
            combined_data = final_df

        combined_data.to_csv(file_path, index=False)
        print(f"Data successfully saved to {file_path}")


def main():
    """
    Main function to demonstrate the usage of the Google Scholar scraper.
    """
    # Initialize scraper
    gs_scraper = GoogleScholarScraper()
    sjr_scraper = SJRMetricsScraper(gs_scraper.driver)
    
    try:
        # List of authors to scrape
        author_names = ["imad hafidi", "ELHADFI YOUSSEF", "ENNAJI Fatimazohra"]
        
        for author in author_names:
            print(f"Processing author: {author}")
            
            # Get author profile
            author_df, citation_df, co_authors_df = gs_scraper.get_author_profile(author)
            
            # Get publications
            publications_df = gs_scraper.get_detailed_author_publications()
            
            # Get SJR metrics
            merged_df = sjr_scraper.get_sjr_metrics_from_publications(publications_df)
            
            # Create final DataFrame
            final_df = DataProcessor.create_final_dataframe(
                author_df, citation_df, co_authors_df, merged_df
            )
            
            # Save to CSV
            DataProcessor.save_to_csv(final_df, f"{author.replace(' ', '_')}_data.csv")
            
            print(f"Completed processing for {author}")
    
    finally:
        # Clean up
        gs_scraper.close()


if __name__ == "__main__":
    main()
