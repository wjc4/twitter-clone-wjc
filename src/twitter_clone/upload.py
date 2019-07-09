import boto3, os, uuid

# use this for aws
# s3 = boto3.client("s3")
# use this for local minio
s3 = boto3.client("s3", endpoint_url="http://localhost:9000")
s3_bucket = os.environ.get("S3_BUCKET")
# s3_url = f"http://{s3_bucket}.s3.amazonaws.com/"

from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = set(["png", "jpg", "jpeg", "gif"])

from botocore.exceptions import ClientError


def create_presigned_url(object_name, bucket_name=s3_bucket, expiration=3600):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    try:
        response = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_name},
            ExpiresIn=expiration,
        )
    except ClientError as e:
        return None

    # The response contains the presigned URL
    return response


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_to_s3(file, acl="public-read"):

    """
    Docs: http://boto3.readthedocs.io/en/latest/guide/s3.html
    """

    source_filename = file.filename
    # check if theres a need to secure filename
    file.filename = secure_filename(file.filename)
    source_extension = os.path.splitext(source_filename)[1]
    # generate a random file name to prevent collision
    destination_filename = uuid.uuid4().hex + source_extension
    try:

        s3.upload_fileobj(
            file,
            s3_bucket,
            destination_filename,
            ExtraArgs={"ACL": acl, "ContentType": file.content_type},
        )

    except Exception as e:
        print("Something Happened: ", e)
        return e

    return destination_filename
    # return "%s/%s/%s" % (s3.meta.endpoint_url, s3_bucket, destination_filename)
    # return "{}{}".format(s3_url, destination_filename)


def delete_file_from_s3(key):
    # Response Syntax
    # {
    #     'DeleteMarker': True|False,
    #     'VersionId': 'string',
    #     'RequestCharged': 'requester'
    # }
    return s3.delete_object(Bucket=s3_bucket, Key=key)
