"""
Models Package.

We import all models here so that:
1. We can import them as 'from app.models import User, Post'
2. SQLAlchemy knows about all models when we run init_db
"""
from app.db.base_class import Base
from .user import User
from .post import Post
