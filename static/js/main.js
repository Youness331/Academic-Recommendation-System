document.getElementById('recommendForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const data = {
        title: document.getElementById('title').value,
        abstract: document.getElementById('abstract').value,
        keywords: document.getElementById('keywords').value
    };

    try {
        const response = await fetch('https://your-api-endpoint.com/recommend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        const recommendations = await response.json();
        displayRecommendations(recommendations);
    } catch (error) {
        console.error('Error:', error);
        alert('Error getting recommendations');
    }
});

function displayRecommendations(recommendations) {
    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '<h2>Recommended Articles</h2>';
    
    recommendations.forEach(rec => {
        resultsDiv.innerHTML += `
            <div class="recommendation-item">
                <h4>${rec.title}</h4>
                <p>${rec.abstract.substring(0, 200)}...</p>
                <p class="similarity-score">Similarity: ${(rec.similarity_score * 100).toFixed(1)}%</p>
            </div>
        `;
    });
}
