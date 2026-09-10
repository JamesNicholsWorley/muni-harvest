"""Find and fetch the Public Document 43 volumes from the State Library.

The volumes live in the state archives' DSpace at archives.lib.state.ma.us. An
item's PDF is not at a guessable URL: it hangs off the item's ORIGINAL bundle,
so the item is asked for its bundles, the bundle for its bitstreams, and the
bitstream carries the download link.

Downloads are resumable and never repeated: a volume already on disk with a
plausible size is left alone. These are 15-30MB scans and there are 24 of them,
and re-fetching the set because a shell died is rude to a public archive.

    python tools/pd43_fetch.py --list
    python tools/pd43_fetch.py --years 2000,2002,2004 --dir pd43
"""
import argparse
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request

API = 'https://archives.lib.state.ma.us/server/api'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) CivicAtlasMA/1.0'
OCLC = 'ocm05938794'          # the PD43 series identifier


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as exc:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))
            del exc
    return None


def volumes():
    """-> {year: (uuid, title)} for every issue of the series."""
    found, page = {}, 0
    while page < 8:
        u = (API + '/discover/search/objects?'
             + urllib.parse.urlencode({'query': OCLC, 'size': '100',
                                       'page': str(page)}))
        d = get(u)
        objs = d['_embedded']['searchResult']['_embedded'].get('objects', [])
        if not objs:
            break
        for o in objs:
            it = o['_embedded']['indexableObject']
            name = it.get('name') or ''
            m = re.search(r'((?:19|20)\d{2})', name)
            if m and it.get('uuid'):
                found[m.group(1)] = (it['uuid'], name)
        total = d['_embedded']['searchResult']['page']['totalPages']
        page += 1
        if page >= total:
            break
    return found


def pdf_url(uuid):
    """The download link for the item's PDF, via its ORIGINAL bundle."""
    b = get('%s/core/items/%s/bundles' % (API, uuid))
    for bundle in b.get('_embedded', {}).get('bundles', []):
        if bundle.get('name') != 'ORIGINAL':
            continue
        bs = get(bundle['_links']['bitstreams']['href'])
        best = None
        for s in bs.get('_embedded', {}).get('bitstreams', []):
            name = (s.get('name') or '').lower()
            size = s.get('sizeBytes') or 0
            if name.endswith('.pdf') or 'pdf' in str(
                    s.get('metadata', {}).get('dc.format.mimetype', '')):
                if best is None or size > best[1]:
                    best = (s['_links']['content']['href'], size, s.get('name'))
        if best:
            return best
    return None


def fetch(url, path, size_hint=0):
    if os.path.exists(path):
        have = os.path.getsize(path)
        # A volume already here at a plausible size is not fetched again.
        if have > 500000 and (not size_hint or abs(have - size_hint) < 65536):
            return 'have', have
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    tmp = path + '.part'
    with urllib.request.urlopen(req, timeout=600) as r, \
            io.open(tmp, 'wb') as fh:
        n = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            fh.write(chunk)
            n += len(chunk)
    os.replace(tmp, path)
    return 'fetched', n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--years', default='')
    ap.add_argument('--dir', default='pd43')
    a = ap.parse_args()

    vols = volumes()
    if a.list:
        print('%d volumes in the series' % len(vols))
        for y in sorted(vols):
            print('  %s  %s' % (y, vols[y][1]))
        return

    want = [y.strip() for y in a.years.split(',') if y.strip()] or sorted(vols)
    os.makedirs(a.dir, exist_ok=True)
    for y in want:
        if y not in vols:
            print('  %s  not in the series' % y)
            continue
        uuid, title = vols[y]
        path = os.path.join(a.dir, 'pd43-%s.pdf' % y)
        try:
            got = pdf_url(uuid)
            if not got:
                print('  %s  no PDF bitstream' % y)
                continue
            url, size, name = got
            how, n = fetch(url, path, size)
            print('  %s  %-9s %7.1f MB  %s' % (y, how, n / 1e6, name or ''))
        except Exception as exc:
            print('  %s  FAILED %s' % (y, exc))


if __name__ == '__main__':
    main()
