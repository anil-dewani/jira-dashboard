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
        progress_report_data[project.key]['to_do'] = len(to_do_issues)
        in_progress_issues = jira.search_issues("project="+project.key+" and status='In Progress'")
        progress_report_data[project.key]['in_progress'] = len(in_progress_issues)
        total_issues = jira.search_issues("project="+project.key)
        progress_report_data[project.key]['total'] = len(total_issues)

    jira_progress_report.document("1").update(progress_report_data)
    return render_template('base.html', name="JIRA Progress Report")