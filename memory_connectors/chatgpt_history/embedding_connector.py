"""
ChatGPT History Embedding-Based Memory Connector

Uses EmbeddingGemma-300M and clustering to automatically discover conversation categories.
"""

import os
import numpy as np
from typing import Dict, Any, List, Tuple
from pathlib import Path
from collections import Counter
import json

def check_dependencies():
    """Check if required dependencies are available."""
    try:
        from sklearn.cluster import AgglomerativeClustering
        from sklearn.metrics.pairwise import cosine_similarity
        from sklearn.feature_extraction.text import TfidfVectorizer
        # Basic dependencies are enough for TF-IDF mode
        return True
    except ImportError:
        return False

# Import at module level for functionality that doesn't need dependency check
try:
    import numpy as np
    from collections import Counter
    import json
except ImportError:
    pass

from ..base import BaseMemoryConnector
from .parser import ChatGPTParser


class ChatGPTEmbeddingConnector(BaseMemoryConnector):
    """Embedding-based connector for ChatGPT conversation history exports."""
    
    def __init__(self, output_path: str, **kwargs):
        super().__init__(output_path, **kwargs)
        # Default to TF-IDF, but support multiple embedding methods
        self.model_name = kwargs.get('model_name', "tfidf")  
        # Allow overriding LM Studio base URL via env var as well
        self.lmstudio_base_url = kwargs.get('lmstudio_base_url', os.getenv('LMSTUDIO_BASE_URL', "http://localhost:8000"))
        
        # Available embedding methods:
        # - "tfidf": Fast TF-IDF based (no neural network)
        # - "lmstudio:text-embedding-nomic-embed-text-v1.5": Nomic via LM Studio
        self.min_cluster_size = kwargs.get('min_cluster_size', 5)
        self.max_clusters = kwargs.get('max_clusters', 20)
        self.distance_threshold = kwargs.get('distance_threshold', 2.5)  # Higher = fewer clusters
        
        # Only check dependencies when actually needed, not at instantiation
        self._dependencies_checked = False
    
    @property
    def connector_name(self) -> str:
        return "ChatGPT History (AI-powered)"
    
    @property
    def supported_formats(self) -> list:
        return ['.zip', '.json']
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available."""
        if not self._dependencies_checked:
            has_deps = check_dependencies()
            if not has_deps:
                raise ImportError(
                    "Missing dependencies for embedding-based categorization. "
                    "Install with: pip install transformers torch scikit-learn"
                )
            self._dependencies_checked = True
        return True
    
    def _load_embedding_model(self):
        """Load the embedding model."""
        # Only check dependencies for models that need them
        if not (self.model_name == "tfidf" or self.model_name.startswith("lmstudio:")):
            self._check_dependencies()  # Ensure dependencies are available
        
        if self.model_name == "tfidf":
            print(f"🤖 Using TF-IDF based embeddings (fast, no downloads needed)")
            from sklearn.feature_extraction.text import TfidfVectorizer
            self.model = TfidfVectorizer(
                max_features=1000,
                stop_words='english',
                ngram_range=(1, 2),
                min_df=2
            )
            self.tokenizer = None
            print("✅ TF-IDF vectorizer ready")
            return
        
        if self.model_name.startswith("lmstudio:"):
            model_id = self.model_name.split(":", 1)[1]
            print(f"🤖 Using LM Studio API for embeddings: {model_id}")
            
            # Check basic dependencies for LM Studio (just requests and sklearn)
            try:
                import requests
                from sklearn.cluster import AgglomerativeClustering
                from sklearn.feature_extraction.text import TfidfVectorizer
            except ImportError as e:
                raise ImportError(f"Missing dependencies for LM Studio embedding: {e}. Install with: pip install requests scikit-learn")
            
            self._check_lmstudio_connection(model_id)
            self.model = model_id  # Store model ID for API calls
            self.tokenizer = None
            print("✅ LM Studio connection verified")
            return
        
        # No other embedding models supported
        raise ValueError(f"Unsupported embedding model: {self.model_name}. Supported models: tfidf, lmstudio:model-name")
    
    def _check_lmstudio_connection(self, model_id: str):
        """Check if LM Studio is running and has the model loaded."""
        import requests
        import json
        
        try:
            # Check if LM Studio server is running
            response = requests.get(f"{self.lmstudio_base_url}/v1/models", timeout=5)
            if response.status_code != 200:
                raise ConnectionError(f"LM Studio server not responding (HTTP {response.status_code})")
            
            # Check if the embedding model is loaded
            models = response.json()
            available_models = [model['id'] for model in models.get('data', [])]
            
            if model_id not in available_models:
                print(f"⚠️ Model '{model_id}' not found in LM Studio")
                print(f"Available models: {', '.join(available_models)}")
                print(f"💡 Please load '{model_id}' in LM Studio first")
                raise ValueError(f"Model '{model_id}' not available in LM Studio")
                
        except requests.exceptions.ConnectionError:
            # Try to start LM Studio API server automatically
            print("🚀 LM Studio API server not running. Attempting to start...")
            if self._start_lmstudio_server(model_id):
                # Retry the connection after starting the server
                try:
                    response = requests.get(f"{self.lmstudio_base_url}/v1/models", timeout=10)
                    if response.status_code == 200:
                        models = response.json()
                        available_models = [model['id'] for model in models.get('data', [])]
                        
                        if model_id not in available_models:
                            print(f"⚠️ Model '{model_id}' not found in LM Studio")
                            print(f"Available models: {', '.join(available_models)}")
                            print(f"💡 Please load '{model_id}' in LM Studio first")
                            raise ValueError(f"Model '{model_id}' not available in LM Studio")
                        return  # Success
                except requests.exceptions.ConnectionError:
                    pass
            
            raise ConnectionError(
                f"Cannot connect to LM Studio at {self.lmstudio_base_url}. "
                f"Please ensure LM Studio is running with the embedding model loaded."
            )
    
    def _start_lmstudio_server(self, model_id: str) -> bool:
        """Attempt to start LM Studio API server automatically.

        - Ensures `lms` CLI is present
        - Downloads (if needed) and loads the requested model
        - Starts the API server on the port parsed from lmstudio_base_url
        - Waits until /v1/models responds and the model is available
        """
        import subprocess
        import time
        import os
        import requests
        from urllib.parse import urlparse
        
        try:
            # Check if LM Studio CLI is available
            lms_path = subprocess.check_output(["which", "lms"], text=True).strip()
            if not lms_path:
                print("❌ LM Studio CLI (lms) not found in PATH")
                return False
                
            # Parse port from base URL
            parsed = urlparse(self.lmstudio_base_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or (8000 if parsed.scheme in ("http", "") else 443)

            # Ensure model is available locally and loaded
            print(f"📦 Ensuring model '{model_id}' is available via lms...")
            try:
                subprocess.run(["lms", "get", model_id, "--always-show-all-results"], check=False)
            except Exception:
                # Non-fatal if get fails; continue
                pass

            print(f"🔁 Loading model '{model_id}' in LM Studio...")
            subprocess.run(["lms", "load", model_id], check=False)

            print(f"🔍 Starting LM Studio API server on {host}:{port}...")
            # Start the server in the background on the specified port
            subprocess.Popen(
                ["lms", "server", "start", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Wait for server to become responsive
            max_wait_seconds = 60
            start_time = time.time()
            while time.time() - start_time < max_wait_seconds:
                try:
                    response = requests.get(f"{self.lmstudio_base_url}/v1/models", timeout=2)
                    if response.status_code == 200:
                        models = response.json()
                        available_models = [m.get('id') for m in models.get('data', [])]
                        if model_id in available_models:
                            print("✅ LM Studio API server started and model available")
                            return True
                        else:
                            # Try to load again if server is up but model missing
                            subprocess.run(["lms", "load", model_id], check=False)
                    time.sleep(2)
                except requests.exceptions.RequestException:
                    time.sleep(2)

            print("❌ Timed out waiting for LM Studio API server to become ready")
            return False
            
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ Failed to start LM Studio server: {e}")
            print("💡 Make sure LM Studio is installed and 'lms' command is available")
            return False
    
    def _call_lmstudio_embeddings(self, texts: list) -> list:
        """Call LM Studio embedding API."""
        import requests
        import json
        
        embeddings = []
        batch_size = 32  # Process in batches
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            payload = {
                "model": self.model,  # model ID
                "input": batch_texts
            }
            
            try:
                response = requests.post(
                    f"{self.lmstudio_base_url}/v1/embeddings",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=60
                )
                response.raise_for_status()
                
                result = response.json()
                batch_embeddings = [item['embedding'] for item in result['data']]
                embeddings.extend(batch_embeddings)
                
                if len(texts) > batch_size:
                    print(f"   Processed {min(i + batch_size, len(texts))}/{len(texts)} texts")
                    
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"LM Studio API call failed: {e}")
        
        return embeddings
    
    def _create_conversation_text(self, conversation) -> str:
        """Create text representation of conversation for embedding."""
        title = conversation.title or "Untitled"
        
        # Get first and last messages (most informative)
        messages = []
        if conversation.messages:
            # First user message
            first_msg = next((msg for msg in conversation.messages if msg.role == 'user'), None)
            if first_msg and first_msg.content:
                messages.append(first_msg.content[:200])  # Limit length
            
            # Last assistant message  
            last_msg = next((msg for msg in reversed(conversation.messages) if msg.role == 'assistant'), None)
            if last_msg and last_msg.content:
                messages.append(last_msg.content[:200])
        
        # Combine title and key messages
        text_parts = [title] + messages
        return " | ".join(text_parts)
    
    def _embed_conversations(self, conversations: List):
        """Generate embeddings for all conversations."""
        import numpy as np
        
        print(f"🔄 Generating embeddings for {len(conversations)} conversations...")
        
        texts = [self._create_conversation_text(conv) for conv in conversations]
        
        if self.model_name == "tfidf":
            # Use TF-IDF (fast, no neural networks)
            embeddings = self.model.fit_transform(texts).toarray()
        elif self.model_name.startswith("lmstudio:"):
            # Use LM Studio API
            embeddings = self._call_lmstudio_embeddings(texts)
            embeddings = np.array(embeddings)
        else:
            raise ValueError(f"Unsupported embedding model: {self.model_name}")
        
        print(f"✅ Generated embeddings with shape: {embeddings.shape}")
        return embeddings
    
    def _discover_clusters(self, embeddings):
        """Discover natural conversation clusters."""
        from sklearn.cluster import AgglomerativeClustering
        import numpy as np
        
        print(f"🔍 Discovering conversation clusters...")
        
        # Use hierarchical clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=self.distance_threshold,
            linkage='ward'
        )
        
        cluster_labels = clustering.fit_predict(embeddings)
        n_clusters = len(set(cluster_labels))
        
        print(f"📊 Discovered {n_clusters} natural clusters")
        return cluster_labels
    
    def _extract_cluster_themes(self, conversations: List, cluster_labels) -> Dict[int, List[str]]:
        """Extract themes from each cluster using BM25/TF-IDF."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        import numpy as np
        
        print("🎯 Extracting themes from clusters...")
        
        cluster_themes = {}
        unique_labels = set(cluster_labels)
        
        for label in unique_labels:
            # Get conversations in this cluster
            cluster_conversations = [conv for i, conv in enumerate(conversations) if cluster_labels[i] == label]
            
            if len(cluster_conversations) < self.min_cluster_size:
                continue
            
            # Combine all text from cluster conversations
            cluster_texts = []
            for conv in cluster_conversations:
                text = self._create_conversation_text(conv)
                cluster_texts.append(text)
            
            # Extract key terms using TF-IDF
            try:
                vectorizer = TfidfVectorizer(
                    max_features=100,
                    stop_words='english',
                    ngram_range=(1, 2),
                    min_df=2
                )
                tfidf_matrix = vectorizer.fit_transform(cluster_texts)
                feature_names = vectorizer.get_feature_names_out()
                
                # Get top terms by TF-IDF score
                mean_scores = np.mean(tfidf_matrix.toarray(), axis=0)
                top_indices = np.argsort(mean_scores)[-10:]  # Top 10 terms
                top_terms = [feature_names[i] for i in top_indices[::-1]]
                
                cluster_themes[label] = top_terms
                
            except Exception as e:
                print(f"⚠️ Could not extract themes for cluster {label}: {e}")
                cluster_themes[label] = ["mixed-topics"]
        
        return cluster_themes
    
    def _generate_category_names(self, cluster_themes: Dict[int, List[str]]) -> Dict[int, str]:
        """Generate human-readable category names using mem-agent."""
        print("✨ Generating category names using mem-agent...")
        
        category_names = {}
        
        for cluster_id, themes in cluster_themes.items():
            try:
                # Create a prompt for the mem-agent to generate category name
                themes_text = ", ".join(themes[:5])  # Top 5 themes
                
                # Use a simple heuristic approach for now
                # In production, this would call mem-agent with a specialized prompt
                category_name = self._heuristic_category_naming(themes)
                category_names[cluster_id] = category_name
                
            except Exception as e:
                print(f"⚠️ Could not generate name for cluster {cluster_id}: {e}")
                category_names[cluster_id] = f"topic-{cluster_id}"
        
        return category_names
    
    def _heuristic_category_naming(self, themes: List[str]) -> str:
        """Simple heuristic for category naming (placeholder for mem-agent integration)."""
        # Simple keyword-based naming as fallback
        theme_text = " ".join(themes).lower()
        
        if any(word in theme_text for word in ['dria', 'firstbatch', 'network']):
            return "Dria"
        elif any(word in theme_text for word in ['agent', 'multi-agent', 'autonomous']):
            return "AI Agents"
        elif any(word in theme_text for word in ['llm', 'language model', 'gpt', 'claude']):
            return "LLMs"
        elif any(word in theme_text for word in ['product', 'strategy', 'business', 'roadmap']):
            return "Product Strategy"
        elif any(word in theme_text for word in ['python', 'code', 'programming', 'development']):
            return "Programming"
        elif any(word in theme_text for word in ['data', 'analytics', 'machine learning']):
            return "Data Science"
        elif any(word in theme_text for word in ['search', 'embeddings', 'vector']):
            return "Semantic Search"
        elif any(word in theme_text for word in ['rag', 'retrieval']):
            return "RAG"
        elif any(word in theme_text for word in ['technical', 'architecture', 'system']):
            return "Technical Discussion"
        elif any(word in theme_text for word in ['personal', 'learning', 'career']):
            return "Personal"
        else:
            # Generate name from most common themes
            top_themes = themes[:2]
            return " ".join(word.title() for word in top_themes[0].split())
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        """Extract conversations from ChatGPT export."""
        print(f"📂 Parsing ChatGPT export from {source_path}")
        
        # Parse the export using existing parser
        parser = ChatGPTParser()
        parsed_data = parser.parse_export(source_path)
        
        return {
            'conversations': parsed_data['conversations'],
            'user_profile': parsed_data['user_profile'],
            'total_conversations': len(parsed_data['conversations']),
            'source_path': source_path
        }
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize conversations using embedding-based clustering."""
        conversations = extracted_data['conversations']
        user_profile = extracted_data['user_profile']
        
        print(f"🤖 AI-powered organization of {len(conversations)} conversations")
        
        if len(conversations) < self.min_cluster_size:
            print(f"⚠️ Too few conversations ({len(conversations)}) for clustering. Using single category.")
            return {
                'user_profile': user_profile,
                'topic_conversations': {'general': conversations},
                'total_conversations': len(conversations),
                'topics_count': 1,
                'method': 'embedding-based',
                'cluster_info': {}
            }
        
        # Load embedding model
        self._load_embedding_model()
        
        # Generate embeddings
        embeddings = self._embed_conversations(conversations)
        
        # Discover clusters
        cluster_labels = self._discover_clusters(embeddings)
        
        # Extract themes from clusters
        cluster_themes = self._extract_cluster_themes(conversations, cluster_labels)
        
        # Generate category names
        category_names = self._generate_category_names(cluster_themes)
        
        # Organize conversations by discovered categories
        topic_conversations = {}
        cluster_info = {}
        
        for i, (conversation, cluster_id) in enumerate(zip(conversations, cluster_labels)):
            # Skip small clusters
            import numpy as np
            cluster_size = np.sum(cluster_labels == cluster_id)
            if cluster_size < self.min_cluster_size:
                if 'other' not in topic_conversations:
                    topic_conversations['other'] = []
                topic_conversations['other'].append(conversation)
                continue
            
            # Use generated category name
            category_name = category_names.get(cluster_id, f"topic-{cluster_id}")
            category_slug = category_name.lower().replace(' ', '-').replace('&', 'and')
            
            if category_slug not in topic_conversations:
                topic_conversations[category_slug] = []
                cluster_info[category_slug] = {
                    'cluster_id': cluster_id,
                    'themes': cluster_themes.get(cluster_id, []),
                    'display_name': category_name,
                    'size': cluster_size
                }
            
            topic_conversations[category_slug].append(conversation)
        
        print(f"✅ Organized into {len(topic_conversations)} AI-discovered categories")
        for category, convs in topic_conversations.items():
            display_name = cluster_info.get(category, {}).get('display_name', category.title())
            print(f"   📁 {display_name}: {len(convs)} conversations")
        
        return {
            'user_profile': user_profile,
            'topic_conversations': topic_conversations,
            'total_conversations': len(conversations),
            'topics_count': len(topic_conversations),
            'method': 'embedding-based',
            'cluster_info': cluster_info
        }
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        """Generate mem-agent memory files with AI-discovered categories."""
        self.ensure_output_dir()
        
        user_profile = organized_data['user_profile']
        topic_conversations = organized_data['topic_conversations']
        cluster_info = organized_data.get('cluster_info', {})
        
        # Create entities directory structure
        entities_dir = self.output_path / 'entities' / 'chatgpt-history'
        topics_dir = entities_dir / 'topics'
        conversations_dir = entities_dir / 'conversations'
        
        entities_dir.mkdir(parents=True, exist_ok=True)
        topics_dir.mkdir(parents=True, exist_ok=True)
        conversations_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"📁 Creating directory structure at {entities_dir}")
        
        # Generate user.md with AI categorization info
        self._generate_user_md(user_profile, topic_conversations, cluster_info)
        
        # Generate index.md for chatgpt-history
        self._generate_index_md(organized_data, entities_dir)
        
        # Generate topic files and individual conversations
        total_files = 0
        
        for topic_slug, conversations in topic_conversations.items():
            cluster_data = cluster_info.get(topic_slug, {})
            display_name = cluster_data.get('display_name', topic_slug.title())
            themes = cluster_data.get('themes', [])
            
            # Generate topic file
            topic_file = topics_dir / f"{topic_slug}.md"
            self._generate_topic_file(topic_file, display_name, conversations, themes)
            total_files += 1
            
            # Generate individual conversation files
            for i, conversation in enumerate(conversations):
                conv_filename = f"conv_{i:03d}_{topic_slug}_{conversation.id[:8] if conversation.id else 'unknown'}.md"
                conv_file = conversations_dir / conv_filename
                self._generate_conversation_file(conv_file, conversation, topic_slug)
                total_files += 1
        
        print(f"✅ Generated {total_files} memory files using AI-powered categorization")
    
    def _generate_user_md(self, user_profile: Dict[str, Any], topic_conversations: Dict[str, List], cluster_info: Dict[str, Any]):
        """Generate user.md file with AI categorization information."""
        user_file = self.output_path / "user.md"
        
        # Calculate topic statistics
        topic_stats = []
        for topic_slug, conversations in topic_conversations.items():
            cluster_data = cluster_info.get(topic_slug, {})
            display_name = cluster_data.get('display_name', topic_slug.title())
            count = len(conversations)
            topic_stats.append((display_name, topic_slug, count))
        
        # Sort by conversation count
        topic_stats.sort(key=lambda x: x[2], reverse=True)
        
        content = f"""## User Profile
- **Name**: {user_profile.name or 'Unknown'}
- **Company**: [[entities/dria.md|Dria]]

## Communication Style

Tell it like it is; don't sugar-coat responses. Be talkative and conversational. Take a forward-thinking view. Readily share strong opinions. Get right to the point. Be practical above all. Be innovative and think outside the box. Do not use the — dash.

## Available Knowledge Sources

### ChatGPT Conversation History (AI-Categorized)
Complete ChatGPT conversation history ({sum(len(convs) for convs in topic_conversations.values())} conversations across {len(topic_conversations)} AI-discovered topics):
- **Overview**: [[entities/chatgpt-history/index.md|ChatGPT History Index]]

### Key Topics Available:
"""
        
        for display_name, topic_slug, count in topic_stats:
            content += f"- **[[entities/chatgpt-history/topics/{topic_slug}.md|{display_name}]]** ({count} conversations)"
            
            # Add theme information if available
            if topic_slug in cluster_info:
                themes = cluster_info[topic_slug].get('themes', [])[:3]  # Top 3 themes
                if themes:
                    content += f" - {', '.join(themes)}"
            content += "\n"
        
        content += f"""

*Categories were automatically discovered using AI-powered semantic analysis of conversation content.*
"""
        
        user_file.write_text(content)
        print(f"📝 Generated user.md with AI-categorized topics")
    
    def _generate_index_md(self, organized_data: Dict[str, Any], entities_dir: Path):
        """Generate index.md for chatgpt-history."""
        index_file = entities_dir / "index.md"
        
        topic_conversations = organized_data['topic_conversations']
        cluster_info = organized_data.get('cluster_info', {})
        method = organized_data.get('method', 'embedding-based')
        
        content = f"""# ChatGPT Conversation History

**Total Conversations**: {organized_data['total_conversations']}  
**Categories**: {organized_data['topics_count']} (AI-discovered)  
**Categorization Method**: {method.title()}

## AI-Discovered Categories

"""
        
        for topic_slug, conversations in topic_conversations.items():
            cluster_data = cluster_info.get(topic_slug, {})
            display_name = cluster_data.get('display_name', topic_slug.title())
            themes = cluster_data.get('themes', [])
            
            content += f"### [[topics/{topic_slug}.md|{display_name}]] ({len(conversations)} conversations)\n"
            if themes:
                content += f"**Key Themes**: {', '.join(themes[:5])}\n"
            content += "\n"
        
        content += """
## How Categories Were Discovered

These categories were automatically discovered using:
1. **Semantic Embeddings**: EmbeddingGemma-300M model to understand conversation content
2. **Hierarchical Clustering**: Grouped similar conversations based on semantic similarity  
3. **Theme Extraction**: BM25/TF-IDF analysis to identify key topics in each cluster
4. **AI Naming**: Generated human-readable category names from discovered themes

This approach ensures categories reflect your actual conversation patterns rather than predefined topics.
"""
        
        index_file.write_text(content)
        print(f"📝 Generated index.md with AI categorization details")
    
    def _generate_topic_file(self, topic_file: Path, display_name: str, conversations: List, themes: List[str]):
        """Generate individual topic file with AI-discovered information."""
        content = f"""# {display_name}

**Conversations**: {len(conversations)}  
**Discovery Method**: AI-powered semantic clustering

## Key Themes Discovered
{chr(10).join(f"- {theme}" for theme in themes[:10]) if themes else "- Mixed topics"}

## Conversation Overview

"""
        
        for i, conversation in enumerate(conversations[:20]):  # Limit for performance
            title = conversation.title or f"Conversation {i+1}"
            conv_id = conversation.id[:8] if conversation.id else 'unknown'
            content += f"- **[[../conversations/conv_{i:03d}_{topic_file.stem}_{conv_id}.md|{title}]]**\n"
        
        if len(conversations) > 20:
            content += f"\n... and {len(conversations) - 20} more conversations\n"
        
        content += f"""

## Usage Notes

This category was automatically discovered through semantic analysis of your conversations. The topics and themes listed above represent the most common discussion patterns found in this cluster of conversations.

When searching for information, consider that conversations in this category typically involve: {', '.join(themes[:3]) if themes else 'mixed topics'}.
"""
        
        topic_file.write_text(content)
    
    def _generate_conversation_file(self, conv_file: Path, conversation, topic_slug: str):
        """Generate individual conversation file."""
        title = conversation.title or "Untitled Conversation"
        
        content = f"""# {title}

**Topic**: [[../topics/{topic_slug}.md|{topic_slug.replace('-', ' ').title()}]]  
**Date**: {conversation.created_at if hasattr(conversation, 'created_at') else 'Unknown'}  
**Messages**: {len(conversation.messages) if conversation.messages else 0}

## Conversation

"""
        
        if conversation.messages:
            for msg in conversation.messages:
                if msg.role == 'user':
                    content += f"**You**: {msg.content}\n\n"
                elif msg.role == 'assistant':
                    content += f"**Assistant**: {msg.content}\n\n"
        else:
            content += "*No messages found in this conversation.*\n"
        
        conv_file.write_text(content)