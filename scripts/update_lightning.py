#!/usr/bin/env python3
"""Convert EUMETSAT MTG LI-2-LFL products to a small shared South Africa JSON feed.

Uses EUMETSAT's *official* EUMDAC client, with credentials supplied exclusively
through environment variables. No credentials or NetCDF data go in the app.
Production feed is marked complete only after successful, contiguous ingestion.
"""
from __future__ import annotations
import datetime as dt
import json
import logging
import math
import os
import pathlib
import shutil
import tempfile
import sys
from typing import Iterable

UTC=dt.timezone.utc
COLLECTION='EO:EUM:DAT:0691'  # LI lightning flashes, MTG 0 degree
WINDOW_MINUTES=25
MAX_OBSERVATION_AGE_MINUTES=18
AREA=(-37.0,14.0,-20.0,38.0)  # South Africa and 100km+ buffer (S W N E)
DEST=pathlib.Path(os.environ.get('CG_FEED_OUTPUT','public/latest.json'))
MAX_RECORDS=25000

def utcnow():return dt.datetime.now(UTC)
def utcstamp(t):return t.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00','Z')
def aware(t):
    if t is None or t is False: return None
    if isinstance(t,str):t=dt.datetime.fromisoformat(t.replace('Z','+00:00'))
    return t.replace(tzinfo=UTC) if t.tzinfo is None else t.astimezone(UTC)
def unavailable(now,why):
    return dict(source='EUMETSAT-MTG-LI-LFL',region='southern-africa',complete=False,
      generated_at=utcstamp(now),observation_end=None,flashes=[],status='unavailable',reason=why)

def body_netcdf_members(entries):
    """Return only real LI flash-array files, excluding trailers/metadata.

    Verified against an actual EUMETSAT LI-2-LFL ZIP (2026-10-14):
    CHK-BODY contains latitude/longitude/flash_time; CHK-TRAIL does not.
    """
    return [name for entry in entries
            if (name:=str(entry)) and '--CHK-BODY--' in name.upper()
            and name.lower().endswith(('.nc','.nc4','.nc4e'))]

def process_netcdf(path, observation_end):
    from netCDF4 import Dataset, num2date
    with Dataset(path) as ds:
        fields=ds.variables
        if not {'latitude','longitude','flash_time'}<=set(fields):
            raise ValueError(f'{path.name}: expected LI-2-LFL latitude/longitude/flash_time arrays missing')
        lats=fields['latitude'][:]
        lons=fields['longitude'][:]
        times=fields['flash_time'][:]
        # netCDF4's default auto-mask-and-scale applies CF scale_factor/add_offset.
        if not (len(lats)==len(lons)==len(times)):
            raise ValueError('Latitude/longitude/time dimensions differ')
        vals=num2date(times,units=getattr(fields['flash_time'],'units','seconds since 2000-01-01 00:00:00.0'),
                      calendar=getattr(fields['flash_time'],'calendar','standard'),
                      only_use_cftime_datetimes=False,only_use_python_datetimes=True)
        output=[]
        for la,lo,tm in zip(lats,lons,vals):
            try:
                la=float(la);lo=float(lo)
                if not(math.isfinite(la) and math.isfinite(lo)) or not(AREA[0]<=la<=AREA[2] and AREA[1]<=lo<=AREA[3]):continue
                # cftime or datetime both support isoformat; convert UTC uniformly.
                tm=aware(tm if isinstance(tm,dt.datetime) else str(tm))
                if tm is None or tm>observation_end+dt.timedelta(minutes=2) or tm<observation_end-dt.timedelta(minutes=WINDOW_MINUTES+8):continue
                output.append(dict(lat=round(la,5),lon=round(lo,5),time=utcstamp(tm)))
            except (ValueError,TypeError,OverflowError): continue
        return output

def grouped_coverage(intervals, now):
    """Require 20 continuous minutes ending recently (no silent missing files)."""
    intervals=sorted((aware(a),aware(b)) for a,b in intervals if a and b)
    if not intervals:return None
    merged=[]
    for st,en in intervals:
        if not merged or st>merged[-1][1]+dt.timedelta(seconds=90):merged.append([st,en])
        else:merged[-1][1]=max(merged[-1][1],en)
    recent=[x for x in merged if x[1]>=now-dt.timedelta(minutes=MAX_OBSERVATION_AGE_MINUTES)]
    if not recent:return None
    candidate=max(recent,key=lambda x:x[1]);start,end=candidate
    if (end-start)<dt.timedelta(minutes=20):return None
    if end>now+dt.timedelta(minutes=2):return None
    return end

def pull():
    import eumdac
    now=utcnow()
    key=os.environ.get('EUMETSAT_CONSUMER_KEY','').strip()
    secret=os.environ.get('EUMETSAT_CONSUMER_SECRET','').strip()
    if not key or not secret:raise RuntimeError('EUMETSAT API credentials missing')
    datastore=eumdac.DataStore(eumdac.AccessToken((key,secret)))
    collection=datastore.get_collection(COLLECTION)
    entries=list(collection.search(dtstart=now-dt.timedelta(minutes=65),dtend=now))
    if not entries:raise RuntimeError('No recent LI-2-LFL satellite files found')
    # Data Store products can be 10-minute archives, so allow up to eight.
    entries.sort(key=lambda p:aware(p.sensing_end) or dt.datetime.min.replace(tzinfo=UTC),reverse=True)
    entries=entries[:8]
    flashes=[];coverage=[]
    with tempfile.TemporaryDirectory(prefix='mtg_li_') as tmp:
        for prod in entries:
            start=aware(prod.sensing_start);end=aware(prod.sensing_end)
            if not start or not end or end<start:continue
            # An L2 product contains several NetCDF members: CHK-BODY holds
            # flash arrays; CHK-TRAIL holds only statistics/metadata.  Never
            # parse the trailer as an observation file (it has no lat/lon/time).
            files=body_netcdf_members(prod.entries)
            if not files:
                raise RuntimeError(f'Product {prod} had no LI-2-LFL CHK-BODY NetCDF member')
            print(f'Found {len(files)} flash-data BODY chunk(s) in {prod}')
            one_product=[]
            for i,member in enumerate(files):
                path=pathlib.Path(tmp)/f'{len(coverage)}_{i}.nc'
                with prod.open(entry=member) as response, path.open('wb') as sink:
                    shutil.copyfileobj(response,sink)
                one_product.extend(process_netcdf(path,end))
                path.unlink(missing_ok=True)
            flashes.extend(one_product)
            coverage.append((start,end))
            if len(flashes)>MAX_RECORDS:raise RuntimeError('Flash array unexpectedly large')
    observed=grouped_coverage(coverage,now)
    if observed is None:raise RuntimeError('Satellite products too old or gaps in recent observation coverage')
    lower=observed-dt.timedelta(minutes=WINDOW_MINUTES)
    # Ensure duplicates across neighbouring archived products do not inflate count.
    uniq={}
    for row in flashes:
        t=aware(row['time'])
        if t<lower or t>observed+dt.timedelta(minutes=2):continue
        uniq[(row['lat'],row['lon'],row['time'])]=row
    return dict(source='EUMETSAT-MTG-LI-LFL',region='southern-africa',complete=True,
                generated_at=utcstamp(now),observation_end=utcstamp(observed),
                observation_window_minutes=WINDOW_MINUTES,flashes=list(uniq.values()),status='ok')

def main():
    now=utcnow()
    try:
        data=pull()
        print(f'EUMETSAT feed: {len(data["flashes"])} flashes, observed {data["observation_end"]}')
    except Exception as exc:
        logging.exception('EUMETSAT feed unavailable')
        data=unavailable(now,type(exc).__name__)
    DEST.parent.mkdir(parents=True,exist_ok=True)
    tmp=DEST.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    tmp.replace(DEST)
    print(f'Wrote {DEST} (complete={data["complete"]})')
    return 0 if data['complete'] else 2

if __name__=='__main__':sys.exit(main())
