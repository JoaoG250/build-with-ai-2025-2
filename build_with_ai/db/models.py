from datetime import datetime

from sqlmodel import Field, SQLModel


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    category: str = Field(nullable=False)
    price: float = Field(nullable=False)
    bar_code: str = Field(nullable=False, unique=True)
    expiry_date: datetime = Field(nullable=False)
    manufacturer: str = Field(nullable=False)
