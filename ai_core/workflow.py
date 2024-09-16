from typing import Sequence, List
from langchain.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import BaseGenerationOutputParser
from langchain_core.outputs import Generation
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent
from langgraph.graph import END, StateGraph, START
from langchain.output_parsers import PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel

import functools
from ai_core.state import MetaStepList, AgentState
from ai_core.utils import sanitize_name, logging


class JsonOutputParser(BaseGenerationOutputParser[str]):
    """
    A Parser wrapper which handles the OutputParserException when JsonOutputFunctionsParser fails
    """

    def parse_result(self, result: List[Generation], *, partial: bool = False) -> str:
        try:
            return JsonOutputFunctionsParser().parse_result(result)
        except OutputParserException as e:
            logging.info(f"result: {result}")
            if hasattr(result, 'content'):
                return result.content
            return str(result)


class DynamicAgent:
    def __init__(
        self,
        agent_name: str, prompt: str,
        llm: BaseLanguageModel,
        output_structure: BaseModel,
        tools: Sequence[BaseTool] = None
    ):
        self.parser = PydanticOutputParser(pydantic_object=output_structure)
        self.agent_name = agent_name

        logging.info(f"Creating agent: {self.agent_name}")
        logging.debug(f"Prompt: {prompt}")

        # Create the prompt with the format instructions
        prompt = ChatPromptTemplate.from_messages([
                ("system", prompt),
                MessagesPlaceholder(variable_name="messages"),
                ("assistant", "{format_instructions}")
            ]
        ).partial(format_instructions=self.parser.get_format_instructions())

        logging.debug(f"Formatted Prompt: {prompt.format_messages(messages=["TEST MESSAGE"])}")

        self.with_tools = tools and len(tools) != 0
        if self.with_tools:
            self.agent = create_react_agent(
                llm,
                tools=tools, 
                state_modifier=prompt
            )
        else:
            self.agent = (
                prompt
                | llm
            )
    
    def get_agent_node(self):
        """
        Get the agent node of the workflow
        """
        partial_agent_node = functools.partial(
            agent_node, agent=self.agent, name=self.agent_name
        )
        
        # Not using because partial_agent_node gives clearer output
        def wrapped_agent_node(state):
            """
            Wrapper function that calls the partial and parses the output
            """
            result = partial_agent_node(state)
            raw_output = result["messages"][-1].content
            logging.debug(f"Raw output: {raw_output}")
            try:
                if isinstance(raw_output, list):
                    parsed_output_list = []
                    for item in raw_output:
                        parsed_output_list.append(self.parser.parse(item))
                    logging.debug(f"Parsed output (list): {parsed_output_list}")
                    result["messages"][-1].content = [parsed_item.dict() for parsed_item in parsed_output_list]
                else:
                    parsed_output = self.parser.parse(raw_output)
                    logging.debug(f"Parsed output: {parsed_output}")
                    result["messages"][-1].content = str(parsed_output.dict())
            except Exception as e:
                logging.error(f"Error parsing output: {e}")
                result["messages"][-1].content = raw_output
            
            return result
        
        return partial_agent_node


def agent_node(state, agent, name):
    """
    Handles each agent's (not supervisor's) output and converts it into the correct format
    """
    logging.info(f"Invoking agent: {name}")
    logging.info(f"State: {state}")

    result = agent.invoke(state)
    # Get the content of the message
    if isinstance(result, dict) and 'messages' in result:
        message_content = result['messages'][-1].content
    elif hasattr(result, 'content'):
        message_content = result.content
    else:
        message_content = result
    
    logging.info(f"message_content type: {type(message_content)}")

    return {"messages": [AIMessage(content=message_content, name=name)]}


def create_team_supervisor(llm: BaseLanguageModel, system_prompt, members):
    """
    An LLM-based router.
    This function is used to determine which agent should be invoked next.
    """
    options = ["FINISH"] + members
    function_def = {
        "name": "route",
        "description": "Select the next role.",
        "parameters": {
            "title": "routeSchema",
            "type": "object",
            "properties": {
                "next": {
                    "title": "Next",
                    "anyOf": [
                        {"enum": options},
                    ],
                },
            },
            "required": ["next"],
        },
    }
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {options}",
            ),
        ]
    ).partial(options=str(options))

    return (
        prompt
        | llm.bind_functions(functions=[function_def], function_call="route")
        | JsonOutputParser()
    )


def create_graph(llm: BaseLanguageModel, 
                 supervisor_prompt: str,
                 workflow: MetaStepList, 
                 output_structures: dict, 
                 available_tools: dict,
                 debug: bool = False):
    """
    Creates a graph(workflow) base on the workflow.

    Args:
        llm: The language model to use for the workflow.
        supervisor_prompt: The prompt for the supervisor.
        workflow: The workflow to create.
        output_structures: The output structures for each agent.
        available_tools: The available tools for the workflow.
        debug: Whether to print debug information.

    To Improve:
        - Add feature to use different LLM for different agents
        - Add feature to enables supervisor to handle loops and conditionals in the workflow (e.g. writer + validator)
    """
    graph = StateGraph(AgentState)
    members = []

    # Create agents for each meta-step
    created_agents = {}  # Dictionary to keep track of created agents

    for a in workflow.steps:
        name = sanitize_name(a.agent)
        
        if name not in created_agents:
            prompt = a.prompt
            tools = []
            for func in a.functions:
                if func is None or func not in available_tools:
                    raise ValueError(f"Function '{func}' is either None or not available in available_tools.")
                tools.append(available_tools[func])
            output_structure = output_structures[a.output]
            
            agent = DynamicAgent(name, prompt, llm, output_structure, tools)
            agent_node = agent.get_agent_node()
            graph.add_node(name, agent_node)
            created_agents[name] = agent
            members.append(name)
        else:
            logging.warning(f"Agent '{name}' already exists. Skipping creation.")

    # Log members
    logging.info(f"Members: {members}")

    # Create supervisor
    supervisor = create_team_supervisor(llm, supervisor_prompt, members)
    graph.add_node("supervisor", supervisor)

    # Add edges
    for member in members:
        # We want our workers to ALWAYS "report back" to the supervisor when done
        graph.add_edge(member, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        lambda x: x["next"],
        {**{member: member for member in members}, "FINISH": END}
    )

    graph.add_edge(START, "supervisor")
    chain = graph.compile(debug=debug)

    return chain

