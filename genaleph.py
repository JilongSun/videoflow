# pip install runwayml
from runwayml import RunwayML
from pathlib import Path
import os

os.environ["RUNWAYML_API_SECRET"] = (
    "key_9e3c7e57ac5fc63225c7ebcd07cdb56404ed9ade7f7c81c7c1cf38af38af73ac542ff68fcf05cb66cf9184506d00dd1dc1c2a52ffe3620fdbca84646e6853260"
)
# The env var RUNWAYML_API_SECRET is expected to contain your API key.
client = RunwayML()

# video = Path("D:\\WorkSpace\\videoflow\\outputs\\videos\\test.mp4")
# response1 = client.uploads.create_ephemeral(file=video)
# uri1 = response1.uri
# print(uri1)

# image = Path("D:\\WorkSpace\\videoflow\\outputs\\images\\black_cat.webp")
# response2 = client.uploads.create_ephemeral(file=image)

# uri2 = response2.uri
# print(uri2)

task = client.video_to_video.create(
    model="gen4_aleph",
    video_uri="runway://eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjUzNzkzODEzLCJ1cGxvYWRCdWNrZXQiOiJydW53YXktdXBsb2Fkcy1wcm9kIiwidXBsb2FkS2V5IjoiZXBoZW1lcmFsLXVwbG9hZHMvNTM3OTM4MTMvYmI1ODc3NjQtOGZmZS00NGFhLTkxNzQtNTU2ZjJkYjM4ZGVjL2ZpbGUubXA0IiwidHlwZSI6ImVwaGVtZXJhbCIsImNvbnRlbnRUeXBlIjoidmlkZW8vbXA0IiwiaWF0IjoxNzcwNTMxNzg0LCJleHAiOjE3NzA2MTgxODQsImlzcyI6Imh0dHBzOi8vYXBpLmRldi5ydW53YXltbC5jb20ifQ.uVPRGLtSltE906sOwxr3G_BDFb8wwGFqJRfmnvOi9-0",
    prompt_text="Replace the cat in the video with the cat in the picture",
    references=[
        {
            "type": "image",
            "uri": "runway://eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjUzNzkzODEzLCJ1cGxvYWRCdWNrZXQiOiJydW53YXktdXBsb2Fkcy1wcm9kIiwidXBsb2FkS2V5IjoiZXBoZW1lcmFsLXVwbG9hZHMvNTM3OTM4MTMvMWY0MzQzYzctYzg2Yy00ODdlLWEyNjItZjZhNGZlNzEyMjgzL2ZpbGUud2VicCIsInR5cGUiOiJlcGhlbWVyYWwiLCJjb250ZW50VHlwZSI6ImltYWdlL3dlYnAiLCJpYXQiOjE3NzA1MzE3MTQsImV4cCI6MTc3MDYxODExNCwiaXNzIjoiaHR0cHM6Ly9hcGkuZGV2LnJ1bndheW1sLmNvbSJ9.1CHuyusWp-VNtsVTpDOtl0XtPwj-F-mPk70OW5JYhfQ",
        },
        {
            "type": "image",
            "uri": "runway://eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjUzNzkzODEzLCJ1cGxvYWRCdWNrZXQiOiJydW53YXktdXBsb2Fkcy1wcm9kIiwidXBsb2FkS2V5IjoiZXBoZW1lcmFsLXVwbG9hZHMvNTM3OTM4MTMvMWY0MzQzYzctYzg2Yy00ODdlLWEyNjItZjZhNGZlNzEyMjgzL2ZpbGUud2VicCIsInR5cGUiOiJlcGhlbWVyYWwiLCJjb250ZW50VHlwZSI6ImltYWdlL3dlYnAiLCJpYXQiOjE3NzA1MzE3MTQsImV4cCI6MTc3MDYxODExNCwiaXNzIjoiaHR0cHM6Ly9hcGkuZGV2LnJ1bndheW1sLmNvbSJ9.1CHuyusWp-VNtsVTpDOtl0XtPwj-F-mPk70OW5JYhfQ",
        },
    ],
    extra_headers={"Content-Type": "application/json"},
).wait_for_task_output()

print(task)
