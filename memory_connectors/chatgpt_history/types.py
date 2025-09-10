"""
Type definitions for ChatGPT export parsing.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatGPTMessage:
    id: str
    author: Dict[str, Any]
    create_time: Optional[float]
    update_time: Optional[float]
    content: Dict[str, Any]
    status: str
    end_turn: Optional[bool]
    weight: float
    metadata: Optional[Dict[str, Any]]
    recipient: str
    channel: Optional[str]


@dataclass
class ChatGPTConversationNode:
    id: str
    message: Optional[ChatGPTMessage]
    parent: Optional[str]
    children: List[str]


@dataclass
class ChatGPTConversation:
    title: str
    create_time: float
    update_time: float
    mapping: Dict[str, ChatGPTConversationNode]
    conversation_id: Optional[str] = None
    current_node: Optional[str] = None


@dataclass
class ParsedMessage:
    id: str
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: Optional[datetime]
    model: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class ParsedConversation:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[ParsedMessage]
    message_count: int
    user_profile: Optional[str] = None
    user_instructions: Optional[str] = None


@dataclass
class UserProfile:
    name: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    communication_style: Optional[str] = None
    technical_interests: Optional[List[str]] = None
    working_patterns: Optional[List[str]] = None
    expertise: Optional[List[str]] = None


@dataclass
class ParserOptions:
    include_system_messages: bool = False
    include_metadata: bool = True
    max_messages: Optional[int] = None