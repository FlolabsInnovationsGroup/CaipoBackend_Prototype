from langchain_core.tools import tool
from typing import List, Annotated
from pathlib import Path
import json  # Add this import
from datetime import datetime  # Add this import

@tool
def get_current_time() -> str:
    """Get the current time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
