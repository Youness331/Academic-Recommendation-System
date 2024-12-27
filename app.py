from flask import Flask, render_template, request
import pickle
import pandas as pd

app = Flask(__name__)

# Load pretrained KNN model and vectorizer
with open("knn_model.pkl", "rb") as model_file:
    knn_model = pickle.load(model_file)

with open("vectorizer.pkl", "rb") as vectorizer_file:
    vectorizer = pickle.load(vectorizer_file)

# Load your dataset (replace 'dataset.csv' with your file)
dataset = pd.read_csv("journal_info.csv")  # Assuming your dataset includes a "Journal" column
journal_names = dataset["title"].tolist()  # Extract journal names

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/suggest', methods=['POST'])
def suggest():
    # Get user input
    title = request.form.get('title')
    abstract = request.form.get('abstract')
    keywords = request.form.get('keywords')

    # Combine inputs into a single text input
    user_input = f"{title} {abstract} {keywords}"

    # Transform input using the vectorizer
    user_vector = vectorizer.transform([user_input])

    # Get top 5 nearest journals
    distances, indices = knn_model.kneighbors(user_vector, n_neighbors=5)
    recommended_journals = [journal_names[i] for i in indices[0]]  # Map indices to journal names

    return render_template('index.html', suggestion=recommended_journals)

if __name__ == '__main__':
    app.run(debug=True)
