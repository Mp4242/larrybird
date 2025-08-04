from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from database.database import Base

class PostLike(Base):
    __tablename__ = "post_likes"

    id       = Column(Integer, primary_key=True)
    post_id  = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id  = Column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("post_id", "user_id"),)  # 1 like / user
