from random import randint

import firebase_admin
import requests
import time
from bs4 import BeautifulSoup
from bs4 import Tag
from firebase_admin import credentials
from firebase_admin import firestore

URL = 'https://hrsa.cunyfirst.cuny.edu/psc/cnyhcprd/GUEST/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?'
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'}
proxies = {
    'http': '217.182.103.42:3128'
}
CAREER = ['GRAD', 'UGRD']


def init():
    """
    initialize firebase settings
    :return: None
    """
    cred = credentials.Certificate("../resources/coursesregister.json")
    firebase_admin.initialize_app(cred)
    global db
    db = firestore.client()


def getHiddenValue(bs):
    """
    get hidden parameters from hidden input tag
    :param bs: BeautifulSoup Object
    :return: a dictionary that contains the hidden parameters
    """
    hidden_values = {}
    div = bs.find(id='win0divPSHIDDENFIELDS')
    inputs = div.find_all('input', {'type': 'hidden'})
    for input in inputs:
        if isinstance(input, Tag):
            hidden_values[input['name']] = str(input['value'])
    return hidden_values


def getParam1(bs, college, icaction, term='', ):
    """
    get the parameters for the request to find college and term.
    It's really hard to find an appropriate function name :(
    :param bs: BeautifulSoup Object
    :param college: value for the INSTITUTION parameter
    :param icaction: value for the ICACTION parameter
    :param term: value for the STRM parameter
    :return: parameters for post request
    """
    values = getHiddenValue(bs)
    values['CLASS_SRCH_WRK2_INSTITUTION$31$'] = college
    values['CLASS_SRCH_WRK2_STRM$35$'] = term
    values['ICAction'] = icaction
    return values


def get_param_for_courses(bs, college, term, career, major):
    """
    get the parameters for the request to search courses.
    It's really hard to find an appropriate function name :(
    :param bs: BeautifulSoup Object
    :param college:value for the INSTITUTION parameter
    :param term: value for the STRM parameter
    :param career:value for the CAREER parameter
    :param major: value for the SUBJECT parameter
    :return: parameters for the post request
    """
    values = getParam1(bs, college, 'CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH')
    values['SSR_CLSRCH_WRK_SUBJECT_SRCH$0'] = major
    values['CLASS_SRCH_WRK2_STRM$35$'] = term
    values['SSR_CLSRCH_WRK_ACAD_CAREER$2'] = career
    values['SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$5'] = 'N'
    return values


def get_term(session, bs, college='QNS01'):
    """
    get term information from page
    :param session: session object
    :param bs: BeautifulSoup object
    :param college: value for the INSTITUTION parameter
    :return: list of terms
    """
    values = getParam1(bs, college, 'CLASS_SRCH_WRK2_INSTITUTION$31$')
    page = session.post(URL, data=values, headers=headers, proxies=proxies)
    bs = BeautifulSoup(page.text, 'lxml')
    terms_elem = bs.find(id='CLASS_SRCH_WRK2_STRM$35$').option.find_next_siblings('option')
    terms = []
    for term in terms_elem:
        terms.append(term['value'])
    return terms


def get_college(bs):
    """
    get colleges information from page
    :param bs: BeautifulSoup object
    :return: list of colleges
    """
    colleges_elem = bs.find(id='CLASS_SRCH_WRK2_INSTITUTION$31$').option.find_next_siblings('option')
    colleges = []
    for college in colleges_elem:
        colleges.append(college['value'])
    return colleges


def get_majors(session, bs, college='QNS01', term='1192'):
    """
    get majors from the page
    :param session: session object
    :param bs: BeautifulSoup Object
    :param college: value for the INSTITUTION parameter
    :param term:value for the STRM parameter
    :return:list of majors
    """
    values = getParam1(bs, college, icaction='CLASS_SRCH_WRK2_STRM$35$', term=term)
    page = session.post(URL, data=values, headers=headers, proxies=proxies)
    bs = BeautifulSoup(page.text, 'lxml')
    majors_elem = bs.find(id='SSR_CLSRCH_WRK_SUBJECT_SRCH$0').option.find_next_siblings('option')
    majors = []
    for major in majors_elem:
        majors.append(major['value'])
    return majors


def get_courses(bs, doc_ref):
    """
    parse the web page to get courses and sections
    store info into firebase
    :param bs: BeautifulSoup object
    :param doc_ref: firebase document reference object
    :return: None
    """
    courses = bs.find(id="ACE_$ICField$4$$0").tr.find_next_siblings('tr')
    for course in courses:
        title = course.find('a', {'class': 'PSHYPERLINK PTCOLLAPSE_ARROW'}).parent
        sections = course.find_all('table', {'class': 'PSLEVEL1GRIDNBONBO'})
        for section in sections:
            section = section.find('tr').find_next_sibling('tr')
            tds = section.find_all('td')

            doc_ref.collection('courses').document(title.get_text().strip().split('-')[0]) \
                .collection('sections').document(tds[0].get_text().strip()).set({
                'section': tds[1].get_text().split()[0].split('-')[1].strip(),
                'time': tds[2].get_text().strip(),
                'Instructor': tds[4].get_text().strip(),
                'Status': tds[6].img['alt']
            }
            )


def search_courses(session):
    """
    search all the courses
    :param session: session object
    :return:None
    """
    page = session.get(URL)
    bs = BeautifulSoup(page.text, 'lxml')
    colleges = get_college(bs)
    for college in colleges:
        terms = get_term(session, bs, college)
        for term in terms[1:]:
            majors = get_majors(session, bs, college, term)
            for major in majors:
                for career in CAREER:
                    doc_ref = db.collection('colleges').document(college) \
                        .collection('majors').document(major) \
                        .collection('terms').document(term) \
                        .collection('career').document(career)

                    values = get_param_for_courses(bs, college, term, career, major)
                    page = session.post(URL, data=values, headers=headers)
                    bs1 = BeautifulSoup(page.text, 'lxml')
                    try:
                        get_courses(bs1, doc_ref)
                    except AttributeError as ex:
                        print('No course found')
                    time.sleep(randint(0, 1))


def main():
    """
    main function
    :return: None
    """
    init()
    session = requests.Session()
    search_courses(session)


if __name__ == '__main__':
    main()
