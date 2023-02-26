from unittest import TestCase

from bs4 import BeautifulSoup

from blotter import BlotterEntry, UnexpectedPageLayout
from icbot.config import settings


MOCK_BLOTTER_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
    <head><title>Blotter page</title></head>
    <body>
        <table>
            {table_contents}
        </table>
    </body>
</html>"""

MOCK_BLOTTER_PAGE_TABLE_TEMPLATE = """<thead>
    <tr>
        <th>Dispatch Number</th>
        <th>Address</th>
        <th>Activity</th>
        <th>Disposition</th>
        <th>Details</th>
    </tr>
</thead>
<tbody>
    {table_contents}
</tbody>"""

MOCK_BLOTTER_PAGE_TABLE = MOCK_BLOTTER_PAGE_TABLE_TEMPLATE.format(table_contents="""<tr>
        <td><a href="/123">123</a></td>
        <td>123 Fake St</td>
        <td>FOO</td>
        <td>COMPLETED</td>
        <td>Y</td>
    </tr>
    <tr>
        <td><a href="/456">456</a></td>
        <td>123 Fake St</td>
        <td>BAR</td>
        <td>IN PROGRESS</td>
        <td>N</td>
    </tr>
    <tr>
        <td><a href="/789">789</a></td>
        <td>123 Fake St</td>
        <td>BAZ FOO</td>
        <td>UNKNOWN AT THIS TIME</td>
        <td>Y</td>
    </tr>""")

MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE = """<!DOCTYPE html>
<html>
    <head><title>Blotter entry</title></head>
    <body>
        <div>
            <dl>
                {entry_contents}
            </dl>
        </div>
    </body>
</html>"""

MOCK_BLOTTER_ENTRY_CONTENTS = """<dt>Dispatch Number</dt>
<dd>123</dd>
<dt>Dispatch Time</dt>
<dd>1/1/1970 1:00:00 AM</dd>
<dt>Activity</dt>
<dd>FOO</dd>
<dt>Details</dt>
<dd>All quiet on the western front</dd>"""


class BlotterEntryTestCase(TestCase):
    def test_create_from_blotter_page(self):
        page = BeautifulSoup(
            MOCK_BLOTTER_PAGE_TEMPLATE.format(table_contents=MOCK_BLOTTER_PAGE_TABLE),
            "html.parser"
        )
        with settings.override({
            "POLICE_LOG_URL": "http://test/police/log",
            "BLOCKING_FILTERS": {
                "ACTIVITIES": ["^FOO"],
                "DISPOSITIONS": [],
                "DETAILS": []
            }
        }):
            entries = BlotterEntry.from_page(page)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0].dispatch_number, 123)
            self.assertEqual(entries[0].url, "http://test/123")
            self.assertEqual(entries[0].activity, "FOO")
            self.assertEqual(entries[0].disposition, "COMPLETED")
            self.assertTrue(entries[0].has_details)
            self.assertTrue(entries[0].exclude)
            self.assertEqual(entries[1].dispatch_number, 456)
            self.assertEqual(entries[1].url, "http://test/456")
            self.assertEqual(entries[1].activity, "BAR")
            self.assertEqual(entries[1].disposition, "IN PROGRESS")
            self.assertFalse(entries[1].has_details)
            self.assertTrue(entries[1].exclude)
            self.assertEqual(entries[2].dispatch_number, 789)
            self.assertEqual(entries[2].url, "http://test/789")
            self.assertEqual(entries[2].activity, "BAZ FOO")
            self.assertEqual(entries[2].disposition, "UNKNOWN AT THIS TIME")
            self.assertTrue(entries[2].has_details)
            self.assertFalse(entries[2].exclude)
        with settings.override({
            "POLICE_LOG_URL": "http://test/police/log",
            "BLOCKING_FILTERS": {
                "ACTIVITIES": [],
                "DISPOSITIONS": ["UNKNOWN"],
                "DETAILS": []
            }
        }):
            entries = BlotterEntry.from_page(page)
            self.assertFalse(entries[0].exclude)
            self.assertTrue(entries[1].exclude)
            self.assertTrue(entries[2].exclude)

    def test_create_from_blotter_page__alternate_layout(self):
        table = """<thead>
    <tr>
        <th>Address</th>
        <th>Dispatch Number</th>
        <th>Details</th>
        <th>Activity</th>
        <th>Disposition</th>
    </tr>
</thead>
<tbody>
    <tr>
        <td>123 Fake St</td>
        <td><a href="/123">123</a></td>
        <td>Y</td>
        <td>FOO</td>
        <td>COMPLETED</td>
    </tr>
    <tr>
        <td>123 Fake St</td>
        <td><a href="/456">456</a></td>
        <td>N</td>
        <td>BAR</td>
        <td>IN PROGRESS</td>
    </tr>
    <tr>
        <td>123 Fake St</td>
        <td><a href="/789">789</a></td>
        <td>Y</td>
        <td>BAZ FOO</td>
        <td>UNKNOWN AT THIS TIME</td>
    </tr>
</tbody>"""
        with settings.override({
            "POLICE_LOG_URL": "http://test/police/log"
        }):
            entries = BlotterEntry.from_page(BeautifulSoup(
                MOCK_BLOTTER_PAGE_TEMPLATE.format(table_contents=table),
                "html.parser"
            ))
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0].dispatch_number, 123)
            self.assertEqual(entries[0].url, "http://test/123")
            self.assertEqual(entries[0].activity, "FOO")
            self.assertEqual(entries[0].disposition, "COMPLETED")
            self.assertTrue(entries[0].has_details)
            self.assertEqual(entries[1].dispatch_number, 456)
            self.assertEqual(entries[1].url, "http://test/456")
            self.assertEqual(entries[1].activity, "BAR")
            self.assertEqual(entries[1].disposition, "IN PROGRESS")
            self.assertFalse(entries[1].has_details)
            self.assertEqual(entries[2].dispatch_number, 789)
            self.assertEqual(entries[2].url, "http://test/789")
            self.assertEqual(entries[2].activity, "BAZ FOO")
            self.assertEqual(entries[2].disposition, "UNKNOWN AT THIS TIME")
            self.assertTrue(entries[2].has_details)

    def test_create_from_blotter_page__missing_header(self):
        page = BeautifulSoup(
            MOCK_BLOTTER_PAGE_TEMPLATE.format(
                table_contents=MOCK_BLOTTER_PAGE_TABLE.replace("<th>Dispatch Number</th>", "")
            ),
            "html.parser"
        )
        with self.assertRaises(UnexpectedPageLayout) as context:
            BlotterEntry.from_page(page)
        self.assertIn("dispatch number", str(context.exception))

    def test_create_from_blotter_page__missing_url(self):
        page = BeautifulSoup(
            MOCK_BLOTTER_PAGE_TEMPLATE.format(
                table_contents=MOCK_BLOTTER_PAGE_TABLE.replace("<a href=\"/456\">456</a>", "")
            ),
            "html.parser"
        )
        with self.assertRaises(UnexpectedPageLayout) as context:
            BlotterEntry.from_page(page)
        self.assertEqual(str(context.exception), "Could not parse dispatch URL from row 2")

    def test_set_details_from_page(self):
        entry = BlotterEntry(
            dispatch_number=123,
            url="",
            activity="",
            disposition="",
            has_details=True
        )
        entry.set_details_from_page(BeautifulSoup(
            MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE.format(entry_contents=MOCK_BLOTTER_ENTRY_CONTENTS),
            "html.parser"
        ))
        self.assertEqual(entry.details, "All quiet on the western front")
        with settings.override({
            "BLOCKING_FILTERS": {
                "ACTIVITIES": [],
                "DISPOSITIONS": [],
                "DETAILS": ["QUIET"]
            }
        }):
            self.assertTrue(entry.exclude)

        entry = BlotterEntry(
            dispatch_number=123,
            url="",
            activity="",
            disposition="",
            has_details=True
        )
        entry.set_details_from_page(BeautifulSoup(
            MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE.format(
                entry_contents=MOCK_BLOTTER_ENTRY_CONTENTS.replace("All quiet on the western front", "\t\r\n")
            ),
            "html.parser"
        ))
        self.assertEqual(entry.details, "")

    def test_set_details_from_page__bad_layout(self):
        page = BeautifulSoup(MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE.format(
            entry_contents=MOCK_BLOTTER_ENTRY_CONTENTS.replace("<dt>Details</dt>", "<dt>asdf</dt>")
        ), "html.parser")
        entry = BlotterEntry(
            dispatch_number=123,
            url="",
            activity="",
            disposition="",
            has_details=True
        )
        with self.assertRaises(UnexpectedPageLayout):
            entry.set_details_from_page(page)
