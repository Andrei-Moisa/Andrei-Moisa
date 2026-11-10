"""Regression tests for parsing GitHub's public contribution calendars."""
import datetime as dt
import unittest

from refresh_activity import PublicCalendar


def calendar_html(counts, *, displayed_total=None, missing_tooltips=()):
    if displayed_total is None:
        displayed_total = sum(counts.values())
    parts = [f'<h2>{displayed_total:,} contributions in the last year</h2>']
    for date, count in counts.items():
        cell = f'contribution-day-{date}'
        parts.append(f'<td id="{cell}" data-date="{date}"></td>')
        if date not in missing_tooltips:
            label = 'No contributions' if count == 0 else f'{count:,} contribution' + ('s' if count != 1 else '')
            parts.append(f'<tool-tip for="{cell}">{label} on {date}.</tool-tip>')
    return '\n'.join(parts)


def parse(counts, start, end, **kwargs):
    parser = PublicCalendar()
    parser.feed(calendar_html(counts, **kwargs))
    return parser.result(start, end)


class PublicCalendarTests(unittest.TestCase):
    def test_exact_range_preserves_counts(self):
        counts = {'2026-11-08': 0, '2026-11-09': 1, '2026-11-10': 1234}
        result = parse(counts, dt.date(2026, 11, 8), dt.date(2026, 11, 10))
        self.assertEqual(result, {
            'total': 1235,
            'days': [{'date': date, 'contributionCount': count} for date, count in counts.items()],
        })

    def test_rolling_year_accepts_sunday_padding_for_every_start_weekday(self):
        for offset in range(7):
            start = dt.date(2025, 11, 9) + dt.timedelta(days=offset)
            end = start.replace(year=2026)
            sunday = start - dt.timedelta(days=(start.weekday() + 1) % 7)
            counts = {}
            date = sunday
            while date <= end:
                counts[date.isoformat()] = 100 if date < start else 2
                date += dt.timedelta(days=1)
            with self.subTest(start=start):
                result = parse(counts, start, end)
                self.assertEqual(len(result['days']), 366)
                self.assertEqual(result['days'][0]['date'], start.isoformat())
                self.assertEqual(result['days'][-1]['date'], end.isoformat())
                self.assertEqual(result['total'], 732)

    def test_padding_on_both_sides_is_excluded_from_returned_total(self):
        counts = {'2024-02-28': 100, '2024-02-29': 2, '2024-03-01': 3, '2024-03-02': 200}
        result = parse(counts, dt.date(2024, 2, 29), dt.date(2024, 3, 1))
        self.assertEqual(result, {
            'total': 5,
            'days': [
                {'date': '2024-02-29', 'contributionCount': 2},
                {'date': '2024-03-01', 'contributionCount': 3},
            ],
        })

    def test_missing_requested_dates_are_rejected(self):
        counts = {'2026-11-08': 0, '2026-11-09': 1, '2026-11-10': 2}
        for missing in counts:
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'does not cover'):
                parse({date: count for date, count in counts.items() if date != missing},
                      dt.date(2026, 11, 8), dt.date(2026, 11, 10))

    def test_missing_tooltips_including_padding_are_rejected(self):
        counts = {'2026-11-08': 10, '2026-11-09': 1, '2026-11-10': 2}
        for missing in counts:
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'no contribution count'):
                parse(counts, dt.date(2026, 11, 9), dt.date(2026, 11, 10), missing_tooltips=(missing,))

    def test_displayed_total_must_match_full_calendar_before_trimming(self):
        counts = {'2026-11-08': 10, '2026-11-09': 1, '2026-11-10': 2}
        with self.assertRaisesRegex(ValueError, 'displayed total'):
            parse(counts, dt.date(2026, 11, 9), dt.date(2026, 11, 10), displayed_total=3)

    def test_empty_calendar_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'does not cover'):
            parse({}, dt.date(2026, 11, 9), dt.date(2026, 11, 10))


if __name__ == '__main__':
    unittest.main()
