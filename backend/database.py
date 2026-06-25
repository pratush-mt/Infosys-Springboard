from models.models import db

def init_db(app):
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        from models.models import User
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()