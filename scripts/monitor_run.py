#!/usr/bin/env python3
import os,sys,time,json,urllib.request

def read_token():
    try:
        with open('.env') as f:
            for l in f:
                if l.strip().startswith('Crypto_Survival_System_Token='):
                    return l.split('=',1)[1].strip().strip('"')
    except FileNotFoundError:
        return None

def api_get(url, headers):
    req=urllib.request.Request(url, headers=headers)
    with urllib.request.build_opener().open(req, timeout=30) as r:
        return json.load(r)

def main():
    if len(sys.argv) < 2:
        print('Usage: monitor_run.py <run_id>')
        return 2
    run_id=sys.argv[1]
    token=read_token()
    if not token:
        print('ERROR: token missing', file=sys.stderr); return 3
    repo='Katiehey/Crypto-Survival-System'
    headers={'Accept':'application/vnd.github+json','Authorization':f'Bearer {token}'}
    start=time.time()
    while time.time()-start < 3600:
        try:
            info=api_get(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}', headers)
        except Exception as e:
            print('Error fetching run', e, file=sys.stderr); time.sleep(5); continue
        print('status=', info.get('status'), 'conclusion=', info.get('conclusion'))
        if info.get('status') == 'completed':
            break
        time.sleep(10)

    try:
        jobs=api_get(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs', headers)
    except Exception as e:
        print('Error fetching jobs', e, file=sys.stderr); jobs={'jobs':[]}

    print('\nJobs total_count=', jobs.get('total_count'))
    for job in jobs.get('jobs',[]):
        print('\nJOB:', job.get('id'), job.get('name'), 'status=', job.get('status'), 'conclusion=', job.get('conclusion'))
        for step in job.get('steps',[]):
            print('  STEP:', step.get('number'), step.get('name'), 'status=', step.get('status'), 'conclusion=', step.get('conclusion'))
        print('  logs_url=', job.get('logs_url'))

    print('\nRun URL:', info.get('html_url'))
    return 0

if __name__ == '__main__':
    sys.exit(main())
