"""
Convert parsed ChatGPT conversations to mem-agent memory format.
"""
import os
import json
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Set
from pathlib import Path

from .parser import ChatGPTParser
from .types import ParsedConversation, ParsedMessage


class MemoryConverter:
    def __init__(self, memory_path: str):
        self.memory_path = Path(memory_path)
        self.chatgpt_dir = self.memory_path / "chatgpt-history"
        self.topics_dir = self.chatgpt_dir / "topics"
        self.conversations_dir = self.chatgpt_dir / "conversations"
        
    def convert_export(self, export_path: str, max_conversations: int = None) -> Dict[str, any]:
        """Convert entire ChatGPT export to mem-agent format"""
        print(f"Converting ChatGPT export from: {export_path}")
        print(f"Target memory path: {self.memory_path}")
        
        # Parse the export
        parser = ChatGPTParser()
        export_data = parser.parse_export(export_path)
        conversations = export_data["conversations"]
        user_profile = export_data.get("user_profile")
        
        if max_conversations:
            conversations = conversations[:max_conversations]
        
        print(f"Processing {len(conversations)} conversations...")
        
        # Create directory structure
        self._create_directories()
        
        # Organize conversations by topics
        topic_groups = self._organize_by_topics(conversations)
        
        # Convert conversations to markdown
        conversion_stats = {
            "total_conversations": len(conversations),
            "topics_created": 0,
            "files_written": 0,
            "empty_conversations": 0
        }
        
        # Write individual conversation files
        for i, conv in enumerate(conversations):
            if not conv.messages:
                conversion_stats["empty_conversations"] += 1
                continue
                
            conv_file = self._write_conversation_file(conv, i)
            if conv_file:
                conversion_stats["files_written"] += 1
        
        # Write topic overview files
        for topic, topic_conversations in topic_groups.items():
            self._write_topic_file(topic, topic_conversations)
            conversion_stats["topics_created"] += 1
        
        # Write main index file
        self._write_index_file(topic_groups, user_profile, conversion_stats)
        
        # Write user profile if available
        if user_profile:
            self._write_user_profile(user_profile)
        
        print(f"Conversion complete:")
        print(f"  - {conversion_stats['files_written']} conversation files written")
        print(f"  - {conversion_stats['topics_created']} topic files created")
        print(f"  - {conversion_stats['empty_conversations']} empty conversations skipped")
        
        return conversion_stats
    
    def _create_directories(self):
        """Create necessary directory structure"""
        self.chatgpt_dir.mkdir(parents=True, exist_ok=True)
        self.topics_dir.mkdir(exist_ok=True)
        self.conversations_dir.mkdir(exist_ok=True)
    
    def _organize_by_topics(self, conversations: List[ParsedConversation]) -> Dict[str, List[ParsedConversation]]:
        """Organize conversations into topic groups using simple keyword matching"""
        # Define topic keywords (could be enhanced with ML/LLM categorization)
        topic_keywords = {
            "ai-agents": ["agent", "autonomous", "ai agent", "multi-agent", "agent framework"],
            "llms": ["llm", "language model", "gpt", "claude", "chatgpt", "openai", "anthropic"],
            "semantic-search": ["semantic search", "embedding", "vector", "similarity", "retrieval"],
            "rag": ["rag", "retrieval augmented", "context retrieval", "knowledge base"],
            "dria": ["dria", "decentralized", "p2p", "distributed ai"],
            "programming": ["python", "javascript", "typescript", "code", "programming", "debug"],
            "data-science": ["data science", "machine learning", "ml", "analysis", "dataset"],
            "product-strategy": ["product", "strategy", "market", "user", "business"],
            "technical-discussion": ["architecture", "system", "design", "infrastructure"],
            "personal": ["personal", "life", "career", "advice", "help"]
        }
        
        topic_groups = defaultdict(list)
        uncat_conversations = []
        
        for conv in conversations:
            # Combine title and first few messages for categorization
            title = conv.title or "Untitled"
            text_for_categorization = title.lower()
            for msg in conv.messages[:3]:  # Check first 3 messages
                if msg.content:
                    text_for_categorization += " " + msg.content.lower()[:200]
            
            assigned_topics = []
            for topic, keywords in topic_keywords.items():
                for keyword in keywords:
                    if keyword in text_for_categorization:
                        assigned_topics.append(topic)
                        break
            
            # Assign to first matching topic or "uncategorized"
            if assigned_topics:
                topic_groups[assigned_topics[0]].append(conv)
            else:
                topic_groups["uncategorized"].append(conv)
        
        return dict(topic_groups)
    
    def _write_conversation_file(self, conv: ParsedConversation, index: int) -> str:
        """Write a single conversation to markdown file"""
        if not conv.messages:
            return None
            
        # Create safe filename
        title = conv.title or "Untitled"
        safe_title = re.sub(r'[^\w\s-]', '', title)
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        filename = f"{conv.id}-{safe_title[:50]}.md"
        file_path = self.conversations_dir / filename
        
        # Generate markdown content
        content = f"# {title}\n\n"
        content += f"**Created:** {conv.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"**Updated:** {conv.updated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"**Messages:** {conv.message_count}\n\n"
        
        if conv.user_profile:
            content += f"**User Profile:** {conv.user_profile[:100]}...\n\n"
        
        content += "---\n\n"
        
        # Add messages
        for i, msg in enumerate(conv.messages):
            role_display = {
                "user": "**You**",
                "assistant": "**Assistant**", 
                "system": "**System**"
            }.get(msg.role, f"**{msg.role.title()}**")
            
            content += f"## {role_display}"
            if msg.timestamp:
                content += f" - {msg.timestamp.strftime('%H:%M:%S')}"
            content += "\n\n"
            
            # Handle None content
            msg_content = msg.content or "[No content]"
            content += f"{msg_content}\n\n"
            
            if msg.model and msg.role == "assistant":
                content += f"*Model: {msg.model}*\n\n"
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return str(file_path)
    
    def _write_topic_file(self, topic: str, conversations: List[ParsedConversation]):
        """Write topic overview file with links to conversations"""
        filename = f"{topic}.md"
        file_path = self.topics_dir / filename
        
        # Generate content
        topic_display = topic.replace('-', ' ').replace('_', ' ').title()
        content = f"# {topic_display}\n\n"
        content += f"**Conversations:** {len(conversations)}\n"
        content += f"**Topic:** {topic}\n\n"
        
        # Add summary
        total_messages = sum(conv.message_count for conv in conversations)
        date_range = self._get_date_range(conversations)
        content += f"This topic contains {len(conversations)} conversations with {total_messages} total messages"
        if date_range:
            content += f" from {date_range}"
        content += ".\n\n"
        
        # Add conversation links
        content += "## Conversations\n\n"
        
        # Sort by date (newest first)
        sorted_conversations = sorted(conversations, key=lambda c: c.updated_at, reverse=True)
        
        for conv in sorted_conversations:
            # Create link to conversation file
            conv_title = conv.title or "Untitled"
            safe_title = re.sub(r'[^\w\s-]', '', conv_title)
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            link_target = f"../conversations/{conv.id}-{safe_title[:50]}.md"
            
            content += f"- **[[{link_target}|{conv_title}]]** "
            content += f"({conv.message_count} messages, {conv.updated_at.strftime('%Y-%m-%d')})\n"
        
        content += "\n"
        
        # Add related topics
        content += "## Related Topics\n\n"
        content += "- [[../index.md|ChatGPT History Overview]]\n"
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _write_index_file(self, topic_groups: Dict[str, List[ParsedConversation]], 
                         user_profile, conversion_stats: Dict):
        """Write main index file for ChatGPT history"""
        file_path = self.chatgpt_dir / "index.md"
        
        content = "# ChatGPT Conversation History\n\n"
        content += f"**Converted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += f"**Total Conversations:** {conversion_stats['total_conversations']}\n"
        content += f"**Topics:** {conversion_stats['topics_created']}\n\n"
        
        if user_profile and user_profile.name:
            content += f"**User:** {user_profile.name}\n"
            if user_profile.role:
                content += f"**Role:** {user_profile.role}\n"
            content += "\n"
        
        content += "This directory contains your ChatGPT conversation history organized by topics. "
        content += "Use the mem-agent tools to search and explore these conversations.\n\n"
        
        # Add topics overview
        content += "## Topics\n\n"
        
        # Sort topics by conversation count
        sorted_topics = sorted(topic_groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        for topic, conversations in sorted_topics:
            topic_display = topic.replace('-', ' ').replace('_', ' ').title()
            content += f"- **[[topics/{topic}.md|{topic_display}]]** ({len(conversations)} conversations)\n"
        
        content += "\n## Usage Examples\n\n"
        content += "Use these mem-agent commands to explore your history:\n\n"
        content += "```python\n"
        content += "# List all topics\n"
        content += "list_files()\n\n"
        content += "# Read a topic overview\n"
        content += 'read_file("chatgpt-history/topics/ai-agents.md")\n\n'
        content += "# Follow a conversation link\n"
        content += 'go_to_link("[[../conversations/conv_0-ai-agent-discussion.md]]")\n'
        content += "```\n"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _write_user_profile(self, user_profile):
        """Write user profile to main memory directory"""
        file_path = self.memory_path / "user.md"
        
        content = "# User Profile\n\n"
        content += f"**Extracted from ChatGPT conversations**\n"
        content += f"**Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        if user_profile.name:
            content += f"**Name:** {user_profile.name}\n"
        if user_profile.role:
            content += f"**Role:** {user_profile.role}\n"
        if user_profile.company:
            content += f"**Company:** {user_profile.company}\n"
        if user_profile.location:
            content += f"**Location:** {user_profile.location}\n"
        
        content += "\n"
        
        if user_profile.communication_style:
            content += "## Communication Style\n\n"
            content += f"{user_profile.communication_style}\n\n"
        
        content += "## ChatGPT History\n\n"
        content += "Your complete ChatGPT conversation history is available at:\n"
        content += "- [[chatgpt-history/index.md|ChatGPT History Overview]]\n\n"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _get_date_range(self, conversations: List[ParsedConversation]) -> str:
        """Get date range for a list of conversations"""
        if not conversations:
            return ""
        
        dates = [conv.created_at for conv in conversations]
        min_date = min(dates)
        max_date = max(dates)
        
        if min_date.date() == max_date.date():
            return min_date.strftime('%Y-%m-%d')
        else:
            return f"{min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}"