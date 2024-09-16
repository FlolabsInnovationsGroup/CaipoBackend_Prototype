from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
import yaml
from ai_core.utils import load_schema_from_mongodb, save_schema_to_mongodb, prepare_output_structures, logging
from tools.tool_factory import get_tools_info
from ai_core.state import MetaStep, MetaStepList, MissingFunction, MissingFunctionList, OutputStructure, OutputStructureList
from ai_core.workflow import create_graph
from langchain_core.messages import HumanMessage

# Prepare prompts Templates
with open('prompts.yaml', 'r') as file:
    prompts = yaml.safe_load(file)

workflow_designer_template = prompts.get('workflow_designer')
output_structure_designer_template = prompts.get('output_structure_designer')
missing_function_identifier_template = prompts.get('missing_function_identifier')
supervisor_prompt_designer_template = prompts.get('supervisor_prompt_designer')

workflow_designer_prompt = PromptTemplate(
    input_variables=["objective", "functions"],
    template=workflow_designer_template
)

output_structure_designer_prompt = PromptTemplate(
    input_variables=["workflow", "functions"],
    template=output_structure_designer_template
)

missing_function_identifier_prompt = PromptTemplate(
    input_variables=["workflow", "functions"],
    template=missing_function_identifier_template
)

supervisor_prompt_designer_prompt = PromptTemplate(
    input_variables=["workflow"],
    template=supervisor_prompt_designer_template
)


def enter_chain(message: str):
    """
    This function is used to start the workflow.
    """
    results = {
        "messages": [HumanMessage(content=message)],
    }
    return results


def generate_steps_and_supervisor_prompt(llm, obj, funcs):
    """
    This function is used to generate a workflow with steps and supervisor prompt.
    """
    # Check if workflow exists in MongoDB
    existing_workflow = load_schema_from_mongodb(key=obj, collection_name="workflows")
    if existing_workflow:
        # Fetch step details from the 'steps' collection and create MetaStep objects
        workflow_steps = []
        for step in existing_workflow["steps"]:
            if isinstance(step, str):
                step_details = load_schema_from_mongodb(key=step, collection_name="steps")
                if step_details:
                    workflow_steps.append(MetaStep(**step_details))
                else:
                    logging.warning(f"Step '{step}' not found in 'steps' collection")
            elif isinstance(step, dict):
                workflow_steps.append(MetaStep(**step))
            else:
                logging.warning(f"Unexpected step format: {step}")
        
        workflow = MetaStepList(steps=workflow_steps)
        supervisor_prompt = existing_workflow["supervisor_prompt"]
    else:
        # Create workflow using LLM
        workflow = llm.with_structured_output(MetaStepList).invoke(
            workflow_designer_prompt.format(objective=obj, functions=str(funcs))
        )
        for step in workflow.steps:
            save_schema_to_mongodb(step.dict(), key=step.step_name, collection_name="steps")
        
        # Create supervisor prompt
        supervisor_prompt = llm.invoke(
            supervisor_prompt_designer_prompt.format(workflow=str(workflow))
        ).content
        save_schema_to_mongodb({
            "supervisor_prompt": supervisor_prompt,
            "steps": [step.step_name for step in workflow.steps]  # Store steps as dictionaries
        }, key=obj, collection_name="workflows")

    logging.info(f"Generated workflow with {len(workflow.steps)} steps")
    
    return workflow, supervisor_prompt


def identify_missing_functions(llm, obj, workflow, funcs: dict):
    """
    This function is used to identify missing functions in the workflow.
    """
    # Search for existing missing functions in the database
    existing_missing_functions = load_schema_from_mongodb(key_prefix=f"{obj}_", collection_name="missing_functions")
    logging.info(f"Existing missing functions: {existing_missing_functions}")
    
    if existing_missing_functions:
        missing_functions = []
        for func in existing_missing_functions:
            missing_functions.append(MissingFunction(**func["function"]))
        missing_functions = MissingFunctionList(missing_functions=missing_functions)
    else:
        # Identify missing functions using LLM if not found in the database
        prompt = missing_function_identifier_prompt.format(workflow=workflow, functions=str(funcs))
        missing_functions = llm.with_structured_output(MissingFunctionList).invoke(prompt)
        
        # Save each missing function in the database
        for missing_function in missing_functions.missing_functions:
            key = f"{obj}_{missing_function.name}"
            save_schema_to_mongodb({"function": missing_function.dict()}, key=key, collection_name="missing_functions")
    
    if missing_functions.missing_functions:
        print("The following functions need to be implemented before running the workflow:")
        print(missing_functions)
        print("\nPlease implement these functions and add them to the available tools before creating the workflow graph.")

    return missing_functions.missing_functions


def generate_output_structures(llm, workflow, funcs) -> OutputStructureList:
    """
    This function is used to generate output structures(what information the agent will produce) for each agent in the workflow.
    """
    # Check if output structures exist in MongoDB
    output_structures = []
    missing_structures = []
    existing_structures_info = []
    for step in workflow.steps:
        existing_structure = load_schema_from_mongodb(key=step.output, collection_name="output_structures")
        if existing_structure:
            output_structures.append(OutputStructure(**existing_structure))
            existing_structures_info.append(f"{step.output}: Already exists")
        else:
            missing_structures.append(step.output)
            existing_structures_info.append(f"{step.output}: Needs to be generated")

    if missing_structures:
        # Generate only missing output structures
        parser = PydanticOutputParser(pydantic_object=OutputStructureList)
        prompt = output_structure_designer_prompt.format(
            workflow=str(workflow),
            functions=str(funcs),
            existing_structures="\n".join(existing_structures_info)
        ) + parser.get_format_instructions()
        response = llm.invoke(prompt)
        cleaned_str = response.content.replace("json", "").replace("```", '')
        new_output_structures = OutputStructureList.parse_raw(cleaned_str)

        for os in new_output_structures.output_structures:
            if os.output_structure_title in missing_structures:
                save_schema_to_mongodb(os.dict(), key=os.output_structure_title, collection_name="output_structures")
                output_structures.append(os)

    return OutputStructureList(output_structures=output_structures)


def create_new_workflow(llm, obj, funcs, debug=False):
    """
    This function is used to create a new workflow. By calling all the functions above
    And create_graph function to create a graph for the workflow.

    Args:
        llm: The language model to use.
        obj: The objective of the workflow.
        funcs: The available functions.
        debug: Whether to print debug information.
    
    To Improve:
        - Add feature to use different LLM for different agents
        - Add feature to enables supervisor to handle loops and conditionals in the workflow (e.g. writer + validator)
    """
    logging.info(f"Creating new workflow for objective: {obj}")
    logging.info(f"Available functions: {funcs}")
    
    logging.info("Step 1: Generating steps and supervisor prompt")
    logging.debug(f"Objective: {obj}")
    logging.info(f"Available tools: {list(funcs.keys())}")
    tools_info = get_tools_info(funcs)
    logging.info(f"Tools info: {tools_info}")
    workflow, supervisor_prompt = generate_steps_and_supervisor_prompt(llm, obj, tools_info)
    logging.info(f"Workflow: {workflow}")

    if identify_missing_functions(llm, obj, workflow, tools_info):
        return
    
    logging.info("Step 2: Generating output structures")
    logging.debug(f"Functions: {tools_info}")
    if not workflow.steps:
        logging.warning("Workflow is empty. No steps to generate output structures for.")
    else:
        output_structure_list = generate_output_structures(llm, workflow, tools_info)
    
    logging.info("Step 3: Preparing output structures")
    output_structures_dict = prepare_output_structures(output_structure_list)
    logging.info(f"Output structures: {output_structures_dict}")
    
    logging.info("Step 4: Creating graph")
    graph = create_graph(llm, supervisor_prompt, workflow, output_structures_dict, funcs, debug)
    logging.info("Workflow creation completed")

    return enter_chain | graph
