import re
import sys
import json
import argparse
import threading
from requests import get
from requests.auth import HTTPBasicAuth

parser = argparse.ArgumentParser()
parser.add_argument('target', help='target')
parser.add_argument('-o', help='output file', dest='output')
parser.add_argument('-u', help='your username', dest='uname')
parser.add_argument('-t', help='number of threads', dest='threads', type=int)
parser.add_argument('--org', help='organization', dest='org', action='store_true')
parser.add_argument('--breach', help='check emails for breach', dest='breach', action='store_true')
args = parser.parse_args()

inp = args.target
breach = args.target
output = args.output
organization = args.org
uname = args.uname or ''
thread_count = args.threads or 2

machine = sys.platform # Detecting the os of current system
colors = not machine.lower().startswith(('os', 'win', 'darwin', 'ios'))
if not colors:
    end = green = bad = info = ''
    start = ' ['
    stop = ']'
else:
    end = '\033[1;m'
    green = '\033[1;32m'
    bad = '\033[1;31m[-]\033[1;m'
    info = '\033[1;33m[!]\033[1;m'
    start = ' \033[1;31m[\033[0m'
    stop = '\033[1;31m]\033[0m'

print ('''%s
	Z E N v1.0
%s''' % (green, end))

if inp.endswith('/'):
	inp = inp[:-1]

targetOrganization = targetRepo = targetUser = False

jsonOutput = {}

if inp.count('/') < 4:
    username = inp.split('/')[-1] if '/' in inp else inp
    if organization:
    	targetOrganization = True
    else:
    	targetUser = True
elif inp.count('/') == 4:
	targetRepo = inp.split('/')
	username = targetRepo[-2]
	repo = targetRepo[-1]
	targetRepo = True
else:
    print(f'{bad} Invalid input')
    quit()

def findContributorsFromRepo(username, repo):
    response = get(
        f'https://api.github.com/repos/{username}/{repo}/contributors?per_page=100',
        auth=HTTPBasicAuth(uname, ''),
    ).text

    return re.findall(r'https://github\.com/(.*?)"', response)

def findReposFromUsername(username):
    response = get(
        f'https://api.github.com/users/{username}/repos?per_page=100&sort=pushed',
        auth=HTTPBasicAuth(uname, ''),
    ).text

    repos = re.findall(r'"full_name":"%s/(.*?)",.*?"fork":(.*?),' % username, response)
    return [repo[0] for repo in repos if repo[1] == 'false']

def findEmailFromContributor(username, repo, contributor):
    response = get(
        f'https://github.com/{username}/{repo}/commits?author={contributor}',
        auth=HTTPBasicAuth(uname, ''),
    ).text

    latestCommit = re.search(r'href="/%s/%s/commit/(.*?)"' % (username, repo), response)
    latestCommit = latestCommit[1] if latestCommit else 'dummy'
    commitDetails = get(
        f'https://github.com/{username}/{repo}/commit/{latestCommit}.patch',
        auth=HTTPBasicAuth(uname, ''),
    ).text

    email = re.search(r'<(.*)>', commitDetails)
    if email:
        email = email[1]
        if breach:
            jsonOutput[contributor] = {'email': email}
            if (
                get(
                    f'https://haveibeenpwned.com/api/v2/breachedaccount/{email}'
                ).status_code
                == 200
            ):
                email = email + start + 'pwned' + stop
                jsonOutput[contributor]['pwned'] = True
            else:
                jsonOutput[contributor]['pwned'] = False
        else:
            jsonOutput[contributor] = email
    return email

def findEmailFromUsername(username):
    repos = findReposFromUsername(username)
    for repo in repos:
        if email := findEmailFromContributor(username, repo, username):
            print(f'{username} : {email}')
            break

def findEmailsFromRepo(username, repo):
    contributors = findContributorsFromRepo(username, repo)
    print ('%s Total contributors: %s%i%s' % (info, green, len(contributors), end))
    for contributor in contributors:
        if email := (findEmailFromContributor(username, repo, contributor)):
            print(f'{contributor} : {email}')

def findUsersFromOrganization(username):
    response = get(
        f'https://api.github.com/orgs/{username}/members?per_page=100',
        auth=HTTPBasicAuth(uname, ''),
    ).text

    return re.findall(r'"login":"(.*?)"', response)

def threader(function, arg):
    threads = []
    for i in arg:
        task = threading.Thread(target=function, args=(i,))
        threads.append(task)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    del threads[:]

def flash(function, arg):
    for begin in range(0, len(arg), thread_count):
        end = begin + thread_count
        splitted = arg[begin:end]
        threader(function, splitted)

if targetOrganization:
	usernames = findUsersFromOrganization(username)
	flash(findEmailFromUsername, usernames)
elif targetUser:
	findEmailFromUsername(username)
elif targetRepo:
	findEmailsFromRepo(username, repo)
if output:
    json_string = json.dumps(jsonOutput, indent=4)
    with open(output, 'w+') as savefile:
        savefile.write(json_string)
