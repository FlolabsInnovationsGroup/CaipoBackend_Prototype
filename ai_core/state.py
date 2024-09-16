from typing import TypedDict, List, Annotated, Optional, Dict, Any, Sequence, Union, ForwardRef
from langchain_core.pydantic_v1 import BaseModel, Field, validator
from pydantic import model_validator
import json
import operator


Property = ForwardRef('Property')

class AgentState(TypedDict):
    """
    The Data Structure between agents
    """
    messages: Annotated[List[str], operator.add]
    team_members: Annotated[List[str], "List of team members involved in the step"]
    next: Annotated[str, "The suggested next step or agent"]


class MetaStep(BaseModel):
    """
    The Meta Step of the Workflow
    """
    step_name: str = Field(description="Step Name")
    agent: str = Field(description="Agent Name")
    tasks: str = Field(description="Describe the tasks the agent will handle for this step")
    prompt: str = Field(description="Define an efficient prompt for this agent")
    functions: List[str] = Field(description="List of python functions the agent can use")
    output: str = Field(description="Name of specific output structure of the agent")

    def __str__(self):
        return json.dumps({
            "step_name": self.step_name,
            "agent": self.agent,
            "tasks": self.tasks,
            "prompt": self.prompt,
            "functions": self.functions,
            "output": self.output
        }, indent=2)
    

class MetaStepList(BaseModel):
    """
    The Meta Step List of the Workflow
    """
    steps: List[MetaStep]

    def __str__(self):
        return "\n".join(str(step) for step in self.steps)


class Property(BaseModel):
    """
    The Property or attribute of the Output Structure
    """
    property_type: str = Field(description="Data type of property, simple types or list", 
                       enum=["str", "int", "bool", "float", "None", "datetime", "list"])
    property_description: str = Field(description="Description of the property")
    property_default: Optional[Any] = Field(description="Default value of the property, None for empty")
    property_list: Optional[Union[Dict[str, Property], Property]] = Field(description="List details if and only if type is list") 
    
    @validator('property_list', pre=True, always=True)
    def validate_list(cls, v, values):
        # Check if 'type' exists in values
        if 'property_type' in values and values['property_type'] == 'list' and v is None:
            raise ValueError("The 'list' field must be provided when 'type' is 'list'")
        # If type is not 'list', ensure list is None
        if 'property_type' in values and values['property_type'] != 'list':
            return None
        return v
    
    def __str__(self):
        return json.dumps(self.dict(), indent=2)
    

class OutputStructure(BaseModel):
    """
    The Output Structure of the Workflow
    """
    output_structure_title: str = Field(description="Name of the structure")
    output_structure_description: str = Field(description="Description of the structure")
    output_structure_type: str = Field(description="Data type of the structure, usually object, sometimes simple type")
    properties: Dict[str, Property] = Field(description="Properties of the structure")
    output_structure_required: List[str] = Field(description="List of required properties' name")

    def __str__(self):
        return json.dumps({
            "title": self.output_structure_title,
            "description": self.output_structure_description,
            "type": self.output_structure_type,
            "properties": {k: v.dict() for k, v in self.properties.items()},
            "required": self.output_structure_required
        }, indent=2)


class OutputStructureList(BaseModel):
    """
    The Output Structure List of the Workflow
    """
    output_structures: List[OutputStructure] = Field(description="List of output structures")

    def __str__(self):
        return "\n".join(str(structure) for structure in self.output_structures)


class MissingFunction(BaseModel):
    """
    The Missing Function of the Workflow
    """
    name: str=Field(description="Name of the missing function")
    description: str=Field(description="Description of the missing function")
    input: str=Field(description="Input data type or format")
    input_type: str=Field(description="Input type, e.g., list, dict, etc.")
    output: str=Field(description="Expected output")
    output_type: str=Field(description="Output type or format")

    def __str__(self):
        return json.dumps({
            "name": self.name,
            "description": self.description,
            "input": self.input,
            "input_type": self.input_type,
            "output": self.output,
            "output_type": self.output_type
        }, indent=2)


class MissingFunctionList(BaseModel):
    """
    The Missing Function List of the Workflow
    """
    missing_functions: List[MissingFunction]

    def __str__(self):
        return "\n".join(str(function) for function in self.missing_functions)


Property.update_forward_refs()