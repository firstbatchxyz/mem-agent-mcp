"""
Google Docs Live Connector - Direct API integration for Google Docs and Drive.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from ..base import BaseMemoryConnector


class GoogleDocsLiveConnector(BaseMemoryConnector):
    """Live connector for Google Docs via Google Drive API."""
    
    def __init__(self, output_path: str, **kwargs):
        super().__init__(output_path, **kwargs)
        self.access_token = kwargs.get('access_token') or kwargs.get('token')
        self.folder_id = kwargs.get('folder_id')
        self.include_comments = kwargs.get('include_comments', True)
        self.include_suggestions = kwargs.get('include_suggestions', False)
        self.max_items = kwargs.get('max_items', 50)
        
        self.headers = {
            'Authorization': f'Bearer {self.access_token}' if self.access_token else '',
            'Accept': 'application/json'
        }
    
    @property
    def connector_name(self) -> str:
        return "Google Docs Live"
    
    @property
    def supported_formats(self) -> list:
        return ['api']
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """
        Extract data from Google Drive API.
        
        Args:
            source_path: Google Drive folder ID or folder URL
        """
        if not self.access_token:
            raise ValueError("Google Drive access token is required for API access")
        
        # Parse folder ID from URL if needed
        folder_id = self._parse_folder_id(source_path)
        
        print(f"🔄 Fetching Google Docs from folder: {folder_id}")
        
        all_data = {
            'folder_id': folder_id,
            'documents': [],
            'total_items': 0
        }
        
        try:
            # Get folder information
            folder_info = self._get_folder_info(folder_id)
            if folder_info:
                all_data['folder_info'] = folder_info
                print(f"📂 Folder: {folder_info.get('name', 'Unknown')}")
            
            # Get documents in folder
            documents = self._get_documents_in_folder(folder_id)
            
            for doc in documents:
                try:
                    doc_data = self._fetch_document_data(doc)
                    if doc_data:
                        all_data['documents'].append(doc_data)
                        all_data['total_items'] += 1
                        
                        max_items = self.max_items or 50
                        if len(all_data['documents']) >= max_items:
                            print(f"⚠️ Reached max items limit ({max_items})")
                            break
                            
                except Exception as e:
                    print(f"⚠️ Error fetching document {doc.get('name', 'unknown')}: {e}")
                    continue
            
            return all_data
            
        except Exception as e:
            print(f"❌ Error accessing Google Drive: {e}")
            print("   - Check if your access token is valid")
            print("   - Verify you have permission to access this folder")
            return all_data
    
    def _parse_folder_id(self, source_path: str) -> str:
        """Extract folder ID from Google Drive URL or return as-is if already an ID."""
        source_path = source_path.strip()
        
        # Handle Google Drive URLs
        if 'drive.google.com' in source_path:
            # Extract folder ID from various Google Drive URL formats
            if '/folders/' in source_path:
                # https://drive.google.com/drive/folders/FOLDER_ID
                folder_id = source_path.split('/folders/')[-1].split('?')[0].split('#')[0]
                return folder_id
            elif 'id=' in source_path:
                # https://drive.google.com/drive/u/0/folders?id=FOLDER_ID
                folder_id = source_path.split('id=')[-1].split('&')[0].split('#')[0]
                return folder_id
        
        # Assume it's already a folder ID
        return source_path
    
    def _google_api_call(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a Google API call with error handling."""
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params or {})
            
            # Handle authentication issues
            if response.status_code == 401:
                print(f"⚠️ Google API authentication failed. Check your access token.")
                return None
            
            # Handle forbidden access
            if response.status_code == 403:
                print(f"⚠️ Access denied. Check permissions for this folder/document.")
                return None
                
            # Handle not found
            if response.status_code == 404:
                print(f"⚠️ Folder or document not found.")
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️ API call failed: {e}")
            return None
    
    def _get_folder_info(self, folder_id: str) -> Optional[Dict]:
        """Get information about the folder."""
        endpoint = f"https://www.googleapis.com/drive/v3/files/{folder_id}"
        params = {
            'fields': 'id,name,description,createdTime,modifiedTime,owners'
        }
        return self._google_api_call(endpoint, params)
    
    def _get_documents_in_folder(self, folder_id: str) -> List[Dict]:
        """Get list of Google Docs in the specified folder."""
        endpoint = "https://www.googleapis.com/drive/v3/files"
        params = {
            'q': f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false",
            'fields': 'files(id,name,description,createdTime,modifiedTime,owners,webViewLink)',
            'pageSize': min(100, (self.max_items or 50) * 2)  # Get more than max in case some fail
        }
        
        result = self._google_api_call(endpoint, params)
        return result.get('files', []) if result else []
    
    def _fetch_document_data(self, doc: Dict) -> Optional[Dict]:
        """Fetch comprehensive data for a single document."""
        doc_id = doc['id']
        doc_name = doc.get('name', 'Untitled')
        
        print(f"📄 Processing document: {doc_name}")
        
        doc_data = {
            'id': doc_id,
            'name': doc_name,
            'description': doc.get('description', ''),
            'created_time': doc.get('createdTime'),
            'modified_time': doc.get('modifiedTime'),
            'web_link': doc.get('webViewLink', ''),
            'owners': doc.get('owners', []),
            'content': '',
            'word_count': 0
        }
        
        # Get document content
        content = self._get_document_content(doc_id)
        if content:
            doc_data['content'] = content
            doc_data['word_count'] = len(content.split())
        
        # Get comments if requested
        if self.include_comments:
            comments = self._get_document_comments(doc_id)
            doc_data['comments'] = comments
        
        return doc_data
    
    def _get_document_content(self, doc_id: str) -> Optional[str]:
        """Get document content as plain text."""
        # Export as plain text
        endpoint = f"https://www.googleapis.com/drive/v3/files/{doc_id}/export"
        params = {
            'mimeType': 'text/plain'
        }
        
        try:
            response = requests.get(endpoint, headers=self.headers, params=params)
            
            if response.status_code == 200:
                return response.text
            else:
                print(f"⚠️ Could not export document content: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"⚠️ Error fetching document content: {e}")
            return None
    
    def _get_document_comments(self, doc_id: str) -> List[Dict]:
        """Get comments on the document."""
        endpoint = f"https://www.googleapis.com/drive/v3/files/{doc_id}/comments"
        params = {
            'fields': 'comments(id,content,author,createdTime,modifiedTime,resolved)'
        }
        
        result = self._google_api_call(endpoint, params)
        return result.get('comments', []) if result else []
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize Google Docs data by topics."""
        print(f"📊 Organizing {extracted_data['total_items']} Google Docs...")
        
        documents = extracted_data['documents']
        folder_info = extracted_data.get('folder_info', {})
        
        organized = {
            'folder_info': folder_info,
            'documents': documents,
            'topics': {},
            'total_items': extracted_data['total_items']
        }
        
        # Organize by topics
        topics = self._categorize_documents_by_topics(documents)
        organized['topics'] = topics
        
        print(f"🗂️ Organized into {len(topics)} topics")
        
        return organized
    
    def _categorize_documents_by_topics(self, documents: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize documents by topics based on content and titles."""
        topics = {}
        
        # Topic keywords for categorization
        topic_keywords = {
            'project-planning': ['project', 'planning', 'roadmap', 'milestone', 'sprint', 'timeline'],
            'meeting-notes': ['meeting', 'standup', 'sync', 'notes', 'minutes', 'agenda'],
            'documentation': ['documentation', 'guide', 'manual', 'wiki', 'spec', 'requirements'],
            'strategy': ['strategy', 'vision', 'goals', 'objectives', 'proposal', 'plan'],
            'analysis': ['analysis', 'research', 'findings', 'report', 'study', 'insights'],
            'processes': ['process', 'workflow', 'procedure', 'policy', 'guidelines'],
            'brainstorming': ['ideas', 'brainstorm', 'concept', 'innovation', 'creative'],
            'reviews': ['review', 'feedback', 'evaluation', 'assessment', 'retrospective']
        }
        
        for doc in documents:
            assigned_topics = []
            
            # Analyze title and content for topic classification
            text_to_analyze = f"{doc['name']} {doc.get('description', '')} {doc.get('content', '')[:500]}".lower()
            
            # Check against topic keywords
            for topic, keywords in topic_keywords.items():
                if any(keyword in text_to_analyze for keyword in keywords):
                    assigned_topics.append(topic)
            
            # Default topic if none match
            if not assigned_topics:
                assigned_topics = ['general']
            
            # Add to primary topic
            primary_topic = assigned_topics[0]
            if primary_topic not in topics:
                topics[primary_topic] = []
            topics[primary_topic].append(doc)
        
        return topics
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """Generate memory files for Google Docs data."""
        print(f"📝 Generating memory files...")
        
        # Create output directories
        memory_dir = self.output_path / 'mcp-server'
        entities_dir = memory_dir / 'entities' / 'google-docs'
        topics_dir = entities_dir / 'topics'
        documents_dir = entities_dir / 'documents'
        
        for dir_path in [memory_dir, entities_dir, topics_dir, documents_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Generate index file
        self._generate_index_file(entities_dir, organized_data)
        
        # Generate topic files and individual documents
        doc_counter = 0
        for topic_name, topic_docs in organized_data['topics'].items():
            topic_file = topics_dir / f"{topic_name}.md"
            self._generate_topic_file(topic_file, topic_name, topic_docs, doc_counter)
            
            # Generate individual document files
            for doc in topic_docs:
                doc_file = documents_dir / f"doc_{doc_counter}-{self._sanitize_filename(doc['name'])}.md"
                self._generate_document_file(doc_file, doc)
                doc_counter += 1
        
        # Update user profile
        self._update_user_profile(memory_dir, organized_data)
        
        print(f"✅ Generated {doc_counter} memory files for Google Docs")
    
    def _generate_index_file(self, entities_dir: Path, organized_data: Dict[str, Any]) -> None:
        """Generate main index file."""
        folder_info = organized_data.get('folder_info', {})
        folder_name = folder_info.get('name', 'Google Docs Folder')
        
        content = f"""# Google Docs - {folder_name}

**Imported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Documents:** {organized_data['total_items']}
**Topics:** {len(organized_data['topics'])}

This directory contains your Google Docs organized by topics.

## Folder Information

- **Name:** {folder_name}
- **Description:** {folder_info.get('description', 'No description')}
- **Created:** {folder_info.get('createdTime', 'Unknown')}
- **Last Modified:** {folder_info.get('modifiedTime', 'Unknown')}

## Topics

"""
        
        for topic_name, docs in organized_data['topics'].items():
            content += f"- **[[topics/{topic_name}.md|{topic_name.replace('-', ' ').title()}]]** ({len(docs)} documents)\n"
        
        content += """
## Usage Examples

Use these mem-agent commands to explore your Google Docs:

```python
# List all topics
list_files("entities/google-docs/topics")

# Read a topic overview
read_file("entities/google-docs/topics/project-planning.md")

# Read a specific document
read_file("entities/google-docs/documents/doc_0-document-name.md")
```
"""
        
        with open(entities_dir / 'index.md', 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_topic_file(self, topic_file: Path, topic_name: str, docs: List[Dict], start_index: int) -> None:
        """Generate topic overview file."""
        content = f"""# {topic_name.replace('-', ' ').title()}

**Total Documents:** {len(docs)}

## Documents in this Topic

"""
        
        for i, doc in enumerate(docs):
            doc_index = start_index + i
            filename = f"doc_{doc_index}-{self._sanitize_filename(doc['name'])}.md"
            
            # Format creation date
            created = ""
            if doc.get('created_time'):
                try:
                    created_dt = datetime.fromisoformat(doc['created_time'].replace('Z', '+00:00'))
                    created = f" - {created_dt.strftime('%Y-%m-%d')}"
                except:
                    pass
            
            content += f"- **[[../documents/{filename}|{doc['name']}]]**{created}\n"
            if doc.get('description'):
                content += f"  *{doc['description']}*\n"
        
        with open(topic_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_document_file(self, doc_file: Path, doc: Dict) -> None:
        """Generate individual document file."""
        content = f"""# {doc['name']}

**Created:** {doc.get('created_time', 'Unknown')}
**Modified:** {doc.get('modified_time', 'Unknown')}
**Word Count:** {doc.get('word_count', 0)}

"""
        
        if doc.get('description'):
            content += f"**Description:** {doc['description']}\n\n"
        
        if doc.get('web_link'):
            content += f"**[Open in Google Docs]({doc['web_link']})**\n\n"
        
        # Add owners info
        if doc.get('owners'):
            owners = [owner.get('displayName', owner.get('emailAddress', 'Unknown')) for owner in doc['owners']]
            content += f"**Owners:** {', '.join(owners)}\n\n"
        
        content += "## Content\n\n"
        if doc.get('content'):
            content += doc['content']
        else:
            content += "*No content available*"
        
        # Add comments if available
        if doc.get('comments'):
            content += "\n\n## Comments\n\n"
            for comment in doc['comments']:
                author = comment.get('author', {}).get('displayName', 'Unknown')
                comment_content = comment.get('content', '')
                created = comment.get('createdTime', '')
                resolved = '✅' if comment.get('resolved') else '📝'
                
                content += f"**{resolved} {author}** - {created}\n"
                content += f"{comment_content}\n\n"
        
        try:
            with open(doc_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except UnicodeEncodeError as e:
            print(f"⚠️ Unicode encoding error writing file {doc_file}: {e}")
            safe_content = content.encode('utf-8', errors='replace').decode('utf-8')
            with open(doc_file, 'w', encoding='utf-8') as f:
                f.write(safe_content)
    
    def _update_user_profile(self, memory_dir: Path, organized_data: Dict[str, Any]) -> None:
        """Update user profile with Google Docs information."""
        user_file = memory_dir / 'user.md'
        
        # Read existing user.md if it exists
        existing_content = ""
        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # Prepare Google Docs section
        folder_info = organized_data.get('folder_info', {})
        folder_name = folder_info.get('name', 'Google Docs Folder')
        
        google_docs_section = f"""
### Google Docs - {folder_name}
Google Docs workspace ({organized_data['total_items']} documents across {len(organized_data['topics'])} topics):
- **Overview**: [[entities/google-docs/index.md|Google Docs Index]]
"""
        
        # Check if Google Docs section already exists
        if "### Google Docs" in existing_content:
            # Update existing section - simple replacement approach
            lines = existing_content.split('\n')
            new_lines = []
            skip_until_next_section = False
            
            for line in lines:
                if line.startswith("### Google Docs"):
                    skip_until_next_section = True
                    new_lines.extend(google_docs_section.strip().split('\n'))
                elif skip_until_next_section and line.startswith("### "):
                    skip_until_next_section = False
                    new_lines.append(line)
                elif not skip_until_next_section:
                    new_lines.append(line)
            
            updated_content = '\n'.join(new_lines)
        else:
            # Add new Google Docs section
            if existing_content:
                # Insert before "### Search Strategy" if it exists
                if "### Search Strategy" in existing_content:
                    updated_content = existing_content.replace("### Search Strategy", google_docs_section + "\n### Search Strategy")
                else:
                    updated_content = existing_content + google_docs_section
            else:
                # Create basic user.md with Google Docs section
                updated_content = f"""## User Profile
- **Name**: User
- **Workspace**: Multi-source

## Communication Style

Professional and productivity-focused. Values organized documentation and collaborative content.

## Available Knowledge Sources

{google_docs_section}
### Search Strategy
When asked about specific documents or topics, check the relevant topic file first, then explore individual documents as needed. Use `list_files()` to discover available files and `read_file()` to access content.
"""
        
        with open(user_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage."""
        import re
        # Remove/replace problematic characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'[^\w\s-]', '', filename)
        filename = re.sub(r'[-\s]+', '-', filename)
        return filename[:100].strip('-')  # Limit length