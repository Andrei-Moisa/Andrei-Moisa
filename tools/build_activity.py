#!/usr/bin/env python3
"""Build assets/activity.svg from public-activity.json (Python standard library only).

The SVG uses one square per day, shaded by the combined contribution count from
the personal and work accounts.
Counts are what each account reports on its public GitHub contribution calendar,
summed by date. They are contribution events, not unique commits.

Usage:
    python3 tools/build_activity.py                  # writes assets/activity.svg
    python3 tools/build_activity.py --readme README.md   # also refreshes the README block

The README block lives between <!-- activity:start --> and <!-- activity:end -->.
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PERSONAL = 'Andrei-Moisa'
WORK = 'Andrei-Moisa-999'

SURFACE = '#07070d'
EMPTY = '#121722'
INK = '#f4f8f9'
DIM = '#b3c4c8'
CYAN = '#00ffff'
PINK = '#ff69b4'
MONO = ("'Roboto Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,"
        "'DejaVu Sans Mono','Liberation Mono',monospace")

# Absolute bins for combined daily contributions.
BINS = [(1, 2), (3, 5), (6, 11), (12, None)]
BIN_LABELS = ['1–2', '3–5', '6–11', '12+']

W, H = 960, 330
X0, Y0 = 66, 156          # grid origin
PITCH, CELL = 16, 13


def mix(hex_a, hex_b, t):
    a = [int(hex_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(hex_b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#%02x%02x%02x' % tuple(round(x + (y - x) * t) for x, y in zip(b, a))


CYAN_RAMP = [mix(CYAN, SURFACE, t) for t in (.32, .52, .76, 1.0)]


def level(n):
    for i, (lo, hi) in enumerate(BINS):
        if n >= lo and (hi is None or n <= hi):
            return i
    return -1


def load(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    accts = data['accounts']
    for name in (PERSONAL, WORK):
        if name not in accts:
            sys.exit('missing account %s in %s' % (name, path))
        days = accts[name]['days']
        total = sum(d['contributionCount'] for d in days)
        if total != accts[name]['total']:
            sys.exit('%s: day counts sum to %d but total says %d' % (name, total, accts[name]['total']))
    pa, wo = accts[PERSONAL]['days'], accts[WORK]['days']
    if [d['date'] for d in pa] != [d['date'] for d in wo]:
        sys.exit('accounts do not cover identical dates; refusing to sum mismatched calendars')
    days = []
    for p, w in zip(pa, wo):
        days.append(dict(date=dt.date.fromisoformat(p['date']), p=p['contributionCount'], w=w['contributionCount']))
    fetched = dt.datetime.fromisoformat(data['fetched_at']).astimezone(dt.timezone.utc).date()
    return days, fetched


def summarize(days, fetched):
    tp = sum(d['p'] for d in days)
    tw = sum(d['w'] for d in days)
    active = sum(1 for d in days if d['p'] + d['w'] > 0)
    months = {}
    for d in days:
        key = (d['date'].year, d['date'].month)
        m = months.setdefault(key, dict(p=0, w=0, first=d['date'], last=d['date']))
        m['p'] += d['p']
        m['w'] += d['w']
        m['last'] = d['date']
    return dict(tp=tp, tw=tw, total=tp + tw, active=active, start=days[0]['date'], end=days[-1]['date'],
                fetched=fetched, months=months, ndays=len(days))


def num(v):
    return ('%.1f' % v).rstrip('0').rstrip('.')


def fmt(n):
    return '{:,}'.format(n)


def svg(days, s):
    out = []
    A = out.append
    start = s['start']
    # GitHub calendars put Sunday in row 0.
    lead = (start.weekday() + 1) % 7
    ncols = (lead + len(days) + 6) // 7
    title = 'Public contribution activity across two GitHub accounts, %s to %s' % (start, s['end'])
    desc = ('Calendar of daily public contribution counts. Each square combines the personal account '
            '@%s (%s contributions) and the work account @%s (%s contributions) for one day. Combined: %s '
            'contributions on %d of %d days. Counts are contribution events as each account reports them '
            '(commits, pull requests, issues, reviews; private work anonymized), summed by date. Not unique commits. '
            'Snapshot fetched %s.' % (PERSONAL, fmt(s['tp']), WORK, fmt(s['tw']), fmt(s['total']),
                                     s['active'], s['ndays'], s['fetched']))
    A('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-labelledby="t d">' % (W, H, W, H))
    A('<title id="t">%s</title>' % escape(title))
    A('<desc id="d">%s</desc>' % escape(desc))
    A('<style>text{font-family:%s}.hud{font-size:11px;letter-spacing:.2em}.lab{font-size:10px;letter-spacing:.16em;fill:%s}'
      '.big{font-size:34px;fill:%s}.mid{font-size:22px;fill:%s}</style>' % (MONO, DIM, INK, INK))
    A('<rect width="%d" height="%d" fill="%s"/>' % (W, H, SURFACE))
    A('<rect x=".5" y=".5" width="%d" height="%d" fill="none" stroke="#1c2430"/>' % (W - 1, H - 1))
    A('<path d="M10 34V10H34M%d %dV%dH%d" fill="none" stroke="%s" stroke-opacity=".62" stroke-width="1.2"/>' % (
        W - 10, H - 34, H - 10, W - 34, CYAN))

    # header
    A('<text class="hud" x="32" y="42" fill="%s">PUBLIC CONTRIBUTIONS · TWO ACCOUNTS</text>' % CYAN)
    A('<text class="hud" x="%d" y="42" fill="%s" text-anchor="end">%s → %s</text>' % (W - 32, DIM, start, s['end']))

    # stat row
    A('<text class="big" x="32" y="94">%s</text>' % fmt(s['total']))
    A('<text class="lab" x="33" y="114">CONTRIBUTIONS, COMBINED</text>')
    A('<text class="big" x="262" y="94">%d</text>' % s['active'])
    A('<text class="lab" x="263" y="114">DAYS WITH ACTIVITY</text>')

    for x, color, handle, role, n in ((470, PINK, PERSONAL, 'PERSONAL ACCOUNT', s['tp']),
                                     (700, CYAN, WORK, 'WORK ACCOUNT', s['tw'])):
        A('<rect x="%d" y="73" width="%d" height="%d" rx="2" fill="%s"/>' % (x, CELL, CELL, color))
        A('<text class="mid" x="%d" y="88">%s</text>' % (x + 22, fmt(n)))
        A('<text class="lab" x="%d" y="104" style="fill:%s">@%s</text>' % (x + 22, INK, handle.upper()))
        A('<text class="lab" x="%d" y="118">%s</text>' % (x + 22, role))

    # month labels (week column holding the 1st, skipping cramped ones)
    last_col = -9
    for i, d in enumerate(days):
        date = d['date']
        col = (lead + i) // 7
        starts_month = date.day == 1 or (i == 0 and date.day <= 21)
        if starts_month and col - last_col >= 3:
            A('<text class="lab" x="%d" y="%d">%s</text>' % (X0 + col * PITCH, Y0 - 10, date.strftime('%b').upper()))
            last_col = col
    for row, name in ((1, 'MON'), (3, 'WED'), (5, 'FRI')):
        A('<text class="lab" x="%d" y="%s" text-anchor="end">%s</text>' % (X0 - 10, Y0 + row * PITCH + 10, name))

    # One full square for each date, with both account counts in its tooltip.
    for i, d in enumerate(days):
        col, row = divmod(lead + i, 7)
        x, y = X0 + col * PITCH, Y0 + row * PITCH
        count = d['p'] + d['w']
        intensity = level(count)
        fill = CYAN_RAMP[intensity] if intensity >= 0 else EMPTY
        A('<rect class="day" x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s">'
          '<title>%s: %d contributions (%d personal, %d work)</title></rect>'
          % (x, y, CELL, CELL, fill, d['date'], count, d['p'], d['w']))

    # footer: provenance + shared scale
    fy = Y0 + 7 * PITCH + 30
    A('<text class="lab" x="32" y="%d">DAILY SUM OF EACH ACCOUNT&apos;S PUBLIC CONTRIBUTION COUNT · NOT UNIQUE COMMITS</text>' % fy)
    A('<text class="lab" x="32" y="%d">SNAPSHOT %s UTC · SEPARATE FROM GITHUB&apos;S NATIVE GRAPH</text>' % (fy + 18, s['fetched']))
    step = 34
    lx = W - 32 - 4 * step + (step - CELL)
    A('<text class="lab" x="%d" y="%s" text-anchor="end">PER DAY</text>' % (lx - 12, fy + 1))
    for i, lab in enumerate(BIN_LABELS):
        x = lx + i * step
        A('<rect x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s"/>' % (x, fy - 11, CELL, CELL, CYAN_RAMP[i]))
        A('<text class="lab" x="%s" y="%d" text-anchor="middle" style="letter-spacing:0">%s</text>' % (num(x + CELL / 2), fy + 18, lab))
    A('</svg>')
    return '\n'.join(out) + '\n'


def readme_block(s, asset):
    def month_label(key, m):
        name = dt.date(key[0], key[1], 1).strftime('%b %Y')
        first_of_month = m['first'].day == 1
        next_month = (m['last'] + dt.timedelta(days=1)).month != m['last'].month
        if not first_of_month or not next_month:
            name += ' (%d–%d)' % (m['first'].day, m['last'].day)
        return name

    alt = ('Combined public contribution calendar for @%s and @%s, %s to %s: %s contributions '
           '(%s personal, %s work) on %d days. One square per day. Contribution events, not unique commits.'
           % (PERSONAL, WORK, s['start'], s['end'], fmt(s['total']), fmt(s['tp']), fmt(s['tw']), s['active']))
    rows = ['| Month | @%s | @%s | Combined |' % (PERSONAL, WORK), '| :-- | --: | --: | --: |']
    for key in sorted(s['months']):
        m = s['months'][key]
        rows.append('| %s | %s | %s | %s |' % (month_label(key, m), fmt(m['p']), fmt(m['w']), fmt(m['p'] + m['w'])))
    rows.append('| **Total** | **%s** | **%s** | **%s** |' % (fmt(s['tp']), fmt(s['tw']), fmt(s['total'])))
    return '\n'.join([
        '<!-- activity:start (generated by tools/build_activity.py; do not edit by hand) -->',
        '<img src="%s" width="100%%" alt="%s">' % (asset, escape(alt, {'"': '&quot;'})),
        '',
        '<sub>Daily contribution counts from the public calendars of '
        '<a href="https://github.com/%s">@%s</a> (personal) and <a href="https://github.com/%s">@%s</a> (work), '
        'combined into one square per day. GitHub counts commits, pull requests, issues and reviews, and shows private work only as '
        'anonymized counts. Snapshot taken %s. GitHub&#39;s native graph further down this page covers this account only.</sub>'
        % (PERSONAL, PERSONAL, WORK, WORK, s['fetched']),
        '',
        '<details>',
        '<summary>Monthly totals</summary>',
        '',
        *rows,
        '',
        '</details>',
        '<!-- activity:end -->',
    ])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--data', default=str(ROOT / 'public-activity.json'))
    ap.add_argument('--out', default=str(ROOT / 'assets' / 'activity.svg'))
    ap.add_argument('--readme', help='README to refresh between activity markers')
    args = ap.parse_args()

    days, fetched = load(args.data)
    s = summarize(days, fetched)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg(days, s), encoding='utf-8')
    print('wrote %s (%d bytes): %s combined, %s personal, %s work, %d active days, %s to %s'
          % (out, out.stat().st_size, fmt(s['total']), fmt(s['tp']), fmt(s['tw']), s['active'], s['start'], s['end']))

    if args.readme:
        rp = Path(args.readme)
        text = rp.read_text(encoding='utf-8')
        a = text.find('<!-- activity:start')
        b = text.find('<!-- activity:end -->')
        if a < 0 or b < 0:
            sys.exit('activity markers not found in %s' % rp)
        rel = Path(args.out).resolve().relative_to(rp.resolve().parent).as_posix()
        text = text[:a] + readme_block(s, rel) + text[b + len('<!-- activity:end -->'):]
        rp.write_text(text, encoding='utf-8')
        print('refreshed activity block in %s' % rp)


if __name__ == '__main__':
    main()
