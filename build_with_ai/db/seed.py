import logging

from pydantic import TypeAdapter
from sqlmodel import Session, select

from build_with_ai.db.models import Product, ProductRead
from build_with_ai.db.session import init_db, session_scope


def seed_products(session: Session):
    """Popula o banco de dados com produtos de exemplo."""
    with open("build_with_ai/db/products.json", "r") as file:
        product_read_list = TypeAdapter(list[ProductRead]).validate_json(file.read())
        for product_read in product_read_list:
            product_db = session.exec(
                select(Product).where(Product.bar_code == product_read.bar_code)
            ).first()
            if not product_db:
                session.add(Product(**product_read.model_dump()))
                session.commit()
    logging.debug("Banco de dados populado com produtos de exemplo.")


if __name__ == "__main__":
    init_db()
    with session_scope() as session:
        seed_products(session)
