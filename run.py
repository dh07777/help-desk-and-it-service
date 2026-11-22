import os
from app import create_app
from app.extensions import db
from seed_data import seed

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Ensure database tables exist and seed if empty
        db.create_all()
        from app.models import User
        if not User.query.first():
            print("Database empty. Seeding initial data...")
            seed()

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('true', '1')
    print(f"\n========================================================")
    print(f"🚀 SupportDesk IT Help Desk System starting on http://localhost:{port}")
    print(f"========================================================\n")
    app.run(host='0.0.0.0', port=port, debug=debug)
