import os
import time
import autogen
import sys
sys.path.append(os.path.abspath('../../'))

from utils import simple_parse, config_list
def get_task_prompt(rfc):
    task_prompt = f"Your job is to translate specifications descibed in RFC documents to well defined and constrained 3D code. \n \
                    {rfc} \n  \
                    Make sure you constrain the code fields for each message type, especially for those constraints using 'must', 'must not', ....\n \
                    Execute code with the supplied function simple_parse only, do NOT use any other functions. Also, Please ***do DOT infer or interprete the 3D code directly***!!! If the code does not successfuly parse, you must fix it. Remember you are generating 3D code, not C code.\n \
                    Add comments to your code and explain your choices \n \
                    "
    return task_prompt

def get_developer_prompt(manual, example):
    developer_prompt = f"You are an expert developer on the 3D language, a Dependent Data Description DSL built on top of c. \
                            You only write syntactically correct 3d code. You make sure that any 3d code follows syntax rules in the manual: \
                            ********* \
                            {manual} \
                            ********* \
                            Here is a checklist of things to keep in mind: \n \
                            - Different message types are unioned by casetype.\ For adding one message type, you only need to add a case in casetype and add type or struct definitions. Please **** do NOT omit **** any existing details!!!\
                            - Your code can only have one entrypoint. The entrypoint name should be more specific, instead of general 'message'. If there are multiple message types your entrypoint function must a higher level function \
                            - *** DO NOT use 'type' as an identifier *** It is a reserved keyword! Use 'message_type' or 'Type' instead.  \
                            - You must add constraints for all fields, if they are mentioned in documentations.\
                            - Do NOT initialize array with zero length!! **DONOT** use 'UINT8BE Body[0];' or 'UINT8BE Body[0:];' or ' UINT8BE Body[]';\
                            - Use 'unit Empty;' for empty switch case struct.\
                            - **Donot** use Ternary expressions like ? :\
                            - Try not use 'define' for constants.\
                            - The 'casetype' syntax should follow this structure: casetype _NAME (Type variable_name) {{ switch(variable_name) {{ ... }} }} NAME;. The Type variable_name should be defined separately, outside of the 'casetype'. Additionally, every case within the casetype must contain a valid structure or logic. Avoid having empty cases like: 'case 1: case 2:'. Do not use 'Default:'  \
                            - Donnot generate constraint for Checksum calculation \
                            - Don't use '[:]' for array size, e.g. **donot*** use 'UINT8BE Data[:];' \
                            - Don't access array element, e.g., 'Data[0]', 'Data[1]' are not supported \
                            - For a field1, if its constraint depends on another field2, and field2 is defined after field1, please add the constraint after field2, because field2 is not defined while defining field1. \
                            - For variable-length field while the length is not specified by any field in that struct, don't use placeholder and init it as 0. please define Parameterized data types: e.g. typedef struct _MESSAGE(UINT32 len) where (len >= sizeof (this)) {{UINT8 Code; {{...}}  UINT8 Data[:byte-size len - sizeof (this)];}} MESSAGE; .\
                            - All defined structs must have names, e.g. a struct in a switch statement -> case VALUE: struct {{ }} name; OR a typedef struct name {{ }}name;\
                            - If a field is only 3 bits, Don't 'UINT8BE flag;' use UINT8BE 'flag: 3'. The syntax of bitfields in 3D is similar to that of C. e.g. {{ UINT8BE f:4; UINT8BE g:4; }} packs two 4 bit fields into a single byte.\
                            - Please don't declare one type twice in the 3D code. Please don't redefine bitfield types like UINT.\
                            - Extract structs and casetypes, and do not nest them inside of other structs, wherever possible to follow idomatic 3d. \n\n \
                            - constraints can only be specified on scalar fields and may refer to preceding scalar fields. e.g {{ UINT8BE f; UINT8BE g {{g>f}};}} \
                            - In 3D struct type, you can't access fields using '.' notation. e.g. struct.field is NOT VALID.\
                            - Base Types can only be one of the following: UINT8BE, UINT16BE, UINT32BE, UINT64BE. \
                            - The length of arrays in 3D can be determined by the values of preceding scalar field, e.g. {{UINT32BE  len; UINT16BE contents[:byte-size len]}} \
                            \n \n ############# \n \
                            Here is a few helpful examples of the task: \n {example}  \
                            \n \n ###########  \n Call the provided function only, make sure you pass syntactically correct code to the funtion only, do not wrap your code. Listen to the feedback from the parsing function and fix any syntax mistakes you make. Explain why you chose to add an action when you do. You MUST retain all fields in the code to translate.\n  "
    return developer_prompt

def agent_config(manual, example):
    engineer = autogen.AssistantAgent(
        name="Developer",
        llm_config={"config_list": config_list},
        is_termination_msg=lambda x: x.get("content", "") and "EverParse succeeded!" in x.get("content", "").rstrip(),
        max_consecutive_auto_reply = 30,
        system_message=get_developer_prompt(manual, example),
    )
    executor = autogen.UserProxyAgent(
        name="Executor",
        system_message="Executor. Execute the 3d code written by the Developer using the custom function simple_parse. You can only execute code using the provided function!! Please ***donot infer and execute the 3D code directly***!",    
        human_input_mode="NEVER",
        code_execution_config={"last_n_messages": 1, "work_dir": "coding", "use_docker": False},
    )

    engineer.register_for_llm(name="simple_parse", description="Parse the 3D code and return the result. If the code is syntactically correct, return 'EverParse succeeded!'. If there are syntax errors, return the error message.")(simple_parse)
    executor.register_for_execution(name="simple_parse")(simple_parse)

    return [engineer, executor]

def agent_loop(manual, rfc, example):
    agent_list = agent_config(manual, example)

    agent_list[1].initiate_chat(
    agent_list[0],
    message=get_task_prompt(rfc)
    )

def extract_format(rfc):
    request_success = False
    with open("DSL/3d_syntax_check.txt", "r") as f:
        manual = f.read()
    with open("example/example.txt", "r") as f:
        example = f.read()
    while not request_success:
        try:
            agent_loop(manual, rfc, example)
            request_success = True
        except Exception as e:
            print(f"Error: {e}")
            print("Retrying......")
            time.sleep(10)
            continue
