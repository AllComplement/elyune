import boto3
import os
import django
from django.conf import settings
from botocore.config import Config

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def init_minio():
    print("Initializing MinIO configuration...")
    
    # Use Config to disable checksums and force path style
    s3_config = Config(
        signature_version='s3v4',
        s3={'addressing_style': 'path'}
    )

    s3 = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=s3_config
    )

    # Register event handler to remove Content-MD5 header for PutBucketCors
    # using 'request-created' event which fires after the request is built
    def remove_checksum(request, **kwargs):
        if 'Content-MD5' in request.headers:
            del request.headers['Content-MD5']

    s3.meta.events.register('request-created.s3.PutBucketCors', remove_checksum)

    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # 1. Create Bucket
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f"Bucket '{bucket_name}' already exists.")
    except Exception:
        print(f"Creating bucket '{bucket_name}'...")
        try:
            s3.create_bucket(Bucket=bucket_name)
        except Exception as e:
            print(f"Error creating bucket: {e}")
            return

    # 2. Set CORS Policy
    cors_configuration = {
        'CORSRules': [{
            'AllowedHeaders': ['*'],
            'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
            'AllowedOrigins': ['*'],
            'ExposeHeaders': ['ETag']
        }]
    }
    
    print("Setting CORS configuration...")
    try:
        # Try to set CORS
        s3.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_configuration)
        print("CORS configuration set successfully.")
    except Exception as e:
        print(f"Warning: Failed to set CORS via boto3: {e}")
        # Note: If this fails with NotImplemented, it's often a MinIO/boto3 checksum mismatch.
        # Ensure your MinIO server allows CORS or use 'mc' CLI tool for complex policies.

if __name__ == '__main__':
    try:
        init_minio()
    except Exception as e:
        print(f"MinIO initialization skipped due to error: {e}")
