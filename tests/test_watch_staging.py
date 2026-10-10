import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

creds = Credentials.from_service_account_file("google_credentials.json", scopes=["https://www.googleapis.com/auth/drive"])
drive_service = build("drive", "v3", credentials=creds)

folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "YOUR_FOLDER_ID_HERE")
folder = drive_service.files().get(fileId=folder_id, fields="id, name, capabilities").execute()

print(f"Folder Name: {folder.get('name')}")
print(f"Can Add Children: {folder.get('capabilities', {}).get('canAddChildren')}")