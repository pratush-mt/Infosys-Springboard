def create_navbar(current_user):
    nav_items = []
    
    if current_user.is_authenticated:
        nav_items.append(f'<li class="nav-item"><span class="nav-link text-light">Welcome, {current_user.username}!</span></li>')
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/dashboard">Dashboard</a></li>')
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/upload">Upload Book</a></li>')
        if current_user.is_admin():
            nav_items.append('<li class="nav-item"><a class="nav-link" href="/admin">Admin</a></li>')
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/logout">Logout</a></li>')
    else:
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/login">Login</a></li>')
        nav_items.append('<li class="nav-item"><a class="nav-link" href="/register">Register</a></li>')
    
    return f'''
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">Book Summarizer</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    {''.join(nav_items)}
                </ul>
            </div>
        </div>
    </nav>
    '''

def create_book_card(book):
    has_summary = len(book.summaries) > 0
    summary_badge = '<span class="badge bg-success">Summarized</span>' if has_summary else '<span class="badge bg-secondary">Not Summarized</span>'
    
    return f'''
    <div class="col-md-4 mb-4">
        <div class="card h-100">
            <div class="card-body">
                <h5 class="card-title">{book.title}</h5>
                <h6 class="card-subtitle mb-2 text-muted">{book.author or "Unknown Author"}</h6>
                <p class="card-text">
                    <small class="text-muted">
                        Uploaded: {book.upload_date.strftime("%Y-%m-%d")}<br>
                        Words: {book.word_count or "N/A"}<br>
                        Language: {book.language or "Unknown"}
                    </small>
                </p>
                {summary_badge}
            </div>
            <div class="card-footer">
                <a href="/book/{book.id}" class="btn btn-sm btn-primary">View</a>
                {f'<a href="/summary/{book.summaries[0].id}" class="btn btn-sm btn-success ms-1">View Summary</a>' if has_summary else f'<a href="/summarize/{book.id}" class="btn btn-sm btn-warning ms-1">Generate Summary</a>'}
                <button onclick="deleteBook({book.id})" class="btn btn-sm btn-danger ms-1">Delete</button>
            </div>
        </div>
    </div>
    '''

def create_pagination(page, pages, search_term='', filter_by='all', sort_by='newest'):
    pagination_items = []
    
    if page > 1:
        pagination_items.append(f'''
        <li class="page-item">
            <a class="page-link" href="/dashboard?page={page-1}&search={search_term}&filter={filter_by}&sort={sort_by}">Previous</a>
        </li>
        ''')
    
    start_page = max(1, page - 2)
    end_page = min(pages, page + 2)
    
    for p in range(start_page, end_page + 1):
        active = 'active' if p == page else ''
        pagination_items.append(f'''
        <li class="page-item {active}">
            <a class="page-link" href="/dashboard?page={p}&search={search_term}&filter={filter_by}&sort={sort_by}">{p}</a>
        </li>
        ''')
    
    if page < pages:
        pagination_items.append(f'''
        <li class="page-item">
            <a class="page-link" href="/dashboard?page={page+1}&search={search_term}&filter={filter_by}&sort={sort_by}">Next</a>
        </li>
        ''')
    
    return f'''
    <nav aria-label="Page navigation">
        <ul class="pagination justify-content-center">
            {''.join(pagination_items)}
        </ul>
    </nav>
    '''