"""
Nuclino data types for workspace parsing.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path


@dataclass
class NuclinoUser:
    """Nuclino user information."""
    name: Optional[str] = None
    email: Optional[str] = None


@dataclass
class NuclinoAttachment:
    """Nuclino attachment (image, file, etc.)."""
    filename: str
    original_path: str
    local_path: Optional[str] = None
    size: Optional[int] = None
    mime_type: Optional[str] = None


@dataclass
class NuclinoItem:
    """Nuclino item (page/document)."""
    id: str
    title: str
    content: str  # Markdown content
    path: Path  # File path in export
    parent_id: Optional[str] = None
    cluster_name: Optional[str] = None
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    author: Optional[NuclinoUser] = None
    attachments: List[NuclinoAttachment] = None
    internal_links: List[str] = None  # Links to other items
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []
        if self.internal_links is None:
            self.internal_links = []


@dataclass
class NuclinoCluster:
    """Nuclino cluster (collection of related items)."""
    name: str
    items: List[NuclinoItem]
    description: Optional[str] = None
    
    def __post_init__(self):
        if self.items is None:
            self.items = []


@dataclass
class NuclinoWorkspace:
    """Complete Nuclino workspace export."""
    name: str
    clusters: List[NuclinoCluster]
    items: List[NuclinoItem]  # All items (flat list)
    attachments: List[NuclinoAttachment]
    export_date: Optional[datetime] = None
    
    def __post_init__(self):
        if self.clusters is None:
            self.clusters = []
        if self.items is None:
            self.items = []
        if self.attachments is None:
            self.attachments = []
    
    def get_items_by_cluster(self, cluster_name: str) -> List[NuclinoItem]:
        """Get all items in a specific cluster."""
        return [item for item in self.items if item.cluster_name == cluster_name]
    
    def get_orphaned_items(self) -> List[NuclinoItem]:
        """Get items that don't belong to any cluster."""
        cluster_names = {cluster.name for cluster in self.clusters}
        return [item for item in self.items if not item.cluster_name or item.cluster_name not in cluster_names]


@dataclass
class ParsedNuclinoData:
    """Parsed Nuclino workspace data."""
    workspace: NuclinoWorkspace
    total_items: int
    total_clusters: int
    total_attachments: int
    topics: Dict[str, List[NuclinoItem]]