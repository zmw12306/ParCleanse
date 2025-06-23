import re
from FSM import *
from typing import Optional, Union, List

def find_matching_brace(text, start_index):
    """Find the index of the matching closing brace for the opening brace at start_index."""
    open_braces = 0
    for i in range(start_index, len(text)):
        if text[i] == '{':
            open_braces += 1
        elif text[i] == '}':
            open_braces -= 1
            if open_braces == 0:
                return i
    return -1  # Return -1 if no matching brace is found

def parse_simple_line(line) -> Optional[Union[List['Node'], List['FSM']]]:
    # pattern = r'(\w+)\s+(\w+)\s*\{\s*([^}]+)\s*\}\s*;\s*//.*'
    pattern = r'(\w+)\s+(\w+)(?:\s*\{\s*([^}]+)\s*\})?\s*;'
    # Use the regex to search the line
    match = re.search(pattern, line)

    if match:
        data_type = match.group(1)  # UINT8BE
        field_name = match.group(2)  # Magic
        condition = match.group(3)  # Magic == 42

        if data_type in ["UINT8BE", "UINT16BE", "UINT32BE", "UINT64BE"]:
            # Return a Node for simple types
            return [Node(field_name, data_type, condition)]
        
        else:
            # Attempt to find and parse the struct definition for this type
            if data_type in FSM_map:
                return [copy.deepcopy(FSM_map[data_type])]
            else:
                print(f"cannot find {data_type} in FSM_map")
                return None
    patternbit = r"(\w+)\s+(\w+)\s*:\s*(\d+)\s*(?:\{\s*([^}]+)\s*\})?\s*;"
    matchbit = re.search(patternbit, line)
    if matchbit:
        data_type = matchbit.group(1)  # UINT8BE
        field_name = matchbit.group(2)  # IHL
        bit_num =  matchbit.group(3)    # 4
        constraint = matchbit.group(4)
        if data_type in ["UINT8BE", "UINT16BE", "UINT32BE", "UINT64BE"]:
            return [Node(field_name, "bit"+bit_num, constraint)]
        else:
            raise ValueError(f"unhandled case")
            return None
    return None

def parse_array_line(line, array_names) -> Optional[Union[List['Node'], List['FSM']]]:
    # Define a regex pattern for identifying variable byte arrays
    array_pattern = re.compile(
    r"(\w+)\s+"                  # Match any word as the data type (e.g., UINT16BE)
    r"(\w+)\s*"                  # Match the variable name (e.g., entries)
    r"\[:byte-size\s*(\((.*?)\)|([^\]]+))\s*]"  # Match the size expression, parentheses optional
    )
    # Check if the line contains a variable byte array
    array_match = array_pattern.search(line.strip())
    if array_match:
        # Extract details of the byte array
        array_type = array_match.group(1)
        array_name = array_match.group(2)
        size_expression = array_match.group(3)
        array_names.add(array_name)
        
        if "sizeof(this)" in size_expression:
            if array_type == "UINT8BE":
                return [Node("empty", None, None), Node(array_name, array_type, None)]
            elif array_type == "UINT16BE":
                return [Node("empty", None, None), Node(array_name, array_type, None)]
            elif array_type == "UINT32BE":
                return [Node("empty", None, None), Node(array_name, array_type, None)]
            elif array_type == "UINT64BE":
                return [Node("empty", None, None), Node(array_name, array_type, None)]
            else:
                if array_type in FSM_map:
                    struct_fsm = copy.deepcopy(FSM_map[array_type])
                    struct_fsm.size_expr = None
                else:
                    raise ValueError(f"cannot find {array_type} in FSM_map")
                    return None

                return [FSM(f"emptyFSM_{array_type}", None), struct_fsm]
        else:

            if array_type == "UINT8BE":
                return [Node("empty", None, f"{size_expression} == 0"), Node(array_name, array_type, f"{size_expression} == 1")]
            elif array_type == "UINT16BE":
                return [Node("empty", None, f"{size_expression} == 0"), Node(array_name, array_type, f"{size_expression} == 2")]
            elif array_type == "UINT32BE":
                return [Node("empty", None, f"{size_expression} == 0"), Node(array_name, array_type, f"{size_expression} == 4")]
            elif array_type == "UINT64BE":
                return [Node("empty", None, f"{size_expression} == 0"), Node(array_name, array_type, f"{size_expression} == 8")]
            else:
                if array_type in FSM_map:
                    struct_fsm = copy.deepcopy(FSM_map[array_type])
                    struct_fsm.size_expr = size_expression
                else:
                    raise ValueError(f"cannot find {array_type} in FSM_map")
                    return None

                return [FSM(f"emptyFSM_{array_type}", size_expression), struct_fsm]
        
    
    array_pattern_num = re.compile(
    r"(\w+)\s+"                  # Match any word as the data type (e.g., UINT16BE)
    r"(\w+)\s*"                  # Match the variable name (e.g., entries)
    r"\[(\d+)]"  # Match the size number
    )
    array_match_num = array_pattern_num.search(line.strip())

    if array_match_num:
        array_name = array_match_num.group(2)
        array_type = array_match_num.group(1)
        array_length = array_match_num.group(3)
        array_names.add(array_name)
        if array_type == "UINT8BE":
            return [Node(array_match_num.group(2), 8 * int(array_length), None)]
        elif array_type == "UINT16BE":
            return [Node(array_match_num.group(2), 16 * int(array_length), None)]
        elif array_type == "UINT32BE":
            return [Node(array_match_num.group(2), 32 * int(array_length), None)]
        elif array_type == "UINT64BE":
            return [Node(array_match_num.group(2), 64 * int(array_length), None)]

    else:
        return None  

def parse_casetype_line(line) -> Optional[List['FSM']]:
    pattern = r'(\w+)\(([\w\s,]+)\)\s+(\w+);'
    match = re.match(pattern, line.strip())
    
    if match:
        data_type = match.group(1)  # e.g., MessageFormat
        params = match.group(2)     # e.g., Type, Length
        name = match.group(3)       # e.g., message
        
        return [copy.deepcopy(FSM_map[data_type])]

    else:
        return None

def parse_line(line, array_names)-> Optional[Union[List['Node'], List['FSM']]]:
    is_simple_line = parse_simple_line(line)
    if is_simple_line:
        return is_simple_line
    
    is_array_line = parse_array_line(line, array_names)
    if is_array_line:
        return is_array_line
    
    is_casetype_line = parse_casetype_line(line)
    if is_casetype_line:
        return is_casetype_line
    
    raise ValueError(f"unhandled case! {line}")

def parse_struct(module, array_names) -> FSM:
    struct_pattern = re.compile(
    r"typedef\s+struct\s+_(\w+)\s*(?:\([^)]*\))?\s*{\s*(.*?)\s*}\s*(\w+);", re.DOTALL
    )
    
    struct_match = struct_pattern.search(module.strip())
    if not struct_match:
        return None

    struct_body = struct_match.group(2)
    struct_name = struct_match.group(3)

    fsm = FSM(struct_name)

    lines = struct_body.splitlines()
    buffer = ""
    brace_depth = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        buffer += stripped + " "
        brace_depth += stripped.count("{") - stripped.count("}")

        if brace_depth == 0:
            node_or_FSM_list = parse_line(buffer.strip(), array_names)
            fsm.addlists(node_or_FSM_list)
            buffer = ""
    
    FSM_map[struct_name] = fsm       
    return fsm  

def parse_casebody(casebody_str, array_names) -> FSM:
    unit_pattern = r'unit\s+(\w+);'
    unit_match = re.match(unit_pattern, casebody_str.strip())
    if unit_match:
        return FSM("emptyFSM")

    # Handle the 'struct' case without a name after 'struct'
    struct_pattern = r'struct\s*\{'
    struct_match = re.search(struct_pattern, casebody_str.strip())

    if struct_match:
        start = struct_match.start()
        i = start
        i = casebody_str.find("{", i)
        end = find_matching_brace(casebody_str, i)
        
        if end != -1:
            # Extract the entire struct declaration
            struct_body = casebody_str[i+1:end].strip()  # Strip off the outer braces
            
            # Extract the struct name after the closing brace
            remaining_str = casebody_str[end+1:].strip()
            struct_name_match = re.match(r'(\w+)\s*;', remaining_str)
            
            if struct_name_match:
                struct_name = struct_name_match.group(1).strip()
                fsm = FSM(struct_name)
                
                # Parse the fields inside the struct
                lines = struct_body.splitlines()
                buffer = ""
                brace_depth = 0

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    
                    buffer += stripped + " "
                    brace_depth += stripped.count('{') - stripped.count('}')

                    if brace_depth == 0:
                        # We have a complete line to parse
                        nodelist = parse_line(buffer, array_names)
                        fsm.addlists(nodelist)
                        buffer = ""  # Reset the buffer for the next line
                   

                FSM_map[struct_name] = fsm
                return fsm

    pattern = r'(\w+)\s+(\w+)(?:\s*\{\s*([^}]+)\s*\})?\s*;'
    match = re.search(pattern, casebody_str)
    if match:
        data_type = match.group(1)  # UINT8BE
        field_name = match.group(2)  # Magic
        condition = match.group(3)  # Magic == 42
        # Attempt to find and parse the struct definition for this type
        if data_type in FSM_map:
            return copy.deepcopy(FSM_map[data_type])
        else:
            raise ValueError(f"cannot find {data_type} in FSM_map")
            
    else:
        print(casebody_str)
        raise ValueError(f"unhandled situation: case body not match")
        return None

def parse_casetype(casetype_str, array_names) -> FSM:
    # Regex to capture the casetype name, type, and body
    casetype_pattern = re.compile(
    r"casetype\s+(\w+)\s*\(([\w\s,]+)\)\s*{\s*switch\s*\(\s*(\w+)\s*\)\s*{([\s\S]+?)}\s*}\s*(\w+);",
    re.DOTALL
    )
    # Match the casetype definition
    casetype_match = casetype_pattern.search(casetype_str.strip())
    if not casetype_match:
        raise ValueError(f"No valid casetype found in the input: {casetype_str}.")
    
    casetype_name = casetype_match.group(1)
    casetype_params = casetype_match.group(2)
    switch_param = casetype_match.group(3)    # Type
    cases_body = casetype_match.group(4)
    alias_name = casetype_match.group(5)
    
    # Extract the type of the switch parameter
    casetype_type = None
    for param in casetype_params.split(","):
        param = param.strip()
        if param.endswith(switch_param):
            casetype_type = param.split()[0]
            break

    print(casetype_type)
    fsm = FSM(alias_name)

    # Regex to capture each individual case
    case_pattern = re.compile(
        r"case\s+(\d+)\s*:\s*(.+?)(?=case\s+\d+\s*:|$)", re.DOTALL
    )
    
    # Find all cases
    cases = case_pattern.findall(cases_body)
    
    # Generate a list of casetype strings with one case each
    for case_number, case_body in cases:
       casebody_FSM =  parse_casebody(case_body, array_names)
       fsm.entry.add_transition(f"{switch_param} == {case_number}", casebody_FSM)
       fsm.exits.append(casebody_FSM)
    print(len(cases))
    if len(cases)!=0:
        fsm.exits.remove(fsm.entry)

    FSM_map[alias_name] =fsm
    return fsm

def parse_and_separate_types(input_text):
    i = 0
    length = len(input_text)
    array_names = set()
    
    while i < length:
        if input_text.startswith("casetype", i):
            start = i
            i = input_text.find("{", i)
            end = find_matching_brace(input_text, i)
            if end != -1:
                while end < length and input_text[end] != ';':
                    end += 1
                print(input_text[start:end+1])
                print("\n")               
                print(parse_casetype(input_text[start:end+1], array_names))
                i = end + 1
    
        elif input_text.startswith("typedef struct", i):
            start = i
            i = input_text.find("{", i)
            end = find_matching_brace(input_text, i)
            if end != -1:
                while end < length and input_text[end] != ';':
                    end += 1
                print("matched struct:")
                print(input_text[start:end+1])
                print("\n")
                print(parse_struct(input_text[start:end+1], array_names))
                
                i = end + 1
        elif input_text.startswith("entrypoint typedef struct", i):
            start = i
            i = input_text.find("{", i)
            end = find_matching_brace(input_text, i)
            if end != -1:
                while end < length and input_text[end] != ';':
                    end += 1
                print("matched struct:")
                print(input_text[start:end+1])
                print("\n")
                print(parse_struct(input_text[start:end+1], array_names))
                i = end + 1
        else:
            i += 1  # Move to the next character if no module start is found
    
    return array_names

def cmp_FSM_seq(lst_FSM_seq, cur_FSM_seq):
    for i in range(len(cur_FSM_seq)):
        if i >= len(lst_FSM_seq):
            return cur_FSM_seq[i:]
        if lst_FSM_seq[i] == cur_FSM_seq[i]:
            continue
        else:
            return cur_FSM_seq[i:]
    
    return []

def get_mutation_variables(pathstr, cur_diff):
    mutation_variables = set()
    cur_fsm = set()
  
    for node_or_FSM in pathstr:           
        if node_or_FSM:
            FSMstart_pattern = re.compile(r'FSM_START\((\w+)\):\s*(.+)')
            FSM_match = re.search(FSMstart_pattern, node_or_FSM)
            if FSM_match:
                if FSM_match.group(1) in cur_diff:
                    cur_fsm.add(FSM_match.group(1))
            
            FSMend_pattern = re.compile(r'FSM_END\((\w+)\)')
            FSM_match = re.search(FSMend_pattern, node_or_FSM)
            if FSM_match and FSM_match.group(1) != 'None' and FSM_match.group(1) in cur_diff and FSM_match.group(1) in cur_fsm:
                cur_fsm.remove(FSM_match.group(1))

            if len(cur_fsm) > 0:
                node_pattern = re.compile(r'Node\((\w+),\s*type=(\w+),\s*condition=(None|.+?)\s*\)')
                node_match = re.search(node_pattern, node_or_FSM)
                if node_match:
                    mutation_variables.add(node_match.group(1))

    return mutation_variables

def generate_test_cases(doc_file, saved_paths, entrystructname, command, protocol, array_names):
    lst_FSM_seq = []
    lst_diff = [entrystructname]

    Incorrect_constraints = set()
    for pathstr in saved_paths:
        print(" -> ".join(filter(None, pathstr)))
        z3_code = []
        variables ={} # z3 variables
        len_fsm = {}
        path_constraint = {}
        dependent_path_constraint = {}
        cur_FSM_seq = []

        print("z3 encoding:")
        bit_number = 0
        for node_or_FSM in pathstr:
            if node_or_FSM:
                node_pattern = re.compile(r'Node\((\w+),\s*type=(\w+),\s*condition=([^,]+)\s*\)')
                node_match = re.search(node_pattern, node_or_FSM)
                if node_match:              
                    generate_z3_code_for_Node(node_match.group(1), node_match.group(2), node_match.group(3), z3_code, array_names, path_constraint, dependent_path_constraint)     
                    if node_match.group(2) == "UINT8BE":
                        variables[node_match.group(1)] = 1
                        for fsm_name in len_fsm:
                            len_fsm[fsm_name] += " + 1"
                    elif node_match.group(2) == "UINT16BE":
                        variables[node_match.group(1)] = 2
                        for fsm_name in len_fsm:
                            len_fsm[fsm_name] += " + 2"
                    elif node_match.group(2) == "UINT32BE":
                        variables[node_match.group(1)] = 4
                        for fsm_name in len_fsm:
                            len_fsm[fsm_name] += " + 4"
                    elif node_match.group(2) == "UINT64BE":
                        variables[node_match.group(1)] = 8
                        for fsm_name in len_fsm:
                            len_fsm[fsm_name] += " + 8"
                    elif node_match.group(2).startswith("bit"):
                        bit_size_str = node_match.group(2)[3:]
                        bit_size = int(bit_size_str)  # Convert it to an integer
                        bit_number += bit_size
                        variables[node_match.group(1)] = node_match.group(2)
                    elif node_match.group(2).isdigit():
                        variables[node_match.group(1)] = int(int(node_match.group(2))/8)
                        for fsm_name in len_fsm:
                            len_fsm[fsm_name] += f" + {variables[node_match.group(1)]}"
                    continue

                # FSM_START(Message): BodyLength
                FSMstart_pattern = re.compile(r'FSM_START\((\w+)\):\s*(.+)')
                FSM_match = re.search(FSMstart_pattern, node_or_FSM)
                if FSM_match:
                    cur_FSM_seq.append(FSM_match.group(1))
                    for fsm_name in len_fsm:
                        print(bit_number)
                        len_fsm[fsm_name] += " + " + str(bit_number / 8)
                        bit_number = 0
                    if FSM_match.group(2) != 'None':
                        print(FSM_match.group(2))
                        z3_code.append(f"Len_{FSM_match.group(1)} = Int('Len_{FSM_match.group(1)}')")
                        z3_code.append(f's.assert_and_track(Len_{FSM_match.group(1)} == {FSM_match.group(2)}, "Len_{FSM_match.group(1)} == {FSM_match.group(2)}")')
                        len_fsm[FSM_match.group(1)] = "0"
                        continue
                
                # FSM_END(Payload)
                FSMend_pattern = re.compile(r'FSM_END\((\w+)\)')
                FSM_match = re.search(FSMend_pattern, node_or_FSM)

                if FSM_match and FSM_match.group(1) != 'None':
                    for fsm_name in len_fsm:
                        len_fsm[fsm_name] += " + " + str(bit_number / 8)
                        bit_number = 0
                    if FSM_match.group(1) in len_fsm:
                        z3_code.append(f's.assert_and_track(Len_{FSM_match.group(1)} == {len_fsm[FSM_match.group(1)]}, "Len_{FSM_match.group(1)} == {len_fsm[FSM_match.group(1)]}")')
                        len_fsm.pop(FSM_match.group(1)) 
                    continue
                
                # [Type == 0] or [(IHL * 4 - 20) == 0]
                case_constraint_pattern = re.compile(r'\[(.+?)\]')
                case_constraint_match = re.search(case_constraint_pattern, node_or_FSM)
                if case_constraint_match:
                    z3_expr, vars = toz3(case_constraint_match.group(1))
                    
                    if "z3_expr" != "True" and "z3_expr" != "False" and len(vars) >= 1:
                        z3_expr_str = z3_expr.sexpr().replace('\n', ' ').strip()
                        z3_expr_name = z3_expr_str.replace('\n', ' ').strip()
                        z3_code.append(f's.assert_and_track({z3_expr}, "{z3_expr_name}")')
                    continue    
        
        print("path_constraint******")            
        print(path_constraint)

        print("dependent_path_constraint")
        print(dependent_path_constraint)

        print("cur_FSM_seq******") 
        print(cur_FSM_seq)
        
        print("len_fsm******")
        print(len_fsm)

        print("diff: cur_FSM_seq******") 
        cur_diff = cmp_FSM_seq(lst_FSM_seq, cur_FSM_seq)
        if not cur_diff:
           cur_diff = lst_diff
        print(cur_diff)

        lst_FSM_seq = cur_FSM_seq
        lst_diff = cur_diff
        print("*********mutation_variables*********")
        if cur_diff == [entrystructname]:
            mutation_variables = variables.keys()
        else:
            mutation_variables = get_mutation_variables(pathstr, cur_diff)
        print(mutation_variables)
        print("******************")

        flag = generate_z3(doc_file, z3_code, variables, path_constraint, dependent_path_constraint, cur_diff, mutation_variables, command, protocol, Incorrect_constraints, array_names)
        if flag == True:
            return flag
        

    return False

def extract_entrypoint_struct_names(format_code):
    # Find all struct names that match 'typedef struct _StructName'
    matches = re.findall(r'entrypoint typedef struct _([a-zA-Z_][a-zA-Z0-9_]*)\s*', format_code)
    
    # Return the list of struct names or None if no matches
    return matches if matches else None

def test_and_refine_format(doc_file, format, protocol, command):
    array_names = parse_and_separate_types(format)
    entrypoint_struct_names = extract_entrypoint_struct_names(format) 

    assert(len(entrypoint_struct_names) == 1)
    fsm = FSM_map[entrypoint_struct_names[0]]
    print("\nAll possible paths in the FSM:\n")
    # Perform DFS traversal and save all paths
    saved_paths = fsm.save_all_paths()
    return generate_test_cases(doc_file, saved_paths, entrypoint_struct_names[0], command, protocol, array_names)
