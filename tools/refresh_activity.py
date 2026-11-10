#!/usr/bin/env python3
"""Fetch both public contribution calendars without signing in or using a token."""
import argparse
import concurrent.futures
import datetime as dt
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import tempfile
from urllib.request import Request, urlopen

from build_activity import PERSONAL, WORK, ROOT


class PublicCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.tooltip = None
        self.tooltip_text = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'td' and attrs.get('data-date'):
            self.cells[attrs['id']] = attrs['data-date']
        if tag == 'tool-tip':
            self.tooltip = attrs.get('for')
            self.tooltip_text = []

    def handle_data(self, text):
        self.text.append(text)
        if self.tooltip:
            self.tooltip_text.append(text)

    def handle_endtag(self, tag):
        if tag == 'tool-tip' and self.tooltip:
            text = ''.join(self.tooltip_text).strip()
            match = re.match(r'^(No|[\d,]+) contributions? on\b', text)
            if match:
                self.counts[self.tooltip] = 0 if match[1] == 'No' else int(match[1].replace(',', ''))
            self.tooltip = None

    def result(self, start, end):
        expected = {start + dt.timedelta(days=i) for i in range((end - start).days + 1)}
        available = {dt.date.fromisoformat(date) for date in self.cells.values()}
        if not expected <= available:
            raise ValueError('The public calendar does not cover the requested dates.')
        if not self.cells.keys() <= self.counts.keys():
            raise ValueError('Some public calendar cells have no contribution count.')
        days = sorted(
            ({'date': date, 'contributionCount': self.counts[cell]} for cell, date in self.cells.items()),
            key=lambda day: day['date'],
        )
        total = sum(day['contributionCount'] for day in days)
        text = ' '.join(' '.join(self.text).split())
        heading = re.search(r'\b([\d,]+) contributions? in\b', text)
        if not heading or int(heading[1].replace(',', '')) != total:
            raise ValueError('Public calendar day counts do not match its displayed total.')
        # GitHub pads its calendar to a week boundary. Validate the full displayed
        # total before trimming those extra days from our rolling-year snapshot.
        days = [day for day in days if start.isoformat() <= day['date'] <= end.isoformat()]
        total = sum(day['contributionCount'] for day in days)
        return {'total': total, 'days': days}


def fetch(login, start, end):
    url = f'https://github.com/users/{login}/contributions'
    request = Request(url, headers={'User-Agent': 'Andrei-Moisa-profile-activity', 'Accept-Language': 'en'})
    with urlopen(request, timeout=20) as response:
        html = response.read().decode('utf-8')
    parser = PublicCalendar()
    parser.feed(html)
    return login, parser.result(start, end)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, default=ROOT / 'public-activity.json')
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    end = now.date()
    try:
        start = end.replace(year=end.year - 1)
    except ValueError:
        start = end.replace(year=end.year - 1, day=28)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        accounts = dict(pool.map(lambda login: fetch(login, start, end), (PERSONAL, WORK)))
    data = {
        'fetched_at': now.isoformat(),
        'source': 'Unauthenticated public GitHub contribution calendars. Dates and counts only.',
        'accounts': accounts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=args.out.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(data, file, indent=2)
            file.write('\n')
        temporary.replace(args.out)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    for login, calendar in accounts.items():
        print(f"{login}: {calendar['total']:,} public contribution events, {start} to {end}")


if __name__ == '__main__':
    main()
