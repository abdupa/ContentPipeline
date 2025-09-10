import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def get_sheets_service():
    """Builds and returns a Google Sheets service object using service account credentials."""
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        raise FileNotFoundError("Google Application Credentials JSON file not found.")
    
    creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)

def fetch_sheet_grid(spreadsheet_id: str, sheet_name: str):
    """
    Fetches the full grid data for a specific sheet, including hyperlinks.
    """
    service = get_sheets_service()
    req = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        ranges=[sheet_name],
        includeGridData=True,
        fields="sheets(data(rowData(values(formattedValue,hyperlink,textFormatRuns))))",
    )
    resp = req.execute()
    
    sheets = resp.get("sheets", [])
    if not sheets: return []
    
    data_blocks = sheets[0].get("data", [])
    if not data_blocks: return []
    
    return data_blocks[0].get("rowData", [])