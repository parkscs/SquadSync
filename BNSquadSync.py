import sys
import os
import configparser
import logging
import logging.config

def override_where():
    # overrides certifi.core.where to return actual location of cacert.pem
    # change this to match the location of cacert.pem
    return os.path.abspath(r"C:\Users\casey\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.9_qbz5n2kfra8p0\LocalCache\local-packages\Python39\site-packages\certifi\cacert.pem")

# is the program compiled?
if hasattr(sys, "frozen"):
    import certifi.core
    
    os.environ["REQUESTS_CA_BUNDLE"] = override_where()
    certifi.core.where = override_where
    
from pip._vendor import requests

requests.utils.DEFAULT_CA_BUNDLE_PATH=override_where()
# End 

# name of config file to read from
confFile = "config.conf"

config = configparser.ConfigParser()
config.sections()
config.read(confFile)

# initialize API key variable
key = config['API']['apikey']

# initialize squad ID variable
squadID = config['API']['squadID']

# initialize .hpp file variable
inputFile = config['HPP']['hppfile']

# initialize .hpp file variable
logFile = config['LOGGING']['logfile']

if (not logFile):
    print("Missing input parameter (logFile) - aborting")
    sys.exit(1)

# Initialize logging
logging.config.fileConfig(logFile)

logger = logging.getLogger('file')
    
# override key/hpp variables if parameters specified during execution
if len(sys.argv) > 1:
    inputFile = sys.argv[1]
    key = sys.argv[2]
    squadID = sys.argv[3]

if (not key):
    logger.error("Missing input parameter (key) - aborting")
    sys.exit(1)

if (not inputFile):
    logger.error("Missing input parameter (inputFile) - aborting")
    sys.exit(1)

if (not squadID):
    logger.error("Missing input parameter (squadID) - aborting")
    sys.exit(1)

headers = {'X-API-Key' : key}

# URLs for armasquads.com REST API
#postURL = 'https://armasquads.com/api/v1/squads/' + squadID + '/members?key=' + key
postURL = 'https://armasquads.com/api/v1/squads/' + squadID + '/members'
logger.debug('postURL is generated as %s', postURL)

#getUrl =  'https://armasquads.com/api/v1/squads/' + squadID + '/members?key=' + key
getUrl =  'https://armasquads.com/api/v1/squads/' + squadID + '/members'
logger.debug('getURL is generated as ' + postURL)

# Class for storing member data
class Member:    
    def __init__(self, uuid, username, name, email, icq, remark):
        self.uuid = uuid
        self.username = username
        self.name = name
        self.email = email
        self.icq = icq
        self.remark = remark    

    # Function to determine when one Member object is equal to another Member object
    # Comparator relies only on username, uuid and remark (rank) - other values such as email, ICQ, etc. are not really relevant
    def __eq__(self, other):
        # return ((self.uuid, self.username, self.name, self.email, self.icq, self.remark) == (other.uuid, other.username, other.name, other.email, other.icq, other.remark))
        return ((self.uuid, self.username, self.remark) == (other.uuid, other.username, other.remark))
    
    # Function to determine when one Member object is not equal to another Member object
    def __ne__(self, other):
        return not (self == other)
    
    # Utility function to output contents of Member object to terminal
    def print(self):
        logger.debug("UUID is %s", self.uuid)
        logger.debug("Username is %s", self.username)
        logger.debug("Name is %s", self.name)
        logger.debug("Email is %s", self.email)
        logger.debug("ICQ is %s", self.icq)
        logger.debug("Remark is %s", self.remark)

# Process content of string array into array of Member objects
def generateMembersListAPI(url):
    # Retrieve roster from Armasquads API
    response = requests.get(url, headers=headers)
    logger.info("Response status code from Armasquads.com in generateMembersListAPI is: %d", response.status_code)

    # If we get any response code other than a 200 (success), exit
    if response.status_code != 200:
        logger.error("Response Status Code %d", response.status_code)
        logger.error("Response other than 200 received - aborting")
        sys.exit()

    # Decode payload to string
    content = response.content
    scontent = content.decode()

    # Split out string into array of individual strings
    svalues = getValues(scontent)
    svaluesArray = svalues.split(',')

    # Begin processing after initial non-member data values
    i = 3

    # Instantiate blank list to build 
    members = list()

    # Iterate through array of strings to build member objects and append to blank list
    # The valuesArray contains tuples (e.g., "UUID", followed by "Bozwell")
    # As such, when iterating through the array to extract only the values, we grab every other 
    # data value (i, i+2, i+4, etc.)
    while i < len(svaluesArray):
        logger.debug("")
        logger.debug("Processing extracted member values at index %d", i)
        # extract member values
        uuid = svaluesArray[i]
        logger.debug("Extracted uuid from API Response is %s", uuid)
        username = svaluesArray[i+2]
        logger.debug("Extracted username from API Response is %s", username)
        name = svaluesArray[i+4]
        logger.debug("Extracted name from API Response is %s", name)
        email = svaluesArray[i+6]
        logger.debug("Extracted email from API Response is %s", email)
        icq = svaluesArray[i+8]
        logger.debug("Extracted icq from API Response is %s", icq)
        remark = svaluesArray[i+10]
        logger.debug("Extracted remark from API Response is %s", remark)

        # Instantiate new member object
        m = Member(uuid, username, name, email, icq, remark)

        # Add newly created member object to list
        members.append(m)

        # Skip to next member's data
        i = i+12

    # Return list containing member objects
    return members

def generateMembersListHPP(input):
    # boolean for tracking when we get to the ranks section of the blackhorse.hpp file
    ranksFound = False;    

    # Process blackhorse.hpp - if we receive any errors, quit out
    logger.info("")
    logger.info("Opening file " + input + " as a read-only file")
    try:
        with open(input, "r") as input:
            members = list()
        
            Lines = [line for line in input.readlines() if line.strip()]
        
        if not Lines:
            logger.error("Error reading file " + input)
            sys.exit(2)

        for line in Lines:
            # Once we're at the end of the ranks section, break out
            if line.startswith("};"):
                logger.info("End of members section found")
                logger.info("")
                break

            # Function to extract values from blackhorse.hpp member list
            if ranksFound:
                # Debug info
                logger.debug("Processing line from .hpp file with values: " + line)

                # Extract the values using function
                values = getValues(line)

                # Set individual variables with corresponding values
                name = values.split(',')[0]
                logger.debug ("Extracted name value is " + str(name))
                id = values.split(',')[1]
                logger.debug ("Extracted id value is " + str(id))
                rank = values.split(',')[2]
                logger.debug ("Extracted rank value is " + str(rank))

                m = Member(id, name, "", "", "", rank)

                # Add newly created member to list
                members.append(m)

            # If we've reached the ranks section, toggle boolean to true
            if line.startswith("ranks[] = {"):
                logger.info("Ranks section found")
                ranksFound = True;

        # Return list containing member objects
        return members
    # Exit if any I/O excpetions are caught
    except IOError as e:
        logger.error("I/O error({0}): {1}".format(e.errno, e.strerror))
        sys.exit(3)

# Split values and strip {}
def getValues(text):
    import re
    matches=re.findall(r'\"(.*?)\"', text)
    return ",".join(matches)

# Search list to see if it contains element
def containsElement(list, element):
    return any(obj == element for obj in list)

# Search list to see if it does not contain element
def doesNotContainElement(list, element):
    return not containsElement(list, element)

# Generate payload for RESTful API request based on member object
def generatePayload(member):
    # Generate payload string
    payload = { 'uuid': member.uuid, 'username': member.username, 'name': member.name, 'email': member.email, 'icq': member.icq, 'remark': member.remark }
    logger.info("Adding Member named %s with UUID %s and Rank %s", member.username, member.uuid, member.remark)
    return payload

# Post payload to RESTful API 
def postPayload(payload):
    logger.info("Posting payload " + str(payload))
    response = requests.post(postURL, json=dict(payload), headers=headers)
    return response

# Delete corresponding member based on member object via RESTful API 
def delMemberAPI(member):
    logger.info("Deleting Member %s with UUID %s and Rank %s", member.username, member.uuid, member.remark)

    #delURL = 'https://armasquads.com/api/v1/squads/' + squadID + '/members/' + member.uuid+ '?key=rYW2TI8sgB8lKM4qyNbMBshVDEgr2GRK6yuyCleCcnv02dh89L'
    delURL = 'https://armasquads.com/api/v1/squads/' + squadID + '/members/' + member.uuid
    logger.debug('delURL generated as ' + delURL)

    response = requests.delete(delURL, headers=headers)
    return response

# Generate and send payload to RESTful API to add new member
def addMemberAPI(member):
    response = postPayload(generatePayload(member))
    return response

# Get Member List from API
membersAPI = generateMembersListAPI(getUrl)

# Get Member List from .hpp file
membersWL = generateMembersListHPP(inputFile)

if not membersWL:
    logger.error("Members list from .hpp file is empty - aborting")
    sys.exit(4)

# Instantiate empty list objects
addList = list()
delList = list()

# For members on Armasquads but *not* in the .hpp file, add these members to list of members to be deleted from Armasquads to mirror .hpp file
for element in membersAPI:
    if doesNotContainElement(membersWL, element):
        logger.debug("Adding member to delList")
        element.print()
        delList.append(element)

# For members that are in the .hpp file but *not* yet on Armasquads.com, add these members to list of members to be added to Armasquads 
for element in membersWL:
    if doesNotContainElement(membersAPI, element):
        logger.debug("Adding member to addList")
        element.print()
        addList.append(element)

# Process all members in list of members to be deleted from Armasquads
logger.info("Iterating through list of members to delete from Armasquads.com")
for member in delList:
    response = delMemberAPI(member)
    logger.info("Deleting member %s from Armasquads.com API.  Response status code is %d", member.name, response.status_code)

# Process all members in list of members to be added to Armasquads
logger.info("Iterating through list of members to add to Armasquads.com")
for member in addList:
    response = addMemberAPI(member)
    logger.info("Adding member %s to Armasquads.com API.  Response status code is %d", member.name, response.status_code)

logger.info("Update complete - exiting")
