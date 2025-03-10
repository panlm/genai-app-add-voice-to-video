# Product Video Creator

Product Video Creator is a Streamlit application that allows users to generate product videos by combining text-to-speech audio with demo videos. This tool is perfect for creating quick product demonstrations or explanations in either English or Chinese.

## Features

1. Text-to-Speech Generation
   - Convert product details to speech in English or Chinese
   - Download generated audio files

2. Audio and Video Merging
   - Upload custom audio files (MP3) and demo videos (MP4, MOV, AVI)
   - Merge audio and video files
   - Download the final product video

## Prerequisites

- Python 3.7+
- AWS account with access to Polly, S3, and MediaConvert services
- AWS CLI configured with appropriate credentials

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/product-video-creator.git
   cd product-video-creator
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Set up the required environment variables (see Environment Variables section below).

2. Run the Streamlit app:
   ```
   streamlit run main.py
   ```

3. Open your web browser and go to the URL provided by Streamlit (usually http://localhost:8501).

4. Follow the on-screen instructions to generate audio from text and merge it with your demo video.

## Environment Variables

Create a `.env` file in the project root directory with the following variables:

```
AWS_ACCESS_KEY_ID=your_access_key_id
AWS_SECRET_ACCESS_KEY=your_secret_access_key
AWS_REGION=your_preferred_region
S3_BUCKET_NAME=your_s3_bucket_name
MEDIACONVERT_ROLE_ARN=your_mediaconvert_role_arn
```

Make sure to replace the placeholder values with your actual AWS credentials and configuration.

Note: Never commit your `.env` file to version control. Add it to your `.gitignore` file to prevent accidental exposure of your credentials.

## Security Note

This application requires AWS credentials to function. Ensure that you keep your AWS credentials secure and do not share them publicly. It's recommended to use IAM roles with the principle of least privilege when deploying this application in a production environment.




# Refer

- https://aws.amazon.com/blogs/media/how-to-turn-articles-into-videos-using-aws-elemental-mediaconvert-and-amazon-polly/
