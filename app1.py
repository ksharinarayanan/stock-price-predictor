from flask import Flask, render_template, url_for, request, session, redirect, jsonify

from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import os

from flask_pymongo import PyMongo
import bcrypt
import requests
import json

from model import *

app = Flask(__name__)


def sendToSlack(webhook, data):

    data = {"text": data}

    data = json.dumps(data)

    url = webhook

    slackResp = requests.post(url, data=data)

    return slackResp.text, slackResp.status_code


def cron_send():

    print("Cron job start!")

    User_data = mongo.db.users

    # user = users.find_one({'username': session['username']})

    users = User_data.find({"webhook": {"$exists": True}})

    # print(users)

    tod = datetime.datetime.now()

    prices = {}

    dates = []

    for day in range(1, 8):
        d = datetime.timedelta(days=day)
        d = tod + d
        dates.append(str(d).split()[0])

    print(dates)

    for user in users:

        companies = user["companies"]

        print(companies)

        for company in companies:

            if company is not None:
                company = company.upper()

            data = ""

            if company not in prices and company is not None and company.strip() is not None:

                query = {"Ticker": company}

                response = requests.post(
                    "http://localhost:3002/predict/", data=query)

                prediction = response.text

                prediction = prediction.replace(
                    '[', '').replace(']', '').replace('\n', '').replace("'", "").split(',')

                data = company + ":\n"

                for d in range(7):
                    data += dates[d] + ": " + prediction[d].strip()
                    data += "\n"

                prices[company] = prediction

            elif company in prices:
                prediction = prices[company]

                data = company + ":\n"

                for d in range(7):
                    data += dates[d] + ": " + prediction[d].strip()
                    data += "\n"

            sendToSlack(user["webhook"], data)

        # print(prices)
    print("Cron job end!")


if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':

    sched = BackgroundScheduler()
    sched.add_job(cron_send, 'interval', hours=24)
    sched.start()


app.secret_key = 'TOPSECRET'

app.config['MONGO_URI'] = 'mongodb://localhost:27017/stockPricePredictor'

mongo = PyMongo(app)


@app.route("/")
def index():
    if 'username' in session and session['username'] is not None:
        # user logged in

        return render_template("loggedPage.html")

        # return redirect(url_for("dashboard"))
        # return 'You are logged in as ' + session['username']

    return render_template("index.html")


@app.route("/login/", methods=['POST'])
def login():
    users = mongo.db.users

    login_user = users.find_one({'username': request.form['username']})

    if login_user:
        if bcrypt.hashpw(request.form['pass'].encode('utf-8'), login_user['password']) == login_user['password']:

            session['username'] = request.form['username']
            return 'Login successful!', 200
            return redirect(url_for('index'))

    return 'Invalid username/password combination', 401


@app.route("/register/", methods=['GET', 'POST'])
def register():

    if 'username' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':

        users = mongo.db.users

        existing_user = users.find_one({'username': request.form['username']})

        if existing_user is None:
            hashpass = bcrypt.hashpw(
                request.form['pass'].encode('utf-8'), bcrypt.gensalt())
            users.insert_one(
                {'username': request.form['username'], 'password': hashpass})

            session['username'] = request.form['username']

            return redirect(url_for('index'))

        return 'That username already exists!'

    return render_template('register.html')


@app.route('/dashboard/')
def dashboard():
    if 'username' in session and session['username'] is not None:
        return render_template('trackerDashboard.html')

    return redirect("/", code=302)


@app.route("/getCompanies/", methods=['GET'])
def getCompany():

    if 'username' in session and session['username'] is not None:

        users = mongo.db.users

        user = users.find_one({'username': session['username']})

        companies = (user['companies'])

        result = ""

        for company in companies:
            if company is not None:
                result += (company + " ")

        return result, 200

    return redirect("/", code=302)


@app.route('/predict/', methods=['POST'])
def predict():

    ticker = request.form["Ticker"]

    print(ticker)
    prediction = our_model(ticker, 7)
    print("THE PREDICTION IS ")
    print(prediction[0])
    print(type(prediction))
    table = prediction.to_frame()
    print(table.values.tolist())

    table = table.values.tolist()

    prices = []

    for t in table:
        prices.append(t[0])

    return jsonify(prices)


@app.route('/addCompany/', methods=['POST'])
def addCompany():

    if 'username' in session and session['username'] is not None:
        users = mongo.db.users

        existing_user = users.find_one({'username': session['username']})

        companies = request.get_json()

        users.update_one({'username': session['username']}, {
            '$set': companies}, upsert=False)

        return '', 201

    return redirect("/", code=302)


@app.route('/slackConfig/', methods=['POST', 'GET'])
def slackConfig():
    if 'username' in session and session['username'] is not None:

        users = mongo.db.users

        user = users.find_one({'username': session['username']})

        if request.method == 'GET':

            if 'webhook' not in user:
                return ''

            return user['webhook']

        else:

            # code to update slack config

            if session['username'] is None or 'username' not in session:
                return 'User not logged in'

            webhook = request.get_json()

            print(webhook)

            users.update_one({'username': session['username']}, {
                '$set': webhook}, upsert=False)

        return ''

    return redirect("/", code=302)


@app.route("/slackMessage/", methods=['POST'])
def testSlack():

    if 'username' in session and session['username'] is not None:

        users = mongo.db.users

        user = users.find_one({'username': session['username']})

        if user['webhook'] is None:
            return 'Webhook not configured!', 403

        webhook = user['webhook']

        jsonData = request.get_json()

        data = {"text": jsonData["message"]}

        data = json.dumps(data)

        url = webhook

        slackResp = requests.post(url, data=data)

        return slackResp.text, slackResp.status_code

    return redirect("/", code=302)


@app.route("/logout/")
def logout():

    session['username'] = None
    return redirect(url_for('index'))


@app.route("/faq/")
def chatbot():

    if 'username' in session and session['username'] is not None:

        return render_template('chatbot.html')

    return redirect("/", code=302)


if __name__ == '__main__':
    app.secret_key = 'thisisatopsecret'
    app.run(port=3000, debug=True)
