#!/usr/bin/env python3
"""
Memory Wizard CLI - Interactive interface for all memory connectors.

A user-friendly command-line wizard that guides users through connecting
various memory sources to mem-agent format.
"""

import os
import sys
import getpass
from pathlib import Path
from typing import Dict, List, Optional
import subprocess

# Import connectors
from memory_connectors import BaseMemoryConnector, ChatGPTHistoryConnector, NotionConnector, NuclinoConnector
from memory_connectors.github_live import GitHubLiveConnector
from memory_connectors.google_docs_live import GoogleDocsLiveConnector

# Import memory path helpers from top-level package
from mcp_server.scripts.memory_setup import get_repo_root, get_default_memory_dir

# Registry of available connectors
CONNECTORS: Dict[str, type] = {
    'chatgpt': ChatGPTHistoryConnector,
    'notion': NotionConnector,
    'nuclino': NuclinoConnector,
    'github': GitHubLiveConnector,
    'google-docs': GoogleDocsLiveConnector,
}

# Connector metadata
CONNECTOR_INFO = {
    'chatgpt': {
        'name': 'ChatGPT History',
        'description': 'Import ChatGPT conversation exports',
        'type': 'export',
        'formats': ['.zip', '.json'],
        'example': '/Users/username/Downloads/chatgpt-export.zip'
    },
    'notion': {
        'name': 'Notion Workspace',
        'description': 'Import Notion workspace exports',
        'type': 'export',
        'formats': ['.zip'],
        'example': '/Users/username/Downloads/notion-export.zip'
    },
    'nuclino': {
        'name': 'Nuclino Workspace',
        'description': 'Import Nuclino workspace exports',
        'type': 'export',
        'formats': ['.zip'],
        'example': '/Users/username/Downloads/nuclino-export.zip'
    },
    'github': {
        'name': 'GitHub Live',
        'description': 'Connect GitHub repositories via API',
        'type': 'live',
        'formats': ['api'],
        'example': 'owner/repository or https://github.com/owner/repo'
    },
    'google-docs': {
        'name': 'Google Docs Live', 
        'description': 'Connect Google Drive folders via API',
        'type': 'live',
        'formats': ['api'],
        'example': 'folder_id or https://drive.google.com/drive/folders/...'
    }
}


class MemoryWizard:
    """Interactive wizard for memory connector setup."""
    
    def __init__(self):
        # Use the same default memory directory as the MCP server
        repo_root = get_repo_root()
        self.output_dir = get_default_memory_dir(repo_root)
        self.selected_connector = None
        self.connector_params = {}
    
    def run(self):
        """Run the interactive wizard."""
        print("🧙‍♂️ Memory Connector Wizard")
        print("=" * 50)
        print("Welcome! I'll help you connect your memory sources to mem-agent format.")
        print()
        
        try:
            # Step 1: Select connector
            self._select_connector()
            
            # Step 2: Configure output directory
            self._configure_output()
            
            # Step 3: Get connector-specific inputs
            self._get_connector_inputs()
            
            # Step 4: Confirm and run
            self._confirm_and_run()
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Run the wizard again anytime.")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            print("Please try again or check your inputs.")
            sys.exit(1)
    
    def _select_connector(self):
        """Let user select which connector to use."""
        print("📚 Available Memory Connectors:")
        print()
        
        connector_list = list(CONNECTOR_INFO.keys())
        
        for i, key in enumerate(connector_list, 1):
            info = CONNECTOR_INFO[key]
            type_emoji = "📤" if info['type'] == 'export' else "🔗"
            formats = ", ".join(info['formats'])
            
            print(f"  {i}. {type_emoji} {info['name']}")
            print(f"     {info['description']}")
            print(f"     Formats: {formats}")
            print()
        
        while True:
            try:
                choice = input(f"Select connector (1-{len(connector_list)}): ").strip()
                choice_idx = int(choice) - 1
                
                if 0 <= choice_idx < len(connector_list):
                    self.selected_connector = connector_list[choice_idx]
                    selected_info = CONNECTOR_INFO[self.selected_connector]
                    print(f"\n✅ Selected: {selected_info['name']}")
                    break
                else:
                    print(f"❌ Please enter a number between 1 and {len(connector_list)}")
                    
            except ValueError:
                print("❌ Please enter a valid number")
            except KeyboardInterrupt:
                raise
    
    def _configure_output(self):
        """Configure output directory."""
        print(f"\n📁 Output Directory Configuration")
        print(f"Default: {self.output_dir}")
        
        custom_path = input("Enter custom path (or press Enter for default): ").strip()
        
        if custom_path:
            self.output_dir = custom_path
            
        # Create directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        print(f"✅ Output directory: {self.output_dir}")
    
    def _get_connector_inputs(self):
        """Get connector-specific inputs."""
        info = CONNECTOR_INFO[self.selected_connector]
        
        print(f"\n🔧 {info['name']} Configuration")
        print("-" * 40)
        
        if info['type'] == 'export':
            self._get_export_inputs(info)
        else:
            self._get_live_inputs(info)
    
    def _get_export_inputs(self, info: Dict):
        """Get inputs for export-based connectors."""
        print(f"You need to provide the path to your {info['name'].lower()} export file.")
        print(f"Supported formats: {', '.join(info['formats'])}")
        print(f"Example: {info['example']}")
        print()
        
        while True:
            file_path = input("Enter file/directory path: ").strip().strip('"\'')
            
            if not file_path:
                print("❌ Please provide a file path")
                continue
                
            path_obj = Path(file_path)
            if not path_obj.exists():
                print(f"❌ Path does not exist: {file_path}")
                retry = input("Try again? (y/n): ").strip().lower()
                if retry != 'y':
                    sys.exit(0)
                continue
            
            # Validate format for files
            if path_obj.is_file():
                if path_obj.suffix.lower() not in info['formats'] and info['formats'] != ['.zip', '.json']:
                    print(f"⚠️ Warning: File extension {path_obj.suffix} not in expected formats {info['formats']}")
                    proceed = input("Proceed anyway? (y/n): ").strip().lower()
                    if proceed != 'y':
                        continue
            
            self.connector_params['source_path'] = file_path
            break
        
        # Get max items (optional)
        max_items = input("Max items to process (press Enter for no limit): ").strip()
        if max_items:
            try:
                self.connector_params['max_items'] = int(max_items)
            except ValueError:
                print("⚠️ Invalid number, ignoring max items limit")
        
        # Connector-specific options for exports too
        if self.selected_connector == 'chatgpt':
            self._get_chatgpt_options()
    
    def _get_live_inputs(self, info: Dict):
        """Get inputs for live API connectors."""
        # Get source path/ID
        print(f"You need to provide the {info['name'].lower()} source identifier.")
        print(f"Example: {info['example']}")
        print()
        
        source = input("Enter source (repository, folder ID, or URL): ").strip().strip('"\'')
        if not source:
            print("❌ Source is required for live connectors")
            sys.exit(1)
        
        self.connector_params['source_path'] = source
        
        # Get authentication token
        self._get_auth_token()
        
        # Get max items (optional)
        max_items = input("Max items to process (press Enter for default): ").strip()
        if max_items:
            try:
                self.connector_params['max_items'] = int(max_items)
            except ValueError:
                print("⚠️ Invalid number, using default max items")
        
        # Connector-specific options
        if self.selected_connector == 'github':
            self._get_github_options()
        elif self.selected_connector == 'chatgpt':
            self._get_chatgpt_options()
    
    def _get_auth_token(self):
        """Get authentication token for live connectors."""
        if self.selected_connector == 'github':
            print("\n🔑 GitHub Authentication")
            print("You need a Personal Access Token from: https://github.com/settings/tokens")
            print("Required scopes:")
            print("  - For public repos: public_repo")  
            print("  - For private repos: repo (full access)")
            print()
            
        elif self.selected_connector == 'google-docs':
            print("\n🔑 Google Drive Authentication")
            print("You need an OAuth 2.0 access token. Quick setup:")
            print("1. Go to: https://developers.google.com/oauthplayground/")
            print("2. Select 'Drive API v3' → 'https://www.googleapis.com/auth/drive.readonly'")
            print("3. Authorize APIs and exchange for token")
            print("Note: Tokens expire after ~1 hour")
            print()
        
        # Option to skip token (for GitHub public repos)
        if self.selected_connector == 'github':
            skip_token = input("Skip token for public repositories only? (y/n): ").strip().lower()
            if skip_token == 'y':
                self.connector_params['token'] = None
                return
        
        while True:
            try:
                token = getpass.getpass("Enter your access token (hidden input): ").strip()
                if token:
                    self.connector_params['token'] = token
                    break
                else:
                    if self.selected_connector == 'github':
                        self.connector_params['token'] = None
                        print("ℹ️ Proceeding without token (public repos only)")
                        break
                    else:
                        print("❌ Token is required for this connector")
            except KeyboardInterrupt:
                raise
    
    def _get_github_options(self):
        """Get GitHub-specific options."""
        print("\n⚙️ GitHub Options")
        
        include_issues = input("Include issues? (Y/n): ").strip().lower()
        self.connector_params['include_issues'] = include_issues != 'n'
        
        include_prs = input("Include pull requests? (Y/n): ").strip().lower() 
        self.connector_params['include_prs'] = include_prs != 'n'
        
        include_wiki = input("Include wiki pages? (Y/n): ").strip().lower()
        self.connector_params['include_wiki'] = include_wiki != 'n'
    
    def _get_chatgpt_options(self):
        """Get ChatGPT-specific options."""
        print("\n🤖 ChatGPT Categorization Options")
        print("Choose how to organize your ChatGPT conversations:")
        print()
        
        # Method selection
        print("[1] Keyword-based (Fast, Customizable)")
        print("    ├─ Uses predefined keywords to categorize conversations")
        print("    ├─ Quick processing, good for known domains")
        print("    └─ Allows keyword list customization")
        print()
        print("[2] AI-powered (Smart, Adaptive)")
        print("    ├─ Discovers categories from your conversation patterns")
        print("    ├─ Uses embeddings + clustering for semantic grouping")
        print("    └─ Generates custom category names for your data")
        print()
        
        while True:
            choice = input("Which method would you prefer? [1/2]: ").strip()
            if choice in ['1', '2']:
                method = 'keyword' if choice == '1' else 'ai'
                self.connector_params['method'] = method
                print(f"✅ Selected: {'Keyword-based' if method == 'keyword' else 'AI-powered'}")
                break
            print("Please enter 1 or 2")
        
        # Method-specific options
        if method == 'keyword':
            print("\n📝 Keyword Customization")
            edit_keywords = input("Do you want to customize the keyword categories? (y/N): ").strip().lower()
            if edit_keywords == 'y':
                self.connector_params['edit_keywords'] = True
                print("✅ You'll be prompted to edit keywords during processing")
        elif method == 'ai':
            print("\n🤖 AI Embedding Model Selection")
            print("[1] TF-IDF (Fast)")
            print("    ├─ Traditional statistical method, very fast")
            print("    └─ Requirements: None")
            print()
            print("[2] Nomic Embed (LM Studio)")
            print("    ├─ High-quality semantic embeddings via LM Studio API")
            print("    └─ Requirements: LM Studio with text-embedding-nomic-embed-text-v1.5")
            print()
            
            while True:
                embedding_choice = input("Which embedding model? [1/2]: ").strip()
                if embedding_choice in ['1', '2']:
                    embedding_model = 'tfidf' if embedding_choice == '1' else 'lmstudio'
                    self.connector_params['embedding_model'] = embedding_model
                    print(f"✅ Selected: {'TF-IDF' if embedding_model == 'tfidf' else 'Nomic Embed (LM Studio)'}")
                    break
                print("Please enter 1 or 2")
    
    def _confirm_and_run(self):
        """Show configuration summary and run connector."""
        print("\n📋 Configuration Summary")
        print("=" * 50)
        
        info = CONNECTOR_INFO[self.selected_connector]
        print(f"Connector: {info['name']}")
        print(f"Source: {self.connector_params['source_path']}")
        print(f"Output: {self.output_dir}")
        
        if 'max_items' in self.connector_params:
            print(f"Max items: {self.connector_params['max_items']}")
        
        if 'token' in self.connector_params:
            token_status = "✅ Provided" if self.connector_params['token'] else "⚠️ None (public only)"
            print(f"Auth token: {token_status}")
        
        if self.selected_connector == 'github':
            options = []
            if self.connector_params.get('include_issues', True):
                options.append('issues')
            if self.connector_params.get('include_prs', True): 
                options.append('PRs')
            if self.connector_params.get('include_wiki', True):
                options.append('wiki')
            print(f"GitHub options: {', '.join(options)}")
        elif self.selected_connector == 'chatgpt':
            method = self.connector_params.get('method', 'keyword')
            print(f"Method: {'Keyword-based' if method == 'keyword' else 'AI-powered'}")
            if method == 'keyword' and self.connector_params.get('edit_keywords'):
                print("Keyword editing: ✅ Enabled")
            elif method == 'ai':
                embedding = self.connector_params.get('embedding_model', 'tfidf')
                print(f"Embedding model: {'TF-IDF' if embedding == 'tfidf' else 'Nomic Embed (LM Studio)'}")
        
        print()
        confirm = input("Proceed with this configuration? (Y/n): ").strip().lower()
        
        if confirm == 'n':
            print("❌ Operation cancelled")
            sys.exit(0)
        
        print("\n🚀 Running connector...")
        print("-" * 30)
        
        success = self._run_connector()
        
        if success:
            self._show_success()
        else:
            self._show_failure()
    
    def _run_connector(self) -> bool:
        """Run the selected connector with configured parameters."""
        try:
            # Build command (run as module for proper package imports)
            cmd = [
                sys.executable, "-m", "memory_connectors.memory_connect",
                self.selected_connector,
                self.connector_params['source_path'],
                "--output", self.output_dir
            ]
            
            # Add optional parameters
            if 'max_items' in self.connector_params:
                cmd.extend(["--max-items", str(self.connector_params['max_items'])])
            
            if 'token' in self.connector_params and self.connector_params['token']:
                cmd.extend(["--token", self.connector_params['token']])
            
            # Add GitHub-specific options
            if self.selected_connector == 'github':
                if not self.connector_params.get('include_issues', True):
                    cmd.append("--no-include-issues")
                if not self.connector_params.get('include_prs', True):
                    cmd.append("--no-include-prs") 
                if not self.connector_params.get('include_wiki', True):
                    cmd.append("--no-include-wiki")
            
            # Add ChatGPT-specific options
            elif self.selected_connector == 'chatgpt':
                if 'method' in self.connector_params:
                    cmd.extend(["--method", self.connector_params['method']])
                
                if self.connector_params.get('edit_keywords'):
                    cmd.append("--edit-keywords")
                
                if 'embedding_model' in self.connector_params:
                    cmd.extend(["--embedding-model", self.connector_params['embedding_model']])
            
            # Run the connector
            result = subprocess.run(cmd, capture_output=False, text=True)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ Error running connector: {e}")
            return False
    
    def _show_success(self):
        """Show success message and next steps."""
        print("\n🎉 Memory Connection Successful!")
        print("=" * 50)
        print(f"📁 Memory files created at: {self.output_dir}")
        print()
        
        # Show user.md location
        user_md = Path(self.output_dir) / "user.md"
        if user_md.exists():
            print(f"👤 User profile: {user_md}")
            print("   This file contains navigation to all your memory sources")
        
        print("\n📚 Next Steps:")
        print("1. Start your mem-agent server:")
        print("   make run-agent")
        print()
        print("2. Configure Claude Desktop with the MCP server:")
        print("   make generate-mcp-json")
        print()
        print("3. Test your memory system by asking Claude questions about your data!")
        print()
        
        # Show example questions based on connector
        self._show_example_questions()
    
    def _show_example_questions(self):
        """Show example questions users can ask."""
        info = CONNECTOR_INFO[self.selected_connector]
        
        print("💡 Example questions to ask Claude:")
        
        if self.selected_connector == 'chatgpt':
            print("   • \"What are my thoughts on AI agents?\"")
            print("   • \"Summarize my recent technical discussions\"")
            print("   • \"What projects have I been working on?\"")
            
        elif self.selected_connector == 'github':
            print("   • \"What does this repository do?\"") 
            print("   • \"What are the main issues in my project?\"")
            print("   • \"Summarize recent pull requests\"")
            
        elif self.selected_connector == 'google-docs':
            print("   • \"What documents do I have about [topic]?\"")
            print("   • \"Summarize my meeting notes\"")
            print("   • \"What's in my project planning docs?\"")
            
        elif self.selected_connector in ['notion', 'nuclino']:
            print("   • \"What's in my workspace about [topic]?\"")
            print("   • \"Show me my documentation on [subject]\"")
            print("   • \"What notes do I have about [project]?\"")
    
    def _show_failure(self):
        """Show failure message with troubleshooting tips."""
        print("\n❌ Memory Connection Failed")
        print("=" * 50)
        
        print("🔧 Troubleshooting tips:")
        
        info = CONNECTOR_INFO[self.selected_connector]
        
        if info['type'] == 'export':
            print("• Check that your export file exists and is not corrupted")
            print("• Verify the file format matches the expected format")
            print("• Try with a smaller dataset using --max-items")
            
        else:  # live connectors
            print("• Verify your authentication token is valid and not expired")
            print("• Check that you have permission to access the specified source")
            
            if self.selected_connector == 'github':
                print("• For private repos, ensure your token has 'repo' scope")
                print("• For public repos, you can try without a token")
                
            elif self.selected_connector == 'google-docs':
                print("• Ensure your token has 'drive.readonly' scope (not 'drive.apps.readonly')")
                print("• Get a fresh token from Google OAuth Playground")
                print("• Check that the folder ID is correct")
        
        print("\n🔄 You can run the wizard again to try different settings")


def main():
    """Main entry point."""
    wizard = MemoryWizard()
    wizard.run()


if __name__ == "__main__":
    main()