"""
Nuclino Workspace Memory Connector

Converts Nuclino workspace exports into mem-agent memory format.
"""

import os
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

from ..base import BaseMemoryConnector
from .parser import NuclinoParser
from .types import NuclinoItem, NuclinoCluster


class NuclinoConnector(BaseMemoryConnector):
    """Connector for Nuclino workspace exports."""
    
    @property
    def connector_name(self) -> str:
        return "Nuclino Workspace"
    
    @property
    def supported_formats(self) -> list:
        return ['.zip']
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """Extract items and clusters from Nuclino export."""
        print(f"📂 Parsing Nuclino workspace export from {source_path}")
        
        # Parse the export using our Nuclino parser
        parser = NuclinoParser()
        parsed_data = parser.parse_export(source_path)
        
        return {
            'workspace': parsed_data.workspace,
            'topics': parsed_data.topics,
            'total_items': parsed_data.total_items,
            'total_clusters': parsed_data.total_clusters,
            'total_attachments': parsed_data.total_attachments,
            'source_path': source_path
        }
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Data is already organized by the parser."""
        workspace = extracted_data['workspace']
        topics = extracted_data['topics']
        
        print(f"🗂️ Organizing {extracted_data['total_items']} items across {len(topics)} topics")
        
        # Additional organization could be done here if needed
        # For now, we use the parser's topic organization
        
        return {
            'workspace': workspace,
            'topic_items': topics,
            'total_items': extracted_data['total_items'],
            'total_clusters': extracted_data['total_clusters'],
            'total_attachments': extracted_data['total_attachments']
        }
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """Generate mem-agent memory files from Nuclino data."""
        self.ensure_output_dir()
        
        workspace = organized_data['workspace']
        topic_items = organized_data['topic_items']
        
        # Create entities directory structure
        entities_dir = self.output_path / 'entities' / 'nuclino-workspace'
        topics_dir = entities_dir / 'topics'
        items_dir = entities_dir / 'items'
        clusters_dir = entities_dir / 'clusters'
        
        entities_dir.mkdir(parents=True, exist_ok=True)
        topics_dir.mkdir(parents=True, exist_ok=True)
        items_dir.mkdir(parents=True, exist_ok=True)
        clusters_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Creating directory structure at {entities_dir}")
        
        # Generate user.md
        self._generate_user_md(workspace, topic_items)
        
        # Generate index.md for nuclino-workspace
        self._generate_index_md(organized_data, entities_dir)
        
        # Generate cluster files
        for cluster in workspace.clusters:
            self._generate_cluster_file(cluster, clusters_dir)
        
        # Generate topic files and individual items
        total_files = 0
        for topic, items in topic_items.items():
            print(f"📝 Processing {topic}: {len(items)} items")
            
            # Generate topic file
            self._generate_topic_file(topic, items, topics_dir)
            
            # Generate individual item files
            for i, item in enumerate(items):
                self._generate_item_file(item, i, topic, items_dir)
                total_files += 1
        
        print(f"✅ Generated {total_files} item files across {len(topic_items)} topics and {len(workspace.clusters)} clusters")
    
    def _generate_user_md(self, workspace, topic_items) -> None:
        """Generate or update user.md file."""
        user_md_path = self.output_path / 'user.md'
        
        # Check if user.md already exists
        existing_content = ""
        if user_md_path.exists():
            with open(user_md_path, 'r') as f:
                existing_content = f.read()
        
        # Add Nuclino section to existing content or create new
        if "## Available Knowledge Sources" in existing_content:
            # Update existing user.md by adding Nuclino section
            lines = existing_content.split('\\n')
            new_lines = []
            in_knowledge_section = False
            added_nuclino = False
            
            for line in lines:
                new_lines.append(line)
                
                if line == "## Available Knowledge Sources":
                    in_knowledge_section = True
                elif in_knowledge_section and line.startswith("##") and "Available Knowledge Sources" not in line:
                    # End of knowledge section, add Nuclino before next section
                    if not added_nuclino:
                        new_lines.insert(-1, "")
                        new_lines.insert(-1, "### Nuclino Workspace")
                        new_lines.insert(-1, f"Complete Nuclino workspace ({sum(len(items) for items in topic_items.values())} items across {len(topic_items)} topics):")
                        new_lines.insert(-1, "- **Overview**: [[entities/nuclino-workspace/index.md|Nuclino Workspace Index]]")
                        new_lines.insert(-1, "")
                        added_nuclino = True
                    in_knowledge_section = False
            
            if not added_nuclino:
                # Add at the end of the file
                new_lines.append("")
                new_lines.append("### Nuclino Workspace")
                new_lines.append(f"Complete Nuclino workspace ({sum(len(items) for items in topic_items.values())} items across {len(topic_items)} topics):")
                new_lines.append("- **Overview**: [[entities/nuclino-workspace/index.md|Nuclino Workspace Index]]")
            
            user_md_content = '\\n'.join(new_lines)
        else:
            # Create new user.md
            user_md_content = f"""## User Profile
- **Name**: User
- **Workspace**: Nuclino

## Communication Style

Professional and knowledge-focused. Values structured information and collaborative documentation.

## Available Knowledge Sources

### Nuclino Workspace
Complete Nuclino workspace ({sum(len(items) for items in topic_items.values())} items across {len(topic_items)} topics):
- **Overview**: [[entities/nuclino-workspace/index.md|Nuclino Workspace Index]]

### Search Strategy
When asked about specific topics, check the relevant topic file first, then explore individual items as needed. Use `list_files()` to discover available files and `read_file()` to access content."""
        
        with open(user_md_path, 'w') as f:
            f.write(user_md_content)
        
        print(f"📄 Updated user.md with Nuclino workspace")
    
    def _generate_index_md(self, organized_data, entities_dir) -> None:
        """Generate index.md for nuclino-workspace."""
        topic_items = organized_data['topic_items']
        total_items = organized_data['total_items']
        total_clusters = organized_data['total_clusters']
        
        index_content = f"""# Nuclino Workspace

**Imported:** {self._get_current_timestamp()}
**Total Items:** {total_items}
**Clusters:** {total_clusters}
**Topics:** {len(topic_items)}

This directory contains your Nuclino workspace organized by topics and clusters. Use the mem-agent tools to search and explore these items.

## Topics

"""
        
        # Sort topics by item count
        sorted_topics = sorted(topic_items.items(), key=lambda x: len(x[1]), reverse=True)
        
        for topic, items in sorted_topics:
            topic_title = topic.replace('-', ' ').title()
            index_content += f"- **[[topics/{topic}.md|{topic_title}]]** ({len(items)} items)\\n"
        
        index_content += f"""

## Clusters

- **[[clusters/|View All Clusters]]** ({total_clusters} total)

## Usage Examples

Use these mem-agent commands to explore your workspace:

```python
# List all topics
list_files("entities/nuclino-workspace/topics")

# Read a topic overview
read_file("entities/nuclino-workspace/topics/knowledge-base.md")

# Read a specific item
read_file("entities/nuclino-workspace/items/item_0-example-item.md")

# Explore clusters
list_files("entities/nuclino-workspace/clusters")
```"""
        
        index_path = entities_dir / 'index.md'
        with open(index_path, 'w') as f:
            f.write(index_content)
        
        print(f"📄 Generated nuclino-workspace/index.md")
    
    def _generate_cluster_file(self, cluster: NuclinoCluster, clusters_dir: Path) -> None:
        """Generate cluster overview file."""
        safe_name = self._make_safe_filename(cluster.name)
        cluster_path = clusters_dir / f'{safe_name}.md'
        
        content = f"""# {cluster.name}

**Items:** {len(cluster.items)}
**Cluster:** {cluster.name}

{cluster.description or f'This cluster contains {len(cluster.items)} items from the Nuclino workspace.'}

## Items in this Cluster

"""
        
        # Sort items by modification time (newest first)
        sorted_items = sorted(
            cluster.items, 
            key=lambda x: x.modified_time or x.created_time or datetime.min, 
            reverse=True
        )
        
        for i, item in enumerate(sorted_items):
            title = item.title or f"Untitled Item {i}"
            safe_title = self._make_safe_filename(title)
            filename = f"item_{i}-{safe_title}.md"
            
            # Format date
            date_str = ""
            if item.modified_time:
                date_str = item.modified_time.strftime("%Y-%m-%d")
            elif item.created_time:
                date_str = item.created_time.strftime("%Y-%m-%d")
            
            content += f"- **[[../items/{filename}|{title}]]**"
            if date_str:
                content += f" ({date_str})"
            content += "\\n"
        
        content += """
## Related

- [[../index.md|Nuclino Workspace Overview]]
"""
        
        with open(cluster_path, 'w') as f:
            f.write(content)
    
    def _generate_topic_file(self, topic, items, topics_dir) -> None:
        """Generate individual topic file."""
        topic_title = topic.replace('-', ' ').title()
        
        # Get date range
        dates = [item.modified_time or item.created_time for item in items if item.modified_time or item.created_time]
        date_range = ""
        if dates:
            min_date = min(dates).strftime("%Y-%m-%d")
            max_date = max(dates).strftime("%Y-%m-%d")
            date_range = f" from {min_date} to {max_date}"
        
        content = f"""# {topic_title}

**Items:** {len(items)}
**Topic:** {topic}

This topic contains {len(items)} items{date_range}.

## Items

"""
        
        # Sort items by modification time (newest first)
        sorted_items = sorted(
            items, 
            key=lambda x: x.modified_time or x.created_time or datetime.min, 
            reverse=True
        )
        
        for i, item in enumerate(sorted_items):
            title = item.title or f"Untitled Item {i}"
            # Clean title for filename
            safe_title = self._make_safe_filename(title)
            filename = f"item_{i}-{safe_title}.md"
            
            # Format date
            date_str = ""
            if item.modified_time:
                date_str = item.modified_time.strftime("%Y-%m-%d")
            elif item.created_time:
                date_str = item.created_time.strftime("%Y-%m-%d")
            
            # Add cluster info if available
            cluster_info = f" [{item.cluster_name}]" if item.cluster_name else ""
            
            content += f"- **[[../items/{filename}|{title}]]{cluster_info}**"
            if date_str:
                content += f" ({date_str})"
            content += "\\n"
        
        content += """
## Related Topics

- [[../index.md|Nuclino Workspace Overview]]
"""
        
        topic_path = topics_dir / f'{topic}.md'
        with open(topic_path, 'w') as f:
            f.write(content)
    
    def _generate_item_file(self, item: NuclinoItem, index: int, topic: str, items_dir: Path) -> None:
        """Generate individual item file."""
        title = item.title or f"Untitled Item {index}"
        safe_title = self._make_safe_filename(title)
        filename = f"item_{index}-{safe_title}.md"
        
        # Format timestamps
        created = item.created_time.strftime("%Y-%m-%d %H:%M:%S") if item.created_time else "Unknown"
        modified = item.modified_time.strftime("%Y-%m-%d %H:%M:%S") if item.modified_time else created
        
        content = f"""# {title}

**Created:** {created}
**Modified:** {modified}
**Topic:** {topic}
"""
        
        if item.cluster_name:
            content += f"**Cluster:** {item.cluster_name}\\n"
        
        content += "\\n---\\n\\n"
        
        # Add attachments info if any
        if item.attachments:
            content += "## Attachments\\n\\n"
            for attachment in item.attachments:
                content += f"- **{attachment.filename}** ({attachment.original_path})\\n"
            content += "\\n---\\n\\n"
        
        # Add internal links if any
        if item.internal_links:
            content += "## Internal Links\\n\\n"
            for link_id in item.internal_links:
                content += f"- Link to item: {link_id}\\n"
            content += "\\n---\\n\\n"
        
        # Add the main content
        content += item.content
        
        item_path = items_dir / filename
        with open(item_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
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