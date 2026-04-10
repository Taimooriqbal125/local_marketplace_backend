import uuid
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, String, Boolean, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    # Avoid circular imports for type hints
    pass


class Category(Base, TimestampMixin):
    """
    Representation of a product or service category.
    Supports hierarchical structures (parent-child relationships).

    Attributes:
        id (uuid.UUID): Primary key.
        name (str): Display name of the category.
        slug (str): Unique URL-friendly identifier.
        sort_order (int): Ordering index for display.
        is_active (bool): Whether the category is visible.
        parent_id (uuid.UUID): ID of the parent category.
        created_at (datetime): Timestamp of creation (from TimestampMixin).
        updated_at (datetime): Timestamp of last update (from TimestampMixin).
    """

    __tablename__ = "categories"

    # Primary key using UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        doc="Unique identifier for the category."
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Display name of the category."
    )
    slug: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
        doc="URL-friendly identifier."
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        doc="Order in which categories are sorted."
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        doc="Toggle visibility of the category."
    )

    # Hierarchical link
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Link to the parent category ID if available."
    )

    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_categories_parent_id_name"),
    )

    # Relationships
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
        lazy="joined",
        doc="Reference to the parent category object."
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="all, delete-orphan",
        single_parent=True,
        passive_deletes=True,
        lazy="selectin",
        doc="List of sub-categories."
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name='{self.name}', slug='{self.slug}')>"