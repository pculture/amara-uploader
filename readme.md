# Amara Uploader
Simple app to store .mp4 videos and add to an Amara team

# Usage
You must set the following environment variables to run:

*`AWS_ACCESS_KEY_ID`: AWS Access ID
*`AWS_SECRET_ACCESS_KEY`: AWS Key
*`S3_BUCKET`: S3 Bucket
*`S3_PATH`: (optional) Path prefix (i.e. directory inside of a bucket)
*`AMARA_API_ENDPOINT`: (optional) Amara Endpoint (default: https://amara.org)
*`SECRET_KEY`: (optional) Secret Key for session storage, etc.

You will need to login with your Amara username / API key.  Once logged in
you can upload a local .mp4 to one of your teams.
