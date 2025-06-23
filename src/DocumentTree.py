import re
import json
from parser_agent import extract_format
from merge_format_agent import merge_format
# from refine_format_agent import refine_format
import os
from utils import askLLM

def contains_table(section_content):
    pattern = r'(?:\s*\+-+[\+-]*\n)+'  # Horizontal dividers (+---+)
    matches = re.findall(pattern, section_content)

    # no format table
    if len(matches) == 0:
        return False
    return True

def summary_section(section):
    prompt = f"""
    Task: Answer in this format: this secition decribes [one sentence].
    {section[1]}: 
    {section[2]}
    """
    return askLLM(prompt)

def summary_subsections(sectionname, summaries):
    prompt = f"""
    Task: Please give a summary in one sentence. Answer in this format: this secition decribes [one sentence].
    {sectionname}:
    {summaries}
    """
    return askLLM(prompt)

def get_most_recent_format():
    directory = "./everparse/everparse_files"
    # List all subdirectories in the given directory
    subfolders = [os.path.join(directory, d) for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]
    
    # Sort the subdirectories based on modification time in descending order
    subfolders.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Return the most recently modified subfolder
    if subfolders:
        subfolder_name = os.path.basename(subfolders[0])
        file_path = os.path.join(subfolders[0], subfolder_name + '.3d')
        return file_path
    else:
        return None

def hierachy(sections):
    prompt = f"""
    Task: Analyze the hierarchical structure of various sections and subsections in a technical document based on their content.

    Document Sections:
    {sections}

    Instructions:
    Identify the Parent-Child relationships among sections. A Parent-Child relationship exists when one section provides a detailed breakdown of another, establishing a clear hierarchical link.
    Example: If Section 1 outlines the general header format and Section 2 delves into a specific header field, then Section 1 is the Parent to Section 2.

    Output Format:
    - List each relationship as: "Section [Number] is the Parent of Section [Number] because [Justification]."
    - Each relationship must be justified with clear reasoning based on the content and role of the sections in the document.

    Please provide your analysis following these instructions and formatting rules.

    """
    return askLLM(prompt)

def extract_format_from_section(section):
    number, title, content = section
    print(f"{number} {title}:\n")
    if contains_table(content) or "format" in content:
        extract_format(title+":\n"+content)
        return get_most_recent_format()
    else:
        return None

def isdescendant(node1, node2):
    if node1.number == node2.number:
        return True
    
    for child in node1.children:
        if isdescendant(child, node2):
            return True
    
    return False

def extract_struct_names(format_code):
    # Find all struct names that match 'typedef struct _StructName'
    matches = re.findall(r'typedef struct _([A-Za-z_]+)', format_code)
    
    # Return the list of struct names or None if no matches
    return matches if matches else None

class SectionNode:
    def __init__(self, number, title, content, summary, format):
        self.number = number
        self.title = title
        self.content = content
        self.summary = summary
        self.format = format
        self.children = []      

    def add_child(self, child):
        if self.find_child(child.number):
            return
        self.children.append(child)

    def remove_child(self, childnum):
        for child in self.children:
            if child.number == childnum:
                self.children.remove(child)
            
    def find_child(self, childnum):
        if self.number == childnum:
            return self
        for child in self.children:
            re = child.find_child(childnum)
            if re:
                return re
        return None

    def display(self, level=0):
        indent = " " * (level * 2)
        print(f"{indent}{self.number}: {self.title}")
        print(f"{indent}summary: {self.summary}")
        print(f"{indent}{self.format}")
        for child in self.children:
            child.display(level + 1)
    
    def to_dict(self):
        # Convert the node and its children to a dictionary
        return {
            'number': self.number,
            'title': self.title,
            'content': self.content,
            'summary': self.summary,
            'format': self.format,
            'children': [child.to_dict() for child in self.children]
        }

    @staticmethod
    def from_dict(data, number_to_node):
        node = SectionNode(data['number'], data['title'], data['content'], data['summary'], data['format'])
        node.children = [SectionNode.from_dict(child, number_to_node) for child in data['children']]
        number_to_node[data['number']] = node
        return node

    def generate_format(self):
        # Recursively check each node's format and print if it's None
        if self.format is None:
            print(f"Section {self.number} titled '{self.title}' has no format specified.")
            extract_format(self.title+":\n"+self.content)
            self.format = get_most_recent_format()
        for child in self.children:
            child.generate_format()

    def find_current_parent(self, node):
        """Find the parent of the given node."""
        for cl in self.children:
            if cl.number == node.number:
                return self
            parent = cl.find_current_parent(node)
            if parent:
                return parent  # Return the parent found in the recursion
        return None  # Return None if no parent is found
            
    def merge(self): #does not merge format, only doc summaries
        if len(self.children) == 0:
            return
        content = ""
        summaries = ""
        child_sections = ""
        child_titles = []
        # print(f"here is the child for section: {self.number}")
        for child in self.children:
            # print(child.number)
            child.merge()
            content += child.number + child.title +":\n" 
            summaries += child.summary+"\n"
            child_sections += child.number + child.title + "--" + child.summary + "\n"
            child_titles.append(child.title)
        self.summary = summary_subsections(self.title, summaries)     

        if len(self.children) > 1:
            print("hierachy result")
            relationships = hierachy(child_sections)
            for line in relationships.strip().split('\n'):
                if "is the Parent of Section" in line:
                    if not (re.search(r'Section (\d+(?:\.\d+)*)', line) and re.search(r'of Section (\d+(?:\.\d+)*)', line)):
                        continue
                    parent = re.search(r'Section (\d+(?:\.\d+)*)', line).group(1)
                    child = re.search(r'of Section (\d+(?:\.\d+)*)', line).group(1)
                    if self.number == parent:
                        continue
                    child_node = self.find_child(child)
                    parent_node = self.find_child(parent)
                    if child_node is None or parent_node is None:
                        continue
                    if isdescendant(parent_node, child_node):
                        continue
                    current_parent = self.find_current_parent(child_node)
                    if current_parent:
                        current_parent.remove_child(child) # Remove from current parent
                    parent_node.add_child(child_node)  # Add to new parent as per relationship

    def merge_child_formats(self, struct_subsection_map):
        
        if len(self.children) == 0:
            if ".3d" in self.format:
                with open(self.format, 'r') as file:
                    format_content = file.read()
                    for struct_name in extract_struct_names(format_content):
                        struct_subsection_map[struct_name] = self.number
            return
        
        if self.format and ".3d" in self.format:
            with open(self.format, 'r') as file:
                self_format_content = file.read()
            combined_formats = "Root format: "+self.summary + self_format_content +'\n' +"child format:"
        else:
            combined_formats = self.summary

        has_child_format = False
        for child in self.children:
            child.merge_child_formats(struct_subsection_map)
            if ".3d" in child.format:
                has_child_format = True
                with open(child.format, 'r') as file:
                    child_format_content = file.read()
                combined_formats = combined_formats + child.summary + child_format_content + '\n'

        if has_child_format:  
            merge_format(combined_formats)
            self.format = get_most_recent_format()
            with open(self.format, 'r') as file:
                format_content = file.read()  # Reads the entire file
                for struct_name in extract_struct_names(format_content):
                    if struct_name not in struct_subsection_map:
                        struct_subsection_map[struct_name] = self.number

class DocumentTree:
    def __init__(self, proto):
        self.root = None
        self.protocol = proto
        self.sections = {}

    def add_section(self, number, title, content, summary, format):
        if '.' not in number:
            if not self.root:
                # This is a root section
                self.root = SectionNode(number, title, content, summary, format)
                self.sections[number] = self.root
            else:
                new_section = SectionNode(number, title, content, summary, format)
                self.root.add_child(new_section)
                self.sections[number] = new_section

        else:
            parent_number = '.'.join(number.split('.')[:-1])
            parent_section = self.sections.get(parent_number)
            if parent_section:
                new_section = SectionNode(number, title, content, summary, format)
                parent_section.add_child(new_section)
                self.sections[number] = new_section
            else:
                # print(f"root: {parent_number}")
                self.root = SectionNode(parent_number, self.protocol, "Complete Format", self.protocol, None)
                self.sections[parent_number] = self.root
                new_section = SectionNode(number, title, content, summary, format)
                self.root.add_child(new_section)
                self.sections[number] = new_section
    
    def display(self):
        if self.root:
            self.root.display()

    def to_json(self):
        # Serialize the entire document tree to JSON
        if self.root:
            return json.dumps(self.root.to_dict(), indent=4)
    
    def save_to_file(self, filename, struct_subsection_map = None):
        # Save the JSON output to a file
        with open(filename, 'w') as file:
            json_data = self.to_json()
            file.write(json_data)
            print(f"Data saved to {filename}")

        if struct_subsection_map:
            # Merge: Save the dictionary to a file
            with open('struct_subsection_map.json', 'w') as file:
                json.dump(struct_subsection_map, file, indent=4)
            
    def load_from_file(self, filename):
        number_to_node = {}
        with open(filename, 'r') as file:
            data = json.load(file)
            self.root = SectionNode.from_dict(data, number_to_node)
        return number_to_node

    def merge(self):#does not merge format, only doc summaries
        self.root.merge()

    def generate_all_formats(self):
        if self.root:
            self.root.generate_format()
    
    def merge_formats(self, struct_subsection_map):
        self.root.merge_child_formats(struct_subsection_map)

    def refine(self, sectioncontent, parserlog):  
        with open(self.root.format, 'r') as file:
            old_format = file.read()
        refine_format(old_format, sectioncontent, parserlog)
        self.root.format = get_most_recent_format()


