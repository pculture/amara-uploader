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
import time
from slugify import slugify

UPLOAD_DIR = os.getenv('UPLOAD_DIR', tempfile.gettempdir())
ALLOWED_EXTENSIONS = set(['mp4'])

app = Flask(__name__)
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['S3_BUCKET'] = os.getenv('S3_BUCKET')
app.config['S3_PATH'] = os.getenv('S3_PATH', '')
app.secret_key = os.getenv('SECRET_KEY',
        '\xd8\x9c\x1a\xe7|\xce\x15\xe4\xa2\xfd\x97B\x8dK\xee|\x08!\x9e\xef[\xc9u4')
app.config['amara_api_endpoint'] = os.getenv('AMARA_API_ENDPOINT',
        'https://amara.org')
app.config['amara_api_url_base'] = '/api'
app.config['api_url'] = app.config['amara_api_endpoint'] + \
        app.config['amara_api_url_base']

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

def _make_api_request(method='GET', path='/', data=None):
    url = app.config['api_url'] + path
    print url
    headers = {
        'Content-Type': 'application/json',
        'X-Api-Username': session.get('username'),
        'X-Api-Key': session.get('api_key'),
    }
    methods = {
        'get': requests.get,
        'put': requests.put,
        'post': requests.post,
    }
    return methods[method.lower()](url, data=data, headers=headers)

def upload_to_s3(filename):
    bucket = app.config['S3_BUCKET']
    s3_conn = S3Connection()
    bucket = s3_conn.get_bucket(bucket)
    print "Connected to S3 bucket"
    k = Key(bucket)
    k.key = os.path.join(app.config['S3_PATH'], os.path.basename(filename))
    print "Created S3 key"
    k.set_contents_from_filename(filename)
    print "Uploaded the video to S3"
    k.make_public()
    print "Made the video public"
    return k

@app.route('/')
def index():
    if 'username' in session and 'api_key' in session:
        resp = _make_api_request('get', '/languages/')
        language_dict = (json.loads(resp.content)).get('languages')
        languages = sorted(language_dict.items(), key = lambda x: x[1])
        resp = _make_api_request('get', '/teams/?limit=100&offset=0')
        teams = (json.loads(resp.content)).get('objects')
        count = ((json.loads(resp.content)).get('meta')).get('total_count')
        i = 1
        while (100*i) < count:
            offset = i * 100
            #print str(i)
            resp2 = _make_api_request('get', '/teams/?limit=100&offset='+str(offset))
            moreteams = (json.loads(resp2.content)).get('objects')
            #print moreteams
            teams += moreteams
            #print teams
            #print len(teams)
            i += 1
        ctx = {
            'username': session['username'],
            'api_key': session['api_key'],
            'teams': teams,
            'languages': languages,
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
    files = request.files.getlist("file")
    #file = request.files['file']
    video_lang = request.form['video-lang']
    team_slug = request.form['team']
    project_slug = request.form['project']
    if project_slug != '':
        resp = _make_api_request('get', '/teams/'+team_slug+'/projects/'+project_slug+'/')
        if resp.status_code != 200:
            data = {
                'name':project_slug,
                'slug': project_slug
            }
            resp = _make_api_request('post', '/teams/'+team_slug+'/projects/',data=json.dumps(data))
            print "Created project: "+ project_slug
            print resp.status_code
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            video_title = filename #request.form['video-title']
            sha = hashlib.sha256()
            sha.update(session['username'])
            sha.update(video_title)
            sha.update(video_lang)
            sha.update(filename)
            #s3_filename = str(sha.hexdigest()) + '.mp4'
            s3_filename = time.strftime("%Y_%m_%d_%H_%M_%S_") + slugify(video_title) + '.mp4'
            print "S3 filename:"
            print s3_filename
            local_path = os.path.join(app.config['UPLOAD_DIR'], s3_filename)
            print "Local path:"
            print local_path
            # save local
            file.save(local_path)
            print "Saved file to local path"
            # upload to s3
            key = upload_to_s3(local_path)
            # cleanup
            os.remove(local_path)
            print "Removed file from local path"
            s3_url = key.generate_url(expires_in=0, query_auth=False)
            print s3_url
            # create video in amara
            data = {
                'title': video_title,
                'primary_audio_language_code': video_lang,
                'video_url': s3_url,
            }
            resp = _make_api_request('post', '/videos/', data=json.dumps(data))
            print "Submitted the video"
            print resp.status_code
            """
            if resp.status_code != 201:
                flash('You do not have access to that team', 'danger')
                return redirect(url_for('index'))
            """
            video_data = json.loads(resp.content)
            print video_data
            if not video_data.has_key('id'):
                flash('Video already exists...', 'danger')
                return redirect(url_for('index'))
            # add to team in amara
            if project_slug != '':
                data = {
                    'team': team_slug,
                    'project': project_slug,
                }
            else:
                data = {
                    'team': team_slug
                }
            resp = _make_api_request('PUT', '/videos/{}/'.format(video_data.get('id')),
                    data=json.dumps(data))
	    print "Moved video to the selected team and project"
    return redirect(url_for('index'))

@app.route('/logout/')
def logout():
    del session['username']
    del session['api_key']
    return redirect(url_for('index'))

if __name__=='__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

