from notion_client import Client
import traceback
from jira import JIRA
import logging
from dotenv import load_dotenv
import os

load_dotenv()

notion = Client(auth=os.getenv("NOTION_TOKEN"))

class JiraIntegrator:
    def __init__(self, server, username, password, project_key):
        """
        Initialize Jira connection and project details.
        Args:
            server (str): Jira server URL
            username (str): Jira username
            password (str): Jira authentication token
            project_key (str): Jira project key where issues will be created
        """
        self.jira = JIRA(
            server=server,
            basic_auth=(username, password)
        )
        self.project_key = project_key
    def _find_or_create_user(self, email):
        """
        Find a Jira user by email or handle user creation/mapping.
        In real-world scenarios, you might need to:
        1. Map Notion emails to Jira usernames
        2. Handle cases where users don't exist
        Args:
            email (str): User's email from Notion
        Returns:
            str: Jira username or default assignee
        """
        # This is a placeholder. In practice, you'd implement:
        # 1. User lookup in Jira
        # 2. Potential user creation
        # 3. Fallback to a default user
        return email.split('@')[0] if email else None
    def create_epic(self, epic_data):
        """
        Create an Epic in Jira.
        Args:
            epic_data (dict): Epic information from Notion
        Returns:
            str: Created Epic's issue key
        """
        epic_issue_dict = {
            'project': {'key': self.project_key},
            'summary': epic_data['summary'],
            'description': epic_data['description'] or 'Epic created from Notion',
            'issuetype': {'name': 'Epic'},
        }
        # Add assignee if exists
        assignee: str = ""
        if epic_data.get('assignee') is not None:
            assignee = self._find_or_create_user(
                epic_data.get('assignee', {}).get("email", "")
            )
        if assignee:
            epic_issue_dict['assignee'] = {'name': assignee}
        epic = self.jira.create_issue(**epic_issue_dict)
        issue_meta = self.jira.createmeta(projectKeys=self.project_key, expand='projects.issuetypes.fields')
        # print("Task Metadata: ", issue_meta)
        return epic.key
    def create_task_hierarchy(self, epic_key, tasks):
        """
        Create tasks and subtasks under an epic.
        Args:
            epic_key (str): Jira Epic issue key
            tasks (list): List of tasks from Notion
        """
        for task_data in tasks:
            # Create Task
            task_issue_dict = {
                'project': {'key': self.project_key},
                'summary': task_data['summary'],
                'description': task_data['description'] or 'Task created from Notion',
                'issuetype': {'name': 'Task'},
                'parent': {'key': epic_key}  # Epic Link field (might vary by Jira instance)
            }
            # Add assignee
            assignee: str = ""
            if task_data.get('assignee') is not None:
                assignee = self._find_or_create_user(task_data.get('assignee', {}).get("email", ""))
            if assignee:
                task_issue_dict['assignee'] = {'name': assignee}
            task = self.jira.create_issue(**task_issue_dict)
            print("Task Created: ", task.key)
            # Create Subtasks
            for subtask_data in task_data.get('subtasks', []):
                subtask_issue_dict = {
                    'project': {'key': self.project_key},
                    'summary': subtask_data['summary'],
                    'description': subtask_data['description'] or 'Subtask created from Notion',
                    'issuetype': {'name': 'Subtask'},
                    'parent': {'key': task.key}
                }
                # Add assignee
                subtask_assignee: str = ""
                if task_data.get('assignee') is not None:
                    subtask_assignee = self._find_or_create_user(subtask_data.get('assignee', {}).get("email", ""))
                if subtask_assignee:
                    subtask_issue_dict['assignee'] = {'name': subtask_assignee}
                sub_task = self.jira.create_issue(**subtask_issue_dict)
                print("SubTask Created: ", sub_task.key)


def extract_created_by_info(person_property):
    """Extract person details from Notion property."""
    # print("Created by Person: ", person_property)
    if not person_property or not person_property.get("created_by"):
        return None
    
    person = person_property["created_by"]
    return {
        "name": person.get("name"),
        "email": person.get("person", {}).get("email")
    }

def extract_assignee_info(person_property):
    """Extract person details from Notion property."""
    if not person_property or not person_property.get("people"):
        return None
    
    person = person_property["people"][0]
    return {
        "name": person.get("name"),
        "email": person.get("person", {}).get("email")
    }

def fetch_page_description(page_id):
    """Retrieve text content from page blocks."""
    try:
        response = notion.blocks.children.list(block_id=page_id)
        blocks = response.get("results", [])
        text = []
        for block in blocks:
            if block["type"] == "paragraph":
                rich_text = block["paragraph"]["rich_text"]
                text.append("".join([t["text"]["content"] for t in rich_text]))
        return "\n".join(text)
    except Exception:
        return ""

def fetch_detailed_data():
    """Fetch structured data from Notion database."""
    response = notion.databases.query(database_id=os.getenv("PARENT_DATABASE_ID"))
    pages = response.get("results", [])
    # print("Pages Response: ", pages)
    
    structured_data = {}
    
    for page in pages:
        properties = page["properties"]
        page_id = page["id"]
        
        # Extract main task details
        task_data = {
            "story": properties["Project name"]["title"][0]["text"]["content"] 
                if properties["Project name"]["title"] else None,
            "description": fetch_page_description(page_id),
            "created_by": extract_created_by_info(properties.get("Created by")),
            "assignee": extract_assignee_info(properties.get("Assignee")),
            "tasks": {},
        }
        
        # Handle sub-tasks
        sub_task_relations = properties.get("Tasks", {}).get("relation", [])
        for sub_task in sub_task_relations:
            try:
                sub_task_page = notion.pages.retrieve(page_id=sub_task["id"])
                sub_task_props = sub_task_page["properties"]
                # print("\n\nTask Properties: ", sub_task_props)
                sub_task_details = {
                    "task": sub_task_props["Task name"]["title"][0]["text"]["content"] 
                        if sub_task_props["Task name"]["title"] else None,
                    "description": fetch_page_description(sub_task["id"]),
                    "assignee": extract_assignee_info(sub_task_props.get("Assignee")),
                    "created_by": extract_created_by_info(sub_task_props.get("Created by")),
                    "sub_tasks": [sub_task["id"] for sub_task in sub_task_props.get("Sub-tasks", {}).get("relation", [])]
                }
                
                task_data["tasks"].update({sub_task["id"]: sub_task_details})
                

            except Exception as e:
                print(f"Error fetching sub-task {sub_task['id']}: {e}")
        
        structured_data.update(task_data)
    
    return structured_data

# def process_subtasks(data: dict) -> dict:
#     results = data.copy()
#     results['tasks'] = results['tasks'].copy()
    
#     subtasks_to_remove = set()
#     for task_id, task_info in data['tasks'].items():
#         if 'sub_tasks' in task_info and task_info['sub_tasks']:
#             for sub_task in task_info["sub_tasks"]:
#                 # Check that subtask is not the same as parent task
#                 if sub_task["id"] != task_id and sub_task["id"] in data["tasks"].keys():
#                     subtasks_to_remove.add(sub_task["id"])
    
#     for subtask_id in subtasks_to_remove:
#         del results['tasks'][subtask_id]
    
#     return results

def resolve_nested_tasks(data):
    """
    Recursively resolve and flatten nested tasks in a dictionary.
    
    This function ensures that sub-tasks are completely replaced with their full task data,
    creating a comprehensive and flattened task structure.
    
    Args:
        data (dict): Nested dictionary containing tasks with potential sub_tasks
    
    Returns:
        dict: Transformed dictionary with sub_tasks fully expanded
    """
    # If the input is not a dictionary, return it as-is
    if not isinstance(data, dict):
        return data
    
    # Create a copy to avoid modifying the original dictionary
    resolved_data = data.copy()
    
    # Check if 'tasks' key exists in the data
    if 'tasks' in resolved_data:
        # Create a new dictionary to store resolved tasks
        new_tasks = {}
        # Keep track of tasks that have been used as sub-tasks
        processed_task_ids = set()
        
        # First pass: Collect all tasks to be resolved
        for task_id, task_info in list(resolved_data['tasks'].items()):
            # Ensure task_info is fully resolved
            resolved_data['tasks'][task_id] = resolve_nested_tasks(task_info)
        
        # Second pass: Process and replace sub-tasks
        for task_id, task_info in list(resolved_data['tasks'].items()):
            # Check if the task has sub-tasks
            if 'sub_tasks' in task_info and task_info['sub_tasks']:
                # Create a list to store fully resolved sub-tasks
                resolved_sub_tasks = []
                
                # Iterate through each sub-task ID
                for sub_task_id in task_info['sub_tasks']:
                    # Check if the sub-task exists in the tasks dictionary
                    if sub_task_id in resolved_data['tasks']:
                        # Get the full sub-task data
                        sub_task = resolved_data['tasks'][sub_task_id]
                        
                        # Mark this sub-task as processed to remove later
                        processed_task_ids.add(sub_task_id)
                        
                        # Add the full sub-task to resolved sub-tasks
                        resolved_sub_tasks.append(sub_task)
                
                # Replace the sub-task IDs with full sub-task data
                task_info['sub_tasks'] = resolved_sub_tasks
            
            # Store the task in new_tasks
            new_tasks[task_id] = task_info
        
        # Remove tasks that were used as sub-tasks
        for task_id in processed_task_ids:
            new_tasks.pop(task_id, None)
        
        # Update the tasks in the resolved data
        resolved_data['tasks'] = new_tasks
    
    return resolved_data

def map_notion_to_jira_fields(notion_data):
    """
    Map Notion data fields to appropriate Jira fields
    Args:
        notion_data (dict): Nested task data from Notion
    Returns:
        dict: Structured data mapped to Jira fields
    """
    jira_mapping = {
        'epic': {
            'summary': notion_data.get('story', 'Unnamed Epic'),
            'description': notion_data.get('description', ''),
            'issue_type': {'name': 'Epic'},
            'assignee': notion_data.get('assignee', {}),
            'created_by': notion_data.get('created_by', {})
        },
        'tasks': []
    }
    # Process tasks
    for task_id, task_info in notion_data.get('tasks', {}).items():
        task_mapping = {
            'summary': task_info.get('task', 'Unnamed Task'),
            'description': task_info.get('description', ''),
            'issue_type': {'name': 'Task'},
            'assignee': task_info.get('assignee', {}),
            'created_by': task_info.get('created_by', {}),
            'subtasks': []
        }
        # Process subtasks
        for subtask in task_info.get('sub_tasks', []):
            subtask_mapping = {
                'summary': subtask.get('task', 'Unnamed Subtask'),
                'description': subtask.get('description', ''),
                'issue_type': {'name': 'Subtask'},
                'assignee': subtask.get('assignee', {}),
                'created_by': subtask.get('created_by', {})
            }
            task_mapping['subtasks'].append(subtask_mapping)
        jira_mapping['tasks'].append(task_mapping)
    return jira_mapping

# def notion_to_jira_mapping(notion_data):
    """
    Transform Notion data into a Jira-friendly structure.
    Args:
        notion_data (dict): Nested task data from Notion
    Returns:
        dict: Structured data for Jira creation
    """
    jira_mapping = {
        'epic': {
            'story': notion_data.get('story', 'Unnamed Epic'),
            'description': notion_data.get('description', ''),
            'assignee': notion_data.get('assignee') if notion_data.get('assignee') is not None else {}
        },
        'tasks': []
    }
    for task_id, task_info in notion_data.get('tasks', {}).items():
        task_entry = {
            'summary': task_info.get('task', 'Unnamed Task'),
            'description': task_info.get('description', ''),
            'assignee': task_info.get('assignee') if task_info.get('assignee') is not None else {},
            'subtasks': []
        }
        # Handle subtasks recursively
        for subtask in task_info.get('sub_tasks', []):
            subtask_entry = {
                'summary': subtask.get('task', 'Unnamed Subtask'),
                'description': subtask.get('description', ''),
                'assignee': subtask.get('assignee') if subtask.get('assignee') is not None else {}
            }
            task_entry['subtasks'].append(subtask_entry)
        jira_mapping['tasks'].append(task_entry)
    return jira_mapping


def main():
    try:
        results = fetch_detailed_data()
        output = resolve_nested_tasks(results)
        jira_fields = map_notion_to_jira_fields(output)

        # Jira Integration Configuration
        jira_integrator = JiraIntegrator(
            server=os.getenv("JIRA_SERVER_URL"),
            username=os.getenv("JIRA_USERNAME"),
            password=os.getenv("JIRA_TOKEN"),
            project_key=os.getenv("JIRA_PROJECT_KEY")
        )
        # Create Epic
        epic_key = jira_integrator.create_epic(jira_fields['epic'])
        print("Epic Key Created: ", epic_key)
        # Create Tasks and Subtasks
        jira_integrator.create_task_hierarchy(epic_key, jira_fields['tasks'])
    except Exception as e:
        traceback.print_exc()
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()