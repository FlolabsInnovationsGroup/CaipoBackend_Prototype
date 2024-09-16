from typing import List, Any, Optional, Union
from langchain_core.pydantic_v1 import BaseModel, Field, validator
from langchain_core.tools import StructuredTool
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import os, re
import logging

from ai_core.state import OutputStructureList, MissingFunctionList, MissingFunction

logging.basicConfig(level=logging.INFO)
load_dotenv(override=True)


def sanitize_name(name):
    """
    To create a valid name for the workflow, step, tool, etc.
    """
    # Remove all invalid characters and replace spaces with underscores
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name)


def process_list(details):
    if isinstance(details, dict):
        item_type = details.get("property_type")
        if item_type == "list":
            return List[process_list(details.get("property_list", {}))]
        else:
            return eval(item_type) if item_type else Any
    else:
        return Any


def process_property(prop_details: dict) -> Any:
    prop_type = prop_details.get("property_type")
    
    if prop_type == "list":
        list_details = prop_details.get("property_list", {})
        return List[process_list(list_details)]
    else:
        return eval(prop_type) if prop_type else Any
    

def build_model_from_schema(schema: dict) -> BaseModel:
    """
    Construct a Pydantic model from a dict, so that we get the format instruction automatically.
    """
    fields = {}
    annotations = {}
    properties = schema.get("properties", {})
    
    for prop, details in properties.items():
        field_type = process_property(details)
        description = details.get("property_description", "")
        
        # Handle optional fields
        if prop not in schema.get("output_structure_required", []):
            field_type = Optional[field_type]
        
        # Add type annotations for each field
        annotations[prop] = field_type
        fields[prop] = Field(description=description)
    
    model_name = schema.get("output_structure_title", "DynamicModel")

    # Dynamically create the Pydantic model class with annotations
    DynamicModel = type(model_name, (BaseModel,), {"__annotations__": annotations, **fields})
    return DynamicModel


def prepare_output_structures(output_structures: OutputStructureList) -> dict:
    """
    Prepare the output structures for the workflow.
    """
    prepared_structures = {}
    for structure in output_structures.output_structures:
        state_instance = build_model_from_schema(structure.dict())
        prepared_structures[structure.output_structure_title] = state_instance
    return prepared_structures


def prepare_available_tools(missing_functions: MissingFunctionList):
    """
    Prepare the available tools for the workflow. (Not used for now)
    """
    available_tools = {}
    for tool in missing_functions.missing_functions:
        tool = []#ToolFactory.get_tool(tool.name)
        if tool is None:
            raise ValueError(f"Tool '{tool.name}' is not available.")
        available_tools[tool.name] = tool
    return available_tools


def save_schema_to_mongodb(schema: dict, key: str, 
                            host=os.getenv('MONGO_HOST'), 
                            port=int(os.getenv('MONGO_PORT')), 
                            db_name=os.getenv('MONGO_CAIPO_DB'), 
                            collection_name=os.getenv('MONGO_SCHEMA_COLLECTION')):
    """
    Save a dict (structure of a class) to the MongoDB.
    """
    client = MongoClient(host, port)
    db = client[db_name]
    collection = db[collection_name]
    collection.insert_one({'_id': key, 'schema': schema})


def load_schema_from_mongodb(key: str = None, key_prefix: str = None,
                             host=os.getenv('MONGO_HOST'),
                             port=int(os.getenv('MONGO_PORT')),
                             db_name=os.getenv('MONGO_CAIPO_DB'),
                             collection_name=os.getenv('MONGO_SCHEMA_COLLECTION')) -> Union[dict, List[dict]]:
    """
    Load a dict (structure of a class) from the MongoDB.
    """
    if not key and not key_prefix:
        raise ValueError("Either 'key' or 'key_prefix' must be provided")

    client = MongoClient(host, port)
    db = client[db_name]
    collection = db[collection_name]
    
    if key:
        document = collection.find_one({'_id': key})
        if document:
            return document['schema']
    elif key_prefix:
        # Find all documents with the given prefix
        results = collection.find({'_id': {'$regex': f'^{key_prefix}'}}).sort('_id', -1)
        documents = list(results)
        if documents:
            return [doc['schema'] for doc in documents]
    
    logging.warning(f"No schema found for key '{key}' or prefix '{key_prefix}'")
    return {} if key else []


def delete_schema_from_mongodb(key: str = None, key_prefix: str = None, 
                               collection_name: str=os.getenv('MONGO_SCHEMA_COLLECTION'),
                               host=os.getenv('MONGO_HOST'),
                               port=int(os.getenv('MONGO_PORT')),
                               db_name=os.getenv('MONGO_CAIPO_DB')):
    """
    Delete a dict (structure of a class) from the MongoDB.
    """
    if not key and not key_prefix:
        raise ValueError("Either 'key' or 'key_prefix' must be provided")

    client = MongoClient(host, port)
    db = client[db_name]
    collection = db[collection_name]
    
    if key:
        result = collection.delete_one({'_id': key})
        if result.deleted_count == 0:
            logging.warning(f"No schema found for key '{key}'")
    elif key_prefix:
        result = collection.delete_many({'_id': {'$regex': f'^{key_prefix}'}})
        if result.deleted_count == 0:
            logging.warning(f"No schemas found with prefix '{key_prefix}'")
    
    return result.deleted_count


def delete_workflow(obj):
    """
    Delete a workflow (workflow, steps, output structures and missing functions) related to the obj from the MongoDB.
    """
    workflow = load_schema_from_mongodb(key=obj, collection_name="workflows")
    
    if workflow:
        step_keys = workflow.get('steps', [])
        output_keys = []

        for step_key in step_keys:
            step = load_schema_from_mongodb(key=step_key, collection_name="steps")
            output_keys.extend([step['output']] if step and 'output' in step else [])
            delete_schema_from_mongodb(key=step_key, collection_name="steps")
        
        for output_key in output_keys:
            delete_schema_from_mongodb(key=output_key, collection_name="output_structures")
    
    delete_schema_from_mongodb(key_prefix=f"{obj}_", collection_name="missing_functions")
    
    delete_schema_from_mongodb(key=obj, collection_name="workflows")