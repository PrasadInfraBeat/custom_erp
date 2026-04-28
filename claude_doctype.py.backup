import anthropic
import os
import json
import re

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def generate_doctype(doctype_name, description):
    print("Asking Claude to generate DocType: " + doctype_name)
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": "You are a Frappe/ERPNext expert. Generate a complete DocType JSON for: " + doctype_name + ". Description: " + description + ". Return ONLY valid JSON, no markdown, no code blocks, no explanation."
        }]
    )
    response = message.content[0].text.strip()
    response = re.sub(r"```json|```", "", response).strip()
    try:
        doctype_json = json.loads(response)
        safe_name = doctype_name.lower().replace(" ", "_")
        folder = "/home/frappe/frappe-bench/apps/custom_erp/custom_erp/doctype/" + safe_name
        os.makedirs(folder, exist_ok=True)
        filename = folder + "/" + safe_name + ".json"
        with open(filename, "w") as f:
            json.dump(doctype_json, f, indent=2)
        print("Saved to " + filename)
    except json.JSONDecodeError as e:
        print("JSON parse error: " + str(e))
        print("Raw response saved to /tmp/claude_response.txt")
        with open("/tmp/claude_response.txt", "w") as f:
            f.write(response)

if __name__ == "__main__":
    doctype_name = input("Enter DocType name: ")
    description = input("Describe the DocType: ")
    generate_doctype(doctype_name, description)
