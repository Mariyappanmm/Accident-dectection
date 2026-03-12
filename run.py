from app import create_app, db

app = create_app()

# Initialize the database structure locally. 
# For production, consider using Flask-Migrate instead.
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run()
