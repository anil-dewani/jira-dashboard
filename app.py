from flask import Flask
from flask import render_template
from jira import JIRA
from dotenv import load_dotenv
import os

from firebase_admin import credentials, firestore, initialize_app

# load enviroment variables from .env file in root folder
load_dotenv()

# Initialize Firestore DB
cred = credentials.Certificate('key.json')
default_app = initialize_app(cred)
db = firestore.client()
jira_progress_report = db.collection('jira_progress_report')


app = Flask(__name__)

@app.route("/")
def index_page():
    jira = JIRA(server=os.environ['JIRA_URL'],basic_auth=(os.environ['JIRA_EMAIL'], os.environ['JIRA_API_TOKEN']))
    projects = jira.projects()
    progress_report_data = {}
    for project in projects:
        progress_report_data[project.key] = {}
        to_do_issues = jira.search_issues("project="+project.key+" and status='To Do'")
        
        to_do_issues_hours = 0
        for to_do_issue in to_do_issues:
            if to_do_issue.fields.customfield_10016 is not None:
                to_do_issues_hours = to_do_issues_hours + float(to_do_issue.fields.customfield_10016)
        
        progress_report_data[project.key]['to_do'] = len(to_do_issues)
        progress_report_data[project.key]['to_do_hours'] = to_do_issues_hours
        
        in_progress_issues = jira.search_issues("project="+project.key+" and status='In Progress'")
        in_progress_issues_hours = 0
        for in_progress_issue in in_progress_issues:
            if in_progress_issue.fields.customfield_10016 is not None:
                in_progress_issues_hours = in_progress_issues_hours + float(in_progress_issue.fields.customfield_10016)
        
        progress_report_data[project.key]['in_progress'] = len(in_progress_issues)
        progress_report_data[project.key]['in_progress_hours'] = in_progress_issues_hours

        total_issues = jira.search_issues("project="+project.key)
        total_issues_hours = 0
        for total_issue in total_issues:
            if total_issue.fields.customfield_10016 is not None:
                total_issues_hours = total_issues_hours + float(total_issue.fields.customfield_10016)
        
        progress_report_data[project.key]['total'] = len(total_issues)
        progress_report_data[project.key]['total_hours'] = total_issues_hours

    jira_progress_report.document("1").update(progress_report_data)
    return render_template('base.html', name="JIRA Progress Report")