import re

path = r'C:\Users\carla\Desktop\AI-Editir\AI-Editor\ai_editor\pipeline.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove triple backticks including variants
content = re.sub(r'^```+python\s*\n?', '', content)
content = re.sub(r'\n```+\s*$', '', content)
content = re.sub(r'```+\s*$', '', content)

# Clean up trailing whitespace
content = content.rstrip()

with open(path, 'w', encoding='utf-8') as f:
    f.write(content + '\n')

print('✓ Fixed pipeline.py - removed markdown backticks')
