# Standard Library Imports
import traceback
import logging
import os
from typing import Optional
from datetime import datetime

# Third-Party Library Imports
from notion_client import Client
from jira import JIRA
from dotenv import load_dotenv

# Initializing Environment variables loader
load_dotenv()

# Configure logging
def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate log filename with timestamp
    log_filename = os.path.join(log_dir, f'notion_to_jira_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()  # Also output to console
        ]
    )
    return logging.getLogger(__name__)

# Global logger object
logger = setup_logging()

class NotionFetcher:
    def __init__(self, notion_token: str, database_id: str):
        """
        Initialize Notion connection.
        Args:
            notion_token (str): Notion Internal Integration Token
            database_id (str): ID of the database containing epics
        """
        # Initializing Notion client
        self.notion: Client = Client(auth=notion_token)
        self.database_id: str = database_id

    def extract_created_by_info(self, person_property: dict):
        """
        Extract person details from a Notion property.
        Args:
            person_property (dict): Dictionary containing user email and name from Notion.
        Returns:
            dict: Simplified dictionary with user details.
        """

        if not person_property or not person_property.get("created_by"):
            return None
        
        person = person_property["created_by"]
        return {
            "name": person.get("name"),
            "email": person.get("person", {}).get("email")
        }

    def extract_assignee_info(self, person_property):
        """
        Extract person details from a Notion property.
        Args:
            person_property (dict): Dictionary containing user email and name from Notion.
        Returns:
            dict: Simplified dictionary with user details.
        """

        if not person_property or not person_property.get("people"):
            return None
        
        person = person_property["people"][0]
        return {
            "name": person.get("name"),
            "email": person.get("person", {}).get("email")
        }

    def fetch_page_description(self, page_id):
        """
        Retrieve text content from page blocks.
        Args:
            page_id (str): ID of the Notion page to be fetched.
        Returns:
            str: Description of the page.
        """
        try:
            response = self.notion.blocks.children.list(block_id=page_id)
            blocks = response.get("results", [])
            text = []
            for block in blocks:
                if block["type"] == "paragraph":
                    rich_text = block["paragraph"]["rich_text"]
                    text.append("".join([t["text"]["content"] for t in rich_text]))
            return "\n".join(text)
        except Exception as e:
            logger.error(f"Error while fetching page description: {e}")
            return ""

    def fetch_detailed_data(self):
        """
        Fetch structured data from Notion database.
        Returns:
            dict: Structured Data obtained from Notion"""
        response = self.notion.databases.query(database_id=os.getenv("PARENT_DATABASE_ID"))
        epics = response.get("results", [])
        
        structured_data = {}
        
        for epic in epics:
            try:
                properties = epic.get("properties")
                page_id = epic.get("id")
                
                # Extract main epic details
                epic_data = {
                    "story": properties["Project name"]["title"][0]["text"]["content"] 
                        if properties["Project name"]["title"] else None,
                    "description": self.fetch_page_description(page_id),
                    "reported_by": self.extract_created_by_info(properties.get("Created by")),
                    "assignee": self.extract_assignee_info(properties.get("Assignee")),
                    "tasks": {},
                }
                logger.info(f"Epic with ID {page_id} found from Notion.")
                
                # Handle sub-tasks
                task_relations = properties.get("Tasks", {}).get("relation", [])
                for task in task_relations:
                    try:
                        task_page = self.notion.pages.retrieve(page_id=task["id"])
                        task_props = task_page["properties"]
                        task_details = {
                            "task": task_props["Task name"]["title"][0]["text"]["content"] 
                                if task_props["Task name"]["title"] else None,
                            "description": self.fetch_page_description(task["id"]),
                            "assignee": self.extract_assignee_info(task_props.get("Assignee")),
                            "reported_by": self.extract_created_by_info(task_props.get("Reported by")),
                            "sub_tasks": [sub_task["id"] for sub_task in task_props.get("Sub-tasks", {}).get("relation", [])]
                        }
                        logger.info(f"Task with ID {task["id"]} found from Notion.")
                        
                        epic_data["tasks"].update({task["id"]: task_details})
                        

                    except Exception as e:
                        logger.error(f"Error fetching sub-task {task['id']}: {e}")
                
                structured_data.update(epic_data)

            except Exception as e:
                logger.error(f"Error while fetching Epic: {e}")
        
        return structured_data

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

    def find_jira_user(self, email: str) -> Optional[str]:
        """
        Find Jira user by email
        Args:
            email (str): User's email
        Returns:
            Optional[str]: Jira username or None if not found
        """
        try:
            # Use alternative search methods compliant with GDPR restrictions
            user = self.jira.search_users(
                query=email,  # Use username part
                maxResults=1
            )

            return user[0].accountId
            
        except Exception as e:
            logger.error(f"GDPR-compliant user search error: {e}")
            return None
        
    def add_users_fields(self, target_dict, source_dict, incl_assignee=False, incl_reporter=False):
        if incl_assignee:
            assignee: dict = {}
            if source_dict.get('assignee') is not None:
                assignee = self.find_jira_user(
                    source_dict.get('assignee', {}).get("email", "")
                )
            if assignee:
                target_dict['assignee'] = {'accountId': assignee}
        if incl_reporter:
            reporter: dict = {}
            if source_dict.get('reported_by') is not None and source_dict['reported_by']:
                reporter = self.find_jira_user(
                    source_dict.get('reported_by', {}).get("email", "")
                )
            if reporter:
                target_dict['reporter'] = {'accountId': reporter}

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
        # Add assignee and reporter if exists
        self.add_users_fields(epic_issue_dict, epic_data, incl_assignee=True, incl_reporter=True)
        epic = self.jira.create_issue(**epic_issue_dict)
        logger.info(f"Epic `{epic_issue_dict['summary']}` Created in Jira with key {epic.key}")
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
            self.add_users_fields(task_issue_dict, task_data, incl_assignee=True, incl_reporter=True)
            task = self.jira.create_issue(**task_issue_dict)
            logger.info(f"Task `{task_issue_dict['summary']}` Created in Jira with key {task.key}")
            # Create Subtasks
            for subtask_data in task_data.get('subtasks', []):
                subtask_issue_dict = {
                    'project': {'key': self.project_key},
                    'summary': subtask_data['summary'],
                    'description': subtask_data['description'] or 'Subtask created from Notion',
                    'issuetype': {'name': 'Subtask'},
                    'parent': {'key': task.key}
                }
                self.add_users_fields(subtask_issue_dict, subtask_data, incl_assignee=True, incl_reporter=True)
                
                sub_task = self.jira.create_issue(**subtask_issue_dict)
                logger.info(f"Sub Task `{subtask_issue_dict['summary']}` Created in Jira with key {sub_task.key}")


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
            'reported_by': notion_data.get('reported_by', {})
        },
        'tasks': []
    }
    # Process tasks
    for _, task_info in notion_data.get('tasks', {}).items():
        task_mapping = {
            'summary': task_info.get('task', 'Unnamed Task'),
            'description': task_info.get('description', ''),
            'issue_type': {'name': 'Task'},
            'assignee': task_info.get('assignee', {}),
            'reported_by': task_info.get('reported_by', {}),
            'subtasks': []
        }
        # Process subtasks
        for subtask in task_info.get('sub_tasks', []):
            subtask_mapping = {
                'summary': subtask.get('task', 'Unnamed Subtask'),
                'description': subtask.get('description', ''),
                'issue_type': {'name': 'Subtask'},
                'assignee': subtask.get('assignee', {}),
                'reported_by': subtask.get('reported_by', {})
            }
            task_mapping['subtasks'].append(subtask_mapping)
        jira_mapping['tasks'].append(task_mapping)
    return jira_mapping

def main():
    """
    Driver function to sequentially do the following:
    1. Obtain Data from Notion Database.
    2. Structure Data in Heirarchical format.
    3. Structure Data for Jira Issues input.
    4. Push Data to Jira via API calls.
    """
    try:
        notion_fetcher = NotionFetcher(
            notion_token=os.getenv("NOTION_TOKEN"),
            database_id=os.getenv("PARENT_DATABASE_ID")
        )
        results = notion_fetcher.fetch_detailed_data()
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
        # Create Tasks and Subtasks
        jira_integrator.create_task_hierarchy(epic_key, jira_fields['tasks'])
    except Exception as e:
        logger.error(f"Error occurred: {e}")

if __name__ == "__main__":
    main()