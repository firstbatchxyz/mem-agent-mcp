"""
Nuclino workspace export parser.
"""

import os
import re
import zipfile
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from pathlib import Path

from .types import (
    NuclinoWorkspace, NuclinoItem, NuclinoCluster, NuclinoAttachment,
    NuclinoUser, ParsedNuclinoData
)


class NuclinoParser:
    """Parser for Nuclino workspace exports."""
    
    def __init__(self):
        self.workspace = None
        self.attachment_map = {}  # Map original paths to local paths
        
    def parse_export(self, export_path: str) -> ParsedNuclinoData:
        """
        Parse Nuclino workspace export.
        
        Args:
            export_path: Path to Nuclino export (.zip file or extracted directory)
            
        Returns:
            ParsedNuclinoData containing workspace structure
        """
        export_path = Path(export_path)
        
        if export_path.is_file() and export_path.suffix == '.zip':
            return self._parse_zip_export(export_path)
        elif export_path.is_dir():
            return self._parse_directory_export(export_path)
        else:
            raise ValueError(f"Unsupported export format: {export_path}")
    
    def _parse_zip_export(self, zip_path: Path) -> ParsedNuclinoData:
        """Parse ZIP export file."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            temp_path = Path(temp_dir)
            
            # Find the main export directory
            export_dirs = [d for d in temp_path.iterdir() if d.is_dir()]
            
            if not export_dirs:
                # Files might be directly in the root
                main_export_dir = temp_path
            else:
                # Use the first directory (common structure)
                main_export_dir = export_dirs[0]
            
            return self._parse_directory_export(main_export_dir)
    
    def _parse_directory_export(self, export_dir: Path) -> ParsedNuclinoData:
        """Parse extracted export directory."""
        print(f"📂 Parsing Nuclino export directory: {export_dir}")
        
        # First, discover the structure
        attachments = self._discover_attachments(export_dir)
        items = self._discover_and_parse_items(export_dir)
        clusters = self._organize_into_clusters(items)
        
        # Create workspace
        workspace_name = export_dir.name if export_dir.name != "temp" else "Nuclino Workspace"
        workspace = NuclinoWorkspace(
            name=workspace_name,
            clusters=clusters,
            items=items,
            attachments=attachments,
            export_date=datetime.now()
        )
        
        # Organize by topics
        topics = self._organize_by_topics(items)
        
        return ParsedNuclinoData(
            workspace=workspace,
            total_items=len(items),
            total_clusters=len(clusters),
            total_attachments=len(attachments),
            topics=topics
        )
    
    def _discover_attachments(self, export_dir: Path) -> List[NuclinoAttachment]:
        """Discover attachment files in the export."""
        attachments = []
        
        # Common attachment folder names in Nuclino exports
        attachment_folders = ['attachments', 'files', 'images', 'assets', 'media']
        
        for folder_name in attachment_folders:
            folder_path = export_dir / folder_name
            if folder_path.exists() and folder_path.is_dir():
                print(f"📎 Found attachment folder: {folder_name}")
                
                for file_path in folder_path.rglob('*'):
                    if file_path.is_file():
                        # Skip hidden files and system files
                        if file_path.name.startswith('.'):
                            continue
                            
                        attachment = NuclinoAttachment(
                            filename=file_path.name,
                            original_path=str(file_path.relative_to(export_dir)),
                            local_path=str(file_path),
                            size=file_path.stat().st_size if file_path.exists() else None
                        )
                        attachments.append(attachment)
                        
                        # Map for reference resolution
                        self.attachment_map[attachment.original_path] = attachment.local_path
        
        # Also check for files in other locations
        for file_path in export_dir.rglob('*'):
            if file_path.is_file() and not file_path.suffix == '.md':
                # Check if it's not already discovered
                relative_path = str(file_path.relative_to(export_dir))
                if relative_path not in self.attachment_map:
                    # Might be an attachment
                    if self._is_likely_attachment(file_path):
                        attachment = NuclinoAttachment(
                            filename=file_path.name,
                            original_path=relative_path,
                            local_path=str(file_path),
                            size=file_path.stat().st_size
                        )
                        attachments.append(attachment)
                        self.attachment_map[relative_path] = str(file_path)
        
        print(f"📎 Discovered {len(attachments)} attachments")
        return attachments
    
    def _is_likely_attachment(self, file_path: Path) -> bool:
        """Check if a file is likely an attachment."""
        attachment_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp',  # Images
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',  # Documents
            '.zip', '.tar', '.gz', '.rar',  # Archives
            '.mp4', '.avi', '.mov', '.mp3', '.wav',  # Media
            '.txt', '.csv', '.json', '.xml'  # Other files
        }
        
        return file_path.suffix.lower() in attachment_extensions
    
    def _discover_and_parse_items(self, export_dir: Path) -> List[NuclinoItem]:
        """Discover and parse all markdown items."""
        items = []
        
        print(f"📄 Discovering Nuclino items...")
        
        # Find all markdown files
        markdown_files = list(export_dir.rglob('*.md'))
        print(f"📄 Found {len(markdown_files)} markdown files")
        
        for md_file in markdown_files:
            try:
                item = self._parse_markdown_item(md_file, export_dir)
                if item:
                    items.append(item)
            except Exception as e:
                print(f"⚠️ Error parsing {md_file}: {e}")
        
        # Resolve internal links
        self._resolve_internal_links(items)
        
        print(f"📄 Parsed {len(items)} items")
        return items
    
    def _parse_markdown_item(self, file_path: Path, export_dir: Path) -> Optional[NuclinoItem]:
        """Parse a markdown file as a Nuclino item."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from content or filename
            title = self._extract_title_from_content(content) or self._extract_title_from_filename(file_path)
            
            # Extract cluster name from directory structure
            cluster_name = self._extract_cluster_from_path(file_path, export_dir)
            
            # Get file timestamps
            stat = file_path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            modified_time = datetime.fromtimestamp(stat.st_mtime)
            
            # Find attachments referenced in content
            attachments = self._extract_attachments_from_content(content)
            
            # Generate ID from path
            item_id = str(hash(str(file_path.relative_to(export_dir))))
            
            return NuclinoItem(
                id=item_id,
                title=title,
                content=content,
                path=file_path.relative_to(export_dir),
                cluster_name=cluster_name,
                created_time=created_time,
                modified_time=modified_time,
                attachments=attachments
            )
            
        except Exception as e:
            print(f"⚠️ Error parsing {file_path}: {e}")
            return None
    
    def _extract_title_from_content(self, content: str) -> Optional[str]:
        """Extract title from markdown content."""
        lines = content.split('\\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        return None
    
    def _extract_title_from_filename(self, file_path: Path) -> str:
        """Extract title from filename."""
        title = file_path.stem
        # Clean up common formatting
        title = title.replace('_', ' ').replace('-', ' ')
        title = re.sub(r'\\s+', ' ', title).strip()
        return title or "Untitled"
    
    def _extract_cluster_from_path(self, file_path: Path, export_dir: Path) -> Optional[str]:
        """Extract cluster name from directory path."""
        relative_path = file_path.relative_to(export_dir)
        
        # If the file is in a subdirectory, use the first directory as cluster
        if len(relative_path.parts) > 1:
            return relative_path.parts[0]
        
        return None
    
    def _extract_attachments_from_content(self, content: str) -> List[NuclinoAttachment]:
        """Extract attachment references from markdown content."""
        attachments = []
        
        # Find image references: ![alt](path)
        image_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        for match in re.finditer(image_pattern, content):
            alt_text, path = match.groups()
            
            if path in self.attachment_map:
                attachments.append(NuclinoAttachment(
                    filename=Path(path).name,
                    original_path=path,
                    local_path=self.attachment_map[path]
                ))
        
        # Find link references: [text](path)
        link_pattern = r'\[([^\]]*)\]\(([^\)]+)\)'
        for match in re.finditer(link_pattern, content):
            text, path = match.groups()
            
            # Check if it's a file attachment (not a URL or internal link)
            if not path.startswith(('http://', 'https://', '#')) and path in self.attachment_map:
                attachments.append(NuclinoAttachment(
                    filename=Path(path).name,
                    original_path=path,
                    local_path=self.attachment_map[path]
                ))
        
        return attachments
    
    def _resolve_internal_links(self, items: List[NuclinoItem]) -> None:
        """Resolve internal links between items."""
        # Build a map of possible link targets
        item_map = {}
        for item in items:
            # Map by title
            item_map[item.title.lower()] = item.id
            # Map by filename
            item_map[item.path.stem.lower()] = item.id
        
        # Find internal links in each item
        for item in items:
            internal_links = []
            
            # Pattern for internal links - this may vary based on Nuclino's format
            link_patterns = [
                r'\[([^\]]*)\]\(([^\)]+)\.md\)',  # [text](file.md)
                r'\[\[([^\]]+)\]\]',  # [[internal link]]
            ]
            
            for pattern in link_patterns:
                for match in re.finditer(pattern, item.content):
                    if len(match.groups()) == 2:
                        text, target = match.groups()
                    else:
                        target = match.group(1)
                    
                    target_lower = target.lower()
                    if target_lower in item_map:
                        internal_links.append(item_map[target_lower])
            
            item.internal_links = internal_links
    
    def _organize_into_clusters(self, items: List[NuclinoItem]) -> List[NuclinoCluster]:
        """Organize items into clusters."""
        cluster_map = {}
        
        for item in items:
            cluster_name = item.cluster_name or "General"
            
            if cluster_name not in cluster_map:
                cluster_map[cluster_name] = NuclinoCluster(
                    name=cluster_name,
                    items=[]
                )
            
            cluster_map[cluster_name].items.append(item)
        
        clusters = list(cluster_map.values())
        
        # Sort clusters by number of items (largest first)
        clusters.sort(key=lambda c: len(c.items), reverse=True)
        
        print(f"🗂️ Organized into {len(clusters)} clusters")
        for cluster in clusters:
            print(f"   - {cluster.name}: {len(cluster.items)} items")
        
        return clusters
    
    def _organize_by_topics(self, items: List[NuclinoItem]) -> Dict[str, List[NuclinoItem]]:
        """Organize items by topics for mem-agent."""
        topics = {}
        
        # Topic keywords for categorization
        topic_keywords = {
            'knowledge-base': ['knowledge', 'guide', 'documentation', 'manual', 'wiki'],
            'projects': ['project', 'planning', 'roadmap', 'milestone', 'sprint', 'epic'],
            'meetings': ['meeting', 'standup', 'sync', 'review', 'retrospective', 'agenda'],
            'processes': ['process', 'procedure', 'workflow', 'standard', 'policy'],
            'team': ['team', 'onboarding', 'training', 'culture', 'organization'],
            'technical': ['technical', 'architecture', 'design', 'implementation', 'api'],
            'research': ['research', 'analysis', 'investigation', 'study', 'findings'],
            'ideas': ['idea', 'brainstorm', 'concept', 'innovation', 'proposal']
        }
        
        for item in items:
            assigned_topics = []
            
            # Combine title, cluster, and content for analysis
            text_to_analyze = f"{item.title} {item.cluster_name or ''} {item.content[:500]}".lower()
            
            # Check against topic keywords
            for topic, keywords in topic_keywords.items():
                if any(keyword in text_to_analyze for keyword in keywords):
                    assigned_topics.append(topic)
            
            # If cluster name suggests a topic, use that
            if item.cluster_name:
                cluster_lower = item.cluster_name.lower()
                for topic, keywords in topic_keywords.items():
                    if any(keyword in cluster_lower for keyword in keywords):
                        if topic not in assigned_topics:
                            assigned_topics.append(topic)
            
            # Default to cluster-based or general
            if not assigned_topics:
                if item.cluster_name:
                    topic_name = item.cluster_name.lower().replace(' ', '-')
                    assigned_topics = [topic_name]
                else:
                    assigned_topics = ['general']
            
            # Add to first matching topic
            primary_topic = assigned_topics[0]
            if primary_topic not in topics:
                topics[primary_topic] = []
            topics[primary_topic].append(item)
        
        print(f"🗂️ Organized into {len(topics)} topics")
        for topic, topic_items in topics.items():
            print(f"   - {topic}: {len(topic_items)} items")
        
        return topics