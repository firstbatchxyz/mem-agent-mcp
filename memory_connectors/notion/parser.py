"""
Notion workspace export parser.
"""

import json
import os
import zipfile
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from .types import (
    NotionWorkspace, NotionPage, NotionDatabase, NotionBlock, NotionUser, 
    NotionProperty, BlockType, ParsedNotionData
)


class NotionParser:
    """Parser for Notion workspace exports."""
    
    def __init__(self):
        self.workspace = None
        
    def parse_export(self, export_path: str) -> ParsedNotionData:
        """
        Parse Notion workspace export.
        
        Args:
            export_path: Path to Notion export (.zip file or extracted directory)
            
        Returns:
            ParsedNotionData containing workspace structure
        """
        export_path = Path(export_path)
        
        if export_path.is_file() and export_path.suffix == '.zip':
            return self._parse_zip_export(export_path)
        elif export_path.is_dir():
            return self._parse_directory_export(export_path)
        else:
            raise ValueError(f"Unsupported export format: {export_path}")
    
    def _parse_zip_export(self, zip_path: Path) -> ParsedNotionData:
        """Parse ZIP export file."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Find the main export directory inside the ZIP
            temp_path = Path(temp_dir)
            export_dirs = [d for d in temp_path.iterdir() if d.is_dir()]
            
            if not export_dirs:
                raise ValueError("No directories found in Notion export ZIP")
            
            # Use the first (and usually only) directory
            main_export_dir = export_dirs[0]
            return self._parse_directory_export(main_export_dir)
    
    def _parse_directory_export(self, export_dir: Path) -> ParsedNotionData:
        """Parse extracted export directory."""
        pages = []
        databases = []
        
        print(f"📂 Parsing Notion export directory: {export_dir}")
        
        # Walk through all files in the export
        for root, dirs, files in os.walk(export_dir):
            root_path = Path(root)
            
            for file in files:
                file_path = root_path / file
                
                if file.endswith('.md'):
                    # Parse markdown file as page
                    page = self._parse_markdown_page(file_path)
                    if page:
                        pages.append(page)
                
                elif file.endswith('.csv'):
                    # Parse CSV as database export
                    database = self._parse_csv_database(file_path)
                    if database:
                        databases.append(database)
        
        workspace = NotionWorkspace(
            pages=pages,
            databases=databases,
            export_date=datetime.now()
        )
        
        # Organize pages by topics
        topics = self._organize_by_topics(workspace.get_all_pages())
        
        return ParsedNotionData(
            workspace=workspace,
            total_pages=len(workspace.get_all_pages()),
            total_databases=len(databases),
            topics=topics
        )
    
    def _parse_markdown_page(self, file_path: Path) -> Optional[NotionPage]:
        """Parse a markdown file as a Notion page."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract title from filename or first heading
            title = self._extract_title(file_path, content)
            
            # Parse blocks from markdown content
            blocks = self._parse_markdown_blocks(content)
            
            # Get file timestamps
            stat = file_path.stat()
            created_time = datetime.fromtimestamp(stat.st_ctime)
            modified_time = datetime.fromtimestamp(stat.st_mtime)
            
            return NotionPage(
                id=str(hash(str(file_path))),  # Generate ID from path
                title=title,
                url=None,
                blocks=blocks,
                properties={},
                created_time=created_time,
                last_edited_time=modified_time
            )
            
        except Exception as e:
            print(f"⚠️ Error parsing {file_path}: {e}")
            return None
    
    def _parse_csv_database(self, file_path: Path) -> Optional[NotionDatabase]:
        """Parse a CSV file as a database export."""
        try:
            import csv
            
            pages = []
            properties = {}
            
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # Get properties from CSV headers
                if reader.fieldnames:
                    for field in reader.fieldnames:
                        properties[field] = {'type': 'text', 'name': field}
                
                # Parse each row as a page
                for i, row in enumerate(reader):
                    title = row.get('Name', row.get('Title', f'Page {i+1}'))
                    
                    page_properties = {}
                    for key, value in row.items():
                        if value:  # Only include non-empty properties
                            page_properties[key] = NotionProperty(
                                name=key,
                                type='text',
                                value=value
                            )
                    
                    # Create a simple block with the row data
                    content_lines = []
                    for key, value in row.items():
                        if value and key.lower() not in ['name', 'title']:
                            content_lines.append(f"**{key}**: {value}")
                    
                    blocks = [NotionBlock(
                        id=f"block_{i}",
                        type=BlockType.PARAGRAPH,
                        content="\\n".join(content_lines),
                        children=[]
                    )]
                    
                    page = NotionPage(
                        id=f"db_page_{i}",
                        title=title,
                        url=None,
                        blocks=blocks,
                        properties=page_properties,
                        database_id=str(hash(str(file_path)))
                    )
                    pages.append(page)
            
            database_title = file_path.stem.replace('_', ' ').title()
            
            return NotionDatabase(
                id=str(hash(str(file_path))),
                title=database_title,
                description=f"Database from {file_path.name}",
                pages=pages,
                properties=properties
            )
            
        except Exception as e:
            print(f"⚠️ Error parsing database {file_path}: {e}")
            return None
    
    def _extract_title(self, file_path: Path, content: str) -> str:
        """Extract title from filename or content."""
        # Try to get title from first heading
        lines = content.split('\\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
            elif line.startswith('## '):
                return line[3:].strip()
        
        # Fallback to filename
        title = file_path.stem
        # Clean up common Notion export formatting
        title = title.replace('%20', ' ')
        title = title.replace('_', ' ')
        
        return title
    
    def _parse_markdown_blocks(self, content: str) -> List[NotionBlock]:
        """Parse markdown content into Notion blocks."""
        blocks = []
        lines = content.split('\\n')
        
        for i, line in enumerate(lines):
            line = line.rstrip()
            
            if not line:
                continue
                
            block_type = BlockType.PARAGRAPH
            block_content = line
            
            # Determine block type
            if line.startswith('# '):
                block_type = BlockType.HEADING_1
                block_content = line[2:].strip()
            elif line.startswith('## '):
                block_type = BlockType.HEADING_2
                block_content = line[3:].strip()
            elif line.startswith('### '):
                block_type = BlockType.HEADING_3
                block_content = line[4:].strip()
            elif line.startswith('- ') or line.startswith('* '):
                block_type = BlockType.BULLETED_LIST_ITEM
                block_content = line[2:].strip()
            elif line.startswith('1. ') or any(line.startswith(f'{j}. ') for j in range(2, 100)):
                block_type = BlockType.NUMBERED_LIST_ITEM
                block_content = line.split('. ', 1)[1] if '. ' in line else line
            elif line.startswith('> '):
                block_type = BlockType.QUOTE
                block_content = line[2:].strip()
            elif line.startswith('```'):
                block_type = BlockType.CODE
                # For code blocks, we might need to handle multiple lines
                block_content = line[3:].strip()
            elif line.strip() == '---':
                block_type = BlockType.DIVIDER
                block_content = ""
            
            block = NotionBlock(
                id=f"block_{i}",
                type=block_type,
                content=block_content,
                children=[]
            )
            blocks.append(block)
        
        return blocks
    
    def _organize_by_topics(self, pages: List[NotionPage]) -> Dict[str, List[NotionPage]]:
        """Organize pages by topics based on titles and content."""
        topics = {}
        
        # Topic keywords for categorization
        topic_keywords = {
            'projects': ['project', 'planning', 'roadmap', 'milestone', 'sprint'],
            'meetings': ['meeting', 'standup', 'sync', 'review', 'retrospective'],
            'notes': ['notes', 'thoughts', 'ideas', 'brainstorm', 'draft'],
            'documentation': ['docs', 'documentation', 'guide', 'manual', 'spec'],
            'tasks': ['todo', 'task', 'action', 'assignment', 'checklist'],
            'knowledge': ['knowledge', 'learning', 'research', 'study', 'reference'],
            'personal': ['personal', 'journal', 'daily', 'weekly', 'reflection']
        }
        
        for page in pages:
            assigned_topics = []
            title_lower = page.title.lower()
            
            # Get some content from blocks for analysis
            content_text = ' '.join([
                block.content.lower() for block in page.blocks[:5]  # First 5 blocks
                if block.content
            ])
            
            combined_text = f"{title_lower} {content_text}"
            
            # Check against topic keywords
            for topic, keywords in topic_keywords.items():
                if any(keyword in combined_text for keyword in keywords):
                    assigned_topics.append(topic)
            
            # Default to 'general' if no topics match
            if not assigned_topics:
                assigned_topics = ['general']
            
            # Add to first matching topic
            primary_topic = assigned_topics[0]
            if primary_topic not in topics:
                topics[primary_topic] = []
            topics[primary_topic].append(page)
        
        return topics