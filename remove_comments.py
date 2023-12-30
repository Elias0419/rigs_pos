import os
import re

def remove_comments(source_string):
    
    
    source_string = re.sub(r'

    
    source_string = re.sub(r'\'\'\'.*?\'\'\'|\"\"\".*?\"\"\"', '', source_string, flags=re.DOTALL)

    return source_string

def process_python_files(directory):
    
    for filename in os.listdir(directory):
        if filename.endswith('.py'):
            file_path = os.path.join(directory, filename)

            
            with open(file_path, 'r') as file:
                content = file.read()

            
            cleaned_content = remove_comments(content)

            
            with open(file_path, 'w') as file:
                file.write(cleaned_content)

            print(f"Processed {filename}")


process_python_files('.')
