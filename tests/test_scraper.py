from asyncio import run
from datetime import date
from unittest import IsolatedAsyncioTestCase
from unittest.mock import call, MagicMock, patch

from aiohttp import ClientResponse

from blotter import BlotterEntry
from icbot.config import settings
from scraper import (
    BadResponse,
    fetch_dispatch_entries,
    fetch_dispatch_entries_for_date_range,
    Scraper
)
from .test_blotter import (
    MOCK_BLOTTER_PAGE_TEMPLATE,
    MOCK_BLOTTER_PAGE_TABLE_TEMPLATE,
    MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE,
    MOCK_BLOTTER_ENTRY_CONTENTS
)


@patch("scraper.ClientSession", spec=True)
class ScraperTestCase(IsolatedAsyncioTestCase):
    async def test_session_singleton(self, mock_session: MagicMock):
        """
        Tests that the ``Scraper.session()`` context manager behaves as a
        singleton (i.e., entering a context block nested within another context
        block yields the same session instance as the outer one, and the
        session is not closed upon termination of the inner context).
        """
        scraper = Scraper()
        async with scraper.session() as session:
            async with scraper.session() as session2:
                self.assertIs(session, session2)
            session.close.assert_not_awaited()
        session.close.assert_awaited_once()

    async def test_http_failure(self, mock_session: MagicMock):
        """
        Tests to confirm the proper error is raised when an HTTP request
        returns a status code greater than or equal to 400.
        """
        mock_response = MagicMock(spec=ClientResponse)
        mock_response.status = 400
        mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
        scraper = Scraper()
        test_url = "http://foo.bar"
        async with scraper.session() as session:
            with self.assertRaises(BadResponse) as context:
                await scraper.fetch_one(session, test_url)
        self.assertEqual(context.exception.url, test_url)
        self.assertEqual(context.exception.status, 400)
        self.assertEqual(context.exception.request_method, "get")
        mock_response.status = 503
        mock_session.return_value.post.return_value.__aenter__.return_value = mock_response
        async with scraper.session() as session:
            with self.assertRaises(BadResponse) as context:
                await scraper.fetch_one(session, test_url, "post")
        self.assertEqual(context.exception.url, test_url)
        self.assertEqual(context.exception.status, 503)
        self.assertEqual(context.exception.request_method, "post")

    async def test_http_success(self, mock_session: MagicMock):
        mock_response = MagicMock(spec=ClientResponse)
        mock_response.status = 200
        mock_response.text.return_value = "success"
        mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
        scraper = Scraper()
        test_url = "http://foo.bar"
        async with scraper.session() as session:
            self.assertEqual(await scraper.fetch_one(session, test_url), "success")

    async def test_http_many_success(self, mock_session: MagicMock):
        """
        Tests the issuing of multiple HTTP requests that are all successful.
        """
        mock_responses = []
        response_strings = ["first", "second", "third"]
        for response_string in response_strings:
            mock_response = MagicMock(spec=ClientResponse)
            mock_response.status = 200
            mock_response.text.return_value = response_string
            mock_responses.append(mock_response)
        mock_session.return_value.get.return_value.__aenter__.side_effect = mock_responses
        scraper = Scraper()
        async with scraper.session() as session:
            responses = await scraper.fetch_many(
                session,
                "http://foo.bar/1",
                "http://foo.bar/2",
                "http://foo.bar/3"
            )
        self.assertEqual(response_strings, responses)

    async def test_many_mixed(self, mock_session: MagicMock):
        """
        Tests the issuing of multiple HTTP requests, some of which are
        successful and some of which fail.
        """
        mock_responses = []
        response_strings = ["first", "second", "BAD", "third", "BAD"]
        for response_string in response_strings:
            mock_response = MagicMock(spec=ClientResponse)
            if response_string == "BAD":
                mock_response.status = 403
            else:
                mock_response.status = 200
                mock_response.text.return_value = response_string
            mock_responses.append(mock_response)
        mock_session.return_value.get.return_value.__aenter__.side_effect = mock_responses
        scraper = Scraper()
        mock_urls = (
            "http://foo.bar/1",
            "http://foo.bar/2",
            "http://foo.bar/bad/1",
            "http://foo.bar/3",
            "http://foo.bar/bad/2"
        )
        async with scraper.session() as session:
            responses = await scraper.fetch_many(session, *mock_urls)
        expected_responses = []
        for i, response_string in enumerate(response_strings):
            if response_string == "BAD":
                response_string = str(BadResponse(
                    "get", mock_urls[i], 403
                ))
            expected_responses.append(response_string)
        self.assertEqual([str(response) for response in responses], expected_responses)

    async def test_fetch_dispatch_entries(self, mock_session: MagicMock):
        mock_table = MOCK_BLOTTER_PAGE_TABLE_TEMPLATE.format(table_contents="""
<tr>
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
</tr>
<tr>
    <td><a href="/1234">1234</a></td>
    <td>123 Fake St</td>
    <td>QUUX</td>
    <td>IN PROGRESS</td>
    <td>Y</td>
</tr>
<tr>
    <td><a href="/4567">4567</a></td>
    <td>123 Fake St</td>
    <td>BAR FOO</td>
    <td>CIRCLING DRAIN</td>
    <td>Y</td>
</tr>
<tr>
    <td><a href="/7890">7890</a></td>
    <td>123 Fake St</td>
    <td>BAZ FOO</td>
    <td>STEADY AS SHE GOES</td>
    <td>N</td>
</tr>
""")
        mock_responses = [MagicMock(spec=ClientResponse) for i in range(4)]
        mock_responses[0].status = 200
        mock_responses[0].text.return_value = MOCK_BLOTTER_PAGE_TEMPLATE.format(
            table_contents=mock_table
        )
        mock_responses[1].status = 500
        mock_responses[2].status = 200
        mock_responses[2].text.return_value = MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE.format(
            entry_contents=MOCK_BLOTTER_ENTRY_CONTENTS
        )
        mock_responses[3].status = 200
        mock_responses[3].text.return_value = MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE.format(
            entry_contents=MOCK_BLOTTER_ENTRY_CONTENTS.replace("quiet", "loud")
        )
        mock_session.return_value.get.return_value.__aenter__.side_effect = mock_responses
        dt = date(2023, 2, 15)
        with settings.override({
            "BLOCKING_FILTERS": {
                "ACTIVITIES": ["UX"],
                "DISPOSITIONS": [],
                "DETAILS": ["QUIET"]
            },
            "POLICE_LOG_URL": "http://test/police/log"
        }):
            entry_set = await fetch_dispatch_entries(dt)
        self.assertEqual(entry_set.date, dt)
        self.assertEqual(len(entry_set.entries), 2)
        self.assertEqual(entry_set.entries[0].dispatch_number, 123)
        self.assertEqual(entry_set.entries[0].activity, "FOO")
        self.assertEqual(entry_set.entries[0].disposition, "COMPLETED")
        self.assertTrue(entry_set.entries[0].has_details)
        self.assertIsNone(entry_set.entries[0].details)
        self.assertIsInstance(entry_set.entries[0].error, BadResponse)
        self.assertEqual(entry_set.entries[0].error.request_method, "get")
        self.assertEqual(entry_set.entries[0].error.url, "http://test/123")
        self.assertEqual(entry_set.entries[0].error.status, 500)
        self.assertEqual(entry_set.entries[1], BlotterEntry(
            dispatch_number=4567,
            url="http://test/4567",
            activity="BAR FOO",
            disposition="CIRCLING DRAIN",
            has_details=True,
            details="All loud on the western front",
            error=None
        ))
        self.assertEqual(mock_session.return_value.get.call_args_list, [
            call("http://test/police/log", data={"activityDate": dt.strftime(settings.POLICE_LOG_DATETIME_FORMAT)}),
            call("http://test/123", data={}),
            call("http://test/789", data={}),
            call("http://test/4567", data={})
        ])
        mock_responses = [MagicMock(spec=ClientResponse) for i in range(2)]
        mock_responses[0].status = 200
        mock_responses[0].text.return_value = MOCK_BLOTTER_PAGE_TEMPLATE.format(
            table_contents=mock_table
        )
        mock_responses[1].status = 200
        mock_responses[1].text.return_value = MOCK_BLOTTER_ENTRY_PAGE_TEMPLATE.format(
            entry_contents=MOCK_BLOTTER_ENTRY_CONTENTS
        )
        mock_session.return_value.get.return_value.__aenter__.side_effect = mock_responses
        with settings.override({
            "BLOCKING_FILTERS": {
                "ACTIVITIES": [],
                "DISPOSITIONS": ["PROGRESS"],
                "DETAILS": []
            },
            "POLICE_LOG_URL": "http://test/police/log"
        }):
            entry_set = await fetch_dispatch_entries(dt, [123, 789])
        self.assertEqual(len(entry_set.entries), 1)
        self.assertEqual(entry_set.entries[0], BlotterEntry(
            dispatch_number=4567,
            url="http://test/4567",
            activity="BAR FOO",
            disposition="CIRCLING DRAIN",
            has_details=True,
            details="All quiet on the western front",
            error=None
        ))
