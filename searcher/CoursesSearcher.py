from random import randint

import firebase_admin
import requests
import time
from bs4 import BeautifulSoup
from bs4 import Tag
from firebase_admin import credentials
from firebase_admin import firestore

def init():
    cred = credentials.Certificate("../resources/coursesregister-da62d-firebase-adminsdk-fedig-d66edc7893.json")
    firebase_admin.initialize_app(cred)
    global db
    db = firestore.client()

URL = 'https://hrsa.cunyfirst.cuny.edu/psc/cnyhcprd/GUEST/HRMS/c/COMMUNITY_ACCESS.CLASS_SEARCH.GBL?'
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'}
proxies = {
    'http': '217.182.103.42:3128'
}
CAREER = ['GRAD', 'UGRD']


def getHiddenValue(bs):
    hidden_values = {}
    div = bs.find(id='win0divPSHIDDENFIELDS')
    inputs = div.find_all('input', {'type': 'hidden'})
    for input in inputs:
        if isinstance(input, Tag):
            hidden_values[input['name']] = str(input['value'])
    return hidden_values


def getParam1(bs, college, icaction, term='', ):
    values = getHiddenValue(bs)
    values['CLASS_SRCH_WRK2_INSTITUTION$31$'] = college
    values['CLASS_SRCH_WRK2_STRM$35$'] = term
    values['ICAction'] = icaction
    return values


def get_param_for_courses(bs, college, term, career, major):
    values = getParam1(bs, college, 'CLASS_SRCH_WRK2_SSR_PB_CLASS_SRCH')
    values['SSR_CLSRCH_WRK_SUBJECT_SRCH$0'] = major
    values['CLASS_SRCH_WRK2_STRM$35$'] = term
    values['SSR_CLSRCH_WRK_ACAD_CAREER$2'] = career
    values['SSR_CLSRCH_WRK_SSR_OPEN_ONLY$chk$5'] = 'N'
    return values


def savePage(page):
    f = open('page.html', 'w')
    f.write(page.text)
    f.close()


def getTerm(session, bs, college='QNS01'):
    values = getParam1(bs, college, 'CLASS_SRCH_WRK2_INSTITUTION$31$')
    page = session.post(URL, data=values, headers=headers, proxies=proxies)
    bs = BeautifulSoup(page.text, 'lxml')
    terms_elem = bs.find(id='CLASS_SRCH_WRK2_STRM$35$').option.find_next_siblings('option')
    terms = []
    for term in terms_elem:
        terms.append(term['value'])
    return terms


def getCollege(bs):
    colleges_elem = bs.find(id='CLASS_SRCH_WRK2_INSTITUTION$31$').option.find_next_siblings('option')
    colleges = []
    for college in colleges_elem:
        colleges.append(college['value'])
    return colleges


def getMajors(session, bs, college='QNS01', term='1192'):
    values = getParam1(bs, college, icaction='CLASS_SRCH_WRK2_STRM$35$', term=term)
    page = session.post(URL, data=values, headers=headers, proxies=proxies)
    bs = BeautifulSoup(page.text, 'lxml')
    majors_elem = bs.find(id='SSR_CLSRCH_WRK_SUBJECT_SRCH$0').option.find_next_siblings('option')
    majors = []
    for major in majors_elem:
        majors.append(major['value'])
    return majors


def get_courses(bs, doc_ref):
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


def getPage(session):
    page = session.get(URL)
    bs = BeautifulSoup(page.text, 'lxml')
    colleges = getCollege(bs)
    for college in colleges:
        terms = getTerm(session, bs, college)
        for term in terms[1:]:
            majors = getMajors(session, bs, college, term)
            for major in majors:
                for career in CAREER:
                    doc_ref = db.collection('colleges').document(college)\
                        .collection('majors').document(major)\
                        .collection('terms').document(term)\
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
    init()
    session = requests.Session()
    getPage(session)


if __name__ == '__main__':
    main()
