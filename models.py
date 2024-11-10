from sqlalchemy import create_engine, Column, Integer, Date, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

from datetime import date

Base = declarative_base()
load_dotenv() 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///work_tracker.db")


class WorkDay(Base):
    __tablename__ = 'work_days'

    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True, nullable=False)
    worked = Column(Boolean, default=False)

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
