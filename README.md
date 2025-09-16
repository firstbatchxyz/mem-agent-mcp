# mem-agent-mcp

This is an MCP server for our model [driaforall/mem-agent](https://huggingface.co/driaforall/mem-agent), which can be connected to apps like Claude Desktop or Lm Studio to interact with an obsidian-like memory system.

## Supported Platforms

- macOS (Metal backend)
- Linux (with GPU, vLLM backend)

## Running Instructions

1. `make check-uv` (if you have uv installed, skip this step).
2. `make install`: Installs LmStudio on MacOS.
3. `make setup`: This will open a file selector and ask you to select the directory where you want to store the memory. 
4. `make run-agent`: If you're on macOS, this will prompt you to select the precision of the model you want to use. 4-bit is very usable as tested, and higher precision models are more reliable but slower.
5. `make generate-mcp-json`: Generates the `mcp.json` file. That will be used in the next step.
6. Instructions per app/provider:
    - Claude Desktop:
        - Copy the generated `mcp.json` to the where your `claude_desktop.json` is located, then, quit and restart Claude Desktop. Check [this guide](https://modelcontextprotocol.io/quickstart/user) for detailed instructions.
    - Lm Studio:
        - Copy the generated `mcp.json` to the `mcp.json` of Lm Studio. Check [this guide](https://lmstudio.ai/docs/app/plugins/mcp) for detailed instructions. If there are problems, change the name of the model in .mlx_model_name (found in the root of this repo) from `mem-agent-mlx-4bit` or `mem-agent-mlx-8bit` to `mem-agent-mlx@4bit` or `mem-agent-mlx@8bit` respectively.


## Memory Instructions

- Each memory directory should follow the structure below:
```
memory/
    ├── user.md
    └── entities/
        └── [entity_name_1].md
        └── [entity_name_2].md
        └── ...
```

- `user.md` is the main file that contains information about the user and their relationships, accompanied by links to the enity file in the format of `[[entities/[entity_name].md]]` per relationship. The link format should be followed strictly.
- `entities/` is the directory that contains the entity files.
- Each entity file follows the same structure as `user.md`.
- Modifying the memory manually does not require restarting the MCP server.

### Example user.md

```markdown
# User Information
- user_name: John Doe
- birth_date: 1990-01-01
- birth_location: New York, USA
- living_location: Enschede, Netherlands
- zodiac_sign: Aquarius

## User Relationships
- company: [[entities/acme_corp.md]]
- mother: [[entities/jane_doe.md]]
```

### Example entity files (jane_doe.md and acme_corp.md)

```markdown
# Jane Doe
- relationship: Mother
- birth_date: 1965-01-01
- birth_location: New York, USA
```

```markdown 
# Acme Corporation
- industry: Software Development
- location: Enschede, Netherlands
```

## Filtering

The model is trained to accepts filters on various domains in between <filter> tags after the user query. These filters are used to filter the retrieved information and/or obfuscate it completely. An example of a user query with filters is:

```
What's my mother's age? <filter> 1. Do not reveal explicit age information, 2. Do not reveal any email addresses </filter>
```

To use this, functionality with the MCP, you have two make targets:
- `make add-filters`: Opens an input loop and adds the filters given by the user to the .filters file.
- `make reset-filters`: Resets the .filters file (clears it).

Adding or removing filters does not require restarting the MCP server.


## Memory Connectors

### Available Connectors

| Connector | Description | Supported Formats | Type |
|-----------|-------------|-------------------|------|
| `chatgpt` | ChatGPT conversation exports | `.zip`, `.json` | Export |
| `notion` | Notion workspace exports | `.zip` | Export |
| `nuclino` | Nuclino workspace exports | `.zip` | Export |
| `github` | GitHub repositories via API | Live API | Live |
| `google-docs` | Google Docs folders via Drive API | Live API | Live |

### Usage

#### 🧙‍♂️ Interactive Memory Wizard (Recommended)
The easiest way to connect your memory sources:

```bash
make memory-wizard
# or
python memory_wizard.py
```

The wizard will guide you through:
- ✅ Connector selection with descriptions
- ✅ Authentication setup (tokens, scopes)  
- ✅ Source configuration (files, URLs, IDs)
- ✅ Output directory setup
- ✅ Connector-specific options
- ✅ Configuration confirmation
- ✅ Automatic execution
- ✅ Success confirmation with next steps

#### Manual CLI Usage

List Available Connectors:
```bash
make connect-memory
# or
python memory_connectors/memory_connect.py --list

#### ChatGPT History Import
```bash
# Basic usage
make connect-memory CONNECTOR=chatgpt SOURCE=/path/to/chatgpt-export.zip

# AI-powered categorization with TF-IDF (fast)
python memory_connectors/memory_connect.py chatgpt /path/to/export.zip --method ai --embedding-model tfidf

# AI-powered categorization with LM Studio (high-quality semantic)
python memory_connectors/memory_connect.py chatgpt /path/to/export.zip --method ai --embedding-model lmstudio

# Keyword-based with custom categories
python memory_connectors/memory_connect.py chatgpt /path/to/export.zip --method keyword --edit-keywords

# Process limited conversations
python memory_connectors/memory_connect.py chatgpt /path/to/export.zip --max-items 100
```

**Categorization Methods:**
- **Keyword-based**: Fast, customizable categories using predefined keywords
- **AI-powered (TF-IDF)**: Statistical clustering, discovers conversation patterns
- **AI-powered (LM Studio)**: Semantic embeddings via neural networks (requires LM Studio)

# Custom output location
make connect-memory CONNECTOR=chatgpt SOURCE=/path/to/export.zip OUTPUT=./memory/custom

# Process only first 100 conversations
make connect-memory CONNECTOR=chatgpt SOURCE=/path/to/export.zip MAX_ITEMS=100

# Direct CLI usage
python memory_connect.py chatgpt /path/to/export.zip --output ./memory --max-items 100
```
#### Notion Workspace Import
```bash
# Basic usage
make connect-memory CONNECTOR=notion SOURCE=/path/to/notion-export.zip

# Custom output location
make connect-memory CONNECTOR=notion SOURCE=/path/to/export.zip OUTPUT=./memory/custom
  
python memory_connectors/memory_connect.py notion /path/to/export.zip --output ./memory

#### Getting ChatGPT Export
1. Go to [ChatGPT Settings](https://chatgpt.com/settings/data-controls)
2. Click "Export data"
3. Wait for email with download link
4. Extract the ZIP file
5. Use the extracted folder or ZIP file with the connector

#### Nuclino Workspace Import
```bash
# Basic usage
make connect-memory CONNECTOR=nuclino SOURCE=/path/to/nuclino-export.zip

# Custom output location  
make connect-memory CONNECTOR=nuclino SOURCE=/path/to/export.zip OUTPUT=./memory/custom

# Direct CLI usage
python memory_connectors/memory_connect.py nuclino /path/to/export.zip --output ./memory

#### Getting Notion Export
1. Go to your Notion workspace settings
2. Click "Settings & members" → "Settings"
3. Scroll to "Export content" and click "Export all workspace content"
4. Choose "Markdown & CSV" format
5. Click "Export" and wait for the download
6. Use the downloaded ZIP file with the connector

#### Getting Nuclino Export
1. Go to your Nuclino workspace
2. Open the main menu (☰) in the top left
3. Click the three dots (⋮) next to your workspace name
4. Select "Workspace settings"
5. Click "Export Workspace" in the Export section
6. Save the generated ZIP file
7. Use the downloaded ZIP file with the connector

#### GitHub Live Integration
```bash
# Basic usage - single repository
make connect-memory CONNECTOR=github SOURCE="microsoft/vscode" TOKEN=your_github_token

# Multiple repositories
make connect-memory CONNECTOR=github SOURCE="owner/repo1,owner/repo2" TOKEN=your_token

# Custom output and limits
make connect-memory CONNECTOR=github SOURCE="facebook/react" OUTPUT=./memory/custom MAX_ITEMS=50 TOKEN=your_token

# Direct CLI usage with interactive token input
python memory_connectors/memory_connect.py github "microsoft/vscode" --max-items 100

# Include specific content types
python memory_connectors/memory_connect.py github "owner/repo" --include-issues --include-prs --include-wiki --token your_token

#### Getting GitHub Personal Access Token
1. Go to [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. Click "Generate new token" → "Generate new token (classic)"
3. Set expiration and select scopes:
   - For **public repositories**: `public_repo` scope
   - For **private repositories**: `repo` scope (full access)
4. Click "Generate token" and copy the generated token
5. Use the token with the `--token` parameter or enter it when prompted

**Note**: Keep your token secure and never commit it to version control!

#### Google Docs Live Integration
```bash
# Basic usage - specific folder
make connect-memory CONNECTOR=google-docs SOURCE="1ABC123DEF456_folder_id" TOKEN=your_access_token

# Using Google Drive folder URL
make connect-memory CONNECTOR=google-docs SOURCE="https://drive.google.com/drive/folders/1ABC123DEF456" TOKEN=your_token

# Custom output and limits
make connect-memory CONNECTOR=google-docs SOURCE="folder_id" OUTPUT=./memory/custom MAX_ITEMS=20 TOKEN=your_token

# Direct CLI usage with interactive token input
python memory_connectors/memory_connect.py google-docs "1ABC123DEF456_folder_id" --max-items 15

#### Getting Google Drive Access Token

**Option 1: Google OAuth 2.0 Playground (Quick Testing)**
1. Go to [Google OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. In "Select & Authorize APIs" section:
   - Find "Drive API v3"
   - Select `https://www.googleapis.com/auth/drive.readonly`
3. Click "Authorize APIs" and sign in to your Google account
4. Click "Exchange authorization code for tokens"
5. Copy the "Access token" (valid for ~1 hour)

**Option 2: Google Cloud Console (Production Use)**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the "Google Drive API"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Configure OAuth consent screen if needed
6. Download the credentials JSON file
7. Use Google's OAuth 2.0 libraries to get access tokens

**Required Scopes**: `https://www.googleapis.com/auth/drive.readonly`

**Finding Folder ID from Google Drive URL**:
- From URL: `https://drive.google.com/drive/folders/1ABC123DEF456ghi789`  
- Folder ID: `1ABC123DEF456ghi789`

**Note**: Access tokens expire (usually 1 hour). For production use, implement token refresh or use service accounts.

### Memory Organization

The connectors automatically organize your conversations into:

- **Topics**: Conversations grouped by subject (AI Agents, Programming, Product Strategy, etc.)
- **User Profile**: Your communication style and preferences
- **Entity Links**: Cross-referenced relationships and projects
- **Search Strategy**: Optimized for mem-agent discovery

Example organized structure:
```
memory/mcp-server/
├── user.md                     # Your profile and navigation
└── entities/
    └── chatgpt-history/
        ├── index.md            # Overview and usage examples
        ├── topics/             # Topic-organized conversation lists
        │   ├── dria.md
        │   ├── ai-agents.md
        │   └── programming.md
        └── conversations/      # Individual conversation files
            ├── conv_0-project-discussion.md
            └── conv_1-technical-planning.md
  
### Testing Your Memory

After importing, test the memory system:

1. Start the mem-agent: `make run-agent`
2. Start Claude Desktop with the MCP server
3. Ask questions like:
   - "What can you tell me about our product roadmap?"
   - "What were my thoughts on AI agent frameworks?"
   - "Summarize my recent technical discussions"

The agent should access your real conversation history instead of providing generic responses.

## Architecture

### Mem-Agent
- **Dria's Memory Agent**: Specialized LLM fine-tuned for memory management and retrieval
- **Local Deployment**: Runs via LM Studio (MLX) or vLLM for privacy and speed
- **Multiple Variants**: 4-bit, 8-bit, and bf16 quantizations available
- **Tool Integration**: Purpose-built for file operations and memory search

### Memory Structure
- **Obsidian-style**: Markdown files with wikilink navigation
- **Topic Organization**: Automatic categorization by subject matter
- **Entity Relationships**: Cross-referenced connections between conversations
- **Search Optimization**: Structured for efficient agent discovery

### MCP Integration
- **FastMCP Framework**: High-performance Model Context Protocol server
- **Claude Desktop**: Claude's desktop app
- **Claude Code**: Anthropic's agentic coding tool that lives in your terminal

#### Claude Code Setup

**Prerequisites**: Start your memory server first:
```bash
make run-agent  # Required: vLLM or MLX model server must be running
```

**Add MCP Server:**
```bash
claude mcp add mem-agent \
  --env MEMORY_DIR="/path/to/your/memory/directory" \
  -- python "/path/to/mcp_server/server.py"
```

**Verify & Use:**
```bash
claude mcp list  # Should show mem-agent as connected
```

Now Claude Code can access your memory system for contextual assistance during development.
- **Tool Execution**: Sandboxed code execution for memory operations
- **Debug Logging**: Comprehensive logging for troubleshooting

#### ChatGPT Integration

**Prerequisites**: Complete memory setup and start your local agent:
```bash
make setup      # Configure memory directory
make run-agent  # Start local vLLM/MLX model server
```

**Start MCP-Compliant HTTP Server:**
```bash
make serve-mcp-http  # Starts server on localhost:8081/mcp
```

**Expose with ngrok (separate terminal):**
```bash
ngrok http 8081  # Copy the forwarding URL
```

**Configure ChatGPT:**
1. Go to [ChatGPT Settings → Connectors](https://chatgpt.com/#settings/Connectors)
2. Enable **Developer mode** in Advanced settings
3. Add new MCP server:
   - **Name**: `mem-agent`
   - **URL**: `https://your-ngrok-url.ngrok.io/mcp`
   - **Protocol**: HTTP
   - **Authentication**: None

**Usage in ChatGPT:**
Select **Developer mode** → Choose `mem-agent` connector → Ask questions like:
- "Use mem-agent to search my memory for discussions about AI research"
- "Query my memory for information about recent project work"

## Troubleshooting

### Common Issues

**Agent returns generic responses instead of using memory:**
- Check that memory files exist in the configured path
- Verify user.md contains proper topic navigation
- Enable debug logging to see agent's reasoning process
- Test with direct questions about known conversation topics

**MCP connection issues:**
- Check Claude Desktop configuration in `~/.config/claude/claude_desktop.json`
- Verify PATH configuration includes LM Studio binary
- Increase timeout settings for large memory imports
- Review logs in `~/Library/Logs/Claude/mcp-server-memory-agent-stdio.log`

**Memory import failures:**
- Ensure export format is supported (.zip or .json for ChatGPT)
- Check file permissions and disk space
- Try with --max-items to limit processing scope
- Verify export contains expected data structure

### Debug Mode

Enable detailed logging by setting environment variables:
```bash
FASTMCP_LOG_LEVEL=DEBUG make serve-mcp
```

Or check the agent's internal reasoning in the log files during operation.

## Development

### Adding New Connectors

1. Create connector class inheriting from `BaseMemoryConnector`
2. Implement required methods: `extract_data()`, `organize_data()`, `generate_memory_files()`
3. Add to connector registry in `memory_connect.py`
4. Update README with usage examples

Example connector skeleton:
```python
from memory_connectors.base import BaseMemoryConnector

class MyConnector(BaseMemoryConnector):
    @property
    def connector_name(self) -> str:
        return "My Service"
    
    @property 
    def supported_formats(self) -> list:
        return ['.zip', '.json']
    
    def extract_data(self, source_path: str) -> Dict[str, Any]:
        # Parse source data
        pass
    
    def organize_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        # Organize into topics  
        pass
    
    def generate_memory_files(self, organized_data: Dict[str, Any]) -> None:
        # Generate markdown files
        pass
```

### Contributing

This system is designed as local add-ons that don't affect the main mem-agent-mcp repository:

- Memory connectors are local extensions
- Legacy compatibility is maintained
- All changes preserve existing functionality
- Debug improvements enhance troubleshooting

Pull requests welcome for new connectors and improvements!
