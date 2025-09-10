"""
Notion data types for workspace parsing.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class BlockType(Enum):
    """Notion block types."""
    PAGE = "page"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    PARAGRAPH = "paragraph"
    BULLETED_LIST_ITEM = "bulleted_list_item"
    NUMBERED_LIST_ITEM = "numbered_list_item"
    QUOTE = "quote"
    CODE = "code"
    DIVIDER = "divider"
    CALLOUT = "callout"
    TOGGLE = "toggle"
    CHILD_PAGE = "child_page"
    CHILD_DATABASE = "child_database"


@dataclass
class NotionUser:
    """Notion user information."""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


@dataclass
class NotionProperty:
    """Notion page property."""
    name: str
    type: str
    value: Any


@dataclass
class NotionBlock:
    """Notion block content."""
    id: str
    type: BlockType
    content: str
    children: List['NotionBlock']
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None
    has_children: bool = False
    archived: bool = False
    
    def __post_init__(self):
        if isinstance(self.type, str):
            try:
                self.type = BlockType(self.type)
            except ValueError:
                # Handle unknown block types
                self.type = BlockType.PARAGRAPH


@dataclass
class NotionPage:
    """Notion page with content and metadata."""
    id: str
    title: str
    url: Optional[str]
    blocks: List[NotionBlock]
    properties: Dict[str, NotionProperty]
    parent_id: Optional[str] = None
    database_id: Optional[str] = None
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None
    created_by: Optional[NotionUser] = None
    last_edited_by: Optional[NotionUser] = None
    archived: bool = False
    icon: Optional[str] = None
    cover: Optional[str] = None


@dataclass
class NotionDatabase:
    """Notion database with pages."""
    id: str
    title: str
    description: Optional[str]
    pages: List[NotionPage]
    properties: Dict[str, Dict[str, Any]]
    parent_id: Optional[str] = None
    created_time: Optional[datetime] = None
    last_edited_time: Optional[datetime] = None
    archived: bool = False
    icon: Optional[str] = None
    cover: Optional[str] = None


@dataclass
class NotionWorkspace:
    """Complete Notion workspace export."""
    pages: List[NotionPage]
    databases: List[NotionDatabase]
    user: Optional[NotionUser] = None
    export_date: Optional[datetime] = None
    
    def get_all_pages(self) -> List[NotionPage]:
        """Get all pages including those in databases."""
        all_pages = list(self.pages)
        for database in self.databases:
            all_pages.extend(database.pages)
        return all_pages


@dataclass
class ParsedNotionData:
    """Parsed Notion workspace data."""
    workspace: NotionWorkspace
    total_pages: int
    total_databases: int
    topics: Dict[str, List[NotionPage]]