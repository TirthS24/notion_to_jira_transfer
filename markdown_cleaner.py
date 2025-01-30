import re

def clean_bracketed_text(text):
    return re.sub(r'\s*\([^)]*\)', '', text).strip()

def markdown_to_dict(md_file):
    with open(md_file, 'r', encoding='utf-8') as file:
        md_content = file.read()
        # print("File Content: ", md_content)
    
    sections = {}
    content = md_content
    description = md_content
    if md_content.find("**Description:**") > 0:
        content = md_content.split("**Description:**")
        description = content[1]
    elif md_content.find("Description:\n") > 0:
        content = md_content.split("Description:\n")
        print("\n\n\nContent: ", content)
        description = content[1]
    for line in content[0].splitlines():
        # header_match = re.match(r'^(#{1,6})\s*(.*)', line)
        key_value_match = re.match(r'^\*{0,2}(.*?):\*{0,2}\s*(.*)', line)
        if key_value_match:
            key, value = key_value_match.groups()
            if key == "Child Tasks":
                cl_pattern = r'([^(]+)\s?\(([^)]+)\.md\)'
                print(value)
                sections[key] = {}
                for match in re.findall(cl_pattern, value):
                    # Clean the name by replacing '%20' with space
                    name = match[0].strip().replace('%20', ' ').lstrip(", ")
                    # Extract the ID (last 32 chars)
                    id_ = match[1][-32:]
                
                    sections[key][id_] = name
            else:
                sections[key] = value

    output = {
        "properties": sections,
        "description": description
    }
    return output

if __name__ == "__main__":
    input_md_file = "sample.md"
    output_dict = markdown_to_dict(input_md_file)
    print(output_dict)
