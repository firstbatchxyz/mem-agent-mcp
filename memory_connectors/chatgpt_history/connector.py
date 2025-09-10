"""
ChatGPT History Memory Connector

Converts ChatGPT conversation exports into mem-agent memory format.
"""

import os
from typing import Dict, Any, List
from pathlib import Path

from ..base import BaseMemoryConnector
from .parser import ChatGPTParser


class ChatGPTHistoryConnector(BaseMemoryConnector):
    """Connector for ChatGPT conversation history exports."""
    
    @property
    def connector_name(self) -> str:
        return "ChatGPT History"
    
    @property
    def supported_formats(self) -> list:
        return ['.zip', '.json']
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """Extract conversations from ChatGPT export."""
        print(f"📂 Parsing ChatGPT export from {source_path}")
        
        # Parse the export using our existing parser
        parser = ChatGPTParser()
        parsed_data = parser.parse_export(source_path)
        
        return {
            'conversations': parsed_data['conversations'],
            'user_profile': parsed_data['user_profile'],
            'total_conversations': len(parsed_data['conversations']),
            'source_path': source_path
        }
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize conversations by topics using existing converter logic."""
        conversations = extracted_data['conversations']
        user_profile = extracted_data['user_profile']
        
        print(f"🗂️ Organizing {len(conversations)} conversations by topics")
        
        # Use existing converter to organize by topics
        # We'll extract the organization logic from convert_export
        topics = {}
        topic_conversations = {}
        
        # Keywords for topic categorization (from existing converter)
        topic_keywords = {
            'dria': ['dria', 'firstbatch', 'decentralized', 'synthetic data', 'network'],
            'ai-agents': ['agent', 'multi-agent', 'autonomous', 'langchain', 'crew'],
            'llms': ['llm', 'language model', 'gpt', 'claude', 'transformer', 'fine-tuning'],
            'product-strategy': ['strategy', 'product', 'market', 'business', 'roadmap'],
            'programming': ['python', 'javascript', 'code', 'programming', 'development'],
            'data-science': ['data science', 'machine learning', 'analytics', 'model'],
            'semantic-search': ['semantic search', 'embeddings', 'vector', 'similarity'],
            'rag': ['rag', 'retrieval', 'augmented generation', 'vector database'],
            'technical-discussion': ['architecture', 'system design', 'technical', 'infrastructure'],
            'personal': ['personal', 'learning', 'career', 'advice']
        }
        
        # Categorize conversations
        for conversation in conversations:
            assigned_topics = []
            title_lower = (conversation.title or '').lower()
            
            # Check against each topic's keywords
            for topic, keywords in topic_keywords.items():
                if any(keyword in title_lower for keyword in keywords):
                    assigned_topics.append(topic)
            
            # Default to uncategorized if no topics match
            if not assigned_topics:
                assigned_topics = ['uncategorized']
            
            # Add to topics (use first matching topic for primary categorization)
            primary_topic = assigned_topics[0]
            if primary_topic not in topic_conversations:
                topic_conversations[primary_topic] = []
            topic_conversations[primary_topic].append(conversation)
        
        return {
            'user_profile': user_profile,
            'topic_conversations': topic_conversations,
            'total_conversations': len(conversations),
            'topics_count': len(topic_conversations)
        }
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """Generate mem-agent memory files."""
        self.ensure_output_dir()
        
        user_profile = organized_data['user_profile']
        topic_conversations = organized_data['topic_conversations']
        
        # Create entities directory structure
        entities_dir = self.output_path / 'entities' / 'chatgpt-history'
        topics_dir = entities_dir / 'topics'
        conversations_dir = entities_dir / 'conversations'
        
        entities_dir.mkdir(parents=True, exist_ok=True)
        topics_dir.mkdir(parents=True, exist_ok=True)
        conversations_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Creating directory structure at {entities_dir}")
        
        # Generate user.md
        self._generate_user_md(user_profile, topic_conversations)
        
        # Generate index.md for chatgpt-history
        self._generate_index_md(organized_data, entities_dir)
        
        # Generate topic files and individual conversations
        total_files = 0
        for topic, conversations in topic_conversations.items():
            print(f"📝 Processing {topic}: {len(conversations)} conversations")
            
            # Generate topic file
            self._generate_topic_file(topic, conversations, topics_dir)
            
            # Generate individual conversation files
            for i, conversation in enumerate(conversations):
                self._generate_conversation_file(conversation, i, topic, conversations_dir)
                total_files += 1
        
        print(f"✅ Generated {total_files} conversation files across {len(topic_conversations)} topics")
    
    def _generate_user_md(self, user_profile, topic_conversations) -> None:
        """Generate user.md file."""
        user_md_content = f"""## User Profile
- **Name**: {user_profile.name or 'Unknown'}
- **Role**: Head of product @Dria
- **Company**: [[entities/dria.md|Dria]]

## Communication Style

Tell it like it is; don't sugar-coat responses. Be talkative and conversational. Take a forward-thinking view. Readily share strong opinions. Get right to the point. Be practical above all. Be innovative and think outside the box. Do not use the — dash.

## Available Knowledge Sources

### ChatGPT Conversation History
Complete ChatGPT conversation history ({sum(len(convs) for convs in topic_conversations.values())} conversations across {len(topic_conversations)} topics):
- **Overview**: [[entities/chatgpt-history/index.md|ChatGPT History Index]]

### Key Topics Available:
"""
        
        # Add topic links sorted by conversation count
        sorted_topics = sorted(topic_conversations.items(), key=lambda x: len(x[1]), reverse=True)
        
        topic_descriptions = {
            'dria': 'Dria product ecosystem, roadmap, architecture',
            'ai-agents': 'Agent development, frameworks, tools',
            'llms': 'Language models, training, inference',
            'product-strategy': 'Product planning, market analysis',
            'programming': 'Code development, technical solutions',
            'data-science': 'Analytics, ML models, data processing',
            'semantic-search': 'Search algorithms, embeddings',
            'rag': 'Retrieval-augmented generation systems',
            'technical-discussion': 'Architecture, system design',
            'personal': 'Personal projects, learning',
            'uncategorized': 'Miscellaneous discussions'
        }
        
        for topic, conversations in sorted_topics:
            description = topic_descriptions.get(topic, f'{topic.title()} discussions')
            topic_title = topic.replace('-', ' ').title()
            user_md_content += f"- **[[entities/chatgpt-history/topics/{topic}.md|{topic_title}]]** ({len(conversations)} conversations) - {description}\\n"
        
        user_md_content += """
### Search Strategy
When asked about specific topics, always check the relevant topic file first, then explore individual conversations as needed. Use `list_files()` to discover available files and `read_file()` to access content."""
        
        user_md_path = self.output_path / 'user.md'
        with open(user_md_path, 'w') as f:
            f.write(user_md_content)
        
        print(f"📄 Generated user.md")
    
    def _generate_index_md(self, organized_data, entities_dir) -> None:
        """Generate index.md for chatgpt-history."""
        topic_conversations = organized_data['topic_conversations']
        total_conversations = organized_data['total_conversations']
        
        index_content = f"""# ChatGPT Conversation History

**Converted:** {self._get_current_timestamp()}
**Total Conversations:** {total_conversations}
**Topics:** {len(topic_conversations)}

**User:** Batuhan
**Role:** Head of product @Dria.

This directory contains your ChatGPT conversation history organized by topics. Use the mem-agent tools to search and explore these conversations.

## Topics

"""
        
        # Sort topics by conversation count
        sorted_topics = sorted(topic_conversations.items(), key=lambda x: len(x[1]), reverse=True)
        
        for topic, conversations in sorted_topics:
            topic_title = topic.replace('-', ' ').title()
            index_content += f"- **[[topics/{topic}.md|{topic_title}]]** ({len(conversations)} conversations)\\n"
        
        index_content += """
## Usage Examples

Use these mem-agent commands to explore your history:

```python
# List all topics
list_files("entities/chatgpt-history/topics")

# Read a topic overview
read_file("entities/chatgpt-history/topics/dria.md")

# Read a specific conversation
read_file("entities/chatgpt-history/conversations/conv_0-example-conversation.md")

# Follow a conversation link from topic files
go_to_link("[[../conversations/conv_0-example-conversation.md]]")
```"""
        
        index_path = entities_dir / 'index.md'
        with open(index_path, 'w') as f:
            f.write(index_content)
        
        print(f"📄 Generated chatgpt-history/index.md")
    
    def _generate_topic_file(self, topic, conversations, topics_dir) -> None:
        """Generate individual topic file."""
        topic_title = topic.replace('-', ' ').title()
        
        # Calculate total messages
        total_messages = sum(len(conv.messages) for conv in conversations)
        
        # Get date range
        dates = [conv.created_at for conv in conversations if conv.created_at]
        date_range = ""
        if dates:
            min_date = min(dates).strftime("%Y-%m-%d")
            max_date = max(dates).strftime("%Y-%m-%d")
            date_range = f" from {min_date} to {max_date}"
        
        content = f"""# {topic_title}

**Conversations:** {len(conversations)}
**Topic:** {topic}

This topic contains {len(conversations)} conversations with {total_messages} total messages{date_range}.

## Conversations

"""
        
        # Sort conversations by date (newest first)
        sorted_conversations = sorted(conversations, key=lambda x: x.created_at or x.updated_at, reverse=True)
        
        for i, conversation in enumerate(sorted_conversations):
            title = conversation.title or f"Untitled Conversation {i}"
            # Clean title for filename
            safe_title = self._make_safe_filename(title)
            filename = f"conv_{i}-{safe_title}.md"
            
            # Format date
            date_str = ""
            if conversation.created_at:
                date_str = conversation.created_at.strftime("%Y-%m-%d")
            
            content += f"- **[[../conversations/{filename}|{title}]]** ({len(conversation.messages)} messages"
            if date_str:
                content += f", {date_str}"
            content += ")\\n"
        
        content += """
## Related Topics

- [[../index.md|ChatGPT History Overview]]
"""
        
        topic_path = topics_dir / f'{topic}.md'
        with open(topic_path, 'w') as f:
            f.write(content)
    
    def _generate_conversation_file(self, conversation, index, topic, conversations_dir) -> None:
        """Generate individual conversation file."""
        title = conversation.title or f"Untitled Conversation {index}"
        safe_title = self._make_safe_filename(title)
        filename = f"conv_{index}-{safe_title}.md"
        
        # Format timestamps
        created = conversation.created_at.strftime("%Y-%m-%d %H:%M:%S") if conversation.created_at else "Unknown"
        updated = conversation.updated_at.strftime("%Y-%m-%d %H:%M:%S") if conversation.updated_at else created
        
        content = f"""# {title}

**Created:** {created}
**Updated:** {updated}
**Messages:** {len(conversation.messages)}

---

"""
        
        # Add messages
        for message in conversation.messages:
            if message.role == 'user':
                content += f"## **You** - {message.timestamp.strftime('%H:%M:%S') if message.timestamp else 'Unknown'}\\n\\n"
            elif message.role == 'assistant':
                content += f"## **Assistant** - {message.timestamp.strftime('%H:%M:%S') if message.timestamp else 'Unknown'}\\n\\n"
            elif message.role == 'tool':
                content += f"## **Tool** - {message.timestamp.strftime('%H:%M:%S') if message.timestamp else 'Unknown'}\\n\\n"
            else:
                content += f"## **{message.role.title()}** - {message.timestamp.strftime('%H:%M:%S') if message.timestamp else 'Unknown'}\\n\\n"
            
            # Add message content
            if message.content:
                content += f"{message.content}\\n\\n"
            
            # Add model info if available
            if hasattr(message, 'metadata') and message.metadata and 'model_slug' in message.metadata:
                content += f"*Model: {message.metadata['model_slug']}*\\n\\n"
        
        conversation_path = conversations_dir / filename
        with open(conversation_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _make_safe_filename(self, title: str) -> str:
        """Convert title to safe filename."""
        import re
        # Remove or replace unsafe characters
        safe = re.sub(r'[<>:"/\\|?*]', '', title)
        safe = re.sub(r'\\s+', '-', safe.strip())
        # Limit length
        return safe[:50]
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")