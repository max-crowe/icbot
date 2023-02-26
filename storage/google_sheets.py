import logging
from datetime import date, datetime
from functools import cached_property
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from icbot.config import settings
from scraper import DispatchEntrySet
from .base import BaseStorage

logger = logging.getLogger(__name__)


class UnexpectedContentsError(RuntimeError):
    pass


class GoogleSheetsStorage(BaseStorage):
    DATE_FORMAT = "%Y-%m-%d"
    HEADERS = [
        "Dispatch ID",
        "URL",
        "Activity",
        "Disposition",
        "Details"
    ]

    def __init__(
        self,
        *,
        spreadsheet_id: str,
        client_secrets_file: str,
        scopes: Optional[list[str]] = None,
        maximum_sheet_count: int = 20
    ):
        self.spreadsheet_id = spreadsheet_id
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes or ["https://www.googleapis.com/auth/drive.file"]
        self.maximum_sheet_count = maximum_sheet_count

    @classmethod
    def get_date_from_sheet_data(cls, sheet_data: dict[str, Any], default: Any = None) -> Any:
        try:
            return datetime.strptime(
                sheet_data["properties"]["title"],
                cls.DATE_FORMAT
            ).date()
        except ValueError:
            return default

    @classmethod
    def value_to_cell(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, (int, float)):
            return {"numberValue": value}
        return {"stringValue": str(value)}

    @classmethod
    def list_to_row(cls, list_: list[Any]) -> dict[str, Any]:
        return {"values": [{"userEnteredValue": cls.value_to_cell(v)} for v in list_]}

    @cached_property
    def service(self) -> Any:
        cached_token_file = settings.DATA_DIR / "token.json"
        creds = None
        if cached_token_file.exists():
            creds = Credentials.from_authorized_user_file(cached_token_file, self.scopes)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = None
        if creds is None:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.client_secrets_file, self.scopes
            )
            creds = flow.run_local_server(port=0)
            with cached_token_file.open("w") as f:
                f.write(creds.to_json())
        return build("sheets", "v4", credentials=creds)

    @cached_property
    def sorted_sheets(self) -> list[dict[str, Any]]:
        book_data = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
        return sorted(
            book_data["sheets"],
            key=lambda sheet_data: GoogleSheetsStorage.get_date_from_sheet_data(sheet_data, default=date(1900, 1, 1))
        )

    def get_latest_date_with_dispatch_ids(self) -> tuple[Optional[date], list[int]]:
        sheets = self.sorted_sheets
        sheet_date = self.get_date_from_sheet_data(sheets[-1])
        sheet_properties = sheets[-1]["properties"]
        dispatch_ids = []
        if sheet_date:
            sheet_contents = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id, range=sheet_properties["title"]
            ).execute()
            if sheet_contents["values"][0][0] != "Dispatch ID":
                raise UnexpectedContentsError(
                    f"Did not find expected contents in top left cell of sheet {sheet_properties['title']}"
                )
            for i, row in enumerate(sheet_contents["values"][1:]):
                if not row[0]:
                    break
                try:
                    dispatch_ids.append(int(row[0]))
                except ValueError:
                    logger.warning(
                        f"Unexpected value at row {i + 2}"
                    )
        return sheet_date, dispatch_ids

    def store_entries(self, entry_set: DispatchEntrySet):
        sheet_id = int(entry_set.date.strftime("%Y%m%d"))
        requests = []
        rows = []
        if sheet_id not in set(data["properties"]["sheetId"] for data in self.sorted_sheets):
            requests.append({
                "addSheet": {
                    "properties": {
                        "sheetId": sheet_id,
                        "title": entry_set.date.strftime(self.DATE_FORMAT)
                    }
                }
            })
            rows.append(self.list_to_row(self.HEADERS))
        for entry in entry_set.entries:
            rows.append(self.list_to_row([
                entry.dispatch_number,
                entry.url,
                entry.activity,
                entry.disposition,
                str(entry.error) if entry.error else entry.details
            ]))
        requests.append({
            "appendCells": {
                "sheetId": sheet_id,
                "rows": rows,
                "fields": "userEnteredValue"
            }
        })
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadsheet_id,
            body={"requests": requests}
        ).execute()

    def prune(self):
        sheets = self.sorted_sheets
        excess_sheets = len(sheets) - self.maximum_sheet_count
        if excess_sheets > 0:
            requests = []
            for i in range(excess_sheets):
                requests.append({
                    "deleteSheet": {
                        "sheetId": sheets[i]["properties"]["sheetId"]
                    }
                })
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests}
            ).execute()
