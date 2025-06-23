# ParCleanse
**ParCleanse** is a tool for validating network protocol parsers against the RFC documents. It analyzes parser implementations, extracts input formats, and checks for inconsistencies with protocol specifications.

> 🚧 This repository is under active development and will be updated with more complete instructions, examples, and scripts.

---

## 🔧 Setup Instructions
1. Download the latest EverParse release from:  
 👉 https://github.com/project-everest/everparse/releases

2. Create the everparse_files Folder
From the root of the ParCleanse repository, create a directory:
```bash
   mkdir -p everparse/everparse_files
```

3. Configure LLM APIs, RFC Inputs, and Parser Executable

4. Run the Tool
```bash
python src/main.py
```

## 📂 Directory Overview
```bash
ParCleanse/
├── DSL/                   # DSL description for the 3D format
├── everparse/             # EverParse repository (manually downloaded)
│   └── everparse_files/   # Input/output directory for 3D files
├── example/               # Examples used in LLM prompts
├── parser/                # Custom parser executables to be tested
├── RFC/                   # RFC documents for protocol specifications
├── src/                   # Core logic: parsing, validation, refinement
└── README.md              # This file
```
