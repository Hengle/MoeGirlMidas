#-*- coding:utf-8 -*-

'''
MoeGirlMidas
Version: 0.1
Author: Lei Mao
Updated: 8/11/2017
Institution: The University of Chicago
Description: MoeGirlMidas is built on WikiMidas (https://github.com/leimao/WikiMidas) that I built previously for crawling the data from Wikipedia and MoeGirl APIs. MoeGirlMidas, however, is more specific to getting the fictional character articles and the character's properties from MoeGirl.
'''

import re
import argparse
from bs4 import BeautifulSoup
import requests
from pyquery import PyQuery as pq

# MoeGirl urls
uri_scheme = 'https'
api_uri = 'moegirl.org/api.php'
locale_default = 'zh'
article_uri = 'moegirl.org/'

# Common sub sections to exclude from output
UNWANTED_SECTIONS = ()

# Message shown if there is no article with the title provided
EMPTY_MESSAGE = '<span style="font-size: x-large;">这个页面没有被找到</span>'

class Article(object):

    def __init__(self, data = None):
        data_default = {'heading': '', 'image': '', 'summary': '', 'content': '', 'properties': {}, 'references': '', 'url': ''}
        if data == None:
            data = data_default
        # Using dictionary.get('key') is a much better habit than using dictionary['key']
        self.heading = data.get('heading')
        self.image = data.get('image')
        self.summary = data.get('summary')
        self.content = data.get('content')
        self.properties = data.get('properties')
        self.references = data.get('references')
        self.url = data.get('url')

class MoeGirlAPI(object):

    def __init__(self, options = None):
        if options is None:
            options = {}
        self.options = options
        # Set locale to locale_default if not spcified
        if 'locale' not in options:
            self.options['locale'] = locale_default
            
    def search(self, term, limit = 10):
        '''
        Search related items on MediaWiki using Opensearch API.
        https://www.mediawiki.org/wiki/API:Opensearch
        The JSON format returns an array containing the search query and an array of result titles.
        '''

        # Define search parameters
        # Parameter description could be found at https://www.mediawiki.org/wiki/API:Opensearch
        term = term.decode('utf-8')
        search_params = {
            'action': 'opensearch', # use 'opensearch' API
            'search': term, # search term that the user provided
            'format': 'json', # retrieved data format
            'limit': limit # maximum number of results to return (default:10, maximum: 500 or 5000?)
        }
        # Specify API url
        url = u"{scheme}://{locale_sub}.{hostname_path}".format(
            scheme = uri_scheme,
            locale_sub = self.options['locale'],
            hostname_path = api_uri
        )
        # Retrieve data from API url
        # The data retrieved from Opensearch API is an array
        # Here is a sample return from Opensearch API: https://en.wikipedia.org/w/api.php?action=opensearch&search=api&limit=10&namespace=0&format=jsonfm
        response = requests.get(url, params = search_params)
        # Parse the retrieved data to json format
        response_json = response.json()
        # Return search results as titles
        # response_json[0] is the query term, response_json[1] is the result title, response_json[2] is the result abstract, response_json[3] is the result url to the web page
        results = response_json[1]

        return results

    def retrieve(self, title):
        '''
        Retrieve and parse article content with the title from MediaWiki webpage without using API.
        '''

        title = title.decode('utf-8')
        url = u'{scheme}://{locale_sub}.{hostname_path}{article_title}'.format(
            scheme = uri_scheme,
            locale_sub = self.options['locale'],
            hostname_path = article_uri,
            article_title = title
        )
        # print(url)
        response = requests.get(url)
        response_content = response.content # response_content is the html content of the url webpage as string

        # Check if an article with the title provided could be found.
        empty_regex = re.compile(EMPTY_MESSAGE)
        if re.findall(pattern = empty_regex, string = response_content) != []:
            print("No article with such title found.")
            return Article()

        # Make PyQuery object
        html = pq(response_content)
        html_summary = pq(response_content[:response_content.find('<h2>')]) # summary content is right before the first <h2> section
        # html_summary = pq(re.findall(pattern = r'(.*?)<h2>', string = response_content, flags = re.DOTALL)[0]) # alternative way to extract summary content using regualr expression, but might be memory-expensive

        # Parse MediaWiki page content using PyQuery
        # Brief instruction
        # '#' is used for 'id', '.' is used for class
        data = {}
        paragraphs = html('body').find('h2, p') # content paragraphs are wrapped inside the <p> and <h2>
        # paragraphs = html('.mw-content-ltr').find('p') # content paragraphs are wrapped inside the class 'mw-content-ltr' or id 'mw-content-text'
        paragraphs_summary = html_summary('.mw-content-ltr').find('p') # summary content paragraphs are wrapped inside the class 'mw-content-ltr' or id 'mw-content-text'
        image_url = html('body').find('.image').find('img').attr('src') # find the url to the first image of the article
        references = html('body').find('.references') # reference are wrapped inside the class 'references'
        data['heading'] = html('#firstHeading').text() # heading might be different to the query title
        data['image'] = image_url
        data['summary'] = ''
        data['content'] = ''
        data['properties'] = {}
        data['url'] = url

        
        # Gather property table
        # Property table html
        # html_property_table = html('.infotemplatebox table').html()

        properties = {}

        html_property_contents = html('.infotemplatebox table tr')
        for row in html_property_contents.items():
            row_name = row.find('th').text() # row name
            row_value = row.find('td').text() # row value

            if row_name != '':
                # non-image rows
                if row_value != '':
                    #non-relatives rows
                    properties[row_name] = row_value
                else:
                    properties['relatives'] = row_name

        data['properties'] = properties

        # Gather references
        data['references'] = []
        for ref in references.items():
            data['references'].append(self._strip_text(ref.text()))

        # Gather summary
        # The summary is right before the first <h2> section in the Wikipedia page html.
        summary_max = 3000
        chars = 0
        for paragraph in paragraphs_summary.items():
            if chars < summary_max:
                chars += len(paragraph.text())
                text_no_tags = self._strip_html(paragraph.outer_html())
                stripped_summary = self._strip_text(text_no_tags)
                data['summary'] += stripped_summary

        # Gather full content
        for idx, paragraph in enumerate(paragraphs.items()):
            if idx == 0:
                data['content'] += data['heading']

            clean_text = self._strip_text(paragraph.text())
            if clean_text:
                data['content'] += '\n\n' + clean_text

        data['content'] = self._remove_ads_from_content(data['content']).strip()

        # Combine data to article object
        article = Article(data)

        return article

    def _strip_html(self, text):

        return BeautifulSoup(text, 'lxml').text

    def _strip_text(self, text):
        """
        Removed unwanted information from article.
        """

        # Remove citation numbers, such as '[12]', '[36]'
        text = re.sub(r'\[\d+]', '', text)
        # Correct spacing around fullstops + commas, such as correcting '   . ' to '. '
        text = re.sub(r' +[.] +', '. ', text)
        text = re.sub(r' +[,] +', ', ', text)
        # Remove sub heading edits tags
        text = re.sub(r'\s*\[\s*edit\s*\]\s*', '\n', text)
        # Remove unwanted areas
        text = re.sub(
            '|'.join(UNWANTED_SECTIONS), '', text, flags = re.I | re.M | re.S
        )

        return text

    def _remove_ads_from_content(self, text):
        """
        Returns article content without references to MoeGirl.
        """

        pattern = r'([^.]*?萌娘百科[^.]*\.)'
        return re.sub(pattern, '', text)

def main():

    parser = argparse.ArgumentParser(description = 'Designate function and keywords')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-s','--search', action = 'store_true', help = 'search article')
    group.add_argument('-r','--retrieve', action = 'store_true', help = 'retrieve article')
    parser.add_argument('keywords', type = unicode, help = 'keywords')
    args = parser.parse_args()

    if args.search:
        moegirl = MoeGirlAPI()
        results = moegirl.search(term = args.keywords, limit = 50)
        print ("Query: %s" %args.keywords)
        print ("Number of Terms Found: %d" %len(results))
        print ("Search Results:")
        for result in results:
            print(result)

    if args.retrieve:
        moegirl = MoeGirlAPI()
        article = moegirl.retrieve(title = args.keywords)
        print article.heading.encode('gbk', 'ignore')
        print('-'*50)
        print article.summary.encode('gbk', 'ignore')
        print('-'*50)
        print article.content.encode('gbk', 'ignore')
        print('-'*50)
        for key in article.properties.keys():
            print key, ':', article.properties[key], '\n'

if __name__ == '__main__':

    main()