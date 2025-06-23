import re
from DocumentTree import *
import sys
import os
from parseformat import test_and_refine_format

sys.path.append(os.path.abspath('../../'))

def clean_text(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        file_content = file.read()

        header_pattern = re.compile(r'RFC (\d+)\s+(.*?)\s+([A-Za-z]+ \d{4})')
        footer_pattern = re.compile(r'^.*\s+\[Page \d+\]$', re.MULTILINE)

        text = header_pattern.sub('', file_content)
        text = footer_pattern.sub('', text)

        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()
    
def handle_doc(readfile, writefile):
    # step 1: clean document
    document_text = clean_text(readfile)

    with open(writefile, 'w', encoding='utf-8') as cleaned_file:
        cleaned_file.write(document_text)

    print(f"Cleaned content written to {writefile}")

    # step 2: segmentation to sections
    # Adjusted regex pattern to capture section numbers more reliably, including standalone section titles
    section_header_pattern = re.compile(r'^(\d+(?:\.\d+)*)(\.?)\s+(.*)$', re.MULTILINE)
    
    headers = list(section_header_pattern.finditer(document_text))
    sections = []

    for i, match in enumerate(headers):
        start_index = match.end()
        # Adjust to find the start of the next section considering document structure
        end_index = headers[i + 1].start() if (i + 1) < len(headers) else len(document_text)
        
        # Extract section number and title, and trim content accurately
        section_number = match.group(1)
        section_title = match.group(3).strip()
        section_content = document_text[start_index:end_index].strip()
        sections.append((section_number, section_title, section_content))
    return sections

def build_doc_tree(protocol, sections, doc_file):
    doc_tree = DocumentTree(protocol)
    # Generate new json tree
    if not os.path.exists(doc_file):       
        for section in sections:       
            if section[2]!="":
                summary = summary_section(section)
            else:
                summary = None
            if not contains_table(section[2]):
                init_format = section[1]
            else:
                init_format = None
            doc_tree.add_section(section[0], section[1], section[2], summary, init_format) 
        doc_tree.merge()
        doc_tree.display()
        doc_tree.save_to_file(doc_file) 
    
    else:
        print("Doc tree exists!!!")

def extract_format_from_doc(protocol, doc_file):
    doc_tree = DocumentTree(protocol)
    if os.path.exists(doc_file):
        doc_tree.load_from_file(doc_file)
        if doc_tree.root:
            print("Document tree loaded successfully.")
            doc_tree.generate_all_formats()
            doc_tree.display()
            doc_tree.save_to_file(doc_file) 
            return doc_tree
            
        else:
            print("Document tree loading failed!")
            return None
        
    else:
        print("error! Doc tree not exist!!!")
        return None

def merge_format_in_doc_tree(protocol, doc_file, struct_subsection_map):
    doc_tree = DocumentTree(protocol)
    if os.path.exists(doc_file):
        doc_tree.load_from_file(doc_file)
        if doc_tree.root:
            print("Document tree loaded successfully.")
            if "everparse_files" in doc_tree.root.format:
                print("Merged formats detected! No need to merge again.")
                return doc_tree
            doc_tree.merge_formats(struct_subsection_map)
            doc_tree.display()
            doc_tree.save_to_file(doc_file, struct_subsection_map) 
            return doc_tree
            
        else:
            print("Document tree loading failed!")
            return None
        
    else:
        print("error! Doc tree not exist!!!")
        return None

def test(protocol):
    read_file_name = f'RFC/{protocol}.txt'
    write_file_name = f'RFC/cleaned_{protocol}.txt'
    match = re.search(r'/([^/]+)\.txt$', read_file_name)
    doc_file = f'RFC/{match.group(1)}.json'
    # step 0: clean document
    sections = handle_doc(read_file_name, write_file_name)
    # step 1: build doc tree without generate format
    build_doc_tree(protocol,sections, doc_file)
    # step 2: generate format for each treenode, not merge
    extract_format_from_doc(protocol, doc_file)
    flag = True
    while(flag):
        struct_subsection_map = {}
        # step 3: merge format until root
        doc_tree = merge_format_in_doc_tree(protocol, doc_file, struct_subsection_map)
        # step 4: test implementation and refine the format
        doc_tree = DocumentTree(protocol)
        if os.path.exists(doc_file):
            doc_tree.load_from_file(doc_file)
        with open(doc_tree.root.format, 'r') as file:
            format_content = file.read()
        command = ".." # This should be the exe for the parser
        flag  = test_and_refine_format(doc_file, format_content, protocol, command)
        return

test("BFD")



