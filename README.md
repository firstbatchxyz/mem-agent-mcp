# mem-agent-mcp

## Supported Platforms

- macOS
- Linux (with GPU)

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

## Example user.md

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

## Example entity files (jane_doe.md and acme_corp.md)

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