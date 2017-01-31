#!/usr/bin/env python

###############################################################################
# 
# This program is free software: you can redistribute it and/or modify 
# it under the terms of the GNU General Public License as published by 
# the Free Software Foundation, either version 3 of the License, or 
# (at your option) any later version. 
#
# This program is distributed in the hope that it will be useful, 
# but WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the 
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License 
# along with this program. If not, see <http://www.gnu.org/licenses/>. 
# 
###############################################################################

# Author: Adam Skarshewski, Australian Centre for Ecogenomics, 2017

import httplib, urllib
import os, sys, subprocess
import getpass, argparse

from HTMLParser import HTMLParser

class LinkParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != 'a':
            return
        for (attr, value) in attrs:
            if attr != 'href':
                continue
            self.links.append(value)

    def get_links(self):
       return self.links

def filter_links(conn, headers, this_dir, begins_with=None):
    conn.request("GET", this_dir, "", headers)
    response = conn.getresponse()

    parser = LinkParser()
    parser.feed(response.read())

    links = []
    for link in parser.get_links():
       if begins_with and not link.upper().startswith(begins_with):
           continue
       links.append(link)

    return links

def mkdir_if_not_exists(path):
    if not os.path.exists(path):
        os.mkdir(path)

def main(args):

    username = args.u
    try:
        pw = os.environ["ACEPASSWORD"]
    except KeyError:
        pw = getpass.getpass()

    params = urllib.urlencode({'username': username , 'password': pw})
    headers = {"Content-type": "application/x-www-form-urlencoded",
            "Accept": "text/plain"}
    conn = httplib.HTTPSConnection("sso.ace.uq.edu.au")
    conn.request("POST", "/login/", params, headers)
    response = conn.getresponse()
    headers = response.getheaders()
    conn.close()

    login_tkt = None
    for (header, value) in headers:
        if header != 'set-cookie':
            next
        if value.startswith('ace_sso_tkt='):
            login_tkt = value

    if login_tkt is None:
        print "Incorrect password for username {0}. Please try again.".format(username)
        sys.exit(-1)

    parser = LinkParser()

    headers = {
        "Cookie" : login_tkt
    }
    conn = httplib.HTTPSConnection("data.ace.uq.edu.au")

    base_dir     = "/users/{0}/".format(username)
    data_dir     = base_dir + "data/"
    #analysis_dir = base_dir + "analysis/"

    job_dict = {}
    for this_dir in (data_dir,):
        plate_links = filter_links(conn, headers, this_dir, 'P')

        for plate_link in plate_links:
            job_links = filter_links(conn, headers, this_dir + plate_link, 'J')
            
            for job_link in job_links:
                job_link = job_link.rstrip("/")
                try:
                    job_dict[job_link].append(plate_link)
                except KeyError:
                    job_dict[job_link] = [plate_link]

    jobs_to_download = args.j
    if not jobs_to_download:
        found_jobs = job_dict.keys()
        print 
        print "Found {0} jobs: {1}".format(len(found_jobs), ", ".join(found_jobs))
        print "Use the -j flag to download.\n"
        sys.exit(0)
   
    if os.path.exists("ace_sequencing") and not args.f:
        print "ace_sequencing directory exists and -f flag not present. Exiting...."
        sys.exit(-1)
                
    mkdir_if_not_exists("ace_sequencing")
    mkdir_if_not_exists("ace_sequencing/data")
    #mkdir_if_not_exists("ace_sequencing/analysis")

    for job_id in jobs_to_download:
        if job_id not in job_dict:
            print "Job {0} not found. Skipping...".format(job_id)
            continue
        plate_ids = job_dict[job_id]
 
        for plate_id in plate_ids:
            remote_dir = data_dir + plate_id + job_id + "/"
            local_dir = "ace_sequencing/data/" + plate_id + job_id

            mkdir_if_not_exists("ace_sequencing/data/" + plate_id)
            mkdir_if_not_exists(local_dir)

            file_links = filter_links(conn, headers, remote_dir)
            for file_link in file_links:
                if file_link.endswith("/") or "?" in file_link:
                    continue

                out_fh = open(local_dir + "/" + file_link, "wb")
                remote_fp = "https://data.ace.uq.edu.au/" + remote_dir + file_link
                print "Downloading {0}".format(remote_fp)
                p = subprocess.Popen([
                    "curl",  
                    "-H", "Cookie: {0}".format(login_tkt), 
                    remote_fp
                ], stdout=out_fh)
                p.wait()
                print
                 
    print "Download complete. Files placed in the ace_sequencing folder in this directory."
       
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description='Script to download data from ACE Sequencing.')
    parser.add_argument('-u', required=True, metavar="username", help='Your ACE sequencing portal username.')
    parser.add_argument('-j', nargs="+", metavar="job_id", help='List of job ids to download.')
    parser.add_argument('-f', action="store_true", help='Force overwrite of ace_sequencing directory.')

    args = parser.parse_args()
    main(args)
