#!/usr/bin/env python3
import os
from translations import TRANSLATIONS
from datetime import datetime

def flatten_dict(d, parent_key='', sep='.'):
    """Flatten a nested dictionary into a single level dictionary with dot notation keys."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def create_po_file(language, translations, output_dir):
    """Create a .po file for the specified language."""
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Create the .po file content
    po_content = f'''# {language.upper()} translations for Lively Ageing.
# Copyright (C) {datetime.now().year} Lively Ageing
# This file is distributed under the same license as the PROJECT project.
msgid ""
msgstr ""
"Project-Id-Version: PROJECT VERSION\\n"
"Report-Msgid-Bugs-To: EMAIL@ADDRESS\\n"
"POT-Creation-Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\\n"
"PO-Revision-Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language: {language}\\n"
"Language-Team: {language} <LL@li.org>\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=utf-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Generated-By: Babel {datetime.now().year}.{datetime.now().month}.0\\n"
\\n'''

    # Add translations
    flat_translations = flatten_dict(translations)
    for key, value in flat_translations.items():
        po_content += f'''
msgid "{key}"
msgstr "{value}"
'''

    # Write the .po file
    po_file_path = os.path.join(output_dir, f"{language}", "LC_MESSAGES", "messages.po")
    os.makedirs(os.path.dirname(po_file_path), exist_ok=True)
    
    with open(po_file_path, 'w', encoding='utf-8') as f:
        f.write(po_content)
    
    print(f"Created {po_file_path}")

def main():
    """Main function to update all translations."""
    for lang, translations in TRANSLATIONS.items():
        create_po_file(lang, translations, 'translations')
        # Compile the .po file to .mo
        os.system(f'pybabel compile -d translations -l {lang}')

if __name__ == '__main__':
    main() 