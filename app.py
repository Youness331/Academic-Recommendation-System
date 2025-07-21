from flask import Flask, render_template, request, jsonify
import pandas as pd
import joblib
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.neighbors import NearestNeighbors
import numpy as np

app = Flask(__name__)

# Paths to required files
TOKENIZER_PATH = "tfidf.pkl"
KMEANS_PATH = "kmeans_model.pkl"
ARTICLES_PATH = "Articles_clustered.csv"

# Load articles dataset and models
print("Loading datasets and models...")
Articles = pd.read_csv(ARTICLES_PATH)
tfidf_vectorizer = joblib.load(TOKENIZER_PATH)
kmeans_model = joblib.load(KMEANS_PATH)

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('corpora/wordnet')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('wordnet')

print(f"Loaded {len(Articles)} articles with {Articles['cluster'].nunique()} clusters")

def clean_text(text):
    """
    Comprehensive text cleaning function for NLP preprocessing.
    """
    if not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters and numbers
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    
    # Tokenize
    tokens = word_tokenize(text)
    
    # Remove stopwords
    stop_words = set(stopwords.words('english')).union(set(stopwords.words('french')))
    tokens = [token for token in tokens if token not in stop_words and len(token) > 2]
    
    # Lemmatize
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(token) for token in tokens]
    
    # Join and clean extra whitespace
    return ' '.join(tokens).strip()

def get_journal_details(journal_name, articles_df):
    """
    Get comprehensive journal information including metrics and scope.
    """
    journal_articles = articles_df[articles_df['journal_name'].str.contains(
        journal_name, case=False, na=False
    )]
    
    if journal_articles.empty:
        return None
    
    # Get the most complete journal record
    journal_info = journal_articles.iloc[0]
    
    # Calculate additional metrics
    def safe_numeric_mean_local(series):
        try:
            numeric_series = pd.to_numeric(series, errors='coerce')
            return numeric_series.mean() if not numeric_series.isna().all() else 0
        except:
            return 0
    
    avg_citations = safe_numeric_mean_local(journal_articles['citations']) if 'citations' in journal_articles.columns else 0
    total_articles = len(journal_articles)
    
    return {
        'name': journal_info.get('journal_name', 'N/A'),
        'issn': journal_info.get('issn', 'N/A'),
        'h_index': journal_info.get('H-index', 'N/A'),
        'quartile': journal_info.get('quartile', 'N/A'),
        'sjr_score': journal_info.get('sjr', 'N/A'),
        'impact_factor': journal_info.get('impact_factor', 'N/A'),
        'publisher': journal_info.get('publisher', 'N/A'),
        'scope': journal_info.get('scope', 'N/A'),
        'avg_citations': round(float(avg_citations), 2) if avg_citations and str(avg_citations) != 'nan' else 'N/A',
        'total_articles': total_articles,
        'index_type': journal_info.get('index', 'N/A')
    }

def predict_comprehensive_recommendations(title, abstract, keywords, k=10):
    """
    Get comprehensive recommendations including detailed journal information.
    """
    # Combine and clean input text
    input_text = f"{title} {abstract} {keywords}"
    cleaned_text = clean_text(input_text)
    
    if not cleaned_text:
        return {'journals': [], 'articles': [], 'cluster_info': None}
    
    # Transform to TF-IDF vector
    text_vector = tfidf_vectorizer.transform([cleaned_text])
    
    # Predict cluster
    predicted_cluster = kmeans_model.predict(text_vector)[0]
    
    # Get articles from the predicted cluster
    cluster_articles = Articles[Articles['cluster'] == predicted_cluster].copy()
    
    if cluster_articles.empty:
        return {'journals': [], 'articles': [], 'cluster_info': None}
    
    # Transform cluster articles to TF-IDF vectors
    if 'combined' in cluster_articles.columns:
        article_vectors = tfidf_vectorizer.transform(cluster_articles['combined'])
        
        # Calculate similarities
        similarities = cosine_similarity(text_vector, article_vectors)[0]
        cluster_articles['similarity'] = similarities * 100
        
        # Sort by similarity
        sorted_articles = cluster_articles.sort_values('similarity', ascending=False)
        
        # Get top articles
        top_articles = sorted_articles.head(k)
        
        # Extract unique journals with their best similarity scores
        journal_recommendations = []
        seen_journals = set()
        
        for _, article in top_articles.iterrows():
            journal_name = article.get('journal_name', '')
            if journal_name and journal_name not in seen_journals:
                journal_details = get_journal_details(journal_name, Articles)
                if journal_details:
                    journal_details['similarity'] = round(article['similarity'], 2)
                    journal_details['recommended_based_on'] = article.get('title', 'Unknown Article')[:100]
                    journal_recommendations.append(journal_details)
                    seen_journals.add(journal_name)
        
        # Prepare article recommendations
        def safe_citation_convert(val):
            try:
                return int(pd.to_numeric(val, errors='coerce')) if pd.notna(pd.to_numeric(val, errors='coerce')) else 0
            except:
                return 0
                
        article_recommendations = []
        for _, article in top_articles.iterrows():
            article_info = {
                'title': article.get('title', 'N/A'),
                'authors': article.get('authors', 'N/A'),
                'journal': article.get('journal_name', 'N/A'),
                'year': article.get('pub year', 'N/A'),
                'citations': safe_citation_convert(article.get('citations', 0)),
                'doi': article.get('DOI', 'N/A'),
                'similarity': round(article['similarity'], 2),
                'abstract': article.get('abstract', 'N/A')[:200] + '...' if article.get('abstract') else 'N/A'
            }
            article_recommendations.append(article_info)
        
        # Cluster information
        cluster_info = {
            'cluster_id': int(predicted_cluster),
            'total_articles': len(cluster_articles),
            'top_similarity': round(max(similarities) * 100, 2),
            'avg_similarity': round(np.mean(similarities) * 100, 2)
        }
        
        return {
            'journals': journal_recommendations[:5],  # Top 5 journals
            'articles': article_recommendations[:k],
            'cluster_info': cluster_info
        }
    
    return {'journals': [], 'articles': [], 'cluster_info': None}

@app.route('/')
def index():
    """Home page with enhanced form."""
    cluster_stats = {
        'total_articles': len(Articles),
        'total_clusters': Articles['cluster'].nunique(),
        'total_journals': Articles['journal_name'].nunique() if 'journal_name' in Articles.columns else 0
    }
    return render_template('index.html', stats=cluster_stats)

@app.route('/suggest', methods=['POST'])
def suggest():
    """Get comprehensive recommendations."""
    # Get user inputs
    title = request.form.get('title', '').strip()
    abstract = request.form.get('abstract', '').strip()
    keywords = request.form.get('keywords', '').strip()
    
    # Validate inputs
    if not any([title, abstract, keywords]):
        return render_template('results.html', 
                             error="Please provide at least a title, abstract, or keywords.",
                             journals=[], articles=[], cluster_info=None)
    
    try:
        # Get comprehensive recommendations
        recommendations = predict_comprehensive_recommendations(title, abstract, keywords, k=10)
        
        return render_template(
            'results.html',
            journals=recommendations['journals'],
            articles=recommendations['articles'],
            cluster_info=recommendations['cluster_info'],
            user_input={'title': title, 'abstract': abstract, 'keywords': keywords}
        )
    except Exception as e:
        return render_template('results.html', 
                             error=f"An error occurred: {str(e)}",
                             journals=[], articles=[], cluster_info=None)

@app.route('/api/journal/<journal_name>')
def get_journal_api(journal_name):
    """API endpoint to get detailed journal information."""
    journal_details = get_journal_details(journal_name, Articles)
    if journal_details:
        return jsonify(journal_details)
    else:
        return jsonify({'error': 'Journal not found'}), 404

@app.route('/stats')
def stats():
    """Statistics page."""
    cluster_distribution = Articles['cluster'].value_counts().sort_index().to_dict()
    
    # Safely convert citations to numeric, handling errors
    def safe_numeric_mean(series):
        try:
            numeric_series = pd.to_numeric(series, errors='coerce')
            return numeric_series.mean() if not numeric_series.isna().all() else 0
        except:
            return 0
    
    def safe_numeric_max(series):
        try:
            numeric_series = pd.to_numeric(series, errors='coerce')
            return numeric_series.max() if not numeric_series.isna().all() else 0
        except:
            return 0
    
    def safe_numeric_sum(series):
        try:
            numeric_series = pd.to_numeric(series, errors='coerce')
            return numeric_series.sum() if not numeric_series.isna().all() else 0
        except:
            return 0
    
    stats_data = {
        'total_articles': len(Articles),
        'total_clusters': Articles['cluster'].nunique(),
        'total_journals': Articles['journal_name'].nunique() if 'journal_name' in Articles.columns else 0,
        'cluster_distribution': cluster_distribution,
        'top_journals': Articles['journal_name'].value_counts().head(10).to_dict() if 'journal_name' in Articles.columns else {},
        'citation_stats': {
            'avg_citations': safe_numeric_mean(Articles['citations']) if 'citations' in Articles.columns else 0,
            'max_citations': safe_numeric_max(Articles['citations']) if 'citations' in Articles.columns else 0,
            'total_citations': safe_numeric_sum(Articles['citations']) if 'citations' in Articles.columns else 0
        }
    }
    
    return render_template('stats.html', stats=stats_data)

if __name__ == "__main__":
    app.run(debug=True)
