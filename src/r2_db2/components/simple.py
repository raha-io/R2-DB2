"""Simple UI components for basic text, image, and link rendering."""

from typing import Optional

from pydantic import Field

from r2-db2.core.simple_component import SimpleComponent, SimpleComponentType


class SimpleTextComponent(SimpleComponent):
    """A simple text component."""

    type: SimpleComponentType = SimpleComponentType.TEXT
    text: str = Field(..., description="The text content to display.")


class SimpleImageComponent(SimpleComponent):
    """A simple image component."""

    type: SimpleComponentType = SimpleComponentType.IMAGE
    url: str = Field(..., description="The URL of the image to display.")
    alt_text: Optional[str] = Field(
        default=None, description="Alternative text for the image."
    )


class SimpleLinkComponent(SimpleComponent):
    """A simple link component."""

    type: SimpleComponentType = SimpleComponentType.LINK
    url: str = Field(..., description="The URL the link points to.")
    text: Optional[str] = Field(
        default=None, description="The display text for the link."
    )
