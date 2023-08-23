import os
from flask import Flask
from flask import render_template
from flask_apscheduler import APScheduler
from jira import JIRA
from dotenv import load_dotenv
from datetime import datetime as date
from time import ctime
from firebase_admin import credentials, firestore, initialize_app
import time

load_dotenv()

# Initialize Firestore DB
cred = credentials.Certificate('key.json')
default_app = initialize_app(cred)
db = firestore.client()
jira_progress_report = db.collection('jira_progress_report')
work_hours_data = db.collection('work_hours_data')
upcoming_tickets = db.collection('upcoming_tickets')
tracking_events = db.collection('tracking_events')

# Initialise flask app
app = Flask(__name__)

# initialize flask scheduler
scheduler = APScheduler()
scheduler.api_enabled = True
scheduler.init_app(app)
scheduler.start()

#86400
@scheduler.task('interval', id='update_work_hours_data', seconds=10000, misfire_grace_time=900)
def update_work_hours_data():
    work_hours_data_document = work_hours_data.document()
    work_hours_data_dict = {}
    work_hours_data_dict['date'] = date.today().strftime('%d %b %Y')

    # store old report data
    old_report_data = jira_progress_report.document("1").get().to_dict()
    old_report_data.pop("updated_at")

    # update report data
    update_report_data()

    # new report data
    new_report_data = jira_progress_report.document("1").get().to_dict()
    new_report_data.pop("updated_at")
    pending_work_hours_total = 0
    total_todo_hours = 0
    for project_data_key, project_data_value in new_report_data.items():
        print(project_data_value)
        pending_work_hours_total = pending_work_hours_total + project_data_value['to_do_hours']
        total_todo_hours = total_todo_hours + project_data_value['total_hours']

    old_todo_hours = 0
    for project_data_key, project_data_value in old_report_data.items():
        print(project_data_value)
        old_todo_hours = old_todo_hours - project_data_value['to_do_hours']

    # calculate differences and store for chart
    work_hours_data_dict['executed_work_hours'] = total_todo_hours - old_todo_hours
    work_hours_data_dict['pending_work_hours'] = pending_work_hours_total
    work_hours_data_dict['timestamp'] = time.time()

    work_hours_data_document.set(work_hours_data_dict)

    # TODO: calculate the hours worked today and set an css class value to be used on calendar
    print('Updated work hours data with fresh datapoints')


# index page rendering
@app.route("/")
def index_page():
    report_data = jira_progress_report.document("1").get()
    report_data = report_data.to_dict() 
    updated_at = report_data.pop("updated_at")

    # TODO: Fetch below values from firestore instead
    dates = []
    pending_work_hours = []
    executed_work_hours = []
    last_week_work_hours_data = work_hours_data.order_by("timestamp").limit_to_last(7).get()

    for current_day_data in last_week_work_hours_data:
        dates.append(str(current_day_data.to_dict()['date']).replace(",", ""))
        executed_work_hours.append(str(current_day_data.to_dict()['executed_work_hours']))
        pending_work_hours.append(str(current_day_data.to_dict()['pending_work_hours']))

    print(pending_work_hours)

    max_work_hours = max(list(map(float, pending_work_hours))) + 30
    print(max_work_hours)
    # convert list to comma seperated values
    dates = "','".join(dates)
    pending_work_hours = ",".join(pending_work_hours)
    executed_work_hours = ",".join(executed_work_hours)
    upcoming_tickets_data = upcoming_tickets.document("1").get().to_dict()
    # TODO: pass a dict showing the next important tickets needing attention
    return render_template('base.html', day_name=date.today().strftime("%A"), jira_progress_report=report_data, updated_at=updated_at, executed_work_hours=executed_work_hours, pending_work_hours=pending_work_hours, dates=dates, max_work_hours=max_work_hours,upcoming_tickets=upcoming_tickets_data)


@app.route("/update")
def update_report_data():
    jira = JIRA(server=os.environ['JIRA_URL'], basic_auth=(os.environ['JIRA_EMAIL'], os.environ['JIRA_API_TOKEN']))
    projects = jira.projects()
    boards = jira.boards()
    progress_report_data = {}
    progress_report_data['updated_at'] = ctime()
    for project in projects:
        progress_report_data[project.key] = {}
        progress_report_data[project.key]['name'] = project.name
        to_do_issues = jira.search_issues("project="+project.key+" and status='To Do' AND reporter = 'me@timefractal.com'")
        to_do_issues_hours = 0
        for to_do_issue in to_do_issues:
            if to_do_issue.fields.customfield_10016 is not None:
                to_do_issues_hours = to_do_issues_hours + float(to_do_issue.fields.customfield_10016)

        progress_report_data[project.key]['to_do'] = len(to_do_issues)
        progress_report_data[project.key]['to_do_hours'] = to_do_issues_hours
        
        in_progress_issues = jira.search_issues("project="+project.key+" and status='In Progress' AND reporter = 'me@timefractal.com'")
        in_progress_issues_hours = 0
        for in_progress_issue in in_progress_issues:
            if in_progress_issue.fields.customfield_10016 is not None:
                in_progress_issues_hours = in_progress_issues_hours + float(in_progress_issue.fields.customfield_10016)
        
        progress_report_data[project.key]['in_progress'] = len(in_progress_issues)
        progress_report_data[project.key]['in_progress_hours'] = in_progress_issues_hours

        total_issues = jira.search_issues("project="+project.key+" AND reporter = 'me@timefractal.com'")
        total_issues_hours = 0
        for total_issue in total_issues:
            if total_issue.fields.customfield_10016 is not None:
                total_issues_hours = total_issues_hours + float(total_issue.fields.customfield_10016)

        progress_report_data[project.key]['total'] = len(total_issues)
        progress_report_data[project.key]['total_hours'] = total_issues_hours

    upcoming_tickets_data = {}
    for board in boards:
        sprints = jira.sprints(board.id)
        closed_sprints = 0
        for sprint in sprints:
            if sprint.state == 'closed':
                closed_sprints = closed_sprints + 1
            else:
                tickets = jira.search_issues("sprint = "+str(sprint.id)+" AND reporter = 'me@timefractal.com'")
                upcoming_tickets_data[board.location.projectKey] = {}
                for ticket in tickets[:5]:
                    upcoming_tickets_data[board.location.projectKey][ticket.key] = ticket.get_field('summary')
                
    upcoming_tickets.document("1").update(upcoming_tickets_data)
    jira_progress_report.document("1").update(progress_report_data)
    updated_at = progress_report_data.pop("updated_at")
    return updated_at


@app.route("/start-tracking/<ticket_id>/", methods=['POST', 'GET'])
def start_tracking(ticket_id):
    tracking_data = {}
    tracking_data['event_type'] = 'start'
    tracking_data['ticket_id'] = ticket_id
    tracking_data['timestamp'] = time.time()
    tracking_events_document = tracking_events.document()
    tracking_events_document.set(tracking_data)
    return "ok"


@app.route("/end-tracking/<ticket_id>/", methods=['POST', 'GET'])
def end_tracking(ticket_id):
    tracking_data = {}
    tracking_data['event_type'] = 'end'
    tracking_data['ticket_id'] = ticket_id
    tracking_data['timestamp'] = time.time()
    tracking_events_document = tracking_events.document()
    tracking_events_document.set(tracking_data)
    return "ok"


@app.route("/pulse/<ticket_id>/", methods=['POST', 'GET'])
def pulse_tracking(ticket_id):
    tracking_data = {}
    tracking_data['event_type'] = 'pulse'
    tracking_data['ticket_id'] = ticket_id
    tracking_data['timestamp'] = time.time()
    tracking_events_document = tracking_events.document()
    tracking_events_document.set(tracking_data)
    return "ok"
