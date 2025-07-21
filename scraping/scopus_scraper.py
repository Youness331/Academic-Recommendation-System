


import json
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager


class ScopusScraper:
    
    def __init__(self, driver_path: Optional[str] = None):
        self.driver = None
        self.wait = None
        self._setup_driver(driver_path)
    
    def _setup_driver(self, driver_path: Optional[str] = None):
        try:
            if driver_path:
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service)
            else:
                self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
            
            self.wait = WebDriverWait(self.driver, 30)
            print("Chrome WebDriver initialized successfully for Scopus scraping.")
        except Exception as e:
            print(f"Error initializing WebDriver: {e}")
            raise
    
    def extract_author_metrics(self, author_id: str) -> Dict[str, Any]:
        # Navigate to author's metrics page
        url = f"https://www.scopus.com/authid/detail.uri?authorId={author_id}#tab=metrics"
        self.driver.get(url)
        
        # Initialize author data dictionary
        author_data = {
            "Author_ID": author_id,
            "Nom_Complet": "N/A",
            "Affiliation": "N/A",
            "Citations": 0,
            "Documents": 0,
            "h-index": 0,
            "FWCI": 0.0
        }
        
        try:
            # Extract author's full name - try multiple selectors
            name_selectors = [
                "Typography-module__lVnit.Typography-module__oFCaL",
                "author-name",
                "Typography-module__oFCaL"
            ]
            
            author_name_element = None
            for selector in name_selectors:
                try:
                    author_name_element = self.wait.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, f".{selector.replace('.', '.')}"))
                    )
                    break
                except:
                    continue
            
            if author_name_element:
                author_data["Nom_Complet"] = author_name_element.text
            
        except Exception as e:
            print(f"Author name unavailable: {e}")
        
        try:
            # Extract affiliation information
            affiliation_container = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".AuthorHeader-module__DRxsE"))
            )
            affiliation_elements = affiliation_container.find_elements(
                By.CSS_SELECTOR, ".Typography-module__lVnit.Typography-module__Nfgvc"
            )
            if affiliation_elements:
                raw_affiliation = affiliation_elements[-1].text
                author_data["Affiliation"] = raw_affiliation.lstrip(', ').replace(', ', ' - ')
                
        except Exception as e:
            print(f"Affiliation unavailable: {e}")
        
        try:
            # Extract metrics (Citations, Documents, h-index)
            metrics_section = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".MetricSection-module__s8lWB"))
            )
            metrics_text = metrics_section.text.lower()
            
            # Extract Citations
            if "citations" in metrics_text:
                citations_section = metrics_text.split("citations")[0]
                citation_numbers = re.findall(r'\d+', citations_section.replace(',', ''))
                if citation_numbers:
                    author_data["Citations"] = int(citation_numbers[-1])
            
            # Extract Documents
            if "documents" in metrics_text:
                documents_section = metrics_text.split("documents")[1]
                document_numbers = re.findall(r'\d+', documents_section.replace(',', ''))
                if document_numbers:
                    author_data["Documents"] = int(document_numbers[-1])
            
            # Extract h-index
            if "h-index" in metrics_text:
                h_index_section = metrics_text.split("h-index")[0]
                h_index_numbers = re.findall(r'\d+', h_index_section.replace(',', ''))
                if h_index_numbers:
                    author_data["h-index"] = int(h_index_numbers[-1])
                    
        except Exception as e:
            print(f"Error extracting metrics: {e}")
        
        try:
            # Extract FWCI (Field-Weighted Citation Impact)
            fwci_element = self.wait.until(
                EC.visibility_of_element_located((By.ID, 'metrics-panel'))
            )
            fwci_text = fwci_element.text.lower()
            
            if "field-weighted citation impact" in fwci_text:
                fwci_match = re.search(r'field-weighted citation impact[\s\S]*?(\d+\.?\d*)', fwci_text)
                if fwci_match:
                    author_data["FWCI"] = float(fwci_match.group(1))
                    
        except Exception as e:
            print(f"FWCI unavailable or extraction error: {e}")
        
        return author_data
    
    def get_co_authors(self, author_id: str, num_co_authors: int = 5) -> Dict[str, List[str]]:
        
        url = f"https://www.scopus.com/search/submit/coAuthorSearch.uri?authorId={author_id}&origin=AuthorProfile&sot=al&sdt=coaut&zone=coAuthorsTab"
        self.driver.get(url)
        
        co_author_ids = []
        
        try:
            # Wait for co-author table to load
            rows = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "tr.searchArea"))
            )
            
            # Extract co-author IDs from checkbox values
            for row in rows[:num_co_authors]:
                try:
                    input_element = row.find_element(
                        By.CSS_SELECTOR, "input[type='checkbox'][id^='auid_']"
                    )
                    co_author_id = input_element.get_attribute("value")
                    if co_author_id:
                        co_author_ids.append(co_author_id)
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            print(f"Error extracting co-author IDs: {e}")
        
        return {author_id: co_author_ids}
    
    def get_author_document_links(self, author_id: str) -> List[str]:
        url = f"https://www.scopus.com/authid/detail.uri?authorId={author_id}"
        self.driver.get(url)
        
        # Scroll to load all content
        self._scroll_to_load_content()
        
        document_links = []
        
        try:
            # Wait for results to load
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'li[data-testid="results-list-item"]')
                )
            )
            
            # Find all document list items
            li_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 'li[data-testid="results-list-item"]'
            )
            
            print(f"Number of documents found: {len(li_elements)}")
            
            # Extract links from each list item
            for li in li_elements:
                try:
                    link_element = li.find_element(
                        By.CSS_SELECTOR, 'a[href^="/record/display.uri"]'
                    )
                    href = link_element.get_attribute('href')
                    if href:
                        document_links.append(href)
                except NoSuchElementException:
                    continue
                    
        except Exception as e:
            print(f"Error fetching document links: {e}")
        
        return document_links
    
    def _scroll_to_load_content(self):
        last_position = self.driver.execute_script("return window.pageYOffset;")
        
        while True:
            # Scroll down by 800 pixels
            self.driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)  # Allow content to load
            
            # Check if we've reached the bottom
            new_position = self.driver.execute_script("return window.pageYOffset;")
            if new_position == last_position:
                break
            last_position = new_position
    
    def close(self):
        if self.driver:
            self.driver.quit()
            print("Scopus scraper WebDriver closed successfully.")


class ScopusDocumentScraper:
    
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 60)
    
    def get_document_info(self, document_link: str) -> Dict[str, Any]:
        self.driver.get(document_link)
        
        # Initialize document data
        doc_data = {
            "title": "N/A",
            "pub_year": "N/A",
            "citations": 0,
            "publisher": "N/A",
            "issn": "N/A",
            "doi": "N/A",
            "document_type": "N/A",
            "source_type": "N/A",
            "abstract": "N/A",
            "authors": [],
            "journal_info": {}
        }
        
        try:
            # Extract document title
            title_selectors = [
                ".Typography-module__lVnit.Typography-module__o9yMJ.Typography-module__JqXS9.Typography-module__ETlt8",
                "[data-testid='document-title']",
                ".document-title",
                "h1"
            ]
            
            title_element = None
            for selector in title_selectors:
                try:
                    title_element = self.wait.until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if title_element:
                doc_data["title"] = title_element.text.strip()
            
        except Exception as e:
            print(f"Error extracting title: {e}")
        
        try:
            # Extract publication year
            year_element = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), '20')]"))
            )
            year_text = year_element.text
            year_match = re.search(r'20\d{2}', year_text)
            if year_match:
                doc_data["pub_year"] = year_match.group()
                
        except Exception as e:
            print(f"Error extracting publication year: {e}")
        
        try:
            # Extract citation count
            citation_element = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, "//span[contains(text(), 'Citations')]"))
            )
            citation_numbers = re.findall(r'\d+', citation_element.text)
            if citation_numbers:
                doc_data["citations"] = int(citation_numbers[0])
                
        except Exception as e:
            print(f"Error extracting citations: {e}")
        
        # Extract detailed document metadata
        self._extract_document_metadata(doc_data)
        
        # Extract abstract
        self._extract_abstract(doc_data)
        
        # Extract authors
        self._extract_authors(doc_data)
        
        # Extract journal information
        if doc_data["issn"] != "N/A":
            doc_data["journal_info"] = self._extract_journal_info(doc_data["issn"])
        
        return doc_data
    
    def _extract_document_metadata(self, doc_data: Dict[str, Any]):
        try:
            # Find the metadata container
            elements = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".Box-module__DQ5q3"))
            )
            
            if len(elements) > 2:
                target_div = elements[2]
                
                # Extract Document Type
                doc_type_elements = target_div.find_elements(
                    By.XPATH, ".//dl[@data-testid='source-info-entry-document-type']/dd"
                )
                if doc_type_elements:
                    doc_data["document_type"] = doc_type_elements[0].text.strip()
                
                # Extract Source Type
                source_type_elements = target_div.find_elements(
                    By.XPATH, ".//dl[@data-testid='source-info-entry-source-type']/dd"
                )
                if source_type_elements:
                    doc_data["source_type"] = source_type_elements[0].text.strip()
                
                # Extract ISSN
                issn_elements = target_div.find_elements(
                    By.XPATH, ".//dl[@data-testid='source-info-entry-issn']/dd"
                )
                if issn_elements:
                    doc_data["issn"] = issn_elements[0].text.strip()
                
                # Extract DOI
                doi_elements = target_div.find_elements(
                    By.XPATH, ".//dl[@data-testid='source-info-entry-doi']/dd"
                )
                if doi_elements:
                    doc_data["doi"] = doi_elements[0].text.strip()
                
                # Extract Publisher
                publisher_elements = target_div.find_elements(
                    By.XPATH, ".//dl[@data-testid='source-info-entry-publisher']/dd"
                )
                if publisher_elements:
                    doc_data["publisher"] = publisher_elements[0].text.strip()
                    
        except Exception as e:
            print(f"Error extracting document metadata: {e}")
    
    def _extract_abstract(self, doc_data: Dict[str, Any]):
        try:
            # Try multiple possible selectors for abstract
            abstract_selectors = [
                ".Typography-module__lVnit.Typography-module__ETlt8.Typography-module__GK8Sg",
                "[data-testid='abstract']",
                ".abstract-content",
                ".abstract-text",
                ".document-abstract"
            ]
            
            abstract_element = None
            for selector in abstract_selectors:
                try:
                    abstract_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if abstract_element and abstract_element.text.strip():
                        break
                except:
                    continue
            
            if abstract_element and abstract_element.text.strip():
                doc_data["abstract"] = abstract_element.text.strip()
            else:
                print("Abstract not found with any selector")
            
        except Exception as e:
            print(f"Error extracting abstract: {e}")
    
    def _extract_authors(self, doc_data: Dict[str, Any]):
        try:
            authors_sections = self.driver.find_elements(
                By.CSS_SELECTOR, ".DocumentHeader-module__LpsWx"
            )
            
            if len(authors_sections) > 1:
                authors_section = authors_sections[1]
                author_elements = authors_section.find_elements(By.TAG_NAME, "li")
                
                authors = []
                for author in author_elements:
                    try:
                        author_name_span = author.find_element(By.TAG_NAME, "span")
                        if author_name_span:
                            author_name = author_name_span.text.strip()
                            if author_name:
                                authors.append(author_name)
                    except:
                        continue
                
                doc_data["authors"] = authors
            else:
                # Try alternative selectors for authors
                try:
                    author_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='author-list'] span")
                    authors = [elem.text.strip() for elem in author_elements if elem.text.strip()]
                    doc_data["authors"] = authors
                except:
                    pass
                
        except Exception as e:
            print(f"Error extracting authors: {e}")
    
    def _extract_journal_info(self, issn: str) -> Dict[str, Any]:
        journal_info = {
            "Nom de la revue": "N/A",
            "H-index": "N/A",
            "Editeur": "N/A",
            "issn": issn,
            "index": "Scopus",
            "portée thématique": "N/A",
            "Quartile": "N/A",
            "Score SJR": "N/A"
        }
        
        try:
            # Navigate to SJR search
            sjr_url = f"https://www.scimagojr.com/journalsearch.php?q={issn}"
            self.driver.get(sjr_url)
            
            # Find search results
            search_results = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".search_results"))
            )
            
            journal_links = search_results.find_elements(By.TAG_NAME, "a")
            
            for journal_link in journal_links:
                try:
                    journal_name_element = journal_link.find_element(By.CSS_SELECTOR, ".jrnlname")
                    journal_name = journal_name_element.text.strip()
                    journal_href = journal_link.get_attribute("href")
                    
                    journal_info['Nom de la revue'] = journal_name
                    
                    # Navigate to journal details page
                    self.driver.get(journal_href)
                    
                    # Extract journal metrics
                    self._extract_sjr_metrics(journal_info)
                    break
                    
                except Exception as e:
                    print(f"Error processing journal link: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error extracting journal information: {e}")
        
        return journal_info
    
    def _extract_sjr_metrics(self, journal_info: Dict[str, Any]):
        try:
            # Extract H-index
            h_index_element = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, ".hindexnumber"))
            )
            journal_info['H-index'] = h_index_element.text.strip()
            
        except Exception as e:
            print(f"Error extracting H-index: {e}")
        
        try:
            # Extract Publisher
            publisher_element = self.wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Publisher')]")
                )
            )
            publisher_link = publisher_element.find_element(
                By.XPATH, "./following-sibling::p/a"
            )
            journal_info['Editeur'] = publisher_link.text.strip()
            
        except Exception as e:
            print(f"Error extracting publisher: {e}")
        
        try:
            # Extract Scope
            scope_element = self.wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Scope')]")
                )
            )
            scope_text = scope_element.find_element(
                By.XPATH, "./following-sibling::p"
            )
            journal_info['portée thématique'] = scope_text.text.strip()
            
        except Exception as e:
            print(f"Error extracting scope: {e}")
        
        try:
            # Extract Quartile and SJR Score
            cellside_elements = self.wait.until(
                EC.visibility_of_all_elements_located((By.CSS_SELECTOR, ".cellside"))
            )
            
            if len(cellside_elements) > 1:
                # Quartile (second cellside element)
                quartile_element = cellside_elements[1]
                quartile_cells = quartile_element.find_elements(By.TAG_NAME, "td")
                if quartile_cells:
                    journal_info['Quartile'] = quartile_cells[-1].text.strip()
            
            if len(cellside_elements) > 3:
                # SJR Score (fourth cellside element)
                sjr_element = cellside_elements[3]
                sjr_cells = sjr_element.find_elements(By.TAG_NAME, "td")
                if sjr_cells:
                    journal_info['Score SJR'] = sjr_cells[-1].text.strip()
                    
        except Exception as e:
            print(f"Error extracting quartile/SJR: {e}")


class ScopusDataProcessor:
    
    def __init__(self):
        self.processed_authors = set()
        self.all_author_data = {}
    
    def get_comprehensive_author_data(self, author_id: str, scopus_scraper: ScopusScraper, 
                                    num_co_authors: int = 5) -> Dict[str, Any]:
        # Get main author metrics
        author_metrics = scopus_scraper.extract_author_metrics(author_id)
        
        # Get co-authors
        co_author_data = scopus_scraper.get_co_authors(author_id, num_co_authors)
        
        # Initialize comprehensive data structure
        comprehensive_data = {
            author_id: {
                "author_info": author_metrics,
                "co_authors": {}
            }
        }
        
        # Process each co-author
        for co_author_id in co_author_data[author_id]:
            try:
                # Get co-author metrics
                co_author_metrics = scopus_scraper.extract_author_metrics(co_author_id)
                
                # Initialize co-author structure
                comprehensive_data[author_id]["co_authors"][co_author_id] = {
                    "co_author_info": co_author_metrics,
                    "co_authors": {}
                }
                
                # Get co-authors of the co-author
                inner_co_authors = scopus_scraper.get_co_authors(co_author_id, num_co_authors)
                
                # Process inner co-authors
                for inner_co_author_id in inner_co_authors[co_author_id]:
                    try:
                        inner_metrics = scopus_scraper.extract_author_metrics(inner_co_author_id)
                        comprehensive_data[author_id]["co_authors"][co_author_id]["co_authors"][inner_co_author_id] = inner_metrics
                    except Exception as e:
                        print(f"Error processing inner co-author {inner_co_author_id}: {e}")
                        
            except Exception as e:
                print(f"Error processing co-author {co_author_id}: {e}")
        
        return comprehensive_data
    
    def process_author_documents(self, author_id: str, scopus_scraper: ScopusScraper, 
                               document_scraper: ScopusDocumentScraper, 
                               max_documents: int = 10) -> List[Dict[str, Any]]:
        # Get document links
        document_links = scopus_scraper.get_author_document_links(author_id)
        
        # Limit number of documents
        document_links = document_links[:max_documents]
        
        processed_documents = []
        
        for i, link in enumerate(document_links):
            try:
                print(f"Processing document {i+1}/{len(document_links)}")
                doc_info = document_scraper.get_document_info(link)
                processed_documents.append(doc_info)
                
                # Add delay to avoid overwhelming the server
                time.sleep(2)
                
            except Exception as e:
                print(f"Error processing document {link}: {e}")
                continue
        
        return processed_documents
    
    def save_data(self, data: Dict[str, Any], filename: str = "scopus_data.json"):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Data successfully saved to {filename}")
        except Exception as e:
            print(f"Error saving data: {e}")


def main():
    # Configuration
    AUTHOR_IDS = [
        "7006835644",  # Example author ID
        "7103251673"   # Another example author ID
    ]
    
    # Initialize scrapers
    scopus_scraper = ScopusScraper()
    document_scraper = ScopusDocumentScraper(scopus_scraper.driver)
    data_processor = ScopusDataProcessor()
    
    try:
        all_results = {}
        
        for author_id in AUTHOR_IDS:
            print(f"\nProcessing author: {author_id}")
            
            # Get comprehensive author data
            author_data = data_processor.get_comprehensive_author_data(
                author_id, scopus_scraper, num_co_authors=2
            )
            
            # Get author documents
            documents = data_processor.process_author_documents(
                author_id, scopus_scraper, document_scraper, max_documents=5
            )
            
            # Add documents to author data
            author_data[author_id]["documents"] = documents
            
            # Store in results
            all_results.update(author_data)
            
            print(f"Completed processing for author: {author_id}")
        
        # Save all results
        data_processor.save_data(all_results, "scopus_complete_data.json")
        
        # Print summary
        print(f"\nScraping completed!")
        print(f"Total authors processed: {len(AUTHOR_IDS)}")
        print(f"Data saved to: scopus_complete_data.json")
        
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
    finally:
        # Clean up
        scopus_scraper.close()


def simple_author_test(author_id: str):

    scraper = ScopusScraper()
    try:
        print(f"Testing author metrics extraction for ID: {author_id}")
        metrics = scraper.extract_author_metrics(author_id)
        print("Author metrics:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        scraper.close()


def simple_coauthors_test(author_id: str, num_coauthors: int = 3):
    scraper = ScopusScraper()
    try:
        print(f"Testing co-authors extraction for ID: {author_id}")
        coauthors = scraper.get_co_authors(author_id, num_coauthors)
        print("Co-authors:")
        for main_id, coauthor_ids in coauthors.items():
            print(f"  Author {main_id} has co-authors: {coauthor_ids}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        scraper.close()


if __name__ == "__main__":
    # You can run different tests by uncommenting the lines below:
    
    # Test basic author metrics
    # simple_author_test("7006835644")
    
    # Test co-authors extraction
    # simple_coauthors_test("7103251673", 3)
    
    # Run full scraping (comment out for testing)
    main()
