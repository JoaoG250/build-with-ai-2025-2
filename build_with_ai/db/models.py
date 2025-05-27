from datetime import datetime

from sqlalchemy import Column
from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(nullable=False))
    category: str = Field(sa_column=Column(nullable=False))
    price: float = Field(sa_column=Column(nullable=False))
    bar_code: str = Field(sa_column=Column(nullable=False, unique=True))
    expiry_date: datetime = Field(sa_column=Column(nullable=False))
    manufacturer: str = Field(sa_column=Column(nullable=False))
