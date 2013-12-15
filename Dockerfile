from ubuntu:12.04
maintainer evan hazlett <ejhazlett@gmail.com>
run apt-get update
run apt-get install -y python-dev python-setuptools libxml2-dev libxslt-dev
run easy_install pip
run pip install uwsgi
add . /app
run pip install -r /app/requirements.txt
expose 5000
cmd ["/usr/local/bin/uwsgi", "--ini", "/app/.docker/app.ini"]
