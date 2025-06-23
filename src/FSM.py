from __future__ import annotations
from typing import List, Dict, Optional, Union
from collections import deque
from toz3 import *

class Node: #children of Node can be Node or FSM
    def __init__(self, name: str, type: Optional[str], condition: Optional[str]):
        self.name = name
        self.type = type
        self.condition = condition
        self.transitions: Dict[Union['Node', 'FSM'], Optional[str]] = {}  # Transitions to children with conditions
    
    def add_transition(self, condition, next):
        self.transitions[next] = condition


    def __repr__(self):
        return f"Node({self.name}, type={self.type}, condition={self.condition})" 

class FSM:
    def __init__(self, name, size=None):
        self.name = name
        self.entry = Node("start", None, None)
        self.exits: List[Union['Node', 'FSM']] = [self.entry]
        self.next: List[Union['Node', 'FSM']] = []# not include in this FSM, but the following FSM
        self.size_expr = size

    def addlists(self, node_or_FSM_list):
        if node_or_FSM_list is None:
            return
        for node_or_FSM in node_or_FSM_list:
            for exit in self.exits:
                if isinstance(exit, Node):
                    exit.add_transition(None, node_or_FSM)
                else:
                    exit.addNext(node_or_FSM)

        self.exits = node_or_FSM_list
                  
    def addNext(self, next: Union['Node', 'FSM']):
        self.next.append(next)

    def addNexts(self, nexts: List[Union['Node', 'FSM']]):
        self.next.extend(nexts)

    def __repr__(self):
        # Perform BFS to traverse the FSM starting from the entry node
        bfs_output = []
        queue = deque([self.entry])  # Start BFS from the entry node

        visited = set()  # To track visited nodes and avoid infinite loops

        while queue:
            current = queue.popleft()
            if current not in visited:
                visited.add(current)
                bfs_output.append(repr(current))

                # Add all unvisited children (next nodes) to the queue
                if isinstance(current, Node):
                    for nt in current.transitions.keys():
                        if nt not in visited:
                            queue.append(nt)
                else:
                    for nt in current.next:
                        if nt not in visited:
                            queue.append(nt)

        return f"FSM({self.name}): " + " -> ".join(bfs_output)

    def dfs(self, current: Union[Node, FSM], pathstr: List[str], saved_pathstr: List[List[str]], flag):
        if current in self.exits:
            flag = True

        if isinstance(current, Node) and current.name != "start" and current.name != "empty":
            pathstr.append(current.__repr__())
            
        elif isinstance(current, Node) and current.name == "empty":
            if current.condition:
                pathstr.append(f"[{current.condition}]")

        elif isinstance(current, FSM) and "emptyFSM" not in current.name:
            pathstr.append(f"FSM_START({current.name}): {current.size_expr}")

        elif isinstance(current, FSM) and "emptyFSM" in current.name:
            if current.size_expr:
                pathstr.append(f"[{current.size_expr} == 0]")


        # If the current node has no children (leaf node), save the path
        if isinstance(current, Node) and not current.transitions and flag:
            saved_pathstr.append(pathstr.copy())
          
        # Continue DFS for all child nodes
        if isinstance(current, Node):
            for child, condition in current.transitions.items():
                condition_str = f" [{condition}]" if condition else ""
                self.dfs(child, pathstr + [condition_str], saved_pathstr, flag)
        
        elif isinstance(current, FSM):
            entry_pathstrs = []
            current.dfs(current.entry, pathstr.copy(), entry_pathstrs,  False)
            if "emptyFSM" not in current.name:
                for entry_pathstr in entry_pathstrs:
                    entry_pathstr.append(f"FSM_END({current.name})")
           
            if not current.next:
                saved_pathstr.extend(entry_pathstrs)
            else:
            # For each path in entry_paths, continue DFS on each next FSM/node            
                for i in range(len(entry_pathstrs)):
                    for child in current.next:
                        # Use the entry_path as the start for DFS on the child nodes/FSMs
                        self.dfs(child, entry_pathstrs[i].copy(), saved_pathstr, flag)


    def save_all_paths(self):
        saved_pathstrs = []
        self.dfs(self.entry, [], saved_pathstrs, False)
        return saved_pathstrs

FSM_map = {}