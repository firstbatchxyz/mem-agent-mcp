"""
GitHub Live Connector - Direct API integration for GitHub repositories.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from ..base import BaseMemoryConnector


class GitHubLiveConnector(BaseMemoryConnector):
    """Live connector for GitHub repositories via API."""
    
    def __init__(self, output_path: str, **kwargs):
        super().__init__(output_path, **kwargs)
        self.token = kwargs.get('token')
        self.repositories = kwargs.get('repositories', [])
        self.include_issues = kwargs.get('include_issues', True)
        self.include_prs = kwargs.get('include_prs', True)
        self.include_wiki = kwargs.get('include_wiki', True)
        self.max_items = kwargs.get('max_items', 100)
        
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'mem-agent-mcp-github-connector'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
    
    @property
    def connector_name(self) -> str:
        return "GitHub Live"
    
    @property
    def supported_formats(self) -> list:
        return ['api']
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """
        Extract data from GitHub API.
        
        Args:
            source_path: Comma-separated repository names (e.g., "owner/repo1,owner/repo2")
        """
        if not self.token:
            print("⚠️ No GitHub token provided - using public API (rate limited)")
        
        repositories = source_path.split(',') if source_path else self.repositories
        if not repositories:
            raise ValueError("No repositories specified")
        
        # Clean up repository names - handle full GitHub URLs
        cleaned_repos = []
        for repo in repositories:
            repo = repo.strip()
            # Convert https://github.com/owner/repo to owner/repo
            if repo.startswith('https://github.com/'):
                repo = repo.replace('https://github.com/', '')
            # Remove trailing .git if present
            if repo.endswith('.git'):
                repo = repo[:-4]
            cleaned_repos.append(repo)
        
        repositories = cleaned_repos
        
        print(f"🔄 Fetching data from {len(repositories)} GitHub repositories...")
        
        all_data = {
            'repositories': [],
            'total_items': 0
        }
        
        for repo in repositories:
            repo = repo.strip()
            print(f"📂 Processing repository: {repo}")
            
            try:
                repo_data = self._fetch_repository_data(repo)
                all_data['repositories'].append(repo_data)
                all_data['total_items'] += repo_data.get('item_count', 0)
            except UnicodeEncodeError as e:
                print(f"⚠️ Unicode encoding error for {repo}: {e}")
                print(f"   This may be due to special characters in repository content")
                continue
            except Exception as e:
                print(f"⚠️ Error fetching {repo}: {e}")
                continue
        
        return all_data
    
    def _fetch_repository_data(self, repo_name: str) -> Dict[str, Any]:
        """Fetch comprehensive data for a single repository."""
        repo_data = {
            'name': repo_name,
            'metadata': {},
            'contents': [],
            'issues': [],
            'pull_requests': [],
            'wiki_pages': [],
            'item_count': 0
        }
        
        # Get repository metadata first to validate repository exists
        repo_info = self._github_api_call(f'/repos/{repo_name}')
        if not repo_info:
            print(f"❌ Repository {repo_name} not found or not accessible")
            print(f"   - Check if repository exists: https://github.com/{repo_name}")
            print(f"   - For private repositories, ensure your token has 'repo' scope")
            return repo_data
            
        repo_data['metadata'] = {
            'full_name': repo_info.get('full_name'),
            'description': repo_info.get('description', ''),
            'language': repo_info.get('language', ''),
            'topics': repo_info.get('topics', []),
            'stars': repo_info.get('stargazers_count', 0),
            'forks': repo_info.get('forks_count', 0),
            'created_at': repo_info.get('created_at'),
            'updated_at': repo_info.get('updated_at'),
            'default_branch': repo_info.get('default_branch', 'main'),
            'private': repo_info.get('private', False)
        }
        
        print(f"✅ Repository found: {repo_info.get('full_name')} ({'private' if repo_info.get('private') else 'public'})")
        default_branch = repo_info.get('default_branch', 'main')
        
        # Get README and documentation
        readme_content = self._fetch_readme(repo_name)
        if readme_content:
            repo_data['contents'].append({
                'type': 'readme',
                'path': 'README.md',
                'content': readme_content,
                'title': f"{repo_name} - README"
            })
            repo_data['item_count'] += 1
        
        # Get documentation files
        docs = self._fetch_documentation(repo_name)
        repo_data['contents'].extend(docs)
        repo_data['item_count'] += len(docs)
        
        # Get repository structure and files
        repo_files = self._fetch_repository_structure(repo_name, default_branch)
        repo_data['contents'].extend(repo_files)
        repo_data['item_count'] += len(repo_files)
        
        # Get issues if requested
        if self.include_issues:
            issues = self._fetch_issues(repo_name)
            repo_data['issues'] = issues
            repo_data['item_count'] += len(issues)
        
        # Get pull requests if requested
        if self.include_prs:
            prs = self._fetch_pull_requests(repo_name)
            repo_data['pull_requests'] = prs
            repo_data['item_count'] += len(prs)
        
        # Get wiki pages if requested
        if self.include_wiki:
            wiki_pages = self._fetch_wiki_pages(repo_name)
            repo_data['wiki_pages'] = wiki_pages
            repo_data['item_count'] += len(wiki_pages)
        
        return repo_data
    
    def _github_api_call(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make a GitHub API call with error handling."""
        url = f"https://api.github.com{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params or {})
            
            # Handle rate limiting
            if response.status_code == 403 and 'rate limit' in response.text.lower():
                print(f"⚠️ GitHub API rate limit exceeded. Try again later or provide a token.")
                return None
            
            # Handle authentication issues
            if response.status_code == 401:
                print(f"⚠️ GitHub API authentication failed. Check your token permissions.")
                return None
                
            # Handle not found - only print for main repo check, not for optional resources
            if response.status_code == 404:
                if '/repos/' in endpoint and endpoint.count('/') == 2:  # Main repo endpoint
                    print(f"⚠️ Repository not found: {endpoint}")
                return None
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            # Only show detailed errors for important endpoints
            if '/repos/' in endpoint and endpoint.count('/') == 2:  # Main repo endpoint
                print(f"⚠️ API call failed for {endpoint}: {e}")
            return None
    
    def _fetch_readme(self, repo_name: str) -> Optional[str]:
        """Fetch repository README content."""
        for readme_name in ['README.md', 'README.rst', 'README.txt', 'README']:
            content = self._fetch_file_content(repo_name, readme_name)
            if content:
                return content
        return None
    
    def _fetch_file_content(self, repo_name: str, file_path: str) -> Optional[str]:
        """Fetch content of a specific file."""
        file_data = self._github_api_call(f'/repos/{repo_name}/contents/{file_path}')
        
        if file_data and file_data.get('type') == 'file':
            # Decode base64 content
            import base64
            try:
                content = base64.b64decode(file_data['content']).decode('utf-8')
                return content
            except (ValueError, UnicodeDecodeError) as e:
                print(f"⚠️ Could not decode file content for {file_path}: {e}")
                return None
        
        return None
    
    def _fetch_repository_structure(self, repo_name: str, branch: str = 'main') -> List[Dict[str, Any]]:
        """Fetch repository structure and important files."""
        files = []
        max_files_per_repo = min(50, (self.max_items or 100) // 2)  # Reserve half for other content
        
        try:
            # Get root directory contents
            contents = self._github_api_call(f'/repos/{repo_name}/contents?ref={branch}')
            
            if not contents:
                return files
            
            files_fetched = 0
            
            # Process files and directories
            for item in contents:
                if files_fetched >= max_files_per_repo:
                    break
                    
                item_name = item.get('name', '')
                item_type = item.get('type', '')
                item_path = item.get('path', '')
                
                # Skip certain files/directories
                if self._should_skip_item(item_name):
                    continue
                
                if item_type == 'file':
                    # Fetch important files
                    if self._is_important_file(item_name):
                        content = self._fetch_file_content(repo_name, item_path)
                        if content:
                            files.append({
                                'type': 'repository_file',
                                'path': item_path,
                                'content': content,
                                'title': f"{repo_name} - {item_name}",
                                'size': item.get('size', 0)
                            })
                            files_fetched += 1
                
                elif item_type == 'dir':
                    # Recursively fetch directory contents (limited depth)
                    dir_files = self._fetch_directory_contents(repo_name, item_path, branch, 
                                                             max_files_per_repo - files_fetched, depth=1)
                    files.extend(dir_files)
                    files_fetched += len(dir_files)
                    
        except Exception as e:
            print(f"⚠️ Error fetching repository structure for {repo_name}: {e}")
            
        return files
    
    def _fetch_directory_contents(self, repo_name: str, dir_path: str, branch: str, 
                                max_files: int, depth: int = 0, max_depth: int = 2) -> List[Dict[str, Any]]:
        """Recursively fetch directory contents with depth limit."""
        files = []
        
        if depth >= max_depth or len(files) >= max_files:
            return files
            
        try:
            contents = self._github_api_call(f'/repos/{repo_name}/contents/{dir_path}?ref={branch}')
            
            if not contents:
                return files
                
            for item in contents:
                if len(files) >= max_files:
                    break
                    
                item_name = item.get('name', '')
                item_type = item.get('type', '')
                item_path = item.get('path', '')
                
                if self._should_skip_item(item_name):
                    continue
                
                if item_type == 'file' and self._is_important_file(item_name):
                    content = self._fetch_file_content(repo_name, item_path)
                    if content:
                        files.append({
                            'type': 'repository_file',
                            'path': item_path,
                            'content': content,
                            'title': f"{repo_name} - {item_path}",
                            'size': item.get('size', 0)
                        })
                        
                elif item_type == 'dir' and depth < max_depth - 1:
                    # Recurse into subdirectory
                    dir_files = self._fetch_directory_contents(repo_name, item_path, branch,
                                                             max_files - len(files), depth + 1, max_depth)
                    files.extend(dir_files)
                    
        except Exception as e:
            print(f"⚠️ Error fetching directory {dir_path}: {e}")
            
        return files
    
    def _should_skip_item(self, name: str) -> bool:
        """Check if item should be skipped."""
        skip_patterns = {
            # Hidden files/directories
            '.git', '.gitignore', '.github', '.vscode', '.idea',
            # Build/cache directories
            'node_modules', '__pycache__', '.pytest_cache', 'dist', 'build',
            # Package files
            'package-lock.json', 'yarn.lock', 'poetry.lock',
            # Binary/large files
            '.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.tar.gz'
        }
        
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in skip_patterns)
    
    def _is_important_file(self, name: str) -> bool:
        """Check if file is considered important to include."""
        important_extensions = {
            '.py', '.js', '.ts', '.tsx', '.jsx', '.java', '.cpp', '.c', '.h',
            '.go', '.rs', '.rb', '.php', '.sh', '.bash', '.zsh',
            '.md', '.rst', '.txt', '.yml', '.yaml', '.json', '.xml',
            '.sql', '.css', '.scss', '.html', '.vue', '.svelte'
        }
        
        important_files = {
            'makefile', 'dockerfile', 'requirements.txt', 'package.json',
            'pyproject.toml', 'cargo.toml', 'composer.json', 'pom.xml',
            'build.gradle', 'cmake.txt', 'license', 'changelog'
        }
        
        name_lower = name.lower()
        
        # Check if it's an important file by name
        if name_lower in important_files:
            return True
            
        # Check if it has an important extension
        for ext in important_extensions:
            if name_lower.endswith(ext):
                return True
                
        return False
    
    def _fetch_documentation(self, repo_name: str) -> List[Dict[str, Any]]:
        """Fetch documentation files from docs/ directory."""
        docs = []
        
        # Check common documentation directories
        doc_paths = ['docs', 'doc', 'documentation', '.github']
        
        for doc_path in doc_paths:
            contents = self._github_api_call(f'/repos/{repo_name}/contents/{doc_path}')
            
            if contents and isinstance(contents, list):
                for item in contents[:10]:  # Limit to prevent too many files
                    if item.get('type') == 'file' and item.get('name', '').endswith(('.md', '.rst', '.txt')):
                        content = self._fetch_file_content(repo_name, item['path'])
                        if content:
                            docs.append({
                                'type': 'documentation',
                                'path': item['path'],
                                'content': content,
                                'title': f"{repo_name} - {item['name']}"
                            })
        
        return docs
    
    def _fetch_issues(self, repo_name: str) -> List[Dict[str, Any]]:
        """Fetch repository issues."""
        issues = []
        
        # Fetch recent closed and open issues
        max_per_request = min(25, (self.max_items or 100) // 4)
        for state in ['open', 'closed']:
            issues_data = self._github_api_call(f'/repos/{repo_name}/issues', {
                'state': state,
                'per_page': max_per_request,
                'sort': 'updated',
                'direction': 'desc'
            })
            
            if issues_data:
                for issue in issues_data:
                    # Skip pull requests (they appear in issues API)
                    if issue.get('pull_request'):
                        continue
                    
                    issues.append({
                        'number': issue['number'],
                        'title': issue['title'],
                        'body': issue.get('body', ''),
                        'state': issue['state'],
                        'created_at': issue['created_at'],
                        'updated_at': issue['updated_at'],
                        'labels': [label['name'] for label in issue.get('labels', [])],
                        'author': issue['user']['login'] if issue.get('user') else None
                    })
        
        return issues
    
    def _fetch_pull_requests(self, repo_name: str) -> List[Dict[str, Any]]:
        """Fetch repository pull requests."""
        prs = []
        
        max_per_request = min(25, (self.max_items or 100) // 4)
        for state in ['open', 'closed']:
            prs_data = self._github_api_call(f'/repos/{repo_name}/pulls', {
                'state': state,
                'per_page': max_per_request,
                'sort': 'updated',
                'direction': 'desc'
            })
            
            if prs_data:
                for pr in prs_data:
                    prs.append({
                        'number': pr['number'],
                        'title': pr['title'],
                        'body': pr.get('body', ''),
                        'state': pr['state'],
                        'created_at': pr['created_at'],
                        'updated_at': pr['updated_at'],
                        'merged': pr.get('merged', False),
                        'author': pr['user']['login'] if pr.get('user') else None,
                        'head_branch': pr['head']['ref'],
                        'base_branch': pr['base']['ref']
                    })
        
        return prs
    
    def _fetch_wiki_pages(self, repo_name: str) -> List[Dict[str, Any]]:
        """Fetch repository wiki pages."""
        wiki_pages = []
        
        # Check if wiki exists by trying to access it
        wiki_data = self._github_api_call(f'/repos/{repo_name}/wiki')
        
        if wiki_data:
            # Note: GitHub Wiki API is limited, this is a simplified implementation
            # In a full implementation, you might need to clone the wiki repo
            pass
        
        return wiki_pages
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize GitHub data by topics and repository."""
        print(f"📊 Organizing {extracted_data['total_items']} items from GitHub...")
        
        organized = {
            'repositories': extracted_data['repositories'],
            'topics': {},
            'total_items': extracted_data['total_items']
        }
        
        # Organize by topics
        for repo in extracted_data['repositories']:
            repo_name = repo['name']
            
            # Create repository-specific topic
            repo_topic = f"github-{repo_name.split('/')[-1]}"
            organized['topics'][repo_topic] = {
                'name': repo_topic,
                'items': [],
                'repository': repo_name,
                'metadata': repo['metadata']
            }
            
            # Add contents
            for content in repo['contents']:
                organized['topics'][repo_topic]['items'].append({
                    'type': 'content',
                    'title': content['title'],
                    'content': content['content'],
                    'path': content['path'],
                    'source_type': content['type']
                })
            
            # Add issues
            for issue in repo['issues']:
                organized['topics'][repo_topic]['items'].append({
                    'type': 'issue',
                    'title': f"Issue #{issue['number']}: {issue['title']}",
                    'content': issue['body'],
                    'metadata': {
                        'number': issue['number'],
                        'state': issue['state'],
                        'labels': issue['labels'],
                        'author': issue['author'],
                        'created_at': issue['created_at']
                    },
                    'source_type': 'issue'
                })
            
            # Add pull requests
            for pr in repo['pull_requests']:
                organized['topics'][repo_topic]['items'].append({
                    'type': 'pull_request',
                    'title': f"PR #{pr['number']}: {pr['title']}",
                    'content': pr['body'],
                    'metadata': {
                        'number': pr['number'],
                        'state': pr['state'],
                        'merged': pr['merged'],
                        'author': pr['author'],
                        'created_at': pr['created_at'],
                        'head_branch': pr['head_branch'],
                        'base_branch': pr['base_branch']
                    },
                    'source_type': 'pull_request'
                })
        
        print(f"🗂️ Organized into {len(organized['topics'])} repository topics")
        
        return organized
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """Generate memory files for GitHub data."""
        print(f"📝 Generating memory files...")
        
        # Create output directories
        memory_dir = self.output_path / 'mcp-server'
        entities_dir = memory_dir / 'entities' / 'github-repositories'
        topics_dir = entities_dir / 'topics'
        items_dir = entities_dir / 'items'
        repos_dir = entities_dir / 'repositories'
        
        for dir_path in [memory_dir, entities_dir, topics_dir, items_dir, repos_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        # Generate index file
        self._generate_index_file(entities_dir, organized_data)
        
        # Generate topic files
        item_counter = 0
        for topic_name, topic_data in organized_data['topics'].items():
            topic_file = topics_dir / f"{topic_name}.md"
            repo_file = repos_dir / f"{topic_name}.md"
            
            # Generate topic overview
            self._generate_topic_file(topic_file, topic_name, topic_data, item_counter)
            
            # Generate repository overview
            self._generate_repository_file(repo_file, topic_data)
            
            # Generate individual item files
            for item in topic_data['items']:
                item_file = items_dir / f"item_{item_counter}-{self._sanitize_filename(item['title'])}.md"
                self._generate_item_file(item_file, item, topic_data['repository'])
                item_counter += 1
        
        # Update user profile
        self._update_user_profile(memory_dir, organized_data)
        
        print(f"✅ Generated {item_counter} memory files for GitHub repositories")
    
    def _generate_index_file(self, entities_dir: Path, organized_data: Dict[str, Any]) -> None:
        """Generate main index file."""
        content = f"""# GitHub Repositories

**Imported:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Items:** {organized_data['total_items']}
**Repositories:** {len(organized_data['repositories'])}

This directory contains your GitHub repositories organized by repository and content type.

## Repositories

"""
        
        for topic_name, topic_data in organized_data['topics'].items():
            repo_name = topic_data['repository']
            item_count = len(topic_data['items'])
            
            content += f"- **[[repositories/{topic_name}.md|{repo_name}]]** ({item_count} items)\n"
        
        content += """
## Topics

"""
        
        for topic_name, topic_data in organized_data['topics'].items():
            item_count = len(topic_data['items'])
            content += f"- **[[topics/{topic_name}.md|{topic_name}]]** ({item_count} items)\n"
        
        content += """
## Usage Examples

Use these mem-agent commands to explore your repositories:

```python
# List all repositories
list_files("entities/github-repositories/repositories")

# Read a repository overview
read_file("entities/github-repositories/repositories/github-repo-name.md")

# Read a specific item
read_file("entities/github-repositories/items/item_0-readme.md")

# Explore by topic
list_files("entities/github-repositories/topics")
```
"""
        
        with open(entities_dir / 'index.md', 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_topic_file(self, topic_file: Path, topic_name: str, topic_data: Dict[str, Any], start_index: int) -> None:
        """Generate topic overview file."""
        repo_name = topic_data['repository']
        metadata = topic_data.get('metadata', {})
        
        content = f"""# {topic_name.replace('-', ' ').title()}

**Repository:** {repo_name}
**Total Items:** {len(topic_data['items'])}

## Repository Info

- **Description:** {metadata.get('description', 'N/A')}
- **Language:** {metadata.get('language', 'N/A')}
- **Stars:** {metadata.get('stars', 0)}
- **Forks:** {metadata.get('forks', 0)}
- **Topics:** {', '.join(metadata.get('topics', []))}

## Contents

"""
        
        for i, item in enumerate(topic_data['items']):
            item_index = start_index + i
            filename = f"item_{item_index}-{self._sanitize_filename(item['title'])}.md"
            
            content += f"- **[[../items/{filename}|{item['title']}]]** ({item['source_type']})\n"
        
        with open(topic_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_repository_file(self, repo_file: Path, topic_data: Dict[str, Any]) -> None:
        """Generate repository overview file."""
        repo_name = topic_data['repository']
        metadata = topic_data.get('metadata', {})
        
        content = f"""# {repo_name}

**Full Name:** {metadata.get('full_name', repo_name)}
**Description:** {metadata.get('description', 'No description available')}

## Repository Details

- **Language:** {metadata.get('language', 'N/A')}
- **Stars:** {metadata.get('stars', 0):,}
- **Forks:** {metadata.get('forks', 0):,}
- **Created:** {metadata.get('created_at', 'N/A')}
- **Last Updated:** {metadata.get('updated_at', 'N/A')}
- **Default Branch:** {metadata.get('default_branch', 'main')}

## Topics

{', '.join(f'`{topic}`' for topic in metadata.get('topics', [])) if metadata.get('topics') else 'No topics specified'}

## Content Overview

This repository contains:

"""
        
        content_types = {}
        for item in topic_data['items']:
            source_type = item['source_type']
            content_types[source_type] = content_types.get(source_type, 0) + 1
        
        for content_type, count in content_types.items():
            content += f"- **{content_type.replace('_', ' ').title()}:** {count} items\n"
        
        content += "\n## Related Files\n\n"
        content += f"- **[[../topics/{topic_data['name']}.md|Topic Overview]]**\n"
        content += f"- **[[../index.md|Main Index]]**\n"
        
        with open(repo_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_item_file(self, item_file: Path, item: Dict[str, Any], repo_name: str) -> None:
        """Generate individual item file."""
        content = f"""# {item['title']}

**Repository:** {repo_name}
**Type:** {item['source_type'].replace('_', ' ').title()}

"""
        
        # Add metadata if available
        if 'metadata' in item:
            metadata = item['metadata']
            content += "## Details\n\n"
            
            if 'number' in metadata:
                content += f"- **Number:** #{metadata['number']}\n"
            if 'state' in metadata:
                content += f"- **State:** {metadata['state']}\n"
            if 'author' in metadata:
                content += f"- **Author:** {metadata['author']}\n"
            if 'created_at' in metadata:
                content += f"- **Created:** {metadata['created_at']}\n"
            if 'labels' in metadata and metadata['labels']:
                content += f"- **Labels:** {', '.join(f'`{label}`' for label in metadata['labels'])}\n"
            if 'merged' in metadata:
                content += f"- **Merged:** {'Yes' if metadata['merged'] else 'No'}\n"
            if 'head_branch' in metadata:
                content += f"- **Head Branch:** `{metadata['head_branch']}`\n"
            if 'base_branch' in metadata:
                content += f"- **Base Branch:** `{metadata['base_branch']}`\n"
            
            content += "\n"
        
        content += "## Content\n\n"
        if item.get('content'):
            content += item['content']
        else:
            content += "*No content available*"
        
        try:
            with open(item_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except UnicodeEncodeError as e:
            print(f"⚠️ Unicode encoding error writing file {item_file}: {e}")
            # Write a simplified version without problematic characters
            safe_content = content.encode('utf-8', errors='replace').decode('utf-8')
            with open(item_file, 'w', encoding='utf-8') as f:
                f.write(safe_content)
    
    def _update_user_profile(self, memory_dir: Path, organized_data: Dict[str, Any]) -> None:
        """Update user profile with GitHub information."""
        user_file = memory_dir / 'user.md'
        
        # Read existing user.md if it exists
        existing_content = ""
        if user_file.exists():
            with open(user_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        
        # Check if GitHub section already exists
        if "### GitHub Repositories" in existing_content:
            # Update existing section
            lines = existing_content.split('\n')
            new_lines = []
            in_github_section = False
            
            for line in lines:
                if line.startswith("### GitHub Repositories"):
                    in_github_section = True
                    new_lines.append(line)
                    new_lines.append(f"GitHub repositories ({organized_data['total_items']} items across {len(organized_data['repositories'])} repositories):")
                elif in_github_section and line.startswith("### "):
                    in_github_section = False
                    # Add GitHub content before next section
                    for topic_name, topic_data in organized_data['topics'].items():
                        repo_name = topic_data['repository']
                        item_count = len(topic_data['items'])
                        new_lines.append(f"- **[[entities/github-repositories/repositories/{topic_name}.md|{repo_name}]]** ({item_count} items)")
                    new_lines.append("")
                    new_lines.append(line)
                elif not in_github_section or not line.startswith("- **[[entities/github-repositories/"):
                    if not (in_github_section and line.strip() == ""):
                        new_lines.append(line)
            
            # If we were still in github section at end of file
            if in_github_section:
                for topic_name, topic_data in organized_data['topics'].items():
                    repo_name = topic_data['repository']
                    item_count = len(topic_data['items'])
                    new_lines.append(f"- **[[entities/github-repositories/repositories/{topic_name}.md|{repo_name}]]** ({item_count} items)")
            
            updated_content = '\n'.join(new_lines)
        else:
            # Add new GitHub section
            github_section = f"""
### GitHub Repositories
GitHub repositories ({organized_data['total_items']} items across {len(organized_data['repositories'])} repositories):
"""
            
            for topic_name, topic_data in organized_data['topics'].items():
                repo_name = topic_data['repository']
                item_count = len(topic_data['items'])
                github_section += f"- **[[entities/github-repositories/repositories/{topic_name}.md|{repo_name}]]** ({item_count} items)\n"
            
            # Add to existing content or create new
            if existing_content:
                # Insert before "### Search Strategy" if it exists
                if "### Search Strategy" in existing_content:
                    updated_content = existing_content.replace("### Search Strategy", github_section + "\n### Search Strategy")
                else:
                    updated_content = existing_content + github_section
            else:
                # Create basic user.md with GitHub section
                updated_content = f"""## User Profile
- **Name**: User
- **Workspace**: Multi-source

## Communication Style

Professional and development-focused. Values structured information and collaborative documentation.

## Available Knowledge Sources

{github_section}
### Search Strategy
When asked about specific repositories or development topics, check the relevant repository file first, then explore individual items as needed. Use `list_files()` to discover available files and `read_file()` to access content.
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