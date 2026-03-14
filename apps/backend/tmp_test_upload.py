import requests
import os

url = "http://localhost:8000/api/v1/admin/cohorts/dab2e943-c02d-427f-bd58-4c672d0b8d15/bulk-upload-resumes"
files = [
    ('files', ('test_resume.pdf', open('test.pdf', 'rb'), 'application/pdf'))
]

try:
    print(f"Uploading to {url}...")
    response = requests.post(url, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")
