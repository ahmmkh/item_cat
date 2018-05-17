
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
import sys
Base = declarative_base()


class User(Base):
    __tablename__ ='user'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(90), nullable=False)
    email = Column(String(90), nullable=False)
  #  u_picture = Column(String(200))


class Categories(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(45), nullable=False)
    u_id = Column(Integer,ForeignKey('user.id'))
    user = relationship(User)
    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'name': self.name
        }


class Items(Base):
    __tablename__ = 'items'
    id = Column(Integer, primary_key=True, nullable=False)
    name = Column(String(45), nullable=False)
    description = Column(String(300), nullable=False)
    c_id = Column(Integer, ForeignKey('categories.id'))
    categories = relationship(Categories)
    u_id = Column(Integer,ForeignKey('user.id'))
    user = relationship(User)
    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category_id': self.c_id
        }


engine = create_engine('sqlite:///itemcat.db')
Base.metadata.create_all(engine)
