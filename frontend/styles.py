CSS_STYLES = '''
<style>
    body {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        background-color: #f8f9fa;
    }
    
    .container {
        max-width: 1200px;
    }
    
    .card {
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
        border: none;
    }
    
    .card:hover {
        transform: translateY(-5px);
    }
    
    .card-title {
        color: #2c3e50;
        font-weight: 600;
    }
    
    .btn-primary {
        background-color: #3498db;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
    }
    
    .btn-primary:hover {
        background-color: #2980b9;
    }
    
    .alert {
        border-radius: 5px;
        padding: 15px;
    }
    
    .form-control {
        border-radius: 5px;
        border: 1px solid #ddd;
        padding: 10px;
    }
    
    .form-control:focus {
        border-color: #3498db;
        box-shadow: 0 0 0 0.2rem rgba(52, 152, 219, 0.25);
    }
    
    .table {
        border-radius: 5px;
        overflow: hidden;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .table th {
        background-color: #3498db;
        color: white;
        border: none;
    }
    
    @media (max-width: 768px) {
        .container {
            padding: 10px;
        }
    }
</style>
'''

BOOTSTRAP_CSS = '''
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
'''

JS_SCRIPTS = '''
<script>
    function deleteBook(bookId) {
        if (confirm('Are you sure you want to delete this book?')) {
            fetch(`/api/books/${bookId}`, {
                method: 'DELETE'
            })
            .then(response => {
                if (response.ok) {
                    location.reload();
                } else {
                    alert('Error deleting book');
                }
            });
        }
    }
    
    function generateSummary(bookId) {
        fetch(`/api/summarize/${bookId}`, {
            method: 'POST'
        })
        .then(response => {
            if (response.ok) {
                alert('Summary generated successfully!');
                location.reload();
            } else {
                alert('Error generating summary');
            }
        });
    }
    
    function searchBooks() {
        const searchTerm = document.getElementById('searchInput').value;
        const filterBy = document.getElementById('filterSelect').value;
        const sortBy = document.getElementById('sortSelect').value;
        
        window.location.href = `/dashboard?search=${encodeURIComponent(searchTerm)}&filter=${filterBy}&sort=${sortBy}`;
    }
    
    function uploadFile() {
        const fileInput = document.getElementById('fileInput');
        const title = document.getElementById('title').value;
        const author = document.getElementById('author').value;
        
        if (!fileInput.files[0]) {
            alert('Please select a file');
            return;
        }
        
        if (!title) {
            alert('Please enter a title');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('title', title);
        formData.append('author', author);
        
        fetch('/api/books', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
            } else {
                alert('Book uploaded successfully!');
                window.location.href = '/dashboard';
            }
        })
        .catch(error => {
            alert('Upload failed: ' + error.message);
        });
    }
</script>
'''