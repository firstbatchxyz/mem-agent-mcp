#!/usr/bin/env python3
"""
Memory Connect CLI

Unified CLI for connecting various memory sources to mem-agent format.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Type

from memory_connectors import BaseMemoryConnector, ChatGPTHistoryConnector, NotionConnector, NuclinoConnector
from memory_connectors.chatgpt_history.embedding_connector import ChatGPTEmbeddingConnector
from memory_connectors.github_live import GitHubLiveConnector
from memory_connectors.google_docs_live import GoogleDocsLiveConnector


# Registry of available connectors
CONNECTORS: Dict[str, Type[BaseMemoryConnector]] = {
    'chatgpt': ChatGPTHistoryConnector,
    'chatgpt-ai': ChatGPTEmbeddingConnector, 
    'notion': NotionConnector,
    'nuclino': NuclinoConnector,
    'github': GitHubLiveConnector,
    'google-docs': GoogleDocsLiveConnector,
}

# Special handling for ChatGPT dual methodologies
CHATGPT_METHODS = {
    'keyword': {
        'connector': ChatGPTHistoryConnector,
        'name': 'Keyword-based (Fast, Customizable)',
        'description': 'Uses predefined keywords to categorize conversations. Quick processing, good for known domains. Allows keyword list customization.'
    },
    'ai': {
        'connector': ChatGPTEmbeddingConnector,
        'name': 'AI-powered (Smart, Adaptive)', 
        'description': 'Discovers categories from your conversation patterns using embeddings + clustering. Generates custom category names for your data.'
    }
}


def choose_chatgpt_method() -> tuple:
    """Interactive ChatGPT method selection with embedding options."""
    print("\n📊 Choose ChatGPT categorization method:")
    print()
    
    methods = list(CHATGPT_METHODS.keys())
    for i, method in enumerate(methods, 1):
        method_info = CHATGPT_METHODS[method]
        print(f"[{i}] {method_info['name']}")
        print(f"    ├─ {method_info['description']}")
        if method == 'ai':
            print(f"    └─ Note: Requires additional dependencies (transformers, torch, scikit-learn)")
        print()
    
    while True:
        try:
            choice = input("Which method would you prefer? [1/2]: ").strip()
            if choice in ['1', '2']:
                selected_method = methods[int(choice) - 1]
                print(f"\n✅ Selected: {CHATGPT_METHODS[selected_method]['name']}")
                
                # If AI method selected, ask for embedding model
                if selected_method == 'ai':
                    embedding_model = choose_embedding_model()
                    return selected_method, embedding_model
                else:
                    return selected_method, None
            else:
                print("❌ Please enter 1 or 2")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Operation cancelled")
            sys.exit(1)

def choose_embedding_model() -> str:
    """Interactive embedding model selection for AI method."""
    print("\n🤖 Choose embedding model:")
    print()
    
    embedding_options = {
        'tfidf': {
            'name': 'TF-IDF (Fast)',
            'description': 'Traditional statistical method, very fast, no neural networks',
            'requirements': 'None'
        },
        'lmstudio': {
            'name': 'Nomic Embed (LM Studio)',
            'description': 'High-quality semantic embeddings via LM Studio API',
            'requirements': 'LM Studio running with text-embedding-nomic-embed-text-v1.5'
        }
    }
    
    options = list(embedding_options.keys())
    for i, option in enumerate(options, 1):
        info = embedding_options[option]
        print(f"[{i}] {info['name']}")
        print(f"    ├─ {info['description']}")
        print(f"    └─ Requirements: {info['requirements']}")
        print()
    
    while True:
        try:
            choice = input("Which embedding model would you prefer? [1/2]: ").strip()
            if choice in ['1', '2']:
                selected_option = options[int(choice) - 1]
                info = embedding_options[selected_option]
                print(f"\n✅ Selected: {info['name']}")
                
                # Return appropriate model name
                if selected_option == 'tfidf':
                    return 'tfidf'
                elif selected_option == 'lmstudio':
                    return 'lmstudio:text-embedding-nomic-embed-text-v1.5'
            else:
                print("❌ Please enter 1 or 2")
        except (ValueError, KeyboardInterrupt):
            print("\n❌ Operation cancelled")
            sys.exit(1)

def edit_chatgpt_keywords():
    """Interactive keyword list editor for ChatGPT categorization."""
    print("🔧 ChatGPT Keyword Editor")
    print()
    
    # Get current keywords from the connector
    try:
        from memory_connectors.chatgpt_history.connector import ChatGPTHistoryConnector
        # This is a bit hacky - we'll read the keywords from the source code
        import inspect
        import ast
        
        # Read the current keywords from the connector source
        connector_file = Path(__file__).parent / 'chatgpt_history' / 'connector.py'
        
        with open(connector_file, 'r') as f:
            source = f.read()
        
        # Parse the AST to find the topic_keywords dictionary
        tree = ast.parse(source)
        current_keywords = None
        
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and 
                any(target.id == 'topic_keywords' for target in node.targets if isinstance(target, ast.Name))):
                # Found the topic_keywords assignment
                current_keywords = ast.literal_eval(node.value)
                break
        
        if not current_keywords:
            print("❌ Could not read current keywords from connector")
            return
            
    except Exception as e:
        print(f"❌ Error reading current keywords: {e}")
        return
    
    # Display current keywords
    print("📋 Current keyword categories:")
    print()
    
    for i, (topic, keywords) in enumerate(current_keywords.items(), 1):
        print(f"[{i}] {topic}")
        print(f"    Keywords: {', '.join(keywords)}")
        print()
    
    # Menu options
    while True:
        print("Options:")
        print("  [a] Add new category")
        print("  [e] Edit existing category") 
        print("  [d] Delete category")
        print("  [s] Save changes")
        print("  [q] Quit without saving")
        print()
        
        choice = input("Choose an option: ").strip().lower()
        
        if choice == 'q':
            print("❌ Changes discarded")
            return
        elif choice == 's':
            save_keywords(current_keywords, connector_file)
            print("✅ Keywords saved successfully!")
            return
        elif choice == 'a':
            add_keyword_category(current_keywords)
        elif choice == 'e':
            edit_keyword_category(current_keywords)
        elif choice == 'd':
            delete_keyword_category(current_keywords)
        else:
            print("❌ Invalid option")

def add_keyword_category(keywords_dict):
    """Add a new keyword category."""
    print("\n➕ Add New Category")
    
    category_name = input("Category name (e.g., 'machine-learning'): ").strip().lower()
    if not category_name:
        print("❌ Category name cannot be empty")
        return
    
    if category_name in keywords_dict:
        print(f"❌ Category '{category_name}' already exists")
        return
    
    print("Enter keywords separated by commas:")
    keywords_input = input("Keywords: ").strip()
    if not keywords_input:
        print("❌ Keywords cannot be empty")
        return
    
    keywords_list = [kw.strip().lower() for kw in keywords_input.split(',') if kw.strip()]
    keywords_dict[category_name] = keywords_list
    
    print(f"✅ Added category '{category_name}' with {len(keywords_list)} keywords")

def edit_keyword_category(keywords_dict):
    """Edit an existing keyword category."""
    print("\n✏️  Edit Category")
    
    categories = list(keywords_dict.keys())
    for i, cat in enumerate(categories, 1):
        print(f"[{i}] {cat}")
    
    try:
        choice = int(input("Select category to edit: ")) - 1
        if 0 <= choice < len(categories):
            category = categories[choice]
            current_keywords = keywords_dict[category]
            
            print(f"\nCurrent keywords for '{category}': {', '.join(current_keywords)}")
            print("Enter new keywords (separated by commas):")
            new_keywords_input = input("Keywords: ").strip()
            
            if new_keywords_input:
                new_keywords = [kw.strip().lower() for kw in new_keywords_input.split(',') if kw.strip()]
                keywords_dict[category] = new_keywords
                print(f"✅ Updated '{category}' with {len(new_keywords)} keywords")
            else:
                print("❌ No changes made")
        else:
            print("❌ Invalid selection")
    except ValueError:
        print("❌ Invalid input")

def delete_keyword_category(keywords_dict):
    """Delete a keyword category."""
    print("\n🗑️  Delete Category")
    
    categories = list(keywords_dict.keys())
    for i, cat in enumerate(categories, 1):
        print(f"[{i}] {cat}")
    
    try:
        choice = int(input("Select category to delete: ")) - 1
        if 0 <= choice < len(categories):
            category = categories[choice]
            
            confirm = input(f"Are you sure you want to delete '{category}'? [y/N]: ").strip().lower()
            if confirm == 'y':
                del keywords_dict[category]
                print(f"✅ Deleted category '{category}'")
            else:
                print("❌ Delete cancelled")
        else:
            print("❌ Invalid selection")
    except ValueError:
        print("❌ Invalid input")

def save_keywords(keywords_dict, connector_file):
    """Save updated keywords back to the connector file."""
    try:
        with open(connector_file, 'r') as f:
            content = f.read()
        
        # Find and replace the topic_keywords dictionary
        import re
        
        # Pattern to match the topic_keywords dictionary
        pattern = r'topic_keywords = \{[^}]*(?:\{[^}]*\}[^}]*)*\}'
        
        # Create new keywords string
        new_keywords_str = "topic_keywords = {\n"
        for topic, keywords in keywords_dict.items():
            keywords_str = "', '".join(keywords)
            new_keywords_str += f"            '{topic}': ['{keywords_str}'],\n"
        new_keywords_str += "        }"
        
        # Replace in content
        new_content = re.sub(pattern, new_keywords_str, content, flags=re.DOTALL)
        
        # Write back to file
        with open(connector_file, 'w') as f:
            f.write(new_content)
            
    except Exception as e:
        print(f"❌ Error saving keywords: {e}")
        raise

def list_connectors():
    """List all available memory connectors."""
    print("🔌 Available Memory Connectors:")
    print()
    
    # Special handling for ChatGPT
    print("  chatgpt")
    print("    Name: ChatGPT History (Multiple Methods)")
    print("    Formats: .zip, .json")
    print("    Methods: Keyword-based, AI-powered")
    print()
    
    for name, connector_class in CONNECTORS.items():
        if name.startswith('chatgpt'):
            continue  # Skip individual ChatGPT variants
        
        connector = connector_class("")  # Dummy instance for info
        print(f"  {name}")
        print(f"    Name: {connector.connector_name}")
        print(f"    Formats: {', '.join(connector.supported_formats)}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Connect memory sources to mem-agent format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # ChatGPT with interactive method selection
  python memory_connect.py chatgpt /path/to/chatgpt-export.zip
  
  # ChatGPT AI-powered with different embedding models
  python memory_connect.py chatgpt /path/to/export.zip --method ai --embedding-model tfidf
  python memory_connect.py chatgpt /path/to/export.zip --method ai --embedding-model lmstudio
  
  # ChatGPT with LM Studio (custom URL)
  python memory_connect.py chatgpt /path/to/export.zip --method ai --embedding-model lmstudio --lmstudio-url http://localhost:8080
  
  # ChatGPT keyword-based
  python memory_connect.py chatgpt /path/to/export.zip --method keyword --output ./memory/custom
  
  # Edit ChatGPT keyword categories
  python memory_connect.py --edit-keywords
  
  # Other connectors
  python memory_connect.py github "owner/repo1,owner/repo2" --token YOUR_TOKEN
  python memory_connect.py github "microsoft/vscode" --max-items 50
  python memory_connect.py google-docs "FOLDER_ID_OR_URL" --token YOUR_ACCESS_TOKEN
  
  # List available connectors
  python memory_connect.py --list
        """
    )
    
    parser.add_argument(
        'connector',
        nargs='?',
        choices=list(CONNECTORS.keys()),
        help='Memory connector to use'
    )
    
    parser.add_argument(
        'source',
        nargs='?',
        help='Path to source data'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='memory/mcp-server',
        help='Output directory for organized memory (default: memory/mcp-server)'
    )
    
    parser.add_argument(
        '--max-items', '-m',
        type=int,
        help='Maximum number of items to process'
    )
    
    parser.add_argument(
        '--token', '-t',
        help='API token for live connectors (GitHub personal access token)'
    )
    
    # Include/exclude flags for GitHub
    parser.add_argument(
        '--include-issues',
        dest='include_issues',
        action='store_true',
        default=True,
        help='Include issues (default: True, GitHub only)'
    )
    parser.add_argument(
        '--no-include-issues',
        dest='include_issues',
        action='store_false',
        help='Exclude issues (GitHub only)'
    )
    
    parser.add_argument(
        '--include-prs',
        dest='include_prs',
        action='store_true', 
        default=True,
        help='Include pull requests (default: True, GitHub only)'
    )
    parser.add_argument(
        '--no-include-prs',
        dest='include_prs',
        action='store_false',
        help='Exclude pull requests (GitHub only)'
    )
    
    parser.add_argument(
        '--include-wiki',
        dest='include_wiki',
        action='store_true',
        default=True,
        help='Include wiki pages (default: True, GitHub only)'
    )
    parser.add_argument(
        '--no-include-wiki',
        dest='include_wiki',
        action='store_false',
        help='Exclude wiki pages (GitHub only)'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available connectors'
    )
    
    parser.add_argument(
        '--method',
        choices=['keyword', 'ai'],
        help='ChatGPT categorization method (skips interactive selection)'
    )
    
    parser.add_argument(
        '--edit-keywords',
        action='store_true',
        help='Edit keyword lists for ChatGPT keyword-based categorization'
    )
    
    parser.add_argument(
        '--embedding-model',
        choices=['tfidf', 'lmstudio'],
        help='Embedding model for AI-powered ChatGPT categorization'
    )
    
    parser.add_argument(
        '--lmstudio-url',
        default='http://localhost:1234',
        help='LM Studio server URL (default: http://localhost:1234)'
    )
    
    args = parser.parse_args()
    
    # Handle list command
    if args.list:
        list_connectors()
        return
    
    # Handle keyword editing
    if args.edit_keywords:
        edit_chatgpt_keywords()
        return
    
    # Validate required arguments
    if not args.connector or not args.source:
        parser.print_help()
        return
    
    # Special handling for ChatGPT method selection
    embedding_model = None
    if args.connector == 'chatgpt':
        if args.method:
            method = args.method
            print(f"✅ Using {CHATGPT_METHODS[method]['name']} (specified via --method)")
            # For AI method, use specified embedding model or default to TF-IDF
            if method == 'ai':
                if args.embedding_model:
                    if args.embedding_model == 'lmstudio':
                        embedding_model = 'lmstudio:text-embedding-nomic-embed-text-v1.5'
                    else:
                        embedding_model = 'tfidf'
                else:
                    embedding_model = 'tfidf'
        else:
            method_result = choose_chatgpt_method()
            if isinstance(method_result, tuple):
                method, embedding_model = method_result
            else:
                method = method_result
        connector_class = CHATGPT_METHODS[method]['connector']
    else:
        connector_class = CONNECTORS[args.connector]
    
    connector_instance = connector_class("")  # Dummy for checking formats
    is_live_connector = 'api' in connector_instance.supported_formats
    
    # Validate source path exists (skip for live connectors)
    if not is_live_connector:
        source_path = Path(args.source)
        if not source_path.exists():
            print(f"❌ Source path does not exist: {source_path}")
            sys.exit(1)
    
    # Validate file format (skip for live connectors)
    if not is_live_connector:
        source_ext = source_path.suffix.lower() if source_path.is_file() else 'directory'
        supported_formats = connector_instance.supported_formats + ['directory'] if args.connector == 'chatgpt' else connector_instance.supported_formats
        if source_ext not in supported_formats:
            print(f"❌ Unsupported format '{source_ext}' for {args.connector} connector")
            print(f"   Supported formats: {', '.join(supported_formats)}")
            sys.exit(1)
    
    # Handle authentication for live connectors
    if is_live_connector:
        token = args.token
        if token is None:  # No --token argument provided at all
            # Interactive token input
            try:
                import getpass
                if args.connector == 'github':
                    print("🔑 GitHub Personal Access Token required")
                    print("   Create one at: https://github.com/settings/tokens")
                    print("   Required scopes: repo (for private repos) or public_repo (for public only)")
                    print()
                    print("   Press Enter to proceed without token (public API, rate limited)")
                    token = getpass.getpass("Enter your GitHub token (or press Enter): ")
                elif args.connector == 'google-docs':
                    print("🔑 Google Docs Access Token required")
                    print("   Get OAuth 2.0 token with Google Drive API access")
                    print("   Required scopes: https://www.googleapis.com/auth/drive.readonly")
                    print()
                    token = getpass.getpass("Enter your Google Drive access token: ")
            except (EOFError, KeyboardInterrupt):
                print("⚠️ No authentication token provided - proceeding with public API (rate limited)")
                token = None
        
        if token and not token.strip():
            token = None
    
    # Create and run connector
    try:
        print(f"🚀 Starting {args.connector} connector...")
        if is_live_connector:
            print(f"   Repositories: {args.source}")
        else:
            print(f"   Source: {source_path}")
        print(f"   Output: {args.output}")
        if args.max_items:
            print(f"   Limit: {args.max_items} items")
        print()
        
        # Create connector with appropriate parameters
        if is_live_connector:
            if args.connector == 'github':
                connector = connector_class(
                    args.output,
                    token=token,
                    include_issues=args.include_issues,
                    include_prs=args.include_prs,
                    include_wiki=args.include_wiki,
                    max_items=args.max_items
                )
            elif args.connector == 'google-docs':
                connector = connector_class(
                    args.output,
                    access_token=token,
                    max_items=args.max_items
                )
            else:
                connector = connector_class(
                    args.output,
                    token=token,
                    max_items=args.max_items
                )
        else:
            # Handle ChatGPT with embedding model
            if args.connector == 'chatgpt' and embedding_model:
                connector_kwargs = {
                    'output_path': args.output,
                    'model_name': embedding_model
                }
                if args.lmstudio_url and 'lmstudio:' in embedding_model:
                    connector_kwargs['lmstudio_base_url'] = args.lmstudio_url
                
                connector = connector_class(**connector_kwargs)
                print(f"🤖 Using embedding model: {embedding_model}")
            else:
                connector = connector_class(args.output)
            
        connector.connect(args.source, max_items=args.max_items)
        
        print()
        print("🎉 Memory connection completed successfully!")
        print(f"📁 Memory files created in: {args.output}")
        
    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()