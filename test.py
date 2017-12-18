#!/usr/bin/env python

from ConfigParser import ConfigParser
import os
import subprocess
import sys

ROOT_DIR = os.path.dirname(__file__)

def main():
    aws_config = ConfigParser()
    try:
        aws_config.read(os.path.expanduser('~/.aws/credentials'))
    except Exception:
        print('Error reading AWS credentials, try running aws configure')
        sys.exit(1)
    subprocess.check_call(['docker', 'build', '-t', 'amara-uploader',
                           ROOT_DIR])
    print('To test, connect to http://127.0.0.1:8080/')
    print
    subprocess.check_call([
        'docker', 'run', '--rm',
        '-p', '8080:5000',
        '-e', 'AWS_ACCESS_KEY_ID={}'.format(
            aws_config.get('default', 'aws_access_key_id')),
        '-e', 'AWS_SECRET_ACCESS_KEY={}'.format(
            aws_config.get('default', 'aws_secret_access_key')),
        '-e', 'S3_BUCKET=amara-uploader-test',
        'amara-uploader'
    ])

if __name__ == '__main__':
    main()
