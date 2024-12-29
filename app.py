from flask import Flask, render_template, request
import pandas as pd
import joblib
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# Paths to required files
TOKENIZER_PATH = "tfidf.pkl"
KMEANS_PATH = "kmeans_model.pkl"
ARTICLES_PATH = "Articles_clustered.csv"

# Load articles dataset
Articles = pd.read_csv(ARTICLES_PATH)

def clean_text(text):
    """Simple text cleaner function."""
    return " ".join(text.lower().split())

def predict_kmeans(title, abstract, keywords, tokenizer_path, kmeans_path, Articles, k=5):
    # Load tokenizer (TF-IDF vectorizer) and KMeans model
    tfidf = joblib.load(tokenizer_path)
    kmeans = joblib.load(kmeans_path)

    # Combine input text
    input_text = title + ' ' + abstract + ' ' + keywords

    # Clean and transform the input text
    text = clean_text(input_text)
    text_vector = tfidf.transform([text])  # Transform into TF-IDF vector

    # Predict the cluster of the input text
    cluster = kmeans.predict(text_vector)

    # Filter articles based on the predicted cluster
    A = pd.DataFrame(Articles[Articles["cluster"] == cluster[0]])

    if 'combined' in A.columns:
        article_vectors = tfidf.transform(A['combined'])
        
        # Compute cosine similarity
        similarities = cosine_similarity(text_vector, article_vectors)[0]
        A['similarity'] = similarities * 100  # Convert similarity to percentage
        
        # Sort by similarity and return top `k` results
        return A.sort_values(by='similarity', ascending=False).head(k)

    return pd.DataFrame()  # Return empty if no cluster match

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/suggest', methods=['POST'])
def suggest():
    # Get user inputs
    title = request.form.get('title', '')
    abstract = request.form.get('abstract', '')
    keywords = request.form.get('keywords', '')

    # Predict the top journals and articles
    recommendations = predict_kmeans(title, abstract, keywords, TOKENIZER_PATH, KMEANS_PATH, Articles, k=5)

    if not recommendations.empty:
        # Split recommendations into journals and articles
        journals = recommendations[['journal_name', 'similarity']].drop_duplicates().to_dict(orient='records')
        articles = recommendations[['title', 'similarity']].drop_duplicates().to_dict(orient='records')
    else:
        journals = []
        articles = []

    return render_template(
        'results.html',
        journals=journals,
        articles=articles,
    )

if __name__ == "__main__":
    app.run(debug=True)
