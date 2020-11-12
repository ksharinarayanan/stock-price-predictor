from nltk.stem.lancaster import LancasterStemmer
from flask import Flask, render_template, url_for, request, session, redirect, jsonify, make_response

from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import os
import numpy as np
from tensorflow.keras.models import load_model
import random
import nltk
from flask_pymongo import PyMongo
import bcrypt
import requests
import json

from model import *

app = Flask(__name__)


def bag_of_words(s, words):
    bag = [0 for _ in range(len(words))]

    s_words = nltk.word_tokenize(s)
    s_words = [stemmer.stem(word.lower()) for word in s_words]

    for se in s_words:
        # adds a counter to an iterable and returns it in a form of numbered object
        for i, w in enumerate(words):
            if w == se:
                bag[i] = 1

    return np.array(bag)


stemmer = LancasterStemmer()

with open('Chatbot_Intents.json') as file:
    data = json.load(file)
# In[4]:


# consist of unique stemmed words/tokens from patterns extended in this list. No duplicates
words = []
# consist of tag words from intent
labels = []
# consist of tokenized sentences from patterns appended in this list
doc_x = []
# consists of tag words from intent matching tokens in doc_x
doc_y = []

# loop through each sentences in the data/intent
for intent in data['intents']:
    # loop through each sentences in patterns in intent
    for pattern in intent['patterns']:
        # tokenize each words in the pattern in intent
        wrds = nltk.word_tokenize(pattern)
        # method iterates over its argument adding each element to the list by extending the list
        words.extend(wrds)
        # method adds its argument as a single element to the end of a list. Length of the list increase by one
        doc_x.append(wrds)
        doc_y.append(intent['tag'])

    if intent['tag'] not in labels:
        labels.append(intent['tag'])

# stems and lower case the words
words = [stemmer.stem(w.lower()) for w in words if w != '?']

# set() removes duplicates, list() change into a list and sorted() sort in ascending order
words = sorted(list(set(words)))

labels = sorted(labels)

model = load_model('final_model.h5')


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
                    "http://localhost:3001/predict/", data=query)

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

            if "error" not in data:
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


@app.route("/testCron/")
def testCron():
    cron_send()
    return ''


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

    if 'username' in session and session['username'] is not None:
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
                return ""

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


@app.route("/chatbot/")
def chatbot():

    if 'username' in session and session['username'] is not None:

        return render_template('chatbot.html')

    return redirect("/", code=302)


@app.route('/chat/')
def chat():
    return render_template('index1.html')


@app.route('/pchat', methods=['POST', 'GET'])
def predict_1():
    while True:
        # prompt user to respond
        userInput = request.form['name']

        # predict the correct label given user input and comparing it to the words in pattern of intent
        results = model.predict(bag_of_words(
            userInput, words).reshape(-1, 468))
        # returns the indices of the maximum values along an axis
        results_index = np.argmax(results)
        # return the label(tag) that best match the user input
        user_tag = labels[results_index]
        # print(results.max()) # -- shows the highest probability for each chosen tag

        # condition set - only result with probability more than 0.85 will be considered correct respond
        if results.max() > 0.85:
            # prints out the responses form matching tag randomly
            for tag_selection in data['intents']:
                if tag_selection['tag'] == user_tag:
                    responses = tag_selection['responses']
            data1 = random.choices(responses)
            resp = make_response(json.dumps(data1))
            resp.status_code = 200
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp

        # user input with probability < 0.85, will get this message
        else:
            data1 = "Sorry I didn't get that. Please try again or go to INVESTOPEDIA for more assistance"
            resp = make_response(json.dumps(data1))
            resp.status_code = 200
            resp.headers['Access-Control-Allow-Origin'] = '*'
            return resp


if __name__ == '__main__':
    app.secret_key = 'thisisatopsecret'
    app.run(port=3000, debug=True)
