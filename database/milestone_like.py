from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from database.database import Base

class MilestoneLike(Base):
	__tablename__ = "milestone_likes"
	message_id = Column(Integer, primary_key=True)
	user_id = Column(Integer, primary_key=True)
	__table_args__ = (UniqueConstraint("message_id","user_id", name="ux_like"),)