import streamlit as st
import boto3
import os
import tempfile
import uuid
import time
from dotenv import load_dotenv
from botocore.exceptions import ClientError

# Load environment variables
load_dotenv()

# Function to check if AWS credentials are set
def check_aws_credentials():
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION', 'S3_BUCKET_NAME', 'MEDIACONVERT_ROLE_ARN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Check AWS credentials before setting up clients
check_aws_credentials()

# Set up AWS clients
try:
    aws_region = os.getenv('AWS_REGION', 'us-west-2')  # Default to us-west-2 if not set
    polly_client = boto3.client('polly',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=aws_region
    )
    mediaconvert_client = boto3.client('mediaconvert',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=aws_region
    )
    s3_client = boto3.client('s3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=aws_region
    )
except ClientError as e:
    st.error(f"Failed to set up AWS clients: {str(e)}")
    st.stop()

def text_to_speech(text, language):
    try:
        voice_id = 'Joanna' if language == 'English' else 'Zhiyu'
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            LanguageCode='en-US' if language == 'English' else 'cmn-CN'
        )
        
        audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        audio_file.write(response['AudioStream'].read())
        audio_file.close()
        
        return audio_file.name
    except ClientError as e:
        st.error(f"Error in text-to-speech conversion: {str(e)}")
        raise

def merge_audio_video(video_path, audio_path):
    job_name = f"merge_job_{uuid.uuid4()}"
    output_key = f"step2_output/{job_name}.mp4"
    s3_output_key = f"s3://{os.getenv('S3_BUCKET_NAME')}/step2_output/{job_name}"
    
    # Get the account-specific endpoint for MediaConvert
    endpoints = mediaconvert_client.describe_endpoints()
    mediaconvert_endpoint = endpoints['Endpoints'][0]['Url']

    # Create a new MediaConvert client with the account-specific endpoint
    mediaconvert = boto3.client('mediaconvert', endpoint_url=mediaconvert_endpoint)

    # Define job settings
    job_settings = {
        "Inputs": [
            {
                "AudioSelectors": {
                    "Audio Selector 1": {
                        "DefaultSelection": "NOT_DEFAULT",
                        "ExternalAudioFileInput": f"s3://{os.getenv('S3_BUCKET_NAME')}/{audio_path}"
                    }
                },
                "VideoSelector": {},
                "TimecodeSource": "ZEROBASED",
                "FileInput": f"s3://{os.getenv('S3_BUCKET_NAME')}/{video_path}"
            }
        ],
        "OutputGroups": [
            {
                "Name": "File Group",
                "OutputGroupSettings": {
                    "Type": "FILE_GROUP_SETTINGS",
                    "FileGroupSettings": {
                        "Destination": s3_output_key
                    }
                },
                "Outputs": [
                    {
                        "VideoDescription": {
                            "CodecSettings": {
                                "Codec": "H_264",
                                "H264Settings": {
                                    "RateControlMode": "QVBR",
                                    "SceneChangeDetect": "TRANSITION_DETECTION",
                                    "MaxBitrate": 5000000,
                                    "QvbrSettings": {
                                        "QvbrQualityLevel": 7
                                    }
                                }
                            }
                        },
                        "AudioDescriptions": [
                            {
                                "AudioSourceName": "Audio Selector 1",
                                "CodecSettings": {
                                    "Codec": "AAC",
                                    "AacSettings": {
                                        "Bitrate": 96000,
                                        "CodingMode": "CODING_MODE_2_0",
                                        "SampleRate": 48000
                                    }
                                }
                            }
                        ],
                        "ContainerSettings": {
                            "Container": "MP4",
                            "Mp4Settings": {}
                        }
                    }
                ]
            }
        ]
    }

    # Create the transcoding job
    job = mediaconvert.create_job(
        Role=os.getenv('MEDIACONVERT_ROLE_ARN'),
        Settings=job_settings,
        UserMetadata={},
        StatusUpdateInterval='SECONDS_60',
        Priority=0
    )

    # Wait for the job to complete (you might want to implement a more sophisticated waiting mechanism)
    while True:
        job_result = mediaconvert.get_job(Id=job['Job']['Id'])
        if job_result['Job']['Status'] in ['COMPLETE', 'ERROR']:
            break
        time.sleep(30)

    if job_result['Job']['Status'] == 'ERROR':
        raise Exception("MediaConvert job failed")

    return output_key

def upload_to_s3(file_path, bucket_name, object_name):
    s3_client.upload_file(file_path, bucket_name, object_name)
    return object_name

def generate_presigned_url(bucket_name, object_name, region_name, expiration=3600):
    try:
        s3_client = boto3.client('s3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region_name
        )
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name,
                                                            'Key': object_name},
                                                    ExpiresIn=expiration)
    except ClientError as e:
        st.error(f"Error generating presigned URL: {str(e)}")
        return None
    return response

def process_video(product_details, video_file):
    # Generate audio from product details
    audio_file = text_to_speech(product_details)
    
    # Save uploaded video to a temporary file
    video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    with open(video_path, "wb") as f:
        f.write(video_file.getbuffer())
    
    # Upload video and audio to S3
    bucket_name = os.getenv('S3_BUCKET_NAME')
    video_s3_key = f"input/{uuid.uuid4()}.mp4"
    audio_s3_key = f"input/{uuid.uuid4()}.mp3"
    
    s3_client.upload_file(video_path, bucket_name, video_s3_key)
    s3_client.upload_file(audio_file, bucket_name, audio_s3_key)
    
    # Merge audio and video
    output_key = merge_audio_video(video_s3_key, audio_s3_key)
    
    # Generate S3 URL for the merged video
    s3_url = f"https://{bucket_name}.s3.amazonaws.com/{output_key}.mp4"
    
    # Clean up temporary files
    os.unlink(audio_file)
    os.unlink(video_path)
    
    return s3_url

def main():
    st.title("Product Video Creator")

    # Step 1: Text-to-Speech
    st.header("Step 1: Generate Audio from Text")
    language = st.selectbox("Select language", ["English", "Chinese"])
    product_details = st.text_area("Enter product details:")
    
    if st.button("Generate Audio"):
        if product_details:
            try:
                audio_file = text_to_speech(product_details, language)
                st.success("Audio generated successfully!")
                
                # Upload audio to S3 and provide download link
                bucket_name = os.getenv('S3_BUCKET_NAME')
                audio_s3_key = f"step1_output/{uuid.uuid4()}.mp3"
                s3_client.upload_file(audio_file, bucket_name, audio_s3_key)
                audio_url = generate_presigned_url(bucket_name, audio_s3_key, aws_region)
                
                if audio_url:
                    st.markdown(f"Download your audio file [here]({audio_url})")
                else:
                    st.error("Failed to generate download link for the audio file.")
                
                # Clean up temporary file
                os.unlink(audio_file)
            except Exception as e:
                st.error(f"An error occurred while generating audio: {str(e)}")
        else:
            st.error("Please enter product details.")

    # Step 2: Merge Audio and Video
    st.header("Step 2: Merge Audio and Video")
    audio_file = st.file_uploader("Upload MP3 file", type=["mp3"])
    video_file = st.file_uploader("Upload demo video", type=["mp4", "mov", "avi"])

    if st.button("Merge Audio and Video"):
        if audio_file and video_file:
            try:
                with st.spinner("Processing..."):
                    # Save uploaded files to temporary locations
                    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                    video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
                    
                    with open(audio_path, "wb") as f:
                        f.write(audio_file.getbuffer())
                    with open(video_path, "wb") as f:
                        f.write(video_file.getbuffer())
                    
                    # Upload files to S3
                    bucket_name = os.getenv('S3_BUCKET_NAME')
                    audio_s3_key = f"step2_input/{uuid.uuid4()}.mp3"
                    video_s3_key = f"step2_input/{uuid.uuid4()}.mp4"
                    
                    s3_client.upload_file(audio_path, bucket_name, audio_s3_key)
                    s3_client.upload_file(video_path, bucket_name, video_s3_key)
                    
                    # Merge audio and video
                    output_key = merge_audio_video(video_s3_key, audio_s3_key)
                    
                    # Generate S3 URL for the merged video
                    s3_url = generate_presigned_url(bucket_name, output_key, aws_region)
                    
                    st.success("Video processed successfully!")
                    if s3_url:
                        st.markdown(f"Download your merged video [here]({s3_url})")
                    else:
                        st.error("Failed to generate download link for the merged video.")
                    
                    # Clean up temporary files
                    os.unlink(audio_path)
                    os.unlink(video_path)
            except Exception as e:
                st.error(f"An error occurred while processing: {str(e)}")
        else:
            st.error("Please upload both an MP3 file and a video file.")

if __name__ == "__main__":
    main()
