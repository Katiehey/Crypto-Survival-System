#!/usr/bin/env python3
import os,sys,time,json,urllib.request,urllib.error

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

def api_post(url, data, headers):
    req=urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='POST')
    with urllib.request.build_opener().open(req, timeout=30) as r:
        # GitHub often returns 204 No Content for dispatch
        return r.getcode(), r.read()

def main():
    token=read_token()
    if not token:
        print('ERROR: Crypto_Survival_System_Token not found in .env', file=sys.stderr)
        return 2
    repo='Katiehey/Crypto-Survival-System'
    headers={'Accept':'application/vnd.github+json', 'Authorization':f'Bearer {token}', 'Content-Type':'application/json'}

    # Check workflow exists
    wf_url=f'https://api.github.com/repos/{repo}/actions/workflows/ci_smoke.yml'
    try:
        wf=api_get(wf_url, headers)
    except urllib.error.HTTPError as e:
        body=e.read().decode()
        print('HTTPError listing workflow:', e.code, body, file=sys.stderr)
        return 3
    except Exception as e:
        print('Error listing workflow:', e, file=sys.stderr); return 3

    if wf.get('message')=='Not Found':
        print('ci_smoke.yml not found in remote workflows. Push the file and retry.', file=sys.stderr)
        return 4

    print('Found workflow:', wf.get('path'), 'id=', wf.get('id'))
    # Dispatch
    dispatch_url=f'https://api.github.com/repos/{repo}/actions/workflows/ci_smoke.yml/dispatches'
    code,body=None,None
    try:
        code,body=api_post(dispatch_url, {'ref':'main'}, headers)
    except urllib.error.HTTPError as e:
        print('Dispatch HTTPError', e.code, e.read().decode(), file=sys.stderr); return 5
    except Exception as e:
        print('Dispatch error', e, file=sys.stderr); return 5

    print('Dispatched, response code', code)
    # Poll for run
    runs_url=f'https://api.github.com/repos/{repo}/actions/workflows/{wf.get("id")}/runs?per_page=5'
    run=None
    start=time.time()
    while time.time()-start < 300:
        try:
            runs=api_get(runs_url, headers).get('workflow_runs', [])
        except Exception:
            runs=[]
        if runs:
            run=runs[0]
            print('Selected run id', run.get('id'), 'status', run.get('status'))
            break
        time.sleep(3)
    if not run:
        print('No run appeared within timeout', file=sys.stderr); return 6

    run_id=run.get('id')
    print('Monitoring run', run_id, 'url=', run.get('html_url'))
    start=time.time()
    info=None
    while time.time()-start < 1800:
        try:
            info=api_get(f'https://api.github.com/repos/{repo}/actions/runs/{run_id}', headers)
        except Exception as e:
            print('Error fetching run info', e, file=sys.stderr); time.sleep(5); continue
        print('status=', info.get('status'), 'conclusion=', info.get('conclusion'))
        if info.get('status')=='completed':
            break
        time.sleep(8)

    # Fetch jobs
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

if __name__=='__main__':
    sys.exit(main())
