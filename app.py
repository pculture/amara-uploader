#!/usr/bin/env python
import os
from flask import Flask
from flask import render_template, url_for, flash, session, redirect, request
from werkzeug import secure_filename
import requests
import tempfile
import hashlib
from boto.s3.connection import S3Connection
from boto.s3.key import Key
import json

UPLOAD_DIR = os.getenv('UPLOAD_DIR', tempfile.gettempdir())
ALLOWED_EXTENSIONS = set(['mp4'])

app = Flask(__name__)
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['AWS_ACCESS_KEY_ID'] = os.getenv('AWS_ACCESS_KEY_ID')
app.config['AWS_SECRET_ACCESS_KEY'] = os.getenv('AWS_SECRET_ACCESS_KEY')
app.config['S3_BUCKET'] = os.getenv('S3_BUCKET')
app.config['S3_PATH'] = os.getenv('S3_PATH', '')
app.secret_key = os.getenv('SECRET_KEY',
        '\xd8\x9c\x1a\xe7|\xce\x15\xe4\xa2\xfd\x97B\x8dK\xee|\x08!\x9e\xef[\xc9u4')
app.config['amara_api_endpoint'] = os.getenv('AMARA_API_ENDPOINT',
        'https://www.amara.org')
app.config['amara_api_url_base'] = '/api2/partners'
app.config['api_url'] = app.config['amara_api_endpoint'] + \
        app.config['amara_api_url_base']

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def _make_api_request(method='GET', path='/', data=None):
    url = app.config['api_url'] + path
    headers = {
        'Accept': 'application/json',
        'X-api-username': session.get('username'),
        'X-apikey': session.get('api_key'),
    }
    methods = {
        'get': requests.get,
        'put': requests.put,
        'post': requests.post,
    }
    return methods[method.lower()](url, data=data, headers=headers)

def upload_to_s3(filename):
    aws_id = app.config['AWS_ACCESS_KEY_ID']
    aws_key = app.config['AWS_SECRET_ACCESS_KEY']
    bucket = app.config['S3_BUCKET']
    s3_conn = S3Connection(aws_id, aws_key)
    bucket = s3_conn.get_bucket(bucket)
    k = Key(bucket)
    k.key = os.path.join(app.config['S3_PATH'], os.path.basename(filename))
    k.set_contents_from_filename(filename)
    k.make_public()
    return k

@app.route('/')
def index():
    if 'username' in session and 'api_key' in session:
        resp = _make_api_request('get', '/teams/?limit=0')
        teams = json.loads(resp.content)
        ctx = {
            'username': session['username'],
            'api_key': session['api_key'],
            'teams': teams.get('objects'),
        }
        return render_template('index.html', **ctx)
    else:
        return redirect(url_for('login'))

@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        api_key = request.form['api_key']
        # temporarily set session
        session['username'] = user
        session['api_key'] = api_key
        # make a request to the api to see if it's valid
        resp = _make_api_request('get', '/teams/')
        if resp.status_code != 401:
            return redirect(url_for('index'))
    ctx = {
        'AMARA_ENDPOINT': app.config['amara_api_endpoint'],
    }
    return render_template('login.html', **ctx)

@app.route('/upload/', methods=['POST'])
def upload():
    file = request.files['file']
    if file and allowed_file(file.filename):
        video_title = request.form['video-title']
        video_lang = request.form['video-lang']
        team_slug = request.form['team']
        filename = secure_filename(file.filename)
        sha = hashlib.sha256()
        sha.update(session['username'])
        sha.update(filename)
        s3_filename = str(sha.hexdigest()) + '.mp4'
        local_path = os.path.join(app.config['UPLOAD_DIR'], s3_filename)
        # save local
        file.save(local_path)
        # upload to s3
        key = upload_to_s3(local_path)
        # cleanup
        os.remove(local_path)
        s3_url = key.generate_url(expires_in=0, query_auth=False,
                force_http=True)
        # create video in amara
        data = {
            'title': video_title,
            'primary_audio_language_code': video_lang,
            'video_url': s3_url,
        }
        resp = _make_api_request('post', '/videos/', data=json.dumps(data))
        if resp.status_code != 200:
            flash('You do not have access to that team', 'danger')
            return redirect(url_for('index'))
        video_data = json.loads(resp.content)
        if not video_data.has_key('id'):
            flash('Video already exists...', 'danger')
            return redirect(url_for('index'))
        # add to team in amara
        data = {
            'team': team_slug,
        }
        resp = _make_api_request('PUT', '/videos/{}/'.format(video_data.get('id')),
                data=json.dumps(data))
    return redirect(url_for('index'))

@app.route('/logout/')
def logout():
    del session['username']
    del session['api_key']
    return redirect(url_for('index'))

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

