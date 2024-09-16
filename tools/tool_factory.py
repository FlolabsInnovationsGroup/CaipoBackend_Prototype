import importlib
import inspect
import os
from langchain_core.tools import StructuredTool
from typing import List
from langchain_core.tools import BaseTool

def collect_tool_functions(project_root=os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))):
    """
    Collect all functions with the @tool decorator from the project.
    """
    tool_functions = []

    # Recursively walk through the project directory
    for root, dirs, files in os.walk(project_root):
        for file in files:
            if file.endswith('.py'):  # Only process Python files
                module_path = os.path.join(root, file)
                module_name = module_path.replace(project_root, '').replace(os.sep, '.').strip('.py')

                # Dynamically import the module
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Collect functions with the @tool decorator
                for name, obj in inspect.getmembers(module):
                    if isinstance(obj, StructuredTool):
                        tool_functions.append(obj)

    return tool_functions


def get_all_tools_from_file(file_path: str=os.path.abspath('./tools/prebuilt_tools.py')) -> List['BaseTool']:
    """
    Returns a list of all tool instances defined in a specific file (prebuilt_tools.py).

    Args:
        file_path (str): The path to the file to scan for tool instances.

    Returns:
        List[BaseTool]: A list containing all the tool instances found in the file.
    """
    # Get the module name from the file path
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    # Dynamically import the module from the file path
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Get the module's global scope
    module_globals = module.__dict__

    # Collect and return all instances of BaseTool from the module
    return [
        obj for name, obj in module_globals.items()
        if isinstance(obj, BaseTool) and not name.startswith('_')
    ]


def get_all_tools() -> dict[str, BaseTool]:
    """
    Returns all available tool instances defined in project.
    
    Returns:
        dict[str, BaseTool]: A dictionary containing all the tool instances.
    """
    custom_tools = collect_tool_functions()
    prebuilt_tools = get_all_tools_from_file()
    return {
        tool.name: tool
        for tool in custom_tools + prebuilt_tools
    }


def get_tools_info(tools: dict[str, BaseTool]) -> dict[str, dict]:
    """
    Returns a list of tool descriptions.

    Args:
        tools (dict[str, BaseTool]): A dictionary of tool instances.

    Returns:
        dict[str, dict]: A dictionary of tool descriptions.

    """
    return {
        tool.name: {
            'description': tool.description,
            'args': tool.args
        }
        for tool in tools.values()
    }
