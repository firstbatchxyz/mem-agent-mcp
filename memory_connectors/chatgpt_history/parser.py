"""
ChatGPT export parser - Python port of MemProxy TypeScript parser.
"""
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from .types import (
    ChatGPTConversation,
    ChatGPTConversationNode, 
    ChatGPTMessage,
    ParsedConversation,
    ParsedMessage,
    ParserOptions,
    UserProfile
)


class ChatGPTParser:
    def __init__(self, options: Optional[ParserOptions] = None):
        self.options = options or ParserOptions()
    
    def parse_export(self, export_path: str) -> Dict[str, any]:
        """Parse ChatGPT export from a directory containing conversations.json"""
        conversations_file = os.path.join(export_path, 'conversations.json')
        attachment_files = self._get_attachment_files(export_path)
        
        if not os.path.exists(conversations_file):
            raise FileNotFoundError(f"conversations.json not found in {export_path}")
        
        print("Reading conversations.json...")
        with open(conversations_file, 'r', encoding='utf-8') as f:
            try:
                raw_conversations = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse conversations.json: {e}")
        
        print(f"Found {len(raw_conversations)} conversations")
        
        parsed_conversations: List[ParsedConversation] = []
        global_user_profile: Optional[UserProfile] = None
        
        for i, conversation_data in enumerate(raw_conversations):
            if i % 100 == 0:
                print(f"Processing conversation {i + 1}/{len(raw_conversations)}")
            
            # Convert dict to dataclass
            conversation = self._dict_to_conversation(conversation_data)
            parsed = self._parse_conversation(conversation, f"conv_{i}")
            parsed_conversations.append(parsed)
            
            # Extract user profile from first conversation that has it
            if not global_user_profile and parsed.user_profile:
                global_user_profile = self._extract_user_profile(
                    parsed.user_profile, 
                    parsed.user_instructions
                )
        
        return {
            "conversations": parsed_conversations,
            "user_profile": global_user_profile,
            "total_files": len(attachment_files) + 2,  # +2 for conversations.json and chat.html
            "attachment_files": attachment_files
        }
    
    def _dict_to_conversation(self, data: Dict) -> ChatGPTConversation:
        """Convert dictionary to ChatGPTConversation dataclass"""
        mapping = {}
        for node_id, node_data in data.get('mapping', {}).items():
            # Convert message if present
            message = None
            if node_data.get('message'):
                msg_data = node_data['message']
                message = ChatGPTMessage(
                    id=msg_data.get('id', ''),
                    author=msg_data.get('author', {}),
                    create_time=msg_data.get('create_time'),
                    update_time=msg_data.get('update_time'),
                    content=msg_data.get('content', {}),
                    status=msg_data.get('status', ''),
                    end_turn=msg_data.get('end_turn'),
                    weight=msg_data.get('weight', 1.0),
                    metadata=msg_data.get('metadata'),
                    recipient=msg_data.get('recipient', ''),
                    channel=msg_data.get('channel')
                )
            
            mapping[node_id] = ChatGPTConversationNode(
                id=node_id,
                message=message,
                parent=node_data.get('parent'),
                children=node_data.get('children', [])
            )
        
        return ChatGPTConversation(
            title=data.get('title', 'Untitled'),
            create_time=data.get('create_time', 0),
            update_time=data.get('update_time', 0),
            mapping=mapping,
            conversation_id=data.get('conversation_id'),
            current_node=data.get('current_node')
        )
    
    def _parse_conversation(self, conversation: ChatGPTConversation, conv_id: str) -> ParsedConversation:
        """Parse a single ChatGPT conversation"""
        messages: List[ParsedMessage] = []
        user_profile: Optional[str] = None
        user_instructions: Optional[str] = None
        
        # Traverse the conversation tree to extract messages in chronological order
        visited_nodes = set()
        message_order = []
        
        # Find the root node (usually 'client-created-root')
        root_node = None
        for node in conversation.mapping.values():
            if node.parent is None:
                root_node = node
                break
        
        if not root_node:
            print(f"Warning: No root node found for conversation: {conversation.title}")
            return ParsedConversation(
                id=conv_id,
                title=conversation.title,
                created_at=datetime.fromtimestamp(conversation.create_time),
                updated_at=datetime.fromtimestamp(conversation.update_time),
                messages=[],
                message_count=0
            )
        
        # Depth-first traversal to maintain chronological order
        def traverse(node_id: str):
            if node_id in visited_nodes:
                return
            visited_nodes.add(node_id)
            
            node = conversation.mapping.get(node_id)
            if not node:
                return
            
            if node.message:
                message_order.append(node_id)
            
            # Visit children in order
            for child_id in node.children:
                traverse(child_id)
        
        traverse(root_node.id)
        
        # Convert nodes to messages
        for node_id in message_order:
            node = conversation.mapping.get(node_id)
            if not node or not node.message:
                continue
            
            message = node.message
            
            # Skip system messages unless explicitly requested
            if (message.author.get('role') == 'system' and 
                not self.options.include_system_messages):
                continue
            
            # Extract user profile and instructions from user_editable_context
            if message.content.get('content_type') == 'user_editable_context':
                user_profile = message.content.get('user_profile')
                user_instructions = message.content.get('user_instructions')
                continue
            
            # Skip empty messages
            content = self._extract_message_content(message)
            if not content.strip():
                continue
            
            parsed_message = ParsedMessage(
                id=message.id,
                role=message.author.get('role', 'unknown'),
                content=content,
                timestamp=(datetime.fromtimestamp(message.create_time) 
                          if message.create_time else None),
                model=message.metadata.get('model_slug') if message.metadata else None,
                metadata=message.metadata if self.options.include_metadata and message.metadata else {}
            )
            
            messages.append(parsed_message)
            
            # Respect maxMessages limit
            if (self.options.max_messages and 
                len(messages) >= self.options.max_messages):
                break
        
        return ParsedConversation(
            id=conv_id,
            title=conversation.title,
            created_at=datetime.fromtimestamp(conversation.create_time),
            updated_at=datetime.fromtimestamp(conversation.update_time),
            messages=messages,
            message_count=len(messages),
            user_profile=user_profile,
            user_instructions=user_instructions
        )
    
    def _extract_message_content(self, message: ChatGPTMessage) -> str:
        """Extract content from a ChatGPT message"""
        parts = message.content.get('parts')
        if not parts or not isinstance(parts, list):
            return ''
        
        content_parts = [part for part in parts if isinstance(part, str)]
        return '\n'.join(content_parts).strip()
    
    def _extract_user_profile(self, user_profile_text: Optional[str], 
                             user_instructions_text: Optional[str]) -> UserProfile:
        """Extract user profile information"""
        profile = UserProfile()
        
        if user_profile_text:
            # Parse user profile text
            name_match = re.search(r'Preferred name:\s*([^\n]+)', user_profile_text, re.IGNORECASE)
            if name_match:
                profile.name = name_match.group(1).strip()
            
            role_match = re.search(r'Role:\s*([^\n]+)', user_profile_text, re.IGNORECASE)
            if role_match:
                role_text = role_match.group(1).strip()
                profile.role = role_text
                
                # Extract company from role
                company_match = re.search(r'@\s*([^\s]+)', role_text)
                if company_match:
                    profile.company = company_match.group(1).strip().rstrip('.,')
        
        if user_instructions_text:
            # Extract communication preferences
            instructions_match = re.search(r'```([^`]+)```', user_instructions_text, re.DOTALL)
            if instructions_match:
                profile.communication_style = instructions_match.group(1).strip()
        
        return profile
    
    def _get_attachment_files(self, export_path: str) -> List[str]:
        """Get list of attachment files from export directory"""
        try:
            files = os.listdir(export_path)
            return sorted([f for f in files if f.startswith('file-')])
        except OSError as e:
            print(f"Warning: Could not read attachment files: {e}")
            return []
    
    def get_export_stats(self, export_path: str) -> Dict[str, any]:
        """Get basic statistics about the export"""
        conversations_file = os.path.join(export_path, 'conversations.json')
        attachment_files = self._get_attachment_files(export_path)
        
        if not os.path.exists(conversations_file):
            raise FileNotFoundError(f"conversations.json not found in {export_path}")
        
        # Get file size
        file_size = os.path.getsize(conversations_file)
        file_size_mb = round(file_size / (1024 * 1024), 1)
        
        # Quick count without full parsing
        with open(conversations_file, 'r', encoding='utf-8') as f:
            try:
                conversations = json.load(f)
            except json.JSONDecodeError:
                raise ValueError('Invalid conversations.json format')
        
        # Estimate message count (rough approximation)
        estimated_message_count = sum(
            len(conv.get('mapping', {})) for conv in conversations
        )
        
        return {
            "conversation_count": len(conversations),
            "file_size": f"{file_size_mb} MB", 
            "attachment_count": len(attachment_files),
            "estimated_message_count": estimated_message_count
        }