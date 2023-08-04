import os
from flask import Flask
from flask import render_template
from flask_apscheduler import APScheduler
from jira import JIRA
from dotenv import load_dotenv
from datetime import datetime as date
from time import ctime
from firebase_admin import credentials, firestore, initialize_app


# load enviroment variables from .env file in root folder
load_dotenv()


# Initialize Firestore DB
cred = credentials.Certificate('key.json')
default_app = initialize_app(cred)
db = firestore.client()
jira_progress_report = db.collection('jira_progress_report')
work_hours_data = db.collection('work_hours_data')

# Initialise flask app
app = Flask(__name__)

# initialize flask scheduler
scheduler = APScheduler()
scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()

# set a job to run once every day to update work hours graph data (86400 seconds = 1 day)
@scheduler.task('interval', id='update_work_hours_data', seconds=86400, misfire_grace_time=900)
def update_work_hours_data():
    work_hours_data_document = work_hours_data.document()
    work_hours_data_dict = {}
    work_hours_data_dict['date'] = date.today().strftime('%d %b %Y')
    # TODO: do some calculations
    work_hours_data_dict['executed_work_hours'] = 20
    work_hours_data_dict['pending_work_hours'] = 40
    work_hours_data_document.set(work_hours_data_dict)
    print('Updated work hours data with fresh datapoints')


# index page rendering
@app.route("/")
def index_page():
    report_data =  jira_progress_report.document("1").get()
    report_data = report_data.to_dict() 
    updated_at = report_data.pop("updated_at")

    # TODO: Fetch below values from firestore instead
    dates = "'01 Aug','02 Aug','03 Aug','04 Aug','05 Aug'"
    pending_work_hours = "28, 30, 32, 20, 39"
    executed_work_hours = "10, 20, 30, 10, 20"
    max_work_hours = 44

    # TODO: pass a dict showing the next important tickets needing attention
    return render_template('base.html', day_name=date.today().strftime("%A"),jira_progress_report=report_data,updated_at=updated_at,executed_work_hours=executed_work_hours,pending_work_hours=pending_work_hours,dates=dates,max_work_hours=max_work_hours)

# ajax call to update report data from the JIRA API
@app.route("/update")
def update_report_data():
    jira = JIRA(server=os.environ['JIRA_URL'],basic_auth=(os.environ['JIRA_EMAIL'], os.environ['JIRA_API_TOKEN']))
    projects = jira.projects()
    progress_report_data = {}
    progress_report_data['updated_at'] = ctime()
    for project in projects:
        progress_report_data[project.key] = {}
        progress_report_data[project.key]['name'] = project.name
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
    updated_at = progress_report_data.pop("updated_at")
    return updated_at