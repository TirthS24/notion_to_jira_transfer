import os
import re
import csv
import logging
from dotenv import load_dotenv
from datetime import datetime
from jira import JIRA
from typing import Optional, Dict, List
from markdown_cleaner import markdown_to_dict
import json
import argparse

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

class HierarchicalDataParser:
    def __init__(self, root_dir):
        """
        Initialize Data Source paths.
        Args:
            root_dir (str): Path of the directory where the source files are located
        """
        self.root_dir = root_dir
        self.epics_dir = os.path.join(root_dir, "Epics")
        self.items_dir = os.path.join(root_dir, "Items")
        self.users_file = os.path.join(root_dir, "users.json")
        self.status_file = os.path.join(root_dir, "status.json")

    def process_user_email(self, name):
        if not name or name == "":
            return ""
        with open(self.users_file, "r", encoding="utf-8") as file:
            users = json.load(file)
            return users.get(name, name)
        
    def process_task_status(self, status):
        if not status or status == "":
            status = "backlog"
        with open(self.status_file, "r", encoding="utf-8") as file:
            status_mapping = json.load(file)
            return status_mapping.get(status)

    def process_child_tasks(self, text):
        cl_pattern = r'([^(]+)\s?\(([^)]+)\.md\)'
        result = {}
        for match in re.findall(cl_pattern, text):
            # Clean the name by replacing '%20' with space and normalizing it
            name = self.normalize_task_name(match[0].strip().replace('%20', ' ').lstrip(", "))
            # Extract the ID (last 32 chars)
            id_ = match[1][-32:]
            result[id_] = name
        
        return result

    # Function to read markdown file and select
    def read_markdown(self, filepath):
        with open(filepath, "r", encoding="utf-8-sig") as file:
            return file.read()

    # Function to clean filenames by removing trailing alphanumeric ID
    def clean_filename(self, filename):
        return re.sub(r'\s[a-f0-9]{16,}$', '', filename)

    def normalize_task_name(self, name):
        """Normalize task name by removing only colons (:)"""
        return name.replace(":", "").strip()

    # Function to extract the ID from a filename
    def extract_id(self, filename):
        match = re.search(r'\s([a-f0-9]{16,})$', filename)
        return match.group(1) if match else None

    # Function to extract reporter from markdown file (assuming first line contains "Created by:")
    def extract_reporter(self, md_content):
        match = re.search(r"Created by:\s*(.*)", md_content, re.IGNORECASE)
        return match.group(1).strip() if match else "Unknown"
    
    def extract_assignee(self, md_content):
        match = re.search(r"Assignee:\s*(.*)", md_content, re.IGNORECASE)
        return match.group(1).strip() if match else "Unknown"
        
    # Function to read CSV file and extract task details
    def read_csv(self, filepath):
        tasks = []
        with open(filepath, "r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            for row in reader:
                task_name = row.get("Task name", "").strip()
                task_id = row.get("ID", "").strip()
                reported_by = self.process_user_email(row.get("Reported By", "").strip())
                assignee = self.process_user_email(row.get("Assignee", "").strip())
                short_description = row.get("Short Description", "").strip()

                status = row.get("Status", "").strip()
                status = self.process_task_status(status.lower())

                priority = row.get("Priority", "").strip()
                priority_mapping = {
                    "P0-Blocker": "Highest",  # Jira default: "Highest"
                    "P1-Critical": "High",    # Jira default: "High"
                    "P2-High": "Medium",      # Jira default: "Medium"
                    "P3-Normal": "Low",       # Jira default: "Low"
                    "P4-Minor": "Lowest"      # Jira default: "Lowest"
                }
                priority = priority_mapping.get(priority, "Medium") if priority else "Medium"
                
                child_tasks = row.get("Child Tasks", "").strip()
                child_tasks = self.process_child_tasks(child_tasks) if child_tasks else {}

                story_points = row.get("# Story Points", "").strip()
                story_points = float(story_points) if story_points else None
                
                item_type = row.get("Type", "").strip()
                if item_type.lower() == "user story" or item_type.lower() == "story":
                    item_type = "Story"
                elif item_type.lower() == "bug" or item_type.lower() == "bugs":
                    item_type = "Bug"
                else:
                    item_type = "Task"

                logger.info(f"Item {task_name} of type {item_type} found from Notion Exports.")
                tasks.append({
                    "id": task_id,
                    "summary": self.clean_filename(task_name),
                    "type": item_type,
                    "reported_by": reported_by,
                    "assignee": assignee,
                    "story_points": story_points,
                    "description": "",  # Will be filled from task markdown file,
                    "short_description": short_description,
                    "child_items": child_tasks,
                    "priority": priority,
                    "status": status
                })

        return tasks

    def process_notion_data(self):
        epics = []

        # Traverse the Epics directory
        for epic_file in os.listdir(self.epics_dir):
            if epic_file.endswith(".md"):  # Identify markdown files (Epics)
                epic_path = os.path.join(self.epics_dir, epic_file)
                epic_summary = self.clean_filename(os.path.splitext(epic_file)[0])  # Clean filename
                epic_content = self.read_markdown(epic_path)  # Read markdown content
                epic_reporter = self.process_user_email(self.extract_reporter(epic_content))  # Extract Created by
                epic_assignee = self.process_user_email(self.extract_assignee(epic_content))  # Extract Assignee
                logger.info(f"Epic {epic_summary} found from Notion Exports.")
                # Create Epic dictionary
                epic_data = {
                    "summary": epic_summary,
                    "description": epic_content,
                    "type": "Epic",
                    "reported_by": epic_reporter,
                    "assignee": epic_assignee,
                    "items": [],
                }

                # Find associated CSV file (Tasks.csv)
                epic_folder_path = os.path.join(self.epics_dir, epic_file[:-3])
                if os.path.exists(epic_folder_path) and os.path.isdir(epic_folder_path):
                    for file in os.listdir(epic_folder_path):
                        if file.endswith(".csv"):  # Read all CSV files
                            csv_path = os.path.join(epic_folder_path, file)
                            epic_data["items"].extend(self.read_csv(csv_path))
                            logger.info(f"Items for Epic {epic_summary} found from Notion Exports.")

                # Read task descriptions from markdown files inside src/Tasks
                for task in epic_data["items"]:
                    for task_file in os.listdir(self.items_dir):
                        file_compare_str = task["summary"] if len(task["summary"]) < 35 else task["summary"][:35]
                        if task_file.endswith(".md") and task_file.lower().startswith(file_compare_str.lower()):
                            logger.info(f"Looking for Task: '{task["summary"]}' in File: '{task_file}'")
                            task_path = os.path.join(self.items_dir, task_file)
                            task["description"] = markdown_to_dict(task_path).get("description")
                            if isinstance(task["child_items"], str) and task["child_items"] == "":
                                task["child_items"] = {}
                            task["child_items"].update(markdown_to_dict(task_path).get("properties", {}).get("Child Tasks", {}))
                            break
                # Add Epic to the list
                epics.append(epic_data)

        return epics

    def reorganize_epic_tasks(self, epics: List[Dict]) -> List[Dict]:
        processed_epics = []
        
        for epic in epics:
            items = epic.get('items', [])
            stories = [item for item in items if item['type'] == 'Story']
            tasks = [item for item in items if item['type'] == 'Task']

            # Normalize task summaries for accurate matching
            task_map = {self.normalize_task_name(task['summary']): task for task in tasks}
            standalone_tasks = []

            # First pass: attach tasks to their correct parents (Story or Task)
            for task in tasks:
                if isinstance(task['child_items'], dict):
                    new_child_items = {}

                    for key, child_task_name in task['child_items'].items():
                        normalized_name = self.normalize_task_name(child_task_name)
                        if normalized_name in task_map:
                            child_task = task_map.pop(normalized_name)  # Remove to prevent duplicates
                            new_child_items[child_task['id']] = child_task
                        else:
                            new_child_items[key] = child_task_name  # Retain unmatched names
                    
                    task['child_items'] = new_child_items  # Update child items

            # Second pass: Attach tasks to Stories
            for story in stories:
                if not isinstance(story['child_items'], dict):
                    story['child_items'] = {}

                new_child_items = {}

                for key, child_task_name in story['child_items'].items():
                    normalized_name = self.normalize_task_name(child_task_name)
                    if normalized_name in task_map:
                        story_task = task_map.pop(normalized_name)  # Remove to prevent duplicate processing
                        new_child_items[story_task['id']] = story_task
                    else:
                        new_child_items[key] = child_task_name  # Retain unmatched items

                story['child_items'] = new_child_items  # Update story child_items

            # Any remaining tasks that weren't matched to a Story stay standalone
            standalone_tasks.extend(task_map.values())

            # Update epic items to include both stories and standalone tasks
            epic['items'] = stories + standalone_tasks
            processed_epics.append(epic)

        return processed_epics

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

    # Function to get transition ID from status name
    def get_transition_id(self, issue_key, target_status):
        transitions = self.jira.transitions(issue_key)
        for transition in transitions:
            if transition['to']['name'].lower() == target_status.lower():
                return transition['id']
        return None

    # Function to change issue status using status name
    def transition_issue(self, issue_key, target_status):
        transition_id = self.get_transition_id(issue_key, target_status)
        if transition_id:
            self.jira.transition_issue(issue_key, transition_id)
            print(f"Issue {issue_key} transitioned to {target_status}.")
        else:
            print(f"Error: No transition found for status '{target_status}'.")

    def find_jira_user(self, email: str) -> Optional[str]:
        """
        Find Jira user by email
        Args:
            email (str): User's email
        Returns:
            Optional[str]: Jira username or None if not found
        """
        try:
            if email:
                # Use alternative search methods compliant with GDPR restrictions
                user = self.jira.search_users(
                    query=email,
                    maxResults=1
                )
                if user:
                    return user[0].accountId
            else:
                return None 
        except Exception as e:
            logger.error(f"GDPR-compliant user search error: {e}")
            return None
        
    def add_users_fields(self, target_dict, source_dict, incl_assignee=False, incl_reporter=False):
        if incl_assignee:
            assignee: dict = {}
            if source_dict.get('assignee') is not None:
                assignee = self.find_jira_user(
                    source_dict.get('assignee', "")
                )
            if assignee:
                target_dict['assignee'] = {'accountId': assignee}
        if incl_reporter:
            reporter: dict = {}
            if source_dict.get('reported_by') is not None and source_dict['reported_by']:
                reporter = self.find_jira_user(
                    source_dict.get('reported_by', "")
                )
            if reporter:
                target_dict['reporter'] = {'accountId': reporter}

    def create_epic(self, epic_data):

        epic_issue_dict = {
            'project': {'key': self.project_key},
            'summary': epic_data['summary'],
            'description': epic_data['description'] or 'Epic created from Notion',
            'issuetype': {'name': epic_data['type']},
        }
        # Add assignee and reporter if exists
        self.add_users_fields(epic_issue_dict, epic_data, incl_assignee=True, incl_reporter=False)
        epic = self.jira.create_issue(**epic_issue_dict)
        logger.info(f"Epic `{epic_issue_dict['summary']}` Created in Jira with key {epic.key}")
        return epic.key
    
    def create_task_hierarchy(self, epic_key, tasks):

        for task_data in tasks:
            # Create Task
            task_issue_dict = {
                'project': {'key': self.project_key},
                'summary': task_data['summary'],
                'description': task_data['description'] or 'Task created from Notion',
                'issuetype': {'name': task_data['type']},
                'parent': {'key': epic_key}, # Epic Link field (might vary by Jira instance)
                # 'priority': {'name': task_data['priority'] or 'Medium'}
            }
            self.add_users_fields(task_issue_dict, task_data, incl_assignee=True, incl_reporter=False)
            task = self.jira.create_issue(**task_issue_dict)
            logger.info(f"Task `{task_issue_dict['summary']}` Created in Jira with key {task.key}")
            self.transition_issue(task.key, task_data['status'])
            logger.info(f"Task `{task_issue_dict['summary']}` status changed to `{task_data['status']}`")
            # transitions = self.jira.transitions(task)
            # for t in transitions:
            #     print(f"id: {t['id']}, name: {t['name']}")
            # Create Subtasks
            for _, sub_data in task_data.get('child_items', {}).items():
                if isinstance(sub_data, str):
                    continue
                sub_data['type'] = 'Sub-task'
                subtask_issue_dict = {
                    'project': {'key': self.project_key},
                    'summary': sub_data['summary'],
                    'description': sub_data['description'] or 'Sub-task created from Notion',
                    'issuetype': {'name': sub_data['type']},
                    'parent': {'key': task.key},
                    # 'priority': {'name': sub_data['priority'] or 'Medium'}
                }
                self.add_users_fields(subtask_issue_dict, sub_data, incl_assignee=True, incl_reporter=False)
                sub_task = self.jira.create_issue(**subtask_issue_dict)
                logger.info(f"Sub Task `{subtask_issue_dict['summary']}` Created in Jira with key {sub_task.key}")
                self.transition_issue(sub_task.key, sub_data['status'])
                logger.info(f"Task `{subtask_issue_dict['summary']}` status changed to `{sub_data['status']}`")

def main():
    parser = argparse.ArgumentParser(description="Process Notion data and upload to Jira.")
    parser.add_argument("--root", required=True, help="Root directory containing Notion export data")
    args = parser.parse_args()

    root_dir = args.root
    # Obtain hierarchical data
    dataParser = HierarchicalDataParser(root_dir)
    epics = dataParser.process_notion_data()
    epics = dataParser.reorganize_epic_tasks(epics)
    # Save as JSON file
    output_file = "epics_data.json"
    with open(output_file, "w", encoding="utf-8") as json_file:
        json.dump(epics, json_file, indent=4)
    
    JIRA_SERVER_URL = os.getenv("JIRA_SERVER_URL")
    JIRA_USERNAME = os.getenv("JIRA_USERNAME")
    JIRA_PASSWORD = os.getenv("JIRA_TOKEN")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")
    jira = JiraIntegrator(JIRA_SERVER_URL, JIRA_USERNAME, JIRA_PASSWORD, JIRA_PROJECT_KEY)
    for data in epics:
        epic_id = jira.create_epic(data)
        jira.create_task_hierarchy(epic_id, data['items'])
    print(f"Data successfully saved to {output_file}")

if __name__ == '__main__':
    main()
