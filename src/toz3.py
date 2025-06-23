import re
from typing import List, Set
from z3 import *
import ast
import json
import subprocess
from DocumentTree import DocumentTree
from utils import askLLM

def identifymismatch(condition, doc):
    prompt = f"""
    Task: {condition} is **allowed** by one unverified parser, which is **not allowed** in myformat. Please identify according to the document description, myformat or parser which is incorrect. Answer 'myformat' or 'parser' directly, and give a reason in one sentence.
    
    Document: {doc}

    Output Format: "[myformat/parser] is incorrect because [Justification]."
    """
    answer = askLLM(prompt)
    match = re.search(r'\b(myformat|parser)\b is incorrect because', answer)
    if match:
        return match.group(1)  # Return the matched result (either 'myformat' or 'parser')
    else:
        return None

# Function to convert a Python AST node into Z3
def ast_to_z3(node, variables):
    if isinstance(node, ast.BoolOp):
        # Handle logical AND and OR
        if isinstance(node.op, ast.And):
            return And(*[ast_to_z3(value, variables) for value in node.values])
        elif isinstance(node.op, ast.Or):
            return Or(*[ast_to_z3(value, variables) for value in node.values])
    elif isinstance(node, ast.Compare):
        # Handle comparison expressions
        left = ast_to_z3(node.left, variables)
        comparators = [ast_to_z3(cmp, variables) for cmp in node.comparators]
        if isinstance(node.ops[0], ast.Eq):
            return left == comparators[0]
        elif isinstance(node.ops[0], ast.NotEq):
            return left != comparators[0]
        elif isinstance(node.ops[0], ast.Lt):
            return left < comparators[0]
        elif isinstance(node.ops[0], ast.LtE):
            return left <= comparators[0]
        elif isinstance(node.ops[0], ast.Gt):
            return left > comparators[0]
        elif isinstance(node.ops[0], ast.GtE):
            return left >= comparators[0]
    elif isinstance(node, ast.BinOp):
        # Handle arithmetic expressions
        left = ast_to_z3(node.left, variables)
        right = ast_to_z3(node.right, variables)
        if isinstance(node.op, ast.Add):
            return left + right
        elif isinstance(node.op, ast.Sub):
            return left - right
        elif isinstance(node.op, ast.Mult):
            return left * right
        elif isinstance(node.op, ast.Div):
            return left / right
        elif isinstance(node.op, ast.Mod):
            return left % right
    elif isinstance(node, ast.UnaryOp):
        # Handle unary operations like NOT
        if isinstance(node.op, ast.Not):
            return Not(ast_to_z3(node.operand, variables))
    elif isinstance(node, ast.Name):
        # Handle variables (automatically add them to the variables dictionary)
        if node.id not in variables:
            variables[node.id] = Int(node.id)  # Automatically create Int variables
        return variables[node.id]
    elif isinstance(node, ast.Constant):
        # Handle constants (like numbers)
        return node.value
    else:
        raise ValueError(f"Unsupported AST node: {ast.dump(node)}")

# Function to replace C-like logical operators (&&, ||, !) with Python equivalents
def replace_logical_operators(expr_str):
    expr_str = expr_str.replace('&&', 'and')
    expr_str = expr_str.replace('||', 'or')
    return expr_str

# Function to parse the expression and convert it to a Z3 expression
def toz3(expr_str):
    variables = {}  # Automatically store variables here
    # Replace C-like logical operators with Python equivalents
    expr_str = replace_logical_operators(expr_str)
    # Parse the expression into an AST
    expr_ast = ast.parse(expr_str, mode='eval')
    # Recursively convert the AST into a Z3 expression
    z3_expr = ast_to_z3(expr_ast.body, variables)
    return z3_expr, variables  # Return both the Z3 expression and the variables

def generate_z3_code_for_Node(field_name, field_type, condition, z3_code, array_names, path_constraint, dependent_path_constraint):
    # Define the variable in Z3
    z3_code.append(f"{field_name} = Int('{field_name}')")
    
   # Add the appropriate constraints based on the type
    if field_type == 'UINT8BE':       
        z3_code.append(f's.assert_and_track(And({field_name} >= 0, {field_name} <= 255), "And({field_name} >= 0, {field_name} <= 255)")')
    elif field_type == 'UINT16BE':
        z3_code.append(f's.assert_and_track(And({field_name} >= 0, {field_name} <= 65535), "And({field_name} >= 0, {field_name} <= 65535)")')
    elif field_type == 'UINT32BE':
        z3_code.append(f's.assert_and_track(And({field_name} >= 0, {field_name} <= 4294967295), "And({field_name} >= 0, {field_name} <= 4294967295)")')
    elif field_type == 'UINT64BE':
        z3_code.append(f's.assert_and_track(And({field_name} >= 0, {field_name} <= 18446744073709551615), "And({field_name} >= 0, {field_name} <= 18446744073709551615)")')
    elif field_type.startswith('bit'):
        bit_size_str = field_type[3:]
        bit_size = int(bit_size_str)
        bit_max = 2**bit_size -1
        z3_code.append(f's.assert_and_track(And({field_name} >= 0, {field_name} <= {bit_max}), "And({field_name} >= 0, {field_name} <= {bit_max})")')
    elif field_type.isdigit():
        max = 2**int(field_type) - 1
        print(max)
        z3_code.append(f's.assert_and_track(And({field_name} >= 0, {field_name} <= {max}), "And({field_name} >= 0, {field_name} <= {max})")')
    if field_name in array_names:
        return
    # Add condition if present
    if condition!='None':
        z3_expr, vars = toz3(condition)
        z3_expr_str = z3_expr.sexpr().replace('\n', ' ').strip()
        z3_expr_name = z3_expr_str.replace('\n', ' ').strip()
        if not z3_code or z3_code[-1] != f's.assert_and_track({z3_expr}, "{z3_expr_name}")':
            z3_code.append(f's.assert_and_track({z3_expr}, "{z3_expr_name}")')
        if len(vars) == 1:
            var = next(iter(vars))
            if var == field_name:
                if var in path_constraint:
                    path_constraint[var].append(f"{z3_expr}")
                else:
                    path_constraint[var]=[f"{z3_expr}"]
            else:
                dependent_path_constraint[z3_expr] = [var, field_name]
        else:
            dependent_path_constraint[z3_expr] = list(vars.keys())

def generate_z3_correct_format(doc_tree, z3_path_code, variables, cur_diff, struct_subsection_map, number_to_node_mp, cmd, output_file):
    # Extract the struct definition
    z3_code = []
        # Start generating Z3 code
    z3_code.append("from z3 import *")
    z3_code.append("s = Solver()")
    z3_code.append("s.set(unsat_core=True)")
    z3_code.extend(z3_path_code)
    # Additional logic or constraints can be added here...
    z3_code.append("pkt = b''")
    z3_code.append("bit_buffer = 0")
    z3_code.append("bit_count = 0")
    # Example: Checking satisfiability
    z3_code.append("result = s.check()")
    z3_code.append("if result == sat:")
    z3_code.append("    solver_status = 'SAT'")
    z3_code.append("    model = s.model()")
    for variable, byte_num in variables.items():
        if isinstance(byte_num, int):
            z3_code.append(f"    {variable}_val = model.eval({variable}).as_long()")
            z3_code.append(f"    result_map['{variable}'] = {variable}_val")  # Store the value in the map
            z3_code.append(f"    print('{variable} =', {variable}_val)")
            z3_code.append(f"    {variable}_bytes = {variable}_val.to_bytes({byte_num}, byteorder='big')")
            z3_code.append(f"    pkt += {variable}_bytes")

        elif isinstance(byte_num, str):
            bit_size_str = byte_num[3:]  # Extract bit size from variable name (e.g., "bit3")
            bit_size = int(bit_size_str)
            z3_code.append(f"    {variable}_val = model.eval({variable}).as_long()")
            z3_code.append(f"    result_map['{variable}'] = {variable}_val")  # Store the value in the map
            z3_code.append(f"    print('{variable} =', {variable}_val)")

             # Append bit values to the buffer
            z3_code.append(f"    bit_buffer = (bit_buffer << {bit_size}) | {variable}_val")  # Shift and append the bit field
            z3_code.append(f"    bit_count += {bit_size}")  # Keep track of how many bits we have in the buffer
            # If we have at least 8 bits, flush to a byte
            z3_code.append(f"    while bit_count >= 8:")
            z3_code.append(f"        byte_val = (bit_buffer >> (bit_count - 8)) & 0xFF")  # Extract the top 8 bits
            z3_code.append(f"        pkt += byte_val.to_bytes(1, byteorder='big')")  # Add the byte to the packet
            z3_code.append(f"        bit_count -= 8")  # Reduce bit count by 8
            z3_code.append(f"        bit_buffer &= (1 << bit_count) - 1")  # Remove the top 8 bits from the buffer

        else:
            print("undefined byte_type")
    
    z3_code.append(f"    print('Packet in hex:', pkt.hex())")

    z3_code.append("elif result == unsat:") 
    z3_code.append("    print('Constraints are unsatisfiable')")
    z3_code.append("    solver_status = 'UNSAT'")
    z3_code.append("    unsat_core = s.unsat_core()")
    z3_code.append("    print('Unsat core:', unsat_core) ")
    z3_code.append("    pkt = None")  # No packet if unsatisfiable

    z3_code.append("else:") 
    z3_code.append("    print('Solver result is unknown')")
    z3_code.append("    solver_status = 'Unknown'")
    z3_code.append("    pkt = None")  # No packet if unsatisfiable

    # Add code to print the final packet
    z3_code.append("if pkt is not None:")
    z3_code.append("    print('Concatenated Packet:', pkt)")
    z3_code.append("    print('Packet in hex:', pkt)")

    # Save hex to file
    z3_code.append(f"    with open('{output_file}', 'wb') as f:")
    z3_code.append("        f.write(pkt)")

    # Join the generated code into a single string
    z3_code_str = '\n'.join(z3_code)
    
    # Print the generated Z3 code (for debugging or review)
    print("Generated Z3 Code:")
    print(z3_code_str)

    exec_context = {
        "solver_status": None,
        "result_map": {},  # External container for the result map
        "unsat_core": [],
    }

    # Execute the generated code
    print("\nz3 result for correct format:")
    exec(z3_code_str, exec_context)

    # Access the solver_status, result_map from exec_context
    solver_status = exec_context["solver_status"]
    result_map = exec_context["result_map"]
    print("solver_status:", solver_status)
    print("Result Map:", result_map)

    if solver_status == "UNSAT" or solver_status == "Unknown":
        print("For correct format, skips when happen")
        return "skip",  "skip", "skip"

    if "go run" in cmd:
        command = "go run main.go input.bin"
    elif "impacket/bin/python3" in cmd:
        command = cmd
    else:
        command = f"{cmd} input.bin"

    try:
        # Execute the command
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("The correct format pass.")
    except subprocess.CalledProcessError as e:
        print(f"Execution failed: {e}")
        print("The correct format fail")
        print(f"please refine format in {cur_diff}")

        # subsections = set()
    
        # for struct_name in cur_diff:
        #     subsections.add(struct_subsection_map[struct_name])
        
        # text = ""
        # for subsection in subsections:
        #     text += number_to_node_mp[subsection].number + number_to_node_mp[subsection].title + "\n" + number_to_node_mp[subsection].content + "\n"
        # file_path = "input.bin"

        # # Open the file in binary mode
        # with open(file_path, 'rb') as file:
        #     data = file.read()

        # doc_tree.refine(text, e.stdout+e.stderr)
        
        return None, None, None
    
    return z3_code_str, z3_code, result_map

def test_truncate_inputs(modified_packet, cmd):
    print("truncated packet:")
    print(modified_packet)
    with open("input.bin", "wb") as f:
        f.write(modified_packet)

    if "go run" in cmd:
        command = "go run main.go input.bin"
    elif "impacket/bin/python3" in cmd:
        command = cmd
    else:
        command = f"{cmd} input.bin"

    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(command)
        print(result)
        print("The incorrect format success")
    except subprocess.CalledProcessError as e:  
        if "impacket/bin/python3" in cmd:
            if "ImpactPacketException" in e.stderr.decode():
                print("The incorrect format fail")
            else:
                print("unexpected Exception! Found error in parser!")
                print(e.stderr.decode())
                print(e)
        else:
            print(f"Execution failed: {e}")
            print("The incorrect format fail")

    return

def generate_z3_incorrect_format(z3_incorrect_code, result_map, fields: Set[str], field_constraints: List[str], flag):
    # flag = False: already have the assignment, no need to add again in z3_code, just need to do delete
    print("field_constraints")
    print(field_constraints)
    constraint_pattern = r"(\s*)s\.assert_and_track\((.+),\s*\"(.+)\"\s*\)$"
    for i in range(len(z3_incorrect_code)):
        z3_line = z3_incorrect_code[i]
        # Check if the current line contains any field_constraint
        for field_constraint in field_constraints:
            if field_constraint in z3_line:     
                match = re.search(constraint_pattern, z3_line)
                if match:
                    indentation = match.group(1)
                    expression = match.group(2)
                    if expression == field_constraint:
                        z3_incorrect_code[i] = f'{indentation}s.assert_and_track(Not({expression}), "Not({expression})")'
                else:
                    print("field_constraint:\n")
                    print(field_constraint)
                    print("\nz3_line:\n")
                    print(z3_line)
                    print(f"ERROR: No match found.")
                    print(field_constraint)
                    print(z3_line)
                    return False
                    # TBA
                break

        if flag:
            if 'pkt = b' in z3_line:            
                for var in result_map:
                    if var not in fields:
                        if f's.assert_and_track({var} == {result_map[var]}, "{var} == {result_map[var]}")' not in z3_incorrect_code:
                            z3_incorrect_code.insert(i, f's.assert_and_track({var} == {result_map[var]}, "{var} == {result_map[var]}")')
                break

       
    z3_code_negate_str = '\n'.join(z3_incorrect_code)

    print(f"\nz3 result for incorrect format with incorrect field: {fields}")
    # print("Generated Z3 Code******:")
    # print(z3_code_negate_str)
    print("exe Z3 Code:")
    exec_context_neg = {
        "solver_status": None,
        "result_map": {},  # External container for the result map
        "unsat_core": [],
    }
    exec(z3_code_negate_str, exec_context_neg) 
      
    # Access the solver_status from exec_context
    solver_status_neg = exec_context_neg["solver_status"]

    if solver_status_neg == "SAT":
        return True
    elif solver_status_neg == "UNSAT":
        unsat_core_neg = exec_context_neg["unsat_core"]
        return False
        # return handle_unsat_core(unsat_core_neg, z3_incorrect_code, field_constraint, result_map)
        
    else:
        print("negative format: Z3.check ==> unknown!")
        return False
    
def handle_unsat_core(unsat_core_neg, z3_incorrect_code, field_constraint, result_map):
    print("handle unsat core")
    z3expr_to_negate = []
    variableset = set()
    pattern = r'^\s*(\w+)\s*==\s*(\d+)\s*$'
    print("****")
    print(unsat_core_neg)
    print("****")
    print(field_constraint)
    print("****")
    for unsat_expr in unsat_core_neg:
        if f"Not({field_constraint}" in str(unsat_expr):
            continue
        match = re.search(pattern, str(unsat_expr))
        if match:
            variable = match.group(1)
            number = match.group(2)
            if int(result_map[variable]) == int(number):
                z3expr_to_negate = [str(unsat_expr)]
                break
        z3expr_to_negate.append(str(unsat_expr))

    print(z3expr_to_negate)
        # negate only one expr in min unsat_core should already make it sat
    if len(z3expr_to_negate)>1:
        z3expr_to_negate = z3expr_to_negate[:-1]
    # Iterate over the result map to find variables involved in the unsat core
    for var in result_map:
        # Check if the variable appears in any of the unsatisfiable expressions
        if any(var in str(unsat_expr) for unsat_expr in unsat_core_neg):
            variableset.add(var)  
    
    print("******variableset")
    print(variableset)
    print("z3expr_to_negate:")
    print(z3expr_to_negate)

    byte_size_pattern = r'And\((\w+)\s*>=\s*0,\s*\1\s*<=\s*(\d+)\)'
    byte_size_match = re.search(byte_size_pattern, z3expr_to_negate[0])
    if byte_size_match:
        variable = byte_size_match.group(1)       
        # Iterate over the z3_incorrect_code to find the variable definition for the z3expr_to_negate
        for i, line in enumerate(z3_incorrect_code):
            if variable not in line:
                continue
            expected_assert_line = f's.assert_and_track({z3expr_to_negate[0]}, "{z3expr_to_negate[0]}")'
            
            if len(line) == len(expected_assert_line):
                flag = True
                for x, (char1, char2) in enumerate(zip(expected_assert_line, line)):
                    if char1 != char2:
                        flag = False
                        print(f"do not equal in: {x}, {char1}, {char2}")
                        break

                print(flag)
                if flag:          
                    expected_line = f"{variable} = Int('{variable}')"
                    print(expected_line)
                    if z3_incorrect_code[i-1] == expected_line:
                        return False

    return generate_z3_incorrect_format(z3_incorrect_code, result_map, variableset, z3expr_to_negate, False)

def generate_z3(doc_file, z3_path_code, variables:dict, path_constraint, dependent_path_constraint, cur_diff: List[str], mutation_variables, cmd, proto, Incorrect_constraints, array_names, output_file = "input.bin"):
    doc_tree = DocumentTree(proto)
    if os.path.exists(doc_file):
        number_to_node_mp = doc_tree.load_from_file(doc_file)
        if doc_tree.root:
            print("Document tree loaded successfully.")

    struct_subsection_map = {}
    with open('struct_subsection_map.json', 'r') as file:
        struct_subsection_map = json.load(file)
        for st in struct_subsection_map:
            print(f"struct {st} => section {struct_subsection_map[st]} => {number_to_node_mp[struct_subsection_map[st]].title}")
    
    # step 1: generate inputs/refine for correct format
    z3_code_str, z3_code, result_map = generate_z3_correct_format(doc_tree, z3_path_code, variables, cur_diff, struct_subsection_map, number_to_node_mp, cmd, output_file)
    doc_tree.save_to_file(doc_file) 
    if z3_code_str is None or z3_code is None:
        return True
    if z3_code_str =="skip":
        return False
    
    # step 2.a
    print("\n generate truncate format:")
    with open("input.bin", "rb") as f:
        correct_packet = f.read()  # Read the entire file content as raw binary data
        print(variables)
        i = 1
        sum = 0
        last_field, last_field_bytes = list(variables.items())[-i]
        sum = sum + last_field_bytes
        while last_field in array_names:
            i = i + 1
            last_field, last_field_bytes = list(variables.items())[-i]
            sum = sum + last_field_bytes

        # Remove the last byte
        print(f"lastfields:{last_field}")
        print(f"lastbytes: {last_field_bytes}")

        modified_packet = correct_packet[:-sum]

        modified_packet1 = correct_packet[:-(sum+1)]
        test_truncate_inputs(modified_packet,cmd)
        print()
        test_truncate_inputs(modified_packet1,cmd)
    
   

    print("\nz3 result for incorrect format:")
    # step 2.a: first handle independent constraints
    for field in mutation_variables:
        if field not in path_constraint:
            continue
        print(f"path_constraint[field]:{path_constraint[field]}")
        for field_constraint in path_constraint[field]:
            print(f"incorrect_cons: {Incorrect_constraints}")

            if field_constraint in Incorrect_constraints:
                continue
            print("z3expr_to_negate:")
            print(field_constraint)
            successornot = generate_z3_incorrect_format(z3_code.copy(), result_map, {field}, [field_constraint], True)       
            if not successornot:
                continue
            if "go run" in cmd:
                command = "go run main.go input.bin"
            elif "impacket/bin/python3" in cmd:
                command = cmd
            else:
                command = f"{cmd} input.bin"

            try:
                # Execute the command
                result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                doc = "\n".join(number_to_node_mp[struct_subsection_map[st]].title + number_to_node_mp[struct_subsection_map[st]].content for structname in cur_diff)
                myformat_or_parser = identifymismatch(f'Not({field_constraint})', doc)
                if myformat_or_parser == "myformat":
                    print(f"please refine format on {field_constraint}, in {cur_diff}")
                    # subsections = set()
                    # for struct_name in cur_diff:
                    #     subsections.add(struct_subsection_map[struct_name])
                    # assert(len(subsections) == 1)
                    # for subsection in subsections:
                    #     number_to_node_mp[subsection].refine(struct_subsection_map)
                    # return False

                elif myformat_or_parser == "parser" or myformat_or_parser == "Parser":
                    print("Found error in parser!")
                    Incorrect_constraints.add(field_constraint)
                else:
                    print("output error!")

            except subprocess.CalledProcessError as e:
                print(f"Execution failed: {e}")
                print("The incorrect format fail")
      
    # step 2.b: then handle dependent constraints

    for condition in dependent_path_constraint:
        print(f"incorrect_cons: {Incorrect_constraints}")
        if condition in Incorrect_constraints:
            continue
        successornot = generate_z3_incorrect_format(z3_code.copy(), result_map, set(dependent_path_constraint[condition]), [str(condition)], True)
        if not successornot:
            continue
        if "go run" in cmd:
            command = "go run main.go input.bin"
        else:
           
            command = f"{cmd} input.bin"

        try:
            # Execute the command
            result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            doc = "\n".join(number_to_node_mp[struct_subsection_map[st]].title + number_to_node_mp[struct_subsection_map[st]].content for structname in cur_diff)
            myformat_or_parser = identifymismatch(f'Not({condition})', doc)
            if myformat_or_parser == "myformat":
                print(f"please refine format on {condition}, in {cur_diff}")
                subsections = set()
                for struct_name in cur_diff:
                    subsections.add(struct_subsection_map[struct_name])
                assert(len(subsections) == 1)
                # for subsection in subsections:
                #     number_to_node_mp[subsection].refine(struct_subsection_map)
                # return False

            elif myformat_or_parser == "parser" or myformat_or_parser == "Parser":
                print("Found error in parser!")
                Incorrect_constraints.add(condition)
            else:
                print("output error!")

        except subprocess.CalledProcessError as e:
            print(f"Execution failed: {e}")
            print("The incorrect format fail")
    
    # step 3 handle truncate formats

    return False
