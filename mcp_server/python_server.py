from agent import execute_sandboxed_code

from fastmcp import FastMCP

def extract_python_code(response: str) -> str:
    """
    Extract the python code from the response and format it with Black.

    Args:
        response: The response from the model.

    Returns:
        The formatted python code from the response.
    """
    if "<python>" in response and "</python>" in response:
        response = response.split("<python>")[1].split("</python>")[0]
        if "```" in response:
            code = response.split("```")[1].split("```")[0]
        else:
            code = response
        
        return code
    else:
        return response
    

# Initialize FastMCP
mcp = FastMCP("python-server")

@mcp.tool
async def execute_python_code(code: str) -> str:
    """
    Execute the given Python code.
    """
    return execute_sandboxed_code(code)


if __name__ == "__main__":
    mcp.run(transport="stdio")