import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session

from build_with_ai.db.models import Product
from build_with_ai.db.session import get_session, init_db
from build_with_ai.db.utils import get_or_create


@dataclass
class AppContext:
    session: Session


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    session = get_session()
    try:
        yield AppContext(session=session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


mcp = FastMCP("build-with-ai", lifespan=app_lifespan)


@mcp.tool(
    description="Queries a product by name and returns its information as a formatted string"
)
def query_product(name: str) -> str:
    """
    Queries a product by name and returns its information as a formatted string.

    This function retrieves or creates a product entry in the database with a fixed bar code and default values.
    It uses the current session from the request context to interact with the database.
    The returned string contains the product's name, category, price, expiry date, manufacturer, and bar code.

    Args:
        name (str): The name of the product to query.

    Returns:
        str: A formatted string containing the product's information.
    """
    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    product, created = get_or_create(
        session=ctx.session,
        model=Product,
        bar_code="1234567890123",
        defaults={
            "name": "Coca-Cola",
            "category": "Soft Drink",
            "price": 1.5,
            "expiry_date": datetime(2025, 12, 31),
            "manufacturer": "Example Corp",
        },
    )
    return f"""Product information:
        name: {product.name}
        category: {product.category}
        price: {product.price}
        expiry_date: {product.expiry_date}
        manufacturer: {product.manufacturer}
        bar_code: {product.bar_code}"""


if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
