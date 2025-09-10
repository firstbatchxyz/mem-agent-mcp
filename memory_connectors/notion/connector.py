"""
Notion Workspace Memory Connector

Converts Notion workspace exports into mem-agent memory format.
"""

import os
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from ..base import BaseMemoryConnector
from .parser import NotionParser
from .types import NotionPage, NotionBlock, BlockType


class NotionConnector(BaseMemoryConnector):
    """Connector for Notion workspace exports."""
    
    @property
    def connector_name(self) -> str:
        return "Notion Workspace"
    
    @property
    def supported_formats(self) -> list:
        return ['.zip']
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """Extract pages and databases from Notion export."""
        print(f"📂 Parsing Notion workspace export from {source_path}")
        
        # Parse the export using our Notion parser
        parser = NotionParser()
        parsed_data = parser.parse_export(source_path)
        
        return {
            'workspace': parsed_data.workspace,
            'topics': parsed_data.topics,
            'total_pages': parsed_data.total_pages,
            'total_databases': parsed_data.total_databases,
            'source_path': source_path
        }
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Data is already organized by the parser."""
        workspace = extracted_data['workspace']
        topics = extracted_data['topics']
        
        print(f"🗂️ Organizing {extracted_data['total_pages']} pages across {len(topics)} topics")
        
        # Additional organization could be done here if needed
        # For now, we use the parser's topic organization
        
        return {
            'workspace': workspace,
            'topic_pages': topics,
            'total_pages': extracted_data['total_pages'],
            'total_databases': extracted_data['total_databases']
        }
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """Generate mem-agent memory files from Notion data."""
        self.ensure_output_dir()
        
        workspace = organized_data['workspace']
        topic_pages = organized_data['topic_pages']
        
        # Create entities directory structure
        entities_dir = self.output_path / 'entities' / 'notion-workspace'
        topics_dir = entities_dir / 'topics'
        pages_dir = entities_dir / 'pages'
        
        entities_dir.mkdir(parents=True, exist_ok=True)
        topics_dir.mkdir(parents=True, exist_ok=True)
        pages_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Creating directory structure at {entities_dir}")
        
        # Generate user.md
        self._generate_user_md(workspace, topic_pages)
        
        # Generate index.md for notion-workspace
        self._generate_index_md(organized_data, entities_dir)
        
        # Generate topic files and individual pages
        total_files = 0
        for topic, pages in topic_pages.items():
            print(f"📝 Processing {topic}: {len(pages)} pages")
            
            # Generate topic file
            self._generate_topic_file(topic, pages, topics_dir)
            
            # Generate individual page files
            for i, page in enumerate(pages):
                self._generate_page_file(page, i, topic, pages_dir)
                total_files += 1
        
        print(f"✅ Generated {total_files} page files across {len(topic_pages)} topics")
    
    def _generate_user_md(self, workspace, topic_pages) -> None:
        """Generate or update user.md file."""
        user_md_path = self.output_path / 'user.md'
        
        # Check if user.md already exists
        existing_content = ""
        if user_md_path.exists():
            with open(user_md_path, 'r') as f:
                existing_content = f.read()
        
        # Add Notion section to existing content or create new
        if "## Available Knowledge Sources" in existing_content:
            # Update existing user.md by adding Notion section
            lines = existing_content.split('\\n')
            new_lines = []
            in_knowledge_section = False
            added_notion = False
            
            for line in lines:
                new_lines.append(line)
                
                if line == "## Available Knowledge Sources":
                    in_knowledge_section = True
                elif in_knowledge_section and line.startswith("##") and "Available Knowledge Sources" not in line:
                    # End of knowledge section, add Notion before next section
                    if not added_notion:
                        new_lines.insert(-1, "")
                        new_lines.insert(-1, "### Notion Workspace")
                        new_lines.insert(-1, f"Complete Notion workspace ({sum(len(pages) for pages in topic_pages.values())} pages across {len(topic_pages)} topics):")
                        new_lines.insert(-1, "- **Overview**: [[entities/notion-workspace/index.md|Notion Workspace Index]]")
                        new_lines.insert(-1, "")
                        added_notion = True
                    in_knowledge_section = False
            
            if not added_notion:
                # Add at the end of the file
                new_lines.append("")
                new_lines.append("### Notion Workspace")
                new_lines.append(f"Complete Notion workspace ({sum(len(pages) for pages in topic_pages.values())} pages across {len(topic_pages)} topics):")
                new_lines.append("- **Overview**: [[entities/notion-workspace/index.md|Notion Workspace Index]]")
            
            user_md_content = '\\n'.join(new_lines)
        else:
            # Create new user.md
            user_md_content = f"""## User Profile
- **Name**: User
- **Workspace**: Notion

## Communication Style

Professional and organized. Values clear structure and comprehensive documentation.

## Available Knowledge Sources

### Notion Workspace
Complete Notion workspace ({sum(len(pages) for pages in topic_pages.values())} pages across {len(topic_pages)} topics):
- **Overview**: [[entities/notion-workspace/index.md|Notion Workspace Index]]

### Search Strategy
When asked about specific topics, check the relevant topic file first, then explore individual pages as needed. Use `list_files()` to discover available files and `read_file()` to access content."""
        
        with open(user_md_path, 'w') as f:
            f.write(user_md_content)
        
        print(f"📄 Updated user.md with Notion workspace")
    
    def _generate_index_md(self, organized_data, entities_dir) -> None:
        """Generate index.md for notion-workspace."""
        topic_pages = organized_data['topic_pages']
        total_pages = organized_data['total_pages']
        total_databases = organized_data['total_databases']
        
        index_content = f"""# Notion Workspace

**Imported:** {self._get_current_timestamp()}
**Total Pages:** {total_pages}
**Databases:** {total_databases}
**Topics:** {len(topic_pages)}

This directory contains your Notion workspace organized by topics. Use the mem-agent tools to search and explore these pages.

## Topics

"""
        
        # Sort topics by page count
        sorted_topics = sorted(topic_pages.items(), key=lambda x: len(x[1]), reverse=True)
        
        for topic, pages in sorted_topics:
            topic_title = topic.replace('-', ' ').title()
            index_content += f"- **[[topics/{topic}.md|{topic_title}]]** ({len(pages)} pages)\\n"
        
        index_content += """
## Usage Examples

Use these mem-agent commands to explore your workspace:

```python
# List all topics
list_files("entities/notion-workspace/topics")

# Read a topic overview
read_file("entities/notion-workspace/topics/projects.md")

# Read a specific page
read_file("entities/notion-workspace/pages/page_0-example-page.md")

# Follow a page link from topic files
go_to_link("[[../pages/page_0-example-page.md]]")
```"""
        
        index_path = entities_dir / 'index.md'
        with open(index_path, 'w') as f:
            f.write(index_content)
        
        print(f"📄 Generated notion-workspace/index.md")
    
    def _generate_topic_file(self, topic, pages, topics_dir) -> None:
        """Generate individual topic file."""
        topic_title = topic.replace('-', ' ').title()
        
        # Calculate total blocks
        total_blocks = sum(len(page.blocks) for page in pages)
        
        # Get date range
        dates = [page.last_edited_time or page.created_time for page in pages if page.last_edited_time or page.created_time]
        date_range = ""
        if dates:
            min_date = min(dates).strftime("%Y-%m-%d")
            max_date = max(dates).strftime("%Y-%m-%d")
            date_range = f" from {min_date} to {max_date}"
        
        content = f"""# {topic_title}

**Pages:** {len(pages)}
**Topic:** {topic}

This topic contains {len(pages)} pages with {total_blocks} total blocks{date_range}.

## Pages

"""
        
        # Sort pages by last edited time (newest first)
        sorted_pages = sorted(pages, key=lambda x: x.last_edited_time or x.created_time or datetime.min, reverse=True)
        
        for i, page in enumerate(sorted_pages):
            title = page.title or f"Untitled Page {i}"
            # Clean title for filename
            safe_title = self._make_safe_filename(title)
            filename = f"page_{i}-{safe_title}.md"
            
            # Format date
            date_str = ""
            if page.last_edited_time:
                date_str = page.last_edited_time.strftime("%Y-%m-%d")
            elif page.created_time:
                date_str = page.created_time.strftime("%Y-%m-%d")
            
            content += f"- **[[../pages/{filename}|{title}]]** ({len(page.blocks)} blocks"
            if date_str:
                content += f", {date_str}"
            content += ")\\n"
        
        content += """
## Related Topics

- [[../index.md|Notion Workspace Overview]]
"""
        
        topic_path = topics_dir / f'{topic}.md'
        with open(topic_path, 'w') as f:
            f.write(content)
    
    def _generate_page_file(self, page: NotionPage, index: int, topic: str, pages_dir: Path) -> None:
        """Generate individual page file."""
        title = page.title or f"Untitled Page {index}"
        safe_title = self._make_safe_filename(title)
        filename = f"page_{index}-{safe_title}.md"
        
        # Format timestamps
        created = page.created_time.strftime("%Y-%m-%d %H:%M:%S") if page.created_time else "Unknown"
        updated = page.last_edited_time.strftime("%Y-%m-%d %H:%M:%S") if page.last_edited_time else created
        
        content = f"""# {title}

**Created:** {created}
**Updated:** {updated}
**Blocks:** {len(page.blocks)}
**Topic:** {topic}

---

"""
        
        # Add page properties if any
        if page.properties:
            content += "## Properties\\n\\n"
            for prop_name, prop in page.properties.items():
                if hasattr(prop, 'value') and prop.value:
                    content += f"**{prop_name}**: {prop.value}\\n"
            content += "\\n---\\n\\n"
        
        # Add blocks content
        content += self._render_blocks_as_markdown(page.blocks)
        
        page_path = pages_dir / filename
        with open(page_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _render_blocks_as_markdown(self, blocks: List[NotionBlock]) -> str:
        """Render Notion blocks as markdown."""
        markdown_lines = []
        
        for block in blocks:
            if not block.content and block.type != BlockType.DIVIDER:
                continue
            
            if block.type == BlockType.HEADING_1:
                markdown_lines.append(f"# {block.content}")
            elif block.type == BlockType.HEADING_2:
                markdown_lines.append(f"## {block.content}")
            elif block.type == BlockType.HEADING_3:
                markdown_lines.append(f"### {block.content}")
            elif block.type == BlockType.BULLETED_LIST_ITEM:
                markdown_lines.append(f"- {block.content}")
            elif block.type == BlockType.NUMBERED_LIST_ITEM:
                markdown_lines.append(f"1. {block.content}")
            elif block.type == BlockType.QUOTE:
                markdown_lines.append(f"> {block.content}")
            elif block.type == BlockType.CODE:
                markdown_lines.append(f"```\\n{block.content}\\n```")
            elif block.type == BlockType.DIVIDER:
                markdown_lines.append("---")
            elif block.type == BlockType.CALLOUT:
                markdown_lines.append(f"> 💡 {block.content}")
            else:  # PARAGRAPH or unknown
                markdown_lines.append(block.content)
            
            # Add children if any
            if block.children:
                child_content = self._render_blocks_as_markdown(block.children)
                # Indent child content
                indented_lines = ["  " + line for line in child_content.split('\\n') if line.strip()]
                markdown_lines.extend(indented_lines)
            
            markdown_lines.append("")  # Add empty line after each block
        
        return '\\n'.join(markdown_lines)
    
    def _make_safe_filename(self, title: str) -> str:
        """Convert title to safe filename."""
        import re
        # Remove or replace unsafe characters
        safe = re.sub(r'[<>:"/\\\\|?*]', '', title)
        safe = re.sub(r'\\s+', '-', safe.strip())
        # Limit length
        return safe[:50]
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp string."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")