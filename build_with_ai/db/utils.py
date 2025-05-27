from typing import Any, Type, TypeVar

from sqlmodel import Session, SQLModel, select

T = TypeVar("T", bound=SQLModel)


def get_or_create(
    session: Session,
    model: Type[T],
    defaults: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[T, bool]:
    instance = session.exec(select(model).filter_by(**kwargs)).first()
    if instance:
        return instance, False
    params = {**kwargs, **(defaults or {})}
    instance = model(**params)
    session.add(instance)
    session.commit()
    session.refresh(instance)
    return instance, True
