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
    """Gerencia o ciclo de vida da aplicação com contexto tipado"""

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
    description="Consulta um produto pelo nome e retorna suas informações como uma string formatada"
)
def query_product(nome: str) -> str:
    """
    Consulta um produto pelo nome e retorna suas informações como uma string formatada.

    Esta função recupera ou cria uma entrada de produto no banco de dados com um código de barras fixo e valores padrão.
    Ela utiliza a sessão atual do contexto da requisição para interagir com o banco de dados.
    A string retornada contém o nome, categoria, preço, data de validade, fabricante e código de barras do produto.

    Args:
        nome (str): O nome do produto a ser consultado.

    Returns:
        str: Uma string formatada contendo as informações do produto.
    """

    ctx: AppContext = mcp.get_context().request_context.lifespan_context  # type: ignore
    product, _ = get_or_create(
        session=ctx.session,
        model=Product,
        bar_code="1234567890123",
        defaults={
            "name": "Coca-Cola",
            "category": "Refrigerante",
            "price": 7.0,
            "expiry_date": datetime(2025, 12, 31),
            "manufacturer": "Example Corp",
        },
    )
    return f"""Informações do produto:
        name: {product.name}
        category: {product.category}
        price: {product.price}
        expiry_date: {product.expiry_date}
        manufacturer: {product.manufacturer}
        bar_code: {product.bar_code}"""


if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
